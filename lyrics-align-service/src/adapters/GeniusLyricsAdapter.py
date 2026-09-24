from __future__ import annotations

import logging

import lyricsgenius

from src.domain.Lyrics import ReferenceLyrics
from src.domain.SongMetadata import SongMetadata


logger = logging.getLogger(__name__)


class GeniusLyricsAdapter:
    def __init__(
        self,
        access_token: str,
        timeout_seconds: int = 15,
        retries: int = 2,
        sleep_time_seconds: float = 0.2,
    ) -> None:
        if not access_token or not access_token.strip():
            raise ValueError("A non-empty Genius access token is required.")

        self.client = lyricsgenius.Genius(
            access_token=access_token,
            timeout=timeout_seconds,
            retries=retries,
            sleep_time=sleep_time_seconds,
            remove_section_headers=False,
            skip_non_songs=True,
        )

    def find_lyrics(
        self,
        metadata: SongMetadata,
    ) -> ReferenceLyrics | None:
        """
        Returns a candidate lyric document, or None if Genius has no match
        or the result has no usable lyrics.

        A missing result is expected and is not a song-processing failure:
        the pipeline should fall back to WhisperX transcription.
        """
        title = metadata.title.strip()
        artist = metadata.artist.strip()

        if not title:
            raise ValueError("Song title is required for Genius lookup.")

        if not artist:
            raise ValueError("Artist is required for Genius lookup.")

        try:
            song = self.client.search_song(
                title=title,
                artist=artist,
            )
        except Exception:
            logger.exception(
                "Genius lookup failed for title=%r, artist=%r.",
                title,
                artist,
            )
            return None

        if song is None:
            logger.info(
                "No Genius result for title=%r, artist=%r.",
                title,
                artist,
            )
            return None

        lyrics = (song.lyrics or "").strip()

        if not lyrics:
            logger.info(
                "Genius result had no usable lyrics for title=%r, artist=%r.",
                title,
                artist,
            )
            return None

        return ReferenceLyrics(
            source="genius",
            text=lyrics,
            title=title,
            artist=artist,
            matched_title=(song.title or "").strip(),
            matched_artist=(song.artist or "").strip(),
            genius_song_id=getattr(song, "id", None),
            genius_url=getattr(song, "url", None),
        )