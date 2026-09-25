from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Song
from .serializers import SongCreateSerializer, SongSerializer
from .services import LyricsAlignClient, LyricsAlignServiceError, enqueue_song_import


class SongViewSet(viewsets.ModelViewSet):
    queryset = Song.objects.all().order_by("artist", "title")
    serializer_class = SongSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action == "create":
            return SongCreateSerializer
        return SongSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Song.objects.all().order_by("artist", "title")

        return Song.objects.filter(is_public=True).order_by("artist", "title")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            job_id, job_status = LyricsAlignClient().create_job(
                title=data["title"],
                artist=data["artist"],
                language=data["language"],
                audio=data["full_mix_file"],
            )
        except LyricsAlignServiceError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        enqueue_song_import(
            job_id=job_id,
            title=data["title"],
            artist=data["artist"],
            user_id=request.user.pk,
        )
        return Response(
            {"job_id": job_id, "status": job_status},
            status=status.HTTP_202_ACCEPTED,
        )
