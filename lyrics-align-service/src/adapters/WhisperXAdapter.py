from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import torch
import whisperx

from src.domain.Transcription import (
    Transcription,
    TranscriptSegment,
    WordSegment,
)
from src.services.VocalsNormalizer import VocalsNormalizer


class WhisperXAdapter:
    def __init__(
        self,
        model_name: str = "large-v3",
        language: str | None = None,
        batch_size: int = 8,
        device: str | None = None,
    ) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.compute_type = "float16" if self.device == "cuda" else "int8"

        self.language = language
        self.model_name = model_name
        self.batch_size = batch_size

        self.model = whisperx.load_model(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
            language=self.language,
        )

        self._alignment_models: dict[str, tuple[Any, dict[str, Any]]] = {}

    def transcribe(self, vocals_path: str | Path) -> Transcription:
        audio = whisperx.load_audio(str(vocals_path))

        raw_result = self.model.transcribe(
            audio,
            batch_size=self.batch_size,
            language=self.language,
        )

        language = raw_result.get("language") or self.language

        return self._to_transcription(
            raw_segments=raw_result.get("segments", []),
            language=language,
            include_words=False,
        )

    def align(
        self,
        vocals_path: str | Path,
        transcription: Transcription,
    ) -> Transcription:
        language = transcription.language or self.language

        if language is None:
            raise ValueError(
                "Cannot align lyrics because no language was provided or detected."
            )

        audio = whisperx.load_audio(str(vocals_path))

        align_model, align_metadata = self._get_alignment_model(language)

        raw_segments = self._to_whisperx_alignment_segments(
            transcription.segments
        )

        aligned_result = whisperx.align(
            transcript=raw_segments,
            model=align_model,
            align_model_metadata=align_metadata,
            audio=audio,
            device=self.device,
            return_char_alignments=False,
        )

        return self._to_transcription(
            raw_segments=aligned_result.get("segments", []),
            language=language,
            include_words=True,
        )

    def align_corrected_lyrics(
        self,
        vocals_path: str | Path,
        initial_transcription: Transcription,
        corrected_segment_texts: list[str],
    ) -> Transcription:
        if len(initial_transcription.segments) != len(corrected_segment_texts):
            raise ValueError(
                "The number of corrected lyric segments must equal the number "
                "of initial transcription segments."
            )

        corrected_segments = [
            replace(segment, text=corrected_text.strip())
            for segment, corrected_text in zip(
                initial_transcription.segments,
                corrected_segment_texts,
                strict=True,
            )
        ]

        corrected_transcription = replace(
            initial_transcription,
            segments=corrected_segments,
        )

        return self.align(
            vocals_path=vocals_path,
            transcription=corrected_transcription,
        )

    def _get_alignment_model(
        self,
        language: str,
    ) -> tuple[Any, dict[str, Any]]:
        if language not in self._alignment_models:
            self._alignment_models[language] = whisperx.load_align_model(
                language_code=language,
                device=self.device,
            )

        return self._alignment_models[language]

    def _to_transcription(
        self,
        raw_segments: list[dict[str, Any]],
        language: str | None,
        include_words: bool,
    ) -> Transcription:
        segments: list[TranscriptSegment] = []

        for index, raw_segment in enumerate(raw_segments):
            text = str(raw_segment.get("text", "")).strip()

            start_ms = self._seconds_to_ms(raw_segment.get("start"))
            end_ms = self._seconds_to_ms(raw_segment.get("end"))

            if start_ms is None or end_ms is None:
                continue

            words = (
                self._to_word_segments(raw_segment.get("words", []))
                if include_words
                else None
            )

            segments.append(
                TranscriptSegment(
                    index=index,
                    text=text,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    confidence=self._read_confidence(raw_segment),
                    words=words,
                )
            )

        return Transcription(
            language=language,
            segments=segments,
            provider="whisperx",
            model_name=self.model_name,
        )

    def _to_word_segments(
        self,
        raw_words: list[dict[str, Any]],
    ) -> list[WordSegment]:
        words: list[WordSegment] = []

        for raw_word in raw_words:
            word_text = str(
                raw_word.get("word")
                or raw_word.get("text")
                or ""
            ).strip()

            if not word_text:
                continue

            words.append(
                WordSegment(
                    word=word_text,
                    start_ms=self._seconds_to_ms(raw_word.get("start")),
                    end_ms=self._seconds_to_ms(raw_word.get("end")),
                    confidence=self._read_confidence(raw_word),
                )
            )

        return words

    def _to_whisperx_alignment_segments(
        self,
        segments: list[TranscriptSegment],
    ) -> list[dict[str, float | str]]:
        alignment_segments: list[dict[str, float | str]] = []

        for segment in segments:
            normalized_text = segment.text.strip()

            if not normalized_text:
                continue

            alignment_segments.append(
                {
                    "start": segment.start_ms / 1000.0,
                    "end": segment.end_ms / 1000.0,
                    "text": normalized_text,
                }
            )

        if not alignment_segments:
            raise ValueError("No non-empty segments are available for alignment.")

        return alignment_segments

    @staticmethod
    def _seconds_to_ms(value: Any) -> int | None:
        if value is None:
            return None

        return round(float(value) * 1000)

    @staticmethod
    def _read_confidence(raw_item: dict[str, Any]) -> float | None:
        value = raw_item.get("score")

        if value is None:
            value = raw_item.get("confidence")

        return float(value) if value is not None else None