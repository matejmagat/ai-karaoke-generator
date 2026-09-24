import re
from abc import ABC, abstractmethod

from src.domain.Lyrics import Lyrics, NormalizedLyrics


class LyricsNormalizationStrategy(ABC):
    @abstractmethod
    def normalize(self, lyrics: Lyrics) -> NormalizedLyrics:
        raise NotImplementedError


class RemoveBracketedAnnotationsStrategy(LyricsNormalizationStrategy):
    _BRACKETED_ANNOTATION_PATTERN = re.compile(
        r"^\s*\[[^\[\]\r\n]+\]\s*$"
    )

    def normalize(self, lyrics: Lyrics) -> NormalizedLyrics:
        if not isinstance(lyrics, NormalizedLyrics):
            normalized_lyrics = NormalizedLyrics(lyrics, normalized_text="", applied_strategies=[])
        else:
            normalized_lyrics = lyrics

        retained_lines = [
            line
            for line in normalized_lyrics.lyrics.text.splitlines()
            if not self._BRACKETED_ANNOTATION_PATTERN.fullmatch(line)
        ]

        return NormalizedLyrics(
            lyrics=normalized_lyrics.lyrics,
            normalized_text="\n".join(retained_lines).strip(),
            applied_strategies=[
               *normalized_lyrics.applied_strategies,
                type(self).__name__,
            ],
        )