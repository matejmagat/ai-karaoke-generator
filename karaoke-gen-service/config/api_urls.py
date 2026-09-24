from django.urls import include, path
from rest_framework.routers import DefaultRouter

from catalog.views import SongViewSet
from library.views import LibraryViewSet, PlaylistViewSet

router = DefaultRouter()
router.register("songs", SongViewSet, basename="song")
router.register("playlists", PlaylistViewSet, basename="playlist")
router.register("libraries", LibraryViewSet, basename="library")

urlpatterns = [
    path("", include(router.urls)),
]