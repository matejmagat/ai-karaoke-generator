from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Union

import librosa
import numpy as np
import pyloudnorm as pyln
import soundfile as sf


PathLike = Union[str, Path]


@dataclass
class VocalSection:
    """Detected non-silent vocal region and its normalization parameters."""

    start_sample: int
    end_sample: int
    input_lufs: float
    gain_db: float
    gain_amplitude: float

    @property
    def length_samples(self) -> int:
        return self.end_sample - self.start_sample

    def duration_seconds(self, sample_rate: int) -> float:
        return self.length_samples / sample_rate


class VocalsNormalizer:
    """
    Detects meaningful vocal sections in an audio file and normalizes each
    section independently toward a LUFS target, while preserving silence,
    timing, channel layout, and transitions between regions.

    Example:
        normalizer = VocalsNormalizer(
            target_lufs=-18.0,
            peak_ceiling_dbfs=-1.0,
            silence_top_db=35,
        )

        sections = normalizer.normalize_file(
            input_file="vocals.wav",
            output_file="vocals_auto_section_normalized.wav",
        )
    """

    def __init__(
        self,
        target_lufs: float = -18.0,
        peak_ceiling_dbfs: float = -1.0,
        max_gain_db: float = 8.0,
        silence_top_db: float = 35.0,
        min_section_seconds: float = 1.0,
        merge_gap_seconds: float = 0.70,
        ramp_ms: float = 25.0,
        output_subtype: str = "PCM_24",
        frame_length: int = 2048,
        hop_length: int = 512,
    ) -> None:
        self.target_lufs = target_lufs
        self.peak_ceiling_dbfs = peak_ceiling_dbfs
        self.max_gain_db = max_gain_db

        self.silence_top_db = silence_top_db
        self.min_section_seconds = min_section_seconds
        self.merge_gap_seconds = merge_gap_seconds

        self.ramp_ms = ramp_ms
        self.output_subtype = output_subtype
        self.frame_length = frame_length
        self.hop_length = hop_length

    @staticmethod
    def db_to_amplitude(db: float) -> float:
        """Convert a decibel gain value to a linear amplitude factor."""
        return 10.0 ** (db / 20.0)

    @staticmethod
    def amplitude_to_db(amplitude: float) -> float:
        """Convert a linear amplitude factor to decibels."""
        if amplitude <= 0.0:
            return -np.inf
        return 20.0 * np.log10(amplitude)

    @classmethod
    def peak_dbfs(cls, samples: np.ndarray) -> float:
        """Return the sample peak of an audio buffer in dBFS."""
        peak = float(np.max(np.abs(samples)))
        return cls.amplitude_to_db(peak)

    @staticmethod
    def gain_ramp(
        num_samples: int,
        gain_from: float,
        gain_to: float,
    ) -> np.ndarray:
        """Create a linear gain envelope between two amplitude factors."""
        if num_samples <= 0:
            return np.empty(0, dtype=np.float32)

        return np.linspace(
            gain_from,
            gain_to,
            num_samples,
            endpoint=True,
            dtype=np.float32,
        )

    @staticmethod
    def merge_intervals(
        intervals: np.ndarray,
        min_length_samples: int,
        merge_gap_samples: int,
    ) -> list[tuple[int, int]]:
        """
        Merge adjacent non-silent intervals separated by short gaps and discard
        resulting sections shorter than ``min_length_samples``.
        """
        if len(intervals) == 0:
            return []

        merged: list[tuple[int, int]] = []
        start, end = map(int, intervals[0])

        for next_start, next_end in intervals[1:]:
            next_start = int(next_start)
            next_end = int(next_end)

            if next_start - end <= merge_gap_samples:
                end = next_end
            else:
                if end - start >= min_length_samples:
                    merged.append((start, end))
                start, end = next_start, next_end

        if end - start >= min_length_samples:
            merged.append((start, end))

        return merged

    def detect_sections(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> list[tuple[int, int]]:
        """
        Detect, merge, and filter vocal sections.

        Audio must have shape ``(samples, channels)``.
        """
        if audio.ndim != 2:
            raise ValueError(
                "Expected two-dimensional audio with shape "
                "(samples, channels)."
            )

        if len(audio) == 0:
            raise RuntimeError("The input audio contains no samples.")

        mono_for_detection = np.mean(audio, axis=1)

        raw_intervals = librosa.effects.split(
            mono_for_detection,
            top_db=self.silence_top_db,
            frame_length=self.frame_length,
            hop_length=self.hop_length,
        )

        min_section_samples = int(self.min_section_seconds * sample_rate)
        merge_gap_samples = int(self.merge_gap_seconds * sample_rate)

        sections = self.merge_intervals(
            raw_intervals,
            min_length_samples=min_section_samples,
            merge_gap_samples=merge_gap_samples,
        )

        if not sections:
            raise RuntimeError(
                "No vocal sections detected. Try increasing "
                f"silence_top_db from {self.silence_top_db:g} to a higher "
                "value, such as 45."
            )

        return sections

    def calculate_section_gains(
        self,
        audio: np.ndarray,
        sample_rate: int,
        sections: list[tuple[int, int]],
    ) -> list[VocalSection]:
        """
        Measure each detected section and determine its LUFS/peak-safe gain.

        Gain is first constrained to ``±max_gain_db``. If that gain would
        exceed the configured peak ceiling, it is reduced further.
        """
        meter = pyln.Meter(sample_rate)
        ceiling_amplitude = self.db_to_amplitude(self.peak_ceiling_dbfs)

        normalized_sections: list[VocalSection] = []

        for start, end in sections:
            section_audio = audio[start:end]
            input_lufs = float(meter.integrated_loudness(section_audio))

            if not np.isfinite(input_lufs):
                gain_db = 0.0
            else:
                requested_gain_db = self.target_lufs - input_lufs
                gain_db = float(
                    np.clip(
                        requested_gain_db,
                        -self.max_gain_db,
                        self.max_gain_db,
                    )
                )

                tentative_peak = float(
                    np.max(
                        np.abs(
                            section_audio
                            * self.db_to_amplitude(gain_db)
                        )
                    )
                )

                if tentative_peak > ceiling_amplitude:
                    peak_limit_gain_db = self.amplitude_to_db(
                        ceiling_amplitude / tentative_peak
                    )
                    gain_db += peak_limit_gain_db

            normalized_sections.append(
                VocalSection(
                    start_sample=start,
                    end_sample=end,
                    input_lufs=input_lufs,
                    gain_db=gain_db,
                    gain_amplitude=self.db_to_amplitude(gain_db),
                )
            )

        return normalized_sections

    def apply_section_gains(
        self,
        audio: np.ndarray,
        sample_rate: int,
        sections: list[VocalSection],
    ) -> np.ndarray:
        """
        Apply section gain envelopes to audio.

        The original audio is copied first, so gaps outside detected vocal
        regions retain their original waveform and timing.
        """
        output = audio.copy()
        ramp_samples = int(self.ramp_ms * sample_rate / 1000.0)

        for index, section in enumerate(sections):
            start = section.start_sample
            end = section.end_sample
            length = section.length_samples
            gain = section.gain_amplitude

            envelope = np.full(length, gain, dtype=np.float32)

            previous_gain = (
                sections[index - 1].gain_amplitude
                if index > 0
                else 1.0
            )
            start_ramp_samples = min(ramp_samples, length // 2)

            if start_ramp_samples > 0:
                envelope[:start_ramp_samples] = self.gain_ramp(
                    start_ramp_samples,
                    previous_gain,
                    gain,
                )

            next_gain = (
                sections[index + 1].gain_amplitude
                if index < len(sections) - 1
                else 1.0
            )
            end_ramp_samples = min(ramp_samples, length // 2)

            if end_ramp_samples > 0:
                envelope[-end_ramp_samples:] = self.gain_ramp(
                    end_ramp_samples,
                    gain,
                    next_gain,
                )

            output[start:end] *= envelope[:, None]

        return np.clip(output, -1.0, 1.0)

    def normalize_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
    ) -> tuple[np.ndarray, list[VocalSection]]:
        """
        Normalize an already-loaded audio array.

        Returns:
            A tuple of ``(normalized_audio, vocal_sections)``.
        """
        sections = self.detect_sections(audio, sample_rate)
        section_gains = self.calculate_section_gains(
            audio,
            sample_rate,
            sections,
        )
        output = self.apply_section_gains(
            audio,
            sample_rate,
            section_gains,
        )

        return output, section_gains

    def normalize_file(
        self,
        input_file: PathLike,
        output_file: PathLike,
        verbose: bool = True,
    ) -> list[VocalSection]:
        """
        Load an audio file, normalize its vocal sections, and write a WAV file.

        The input's mono/stereo layout is preserved. Output format is
        controlled through ``output_subtype``, which defaults to ``PCM_24``.
        """
        input_path = Path(input_file)
        output_path = Path(output_file)

        audio, sample_rate = sf.read(
            input_path,
            always_2d=True,
            dtype="float32",
        )

        if len(audio) == 0:
            raise RuntimeError(f"The input file contains no audio: {input_path}")

        output, sections = self.normalize_audio(audio, sample_rate)

        if verbose:
            self.print_section_report(sections, sample_rate)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        sf.write(
            output_path,
            output,
            sample_rate,
            subtype=self.output_subtype,
        )

        if verbose:
            print(f"\nWrote one continuous output file: {output_path}")

        return sections

    @staticmethod
    def print_section_report(
        sections: list[VocalSection],
        sample_rate: int,
    ) -> None:
        """Print detected regions and the gain selected for each section."""
        print(f"Detected {len(sections)} vocal sections:\n")

        for index, section in enumerate(sections, start=1):
            start_seconds = section.start_sample / sample_rate
            end_seconds = section.end_sample / sample_rate
            duration = section.duration_seconds(sample_rate)

            print(
                f"{index:02d}: "
                f"{start_seconds:8.2f}s to {end_seconds:8.2f}s "
                f"({duration:5.2f}s)"
            )

            if np.isfinite(section.input_lufs):
                print(
                    f"    {section.input_lufs:6.2f} LUFS -> "
                    f"gain {section.gain_db:+5.2f} dB"
                )
            else:
                print("    skipped LUFS measurement (silence / invalid LUFS)")