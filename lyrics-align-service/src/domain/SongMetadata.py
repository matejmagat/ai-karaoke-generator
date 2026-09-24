from dataclasses import dataclass


@dataclass(frozen=True)
class SongMetadata:
    title: str
    artist: str
    album: str | None = None
    release_year: int | None = None