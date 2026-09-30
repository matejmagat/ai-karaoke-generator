from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

User = get_user_model()


class AuthenticationAPITests(APITestCase):
    def setUp(self):
        self.password = "StrongPass-123!"
        self.user = User.objects.create_user(
            username="existing",
            email="existing@example.com",
            password=self.password,
        )

    def test_register_creates_user_and_returns_tokens(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "new-user",
                "email": "new@example.com",
                "password": "NewStrongPass-123!",
                "password_confirm": "NewStrongPass-123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="new-user").exists())
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_register_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "new-user",
                "email": "new@example.com",
                "password": "NewStrongPass-123!",
                "password_confirm": "DifferentPass-123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="new-user").exists())

    def test_login_returns_access_and_refresh_tokens(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_configured_token_lifetimes_are_longer(self):
        self.assertEqual(
            settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"],
            timedelta(hours=24),
        )
        self.assertEqual(
            settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"],
            timedelta(days=30),
        )
        access = AccessToken.for_user(self.user)
        refresh = RefreshToken.for_user(self.user)
        self.assertEqual(access["exp"] - access["iat"], 24 * 60 * 60)
        self.assertEqual(refresh["exp"] - refresh["iat"], 30 * 24 * 60 * 60)

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_returns_new_access_token(self):
        login = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": self.password},
            format="json",
        )
        response = self.client.post(
            reverse("token-refresh"),
            {"refresh": login.data["refresh"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
