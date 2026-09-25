from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .models import Song
from .serializers import SongSerializer


class SongViewSet(viewsets.ModelViewSet):
    queryset = Song.objects.all().order_by("artist", "title")
    serializer_class = SongSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Song.objects.all().order_by("artist", "title")

        return Song.objects.filter(is_public=True).order_by("artist", "title")

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)
