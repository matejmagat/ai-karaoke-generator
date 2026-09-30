from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.domain.Transcription import Transcription


class LyricsSource(Enum):
    REFERENCE_CORRECTED = 1
    WHISPER_FALLBACK = 2


@dataclass(frozen=True)
class SegmentCorrection:
    segment_index: int
    original_text: str
    corrected_text: str
    similarity_score: float | None
    applied: bool
    lyric_token_start: int | None = None
    lyric_token_end: int | None = None
    reason: str | None = None


@dataclass(frozen=True)
class LyricsCorrectionResult:
    transcription: Transcription
    source: LyricsSource
    corrections: list[SegmentCorrection]
    reference_lyrics_found: bool
    accepted_correction_count: int
    fallback_segment_count: int
