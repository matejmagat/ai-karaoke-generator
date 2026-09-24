from django.db import transaction
from rest_framework import serializers

from catalog.models import Song
from catalog.serializers import SongSerializer

from .models import (
    Library,
    LibraryPlaylist,
    LibrarySong,
    Playlist,
    PlaylistSong,
)


class PlaylistSongSerializer(serializers.ModelSerializer):
    """
    Read-only representation of one item inside a playlist.
    """

    song = SongSerializer(read_only=True)

    class Meta:
        model = PlaylistSong
        fields = [
            "id",
            "position",
            "added_at",
            "song",
        ]
        read_only_fields = fields


class PlaylistSerializer(serializers.ModelSerializer):
    """
    Response:
        Includes fully serialized, ordered playlist entries in `entries`.

    Create / update input:
        {
          "name": "Rock classics",
          "description": "Songs for Saturday",
          "is_public": false,
          "song_ids": [
            "9e9c4228-378b-4774-b7e7-2c792625bfda",
            "d608cfe1-dac6-47fe-b919-8168b283619d"
          ]
        }

    `song_ids` replaces the complete playlist contents when it is provided.
    The position is derived from array order: first item -> position 1.
    """

    entries = PlaylistSongSerializer(
        source="playlistsong_set",
        many=True,
        read_only=True,
    )

    song_ids = serializers.PrimaryKeyRelatedField(
        source="songs",
        queryset=Song.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )

    song_count = serializers.IntegerField(
        source="songs.count",
        read_only=True,
    )

    class Meta:
        model = Playlist
        fields = [
            "id",
            "name",
            "description",
            "is_public",
            "created_at",
            "updated_at",
            "song_count",
            "entries",
            "song_ids",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "song_count",
            "entries",
        ]

    def validate_song_ids(self, songs):
        """
        Reject duplicate IDs before attempting to create PlaylistSong rows.
        """
        song_ids = [song.pk for song in songs]

        if len(song_ids) != len(set(song_ids)):
            raise serializers.ValidationError(
                "A song may appear only once in a playlist."
            )

        return songs

    @transaction.atomic
    def create(self, validated_data):
        """
        `owner` must be supplied by the viewset using serializer.save(owner=...).
        """
        songs = validated_data.pop("songs", [])

        playlist = Playlist.objects.create(**validated_data)

        PlaylistSong.objects.bulk_create(
            [
                PlaylistSong(
                    playlist=playlist,
                    song=song,
                    position=index,
                )
                for index, song in enumerate(songs, start=1)
            ]
        )

        return playlist

    @transaction.atomic
    def update(self, instance, validated_data):
        """
        If song_ids is omitted, keep existing playlist contents.

        If song_ids is present—even []—replace every existing membership
        with the submitted ordered song list.
        """
        songs_provided = "songs" in validated_data
        songs = validated_data.pop("songs", None)

        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)

        instance.save()

        if songs_provided:
            instance.playlistsong_set.all().delete()

            PlaylistSong.objects.bulk_create(
                [
                    PlaylistSong(
                        playlist=instance,
                        song=song,
                        position=index,
                    )
                    for index, song in enumerate(songs, start=1)
                ]
            )

        return instance


class LibrarySongSerializer(serializers.ModelSerializer):
    """
    Read-only representation of an individual Song inside a Library.
    """

    song = SongSerializer(read_only=True)

    class Meta:
        model = LibrarySong
        fields = [
            "id",
            "position",
            "added_at",
            "song",
        ]
        read_only_fields = fields


class LibraryPlaylistSerializer(serializers.ModelSerializer):
    """
    Read-only representation of a Playlist inside a Library.

    The nested PlaylistSerializer includes its ordered songs.
    For a very large library, replace this with a smaller playlist summary
    serializer to avoid returning every song in every playlist.
    """

    playlist = PlaylistSerializer(read_only=True)

    class Meta:
        model = LibraryPlaylist
        fields = [
            "id",
            "position",
            "added_at",
            "playlist",
        ]
        read_only_fields = fields


