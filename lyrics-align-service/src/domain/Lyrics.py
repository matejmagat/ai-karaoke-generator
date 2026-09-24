from dataclasses import dataclass


@dataclass(frozen=True)
class Lyrics:
    title: str
    artist: str
    source: str
    text: str

@dataclass(frozen=True)
class ReferenceLyrics(Lyrics):
    matched_title: str
    matched_artist: str
    genius_song_id: int | None
    genius_url: str | None


@dataclass(frozen=True)
class NormalizedLyrics:
    lyrics: Lyrics
    normalized_text: str
    applied_strategies: list[str]

