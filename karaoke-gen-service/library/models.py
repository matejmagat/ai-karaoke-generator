from django.db import models

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import Song


class Playlist(models.Model):
    id = models.BigAutoField(primary_key=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="playlists",
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False)

    songs = models.ManyToManyField(
        Song,
        through="PlaylistSong",
        related_name="playlists",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="unique_playlist_name_per_owner",
            ),
        ]

    def __str__(self):
        return f"{self.owner.username}: {self.name}"


class PlaylistSong(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE)
    song = models.ForeignKey(Song, on_delete=models.CASCADE)

    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["playlist", "song"],
                name="song_only_once_per_playlist",
            ),
            models.UniqueConstraint(
                fields=["playlist", "position"],
                name="unique_playlist_song_position",
            ),
        ]

    def __str__(self):
        return f"{self.position}. {self.song}"


class Library(models.Model):
    id = models.BigAutoField(primary_key=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="libraries",
    )

    name = models.CharField(max_length=150, default="My Library")
    description = models.TextField(blank=True)

    songs = models.ManyToManyField(
        Song,
        through="LibrarySong",
        related_name="libraries",
        blank=True,
    )

    playlists = models.ManyToManyField(
        Playlist,
        through="LibraryPlaylist",
        related_name="libraries",
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="unique_library_name_per_owner",
            ),
        ]

    def __str__(self):
        return f"{self.owner.username}: {self.name}"


class LibrarySong(models.Model):
    library = models.ForeignKey(Library, on_delete=models.CASCADE)
    song = models.ForeignKey(Song, on_delete=models.CASCADE)

    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["library", "song"],
                name="song_only_once_per_library",
            ),
            models.UniqueConstraint(
                fields=["library", "position"],
                name="unique_library_song_position",
            ),
        ]


class LibraryPlaylist(models.Model):
    library = models.ForeignKey(Library, on_delete=models.CASCADE)
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE)

    position = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["library", "playlist"],
                name="playlist_only_once_per_library",
            ),
            models.UniqueConstraint(
                fields=["library", "position"],
                name="unique_library_playlist_position",
            ),
        ]