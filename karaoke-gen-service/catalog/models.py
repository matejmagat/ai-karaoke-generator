from django.db import models
import uuid

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models


def song_upload_path(instance, filename):
    return f"songs/{instance.id}/{filename}"


class Song(models.Model):
    class ProcessingStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    title = models.CharField(max_length=255)
    artist = models.CharField(max_length=255, blank=True)

    vocals_file = models.FileField(
        upload_to=song_upload_path,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["mp3", "wav", "flac", "m4a", "ogg"])],
    )

    instrumental_file = models.FileField(
        upload_to=song_upload_path,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["mp3", "wav", "flac", "m4a", "ogg"])],
    )

    lyrics_srt_file = models.FileField(
        upload_to=song_upload_path,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["srt"])],
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="uploaded_songs",
        null=True,
        blank=True,
    )

    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    processing_error = models.TextField(blank=True)

    duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration of the playable karaoke track.",
    )

    is_public = models.BooleanField(
        default=False,
        help_text="Whether non-admin users may browse and add this song.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["artist", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["title", "artist"],
                name="unique_song_title_per_artist",
            ),
        ]
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["artist"]),
            models.Index(fields=["processing_status"]),
        ]

    def __str__(self):
        return f"{self.artist} — {self.title}" if self.artist else self.title