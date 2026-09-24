from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SongViewSet

router = DefaultRouter()
router.register("songs", SongViewSet, basename="song")

urlpatterns = [
    path("", include(router.urls)),
]