from pathlib import Path

from rest_framework import serializers

from .models import Song


class SongSerializer(serializers.ModelSerializer):
    class Meta:
        model = Song
        fields = [
            "id",
            "title",
            "artist",
            "vocals_file",
            "instrumental_file",
            "lyrics_srt_file",
            "processing_status",
            "duration_seconds",
            "is_public",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "vocals_file",
            "instrumental_file",
            "lyrics_srt_file",
            "processing_status",
            "created_at",
            "updated_at",
        ]


class SongCreateSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=1, max_length=255)
    artist = serializers.CharField(min_length=1, max_length=255)
    language = serializers.RegexField(
        r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?$",
        max_length=10,
    )
    full_mix_file = serializers.FileField(write_only=True)

    def validate_full_mix_file(self, value):
        extension = Path(value.name).suffix.lower()
        if extension not in {".mp3", ".wav"}:
            raise serializers.ValidationError("Only MP3 and WAV files are supported.")
        if value.size == 0:
            raise serializers.ValidationError("The uploaded audio file is empty.")
        return value
