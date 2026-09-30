from django.contrib import admin

from .models import Song


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "artist",
        "processing_status",
        "is_public",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("processing_status", "is_public", "created_at")
    search_fields = ("title", "artist", "uploaded_by__username")
    autocomplete_fields = ("uploaded_by",)
    readonly_fields = ("id", "created_at", "updated_at")