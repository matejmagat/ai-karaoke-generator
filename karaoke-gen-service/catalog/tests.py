from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Song

User = get_user_model()


class SongAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="singer", password="pass")
        self.admin = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )
        self.public_song = Song.objects.create(
            title="Public Song", artist="Artist", is_public=True
        )
        self.private_song = Song.objects.create(
            title="Private Song", artist="Artist", is_public=False
        )

    def authenticate(self, user=None):
        token = RefreshToken.for_user(user or self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_list_songs_is_public_and_hides_private_songs(self):
        response = self.client.get(reverse("song-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data}
        self.assertIn(str(self.public_song.pk), ids)
        self.assertNotIn(str(self.private_song.pk), ids)

    def test_retrieve_public_song(self):
        response = self.client.get(reverse("song-detail", args=[self.public_song.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_song_requires_jwt_and_assigns_uploader(self):
        payload = {"title": "Created Song", "artist": "New Artist"}
        self.assertEqual(
            self.client.post(reverse("song-list"), payload, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.authenticate()
        response = self.client.post(reverse("song-list"), payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Song.objects.get(pk=response.data["id"]).uploaded_by, self.user)

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
