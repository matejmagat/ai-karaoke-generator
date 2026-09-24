from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class WordSegment:
    word: str
    start_ms: int | None
    end_ms: int | None
    confidence: float | None = None


@dataclass(frozen=True)
class TranscriptSegment:
    index: int
    text: str
    start_ms: int
    end_ms: int
    confidence: float | None = None
    words: list[WordSegment] | None = None


@dataclass(frozen=True)
class Transcription:
    language: str | None
    segments: list[TranscriptSegment]
    provider: Literal["whisperx"] = "whisperx"
    model_name: str = ""