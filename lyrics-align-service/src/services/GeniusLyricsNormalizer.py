import re
from abc import ABC, abstractmethod
from typing import Sequence

from src.domain.Lyrics import NormalizedLyrics
from src.domain.normalization.LyricsNormalizationStrategy import LyricsNormalizationStrategy, RemoveBracketedAnnotationsStrategy
from src.domain.Lyrics import Lyrics

class GeniusLyricsNormalizer:
    def __init__(
        self,
        strategies: Sequence[LyricsNormalizationStrategy] | None = None,
    ) -> None:
        self._strategies = list(
            strategies
            if strategies is not None
            else [RemoveBracketedAnnotationsStrategy()]
        )

    def normalize(self, lyrics: Lyrics) -> NormalizedLyrics:

        for strategy in self._strategies:
            lyrics = strategy.normalize(lyrics)

        return lyrics