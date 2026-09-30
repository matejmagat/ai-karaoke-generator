from django.db.models import Max
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from catalog.models import Song

from .models import Library, Playlist, PlaylistSong
from .serializers import LibrarySerializer, PlaylistSerializer, PlaylistSongSerializer


class PlaylistViewSet(viewsets.ModelViewSet):
    serializer_class = PlaylistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Playlist.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"], url_path="add-song")
    def add_song(self, request, pk=None):
        playlist = self.get_object()
        song_id = request.data.get("song_id")

        if not song_id:
            return Response(
                {"detail": "song_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        song = get_object_or_404(Song, pk=song_id)
        if playlist.playlistsong_set.filter(song=song).exists():
            return Response(
                {"detail": "This song is already in the playlist."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        maximum = playlist.playlistsong_set.aggregate(Max("position"))["position__max"]
        entry = PlaylistSong.objects.create(
            playlist=playlist,
            song=song,
            position=(maximum or 0) + 1,
        )
        return Response(
            PlaylistSongSerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )


class LibraryViewSet(viewsets.ModelViewSet):
    serializer_class = LibrarySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Library.objects
            .filter(owner=self.request.user)
            .select_related("owner")
            .prefetch_related(
                "librarysong_set__song",
                "libraryplaylist_set__playlist__playlistsong_set__song",
            )
            .order_by("name")
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
