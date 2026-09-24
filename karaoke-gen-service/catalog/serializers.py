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
            "processing_status",
            "created_at",
            "updated_at",
        ]