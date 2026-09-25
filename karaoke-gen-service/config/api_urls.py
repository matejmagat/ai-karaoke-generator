from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from catalog.views import SongViewSet
from library.views import LibraryViewSet, PlaylistViewSet
from users.views import RegisterView

router = DefaultRouter()
router.register("songs", SongViewSet, basename="song")
router.register("playlists", PlaylistViewSet, basename="playlist")
router.register("libraries", LibraryViewSet, basename="library")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("", include(router.urls)),
]