class LibrarySerializer(serializers.ModelSerializer):
    """
    Response:
        Returns ordered standalone songs in `song_entries` and ordered
        playlists in `playlist_entries`.

    Create / update input:
        {
          "name": "My karaoke night",
          "description": "Songs and playlists for Friday",
          "song_ids": [
            "9e9c4228-378b-4774-b7e7-2c792625bfda"
          ],
          "playlist_ids": [1, 8]
        }

    Each provided ID list replaces that relationship only when present.
    For example, PATCH with only `song_ids` does not alter the library's
    playlist membership.
    """

    song_entries = LibrarySongSerializer(
        source="librarysong_set",
        many=True,
        read_only=True,
    )

    playlist_entries = LibraryPlaylistSerializer(
        source="libraryplaylist_set",
        many=True,
        read_only=True,
    )

    song_ids = serializers.PrimaryKeyRelatedField(
        source="songs",
        queryset=Song.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )

    playlist_ids = serializers.PrimaryKeyRelatedField(
        source="playlists",
        queryset=Playlist.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )

    song_count = serializers.IntegerField(
        source="songs.count",
        read_only=True,
    )

    playlist_count = serializers.IntegerField(
        source="playlists.count",
        read_only=True,
    )

    class Meta:
        model = Library
        fields = [
            "id",
            "name",
            "description",
            "created_at",
            "updated_at",
            "song_count",
            "playlist_count",
            "song_entries",
            "playlist_entries",
            "song_ids",
            "playlist_ids",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "song_count",
            "playlist_count",
            "song_entries",
            "playlist_entries",
        ]

    def validate_song_ids(self, songs):
        song_ids = [song.pk for song in songs]

        if len(song_ids) != len(set(song_ids)):
            raise serializers.ValidationError(
                "A song may appear only once in a library."
            )

        return songs

    def validate_playlist_ids(self, playlists):
        playlist_ids = [playlist.pk for playlist in playlists]

        if len(playlist_ids) != len(set(playlist_ids)):
            raise serializers.ValidationError(
                "A playlist may appear only once in a library."
            )

        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return playlists

        if request.user.is_staff:
            return playlists

        if any(playlist.owner_id != request.user.id for playlist in playlists):
            raise serializers.ValidationError(
                "You can add only your own playlists to a library."
            )

        return playlists

    @transaction.atomic
    def create(self, validated_data):
        """
        `owner` must be supplied by the viewset:
            serializer.save(owner=self.request.user)
        """
        songs = validated_data.pop("songs", [])
        playlists = validated_data.pop("playlists", [])

        library = Library.objects.create(**validated_data)

        LibrarySong.objects.bulk_create(
            [
                LibrarySong(
                    library=library,
                    song=song,
                    position=index,
                )
                for index, song in enumerate(songs, start=1)
            ]
        )

        LibraryPlaylist.objects.bulk_create(
            [
                LibraryPlaylist(
                    library=library,
                    playlist=playlist,
                    position=index,
                )
                for index, playlist in enumerate(playlists, start=1)
            ]
        )

        return library

    @transaction.atomic
    def update(self, instance, validated_data):
        """
        Omitted `song_ids` or `playlist_ids` leave that relation unchanged.
        Supplied empty arrays clear the respective relation.
        """
        songs_provided = "songs" in validated_data
        playlists_provided = "playlists" in validated_data

        songs = validated_data.pop("songs", None)
        playlists = validated_data.pop("playlists", None)

        for attribute, value in validated_data.items():
            setattr(instance, attribute, value)

        instance.save()

        if songs_provided:
            instance.librarysong_set.all().delete()

            LibrarySong.objects.bulk_create(
                [
                    LibrarySong(
                        library=instance,
                        song=song,
                        position=index,
                    )
                    for index, song in enumerate(songs, start=1)
                ]
            )

        if playlists_provided:
            instance.libraryplaylist_set.all().delete()

            LibraryPlaylist.objects.bulk_create(
                [
                    LibraryPlaylist(
                        library=instance,
                        playlist=playlist,
                        position=index,
                    )
                    for index, playlist in enumerate(playlists, start=1)
                ]
            )

        return instance