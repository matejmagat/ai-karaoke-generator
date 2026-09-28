from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from library.models import LibrarySong

from .models import Song, SongProcessingJob
from .services import LyricsAlignServiceError, complete_song_import

User = get_user_model()


class SongAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="singer", password="pass")
        self.other_user = User.objects.create_user(username="other", password="pass")
        self.admin = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )
        self.public_song = Song.objects.create(
            title="Public Song",
            artist="Artist",
            is_public=True,
            uploaded_by=self.other_user,
        )
        self.private_song = Song.objects.create(
            title="Private Song",
            artist="Artist",
            is_public=False,
            uploaded_by=self.other_user,
        )
        self.owned_private_song = Song.objects.create(
            title="Owned Private Song",
            artist="Artist",
            is_public=False,
            uploaded_by=self.user,
        )

    def authenticate(self, user=None):
        token = RefreshToken.for_user(user or self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    @staticmethod
    def upload(name="full-mix.mp3", content=b"audio"):
        return SimpleUploadedFile(name, content, content_type="audio/mpeg")

    def test_anonymous_list_only_includes_public_songs(self):
        response = self.client.get(reverse("song-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data}
        self.assertIn(str(self.public_song.pk), ids)
        self.assertNotIn(str(self.private_song.pk), ids)
        self.assertNotIn(str(self.owned_private_song.pk), ids)

    def test_authenticated_list_includes_public_and_owned_private_songs(self):
        self.authenticate()
        response = self.client.get(reverse("song-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data}
        self.assertIn(str(self.public_song.pk), ids)
        self.assertIn(str(self.owned_private_song.pk), ids)
        self.assertNotIn(str(self.private_song.pk), ids)

    def test_retrieve_public_song(self):
        response = self.client.get(reverse("song-detail", args=[self.public_song.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_regular_user_can_retrieve_owned_private_song(self):
        self.authenticate()
        response = self.client.get(
            reverse("song-detail", args=[self.owned_private_song.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.owned_private_song.pk))

    def test_regular_user_cannot_retrieve_another_users_private_song(self):
        self.authenticate()
        response = self.client.get(reverse("song-detail", args=[self.private_song.pk]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_song_requires_jwt(self):
        response = self.client.post(
            reverse("song-list"),
            {
                "title": "Created Song",
                "artist": "New Artist",
                "language": "en",
                "full_mix_file": self.upload(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("catalog.views.enqueue_song_import")
    @patch("catalog.views.LyricsAlignClient")
    def test_create_song_starts_and_persists_alignment_job(
        self, client_class, enqueue
    ):
        client_class.return_value.create_job.return_value = ("job-123", "queued")
        self.authenticate()
        response = self.client.post(
            reverse("song-list"),
            {
                "title": "Created Song",
                "artist": "New Artist",
                "language": "hr",
                "full_mix_file": self.upload("full-mix.wav"),
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data["job_id"], "job-123")
        self.assertEqual(response.data["status"], "queued")
        self.assertIsNone(response.data["song_id"])
        job = SongProcessingJob.objects.get(pk="job-123")
        self.assertEqual(job.owner, self.user)
        self.assertEqual(job.title, "Created Song")
        self.assertFalse(Song.objects.filter(title="Created Song").exists())
        enqueue.assert_called_once_with(processing_job_id="job-123")

    @patch("catalog.views.LyricsAlignClient")
    def test_create_song_returns_bad_gateway_when_alignment_is_unavailable(
        self, client_class
    ):
        client_class.return_value.create_job.side_effect = LyricsAlignServiceError(
            "Could not create a lyrics alignment job."
        )
        self.authenticate()
        response = self.client.post(
            reverse("song-list"),
            {
                "title": "Created Song",
                "artist": "New Artist",
                "language": "en",
                "full_mix_file": self.upload(),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_create_song_requires_all_generation_fields(self):
        self.authenticate()
        response = self.client.post(
            reverse("song-list"),
            {"title": "Created Song", "artist": "New Artist"},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("language", response.data)
        self.assertIn("full_mix_file", response.data)

    def test_create_song_rejects_non_mp3_or_wav_files(self):
        self.authenticate()
        response = self.client.post(
            reverse("song-list"),
            {
                "title": "Created Song",
                "artist": "New Artist",
                "language": "en",
                "full_mix_file": self.upload("full-mix.flac"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("full_mix_file", response.data)

    def test_processing_status_requires_authentication(self):
        job = SongProcessingJob.objects.create(
            job_id="job-private",
            owner=self.user,
            title="Song",
            artist="Artist",
        )
        response = self.client.get(
            reverse("song-processing-status", args=[job.job_id])
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_processing_status_returns_current_users_job(self):
        job = SongProcessingJob.objects.create(
            job_id="job-owned",
            owner=self.user,
            title="Song",
            artist="Artist",
            status=SongProcessingJob.Status.PROCESSING,
        )
        self.authenticate()
        response = self.client.get(
            reverse("song-processing-status", args=[job.job_id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["job_id"], job.job_id)
        self.assertEqual(response.data["status"], "processing")

    def test_processing_status_hides_another_users_job(self):
        job = SongProcessingJob.objects.create(
            job_id="job-other",
            owner=self.other_user,
            title="Song",
            artist="Artist",
        )
        self.authenticate()
        response = self.client.get(
            reverse("song-processing-status", args=[job.job_id])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("catalog.services.LyricsAlignClient")
    def test_completed_job_creates_song_and_adds_it_to_users_library(
        self, client_class
    ):
        job = SongProcessingJob.objects.create(
            job_id="job-123",
            owner=self.user,
            title="Generated Song",
            artist="Artist",
        )
        client = client_class.return_value
        client.wait_for_completion.return_value = {
            "srt": "/jobs/job-123/download/srt",
            "instrumental": "/jobs/job-123/download/instrumental",
            "vocals": "/jobs/job-123/download/vocals",
        }
        client.download_artifact.side_effect = [
            BytesIO(b"1\n00:00:00,000 --> 00:00:01,000\nHello\n"),
            BytesIO(b"instrumental"),
            BytesIO(b"vocals"),
        ]

        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            song = complete_song_import(processing_job_id=job.job_id)
            song.refresh_from_db()
            job.refresh_from_db()
            self.assertEqual(song.processing_status, Song.ProcessingStatus.READY)
            self.assertEqual(song.uploaded_by, self.user)
            self.assertEqual(job.status, SongProcessingJob.Status.COMPLETED)
            self.assertEqual(job.song, song)
            self.assertEqual(
                song.lyrics_srt_file.read(),
                b"1\n00:00:00,000 --> 00:00:01,000\nHello\n",
            )
            self.assertEqual(song.instrumental_file.read(), b"instrumental")
            self.assertEqual(song.vocals_file.read(), b"vocals")
            self.assertTrue(
                LibrarySong.objects.filter(
                    library__owner=self.user,
                    library__name="My Library",
                    song=song,
                    position=1,
                ).exists()
            )

    def test_regular_user_can_update_owned_private_song(self):
        self.authenticate()
        response = self.client.put(
            reverse("song-detail", args=[self.owned_private_song.pk]),
            {"title": "Updated", "artist": "Artist", "is_public": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.owned_private_song.refresh_from_db()
        self.assertEqual(self.owned_private_song.title, "Updated")

    def test_regular_user_can_partially_update_owned_private_song(self):
        self.authenticate()
        response = self.client.patch(
            reverse("song-detail", args=[self.owned_private_song.pk]),
            {"title": "Patched"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.owned_private_song.refresh_from_db()
        self.assertEqual(self.owned_private_song.title, "Patched")

    def test_regular_user_can_delete_owned_private_song(self):
        self.authenticate()
        response = self.client.delete(
            reverse("song-detail", args=[self.owned_private_song.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Song.objects.filter(pk=self.owned_private_song.pk).exists()
        )

    def test_regular_user_cannot_update_another_users_public_song(self):
        self.authenticate()
        response = self.client.put(
            reverse("song-detail", args=[self.public_song.pk]),
            {"title": "Updated", "artist": "Artist", "is_public": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_cannot_partially_update_another_users_public_song(self):
        self.authenticate()
        response = self.client.patch(
            reverse("song-detail", args=[self.public_song.pk]),
            {"title": "Patched"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_cannot_delete_another_users_public_song(self):
        self.authenticate()
        response = self.client.delete(
            reverse("song-detail", args=[self.public_song.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Song.objects.filter(pk=self.public_song.pk).exists())

    def test_regular_user_cannot_modify_another_users_private_song(self):
        self.authenticate()
        response = self.client.patch(
            reverse("song-detail", args=[self.private_song.pk]),
            {"title": "Patched"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_user_cannot_delete_public_song(self):
        response = self.client.delete(
            reverse("song-detail", args=[self.public_song.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_update_song(self):
        self.authenticate(self.admin)
        response = self.client.put(
            reverse("song-detail", args=[self.private_song.pk]),
            {"title": "Updated", "artist": "Artist", "is_public": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private_song.refresh_from_db()
        self.assertEqual(self.private_song.title, "Updated")

    def test_admin_can_partially_update_song(self):
        self.authenticate(self.admin)
        response = self.client.patch(
            reverse("song-detail", args=[self.private_song.pk]),
            {"is_public": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.private_song.refresh_from_db()
        self.assertTrue(self.private_song.is_public)

    def test_admin_can_delete_song(self):
        self.authenticate(self.admin)
        response = self.client.delete(
            reverse("song-detail", args=[self.private_song.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Song.objects.filter(pk=self.private_song.pk).exists())
