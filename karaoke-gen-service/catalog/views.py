from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Song, SongProcessingJob
from .permissions import IsSongOwnerOrAdminOrReadOnly
from .serializers import (
    SongCreateSerializer,
    SongProcessingJobSerializer,
    SongSerializer,
)
from .services import LyricsAlignClient, LyricsAlignServiceError, enqueue_song_import


class SongViewSet(viewsets.ModelViewSet):
    queryset = Song.objects.all().order_by("artist", "title")
    serializer_class = SongSerializer
    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
        IsSongOwnerOrAdminOrReadOnly,
    ]

    def get_serializer_class(self):
        if self.action == "create":
            return SongCreateSerializer
        return SongSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Song.objects.all().order_by("artist", "title")

        visible_songs = Q(is_public=True)
        if user.is_authenticated:
            visible_songs |= Q(uploaded_by=user)

        return Song.objects.filter(visible_songs).order_by("artist", "title")

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

        job = SongProcessingJob.objects.create(
            job_id=job_id,
            owner=request.user,
            title=data["title"],
            artist=data["artist"],
            status=job_status,
        )
        enqueue_song_import(processing_job_id=job.job_id)

        return Response(
            SongProcessingJobSerializer(job).data,
            status=status.HTTP_202_ACCEPTED,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path=r"processing-status/(?P<job_id>[^/.]+)",
        permission_classes=[permissions.IsAuthenticated],
    )
    def processing_status(self, request, job_id=None):
        jobs = SongProcessingJob.objects.select_related("song")
        if not request.user.is_staff:
            jobs = jobs.filter(owner=request.user)

        try:
            job = jobs.get(pk=job_id)
        except SongProcessingJob.DoesNotExist:
            return Response(
                {"detail": "Processing job not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(SongProcessingJobSerializer(job).data)
