from abc import ABC, abstractmethod
from dataclasses import asdict

from src.domain.Transcription import Transcription
import json

class LyricsExportStrategy(ABC):
    """
    Interface for exporting a Transcription to a specific text-based format.
    """

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """The file extension produced by this exporter, including the dot."""
        raise NotImplementedError

    @abstractmethod
    def export(self, transcription: Transcription) -> str:
        """Convert a transcription into its target file contents."""
        raise NotImplementedError


class SRTExportStrategy(LyricsExportStrategy):
    """
    Exports word-level transcription alignment as SubRip (.srt).

    Each WordSegment with a valid start and end timestamp becomes one SRT cue.
    """

    @property
    def file_extension(self) -> str:
        return ".srt"

    def export(self, transcription: Transcription) -> str:
        cues: list[str] = []
        cue_number = 1

        for segment in transcription.segments:
            if not segment.words:
                continue

            for word_segment in segment.words:
                if word_segment.start_ms is None or word_segment.end_ms is None:
                    continue

                word = self._normalize_word(word_segment.word)

                if not word:
                    continue

                if word_segment.start_ms < 0:
                    raise ValueError(
                        f"Word '{word}' has a negative start timestamp: "
                        f"{word_segment.start_ms} ms."
                    )

                if word_segment.end_ms < word_segment.start_ms:
                    raise ValueError(
                        f"Word '{word}' ends before it starts: "
                        f"{word_segment.start_ms} ms -> {word_segment.end_ms} ms."
                    )

                start_timestamp = self._format_timestamp(word_segment.start_ms)
                end_timestamp = self._format_timestamp(word_segment.end_ms)

                cue = (
                    f"{cue_number}\n"
                    f"{start_timestamp} --> {end_timestamp}\n"
                    f"{word}"
                )

                cues.append(cue)
                cue_number += 1

        return "\n\n".join(cues) + ("\n" if cues else "")

    @staticmethod
    def _format_timestamp(milliseconds: int) -> str:
        """
        Convert milliseconds to the required SRT timestamp format:

        HH:MM:SS,mmm
        """
        if milliseconds < 0:
            raise ValueError(
                f"SRT timestamps cannot be negative; received {milliseconds} ms."
            )

        hours, remainder = divmod(milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, ms = divmod(remainder, 1_000)

        return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"

    @staticmethod
    def _normalize_word(word: str) -> str:
        """
        Remove unwanted surrounding whitespace while retaining punctuation.

        Keeping punctuation is normally desirable: for example, 'world!'
        should display exactly as the transcript produced it.
        """
        return word.strip()

class JsonExportStrategy(LyricsExportStrategy):
    """
    Exports the full transcription hierarchy as formatted JSON.
    """

    @property
    def file_extension(self) -> str:
        return ".json"

    def export(self, transcription: Transcription) -> str:
        return json.dumps(
            asdict(transcription),
            ensure_ascii=False,
            indent=2,
        ) + "\n"