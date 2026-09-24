from django.contrib import admin

# collections/admin.py
from django.contrib import admin

from .models import (
    Library,
    LibraryPlaylist,
    LibrarySong,
    Playlist,
    PlaylistSong,
)


class PlaylistSongInline(admin.TabularInline):
    model = PlaylistSong
    extra = 1
    autocomplete_fields = ("song",)
    ordering = ("position",)


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_public", "created_at")
    list_filter = ("is_public",)
    search_fields = ("name", "owner__username")
    autocomplete_fields = ("owner",)
    inlines = [PlaylistSongInline]


class LibrarySongInline(admin.TabularInline):
    model = LibrarySong
    extra = 1
    autocomplete_fields = ("song",)
    ordering = ("position",)


class LibraryPlaylistInline(admin.TabularInline):
    model = LibraryPlaylist
    extra = 1
    autocomplete_fields = ("playlist",)
    ordering = ("position",)


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    search_fields = ("name", "owner__username")
    autocomplete_fields = ("owner",)
    inlines = [LibrarySongInline, LibraryPlaylistInline]