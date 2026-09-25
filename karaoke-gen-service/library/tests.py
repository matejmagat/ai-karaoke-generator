from base64 import b64encode

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from catalog.models import Song

from .models import Library, Playlist, PlaylistSong

User = get_user_model()


class AuthenticatedAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="pass")
        self.other_user = User.objects.create_user(username="other", password="pass")
        self.song = Song.objects.create(title="Song", artist="Artist", is_public=True)
        self.authenticate()

    def authenticate(self, user=None):
        token = RefreshToken.for_user(user or self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class PlaylistAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.playlist = Playlist.objects.create(owner=self.user, name="Favorites")
        self.other_playlist = Playlist.objects.create(
            owner=self.other_user, name="Other favorites"
        )

    def test_basic_auth_is_rejected(self):
        credentials = b64encode(b"owner:pass").decode()
        self.client.credentials(HTTP_AUTHORIZATION=f"Basic {credentials}")
        response = self.client.get(reverse("playlist-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_returns_only_current_users_playlists(self):
        response = self.client.get(reverse("playlist-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [self.playlist.pk])

    def test_create_playlist(self):
        response = self.client.post(
            reverse("playlist-list"),
            {"name": "New", "song_ids": [str(self.song.pk)]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Playlist.objects.get(pk=response.data["id"])
        self.assertEqual(created.owner, self.user)
        self.assertEqual(created.songs.get(), self.song)

    def test_retrieve_own_playlist_and_hide_another_users(self):
        own = self.client.get(reverse("playlist-detail", args=[self.playlist.pk]))
        other = self.client.get(
            reverse("playlist-detail", args=[self.other_playlist.pk])
        )
        self.assertEqual(own.status_code, status.HTTP_200_OK)
        self.assertEqual(other.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_playlist(self):
        response = self.client.put(
            reverse("playlist-detail", args=[self.playlist.pk]),
            {"name": "Renamed", "description": "Updated", "is_public": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.playlist.refresh_from_db()
        self.assertEqual(self.playlist.name, "Renamed")

    def test_partially_update_playlist(self):
        response = self.client.patch(
            reverse("playlist-detail", args=[self.playlist.pk]),
            {"description": "Patched"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.playlist.refresh_from_db()
        self.assertEqual(self.playlist.description, "Patched")

    def test_delete_playlist(self):
        response = self.client.delete(
            reverse("playlist-detail", args=[self.playlist.pk])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Playlist.objects.filter(pk=self.playlist.pk).exists())

    def test_add_song_action(self):
        response = self.client.post(
            reverse("playlist-add-song", args=[self.playlist.pk]),
            {"song_id": str(self.song.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            PlaylistSong.objects.filter(playlist=self.playlist, song=self.song).exists()
        )


class LibraryAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.playlist = Playlist.objects.create(owner=self.user, name="Favorites")
        self.library = Library.objects.create(owner=self.user, name="My Library")
        self.other_library = Library.objects.create(
            owner=self.other_user, name="Other Library"
        )

    def test_list_returns_only_current_users_libraries(self):
        response = self.client.get(reverse("library-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [self.library.pk])

    def test_create_library(self):
        response = self.client.post(
            reverse("library-list"),
            {
                "name": "New Library",
                "song_ids": [str(self.song.pk)],
                "playlist_ids": [self.playlist.pk],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = Library.objects.get(pk=response.data["id"])
        self.assertEqual(created.owner, self.user)
        self.assertEqual(created.songs.get(), self.song)
        self.assertEqual(created.playlists.get(), self.playlist)

    def test_retrieve_own_library_and_hide_another_users(self):
        own = self.client.get(reverse("library-detail", args=[self.library.pk]))
        other = self.client.get(reverse("library-detail", args=[self.other_library.pk]))
        self.assertEqual(own.status_code, status.HTTP_200_OK)
        self.assertEqual(other.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_library(self):
        response = self.client.put(
            reverse("library-detail", args=[self.library.pk]),
            {"name": "Renamed", "description": "Updated"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.library.refresh_from_db()
        self.assertEqual(self.library.name, "Renamed")

    def test_partially_update_library(self):
        response = self.client.patch(
            reverse("library-detail", args=[self.library.pk]),
            {"description": "Patched"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.library.refresh_from_db()
        self.assertEqual(self.library.description, "Patched")

    def test_delete_library(self):
        response = self.client.delete(reverse("library-detail", args=[self.library.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Library.objects.filter(pk=self.library.pk).exists())
