# src/domain/services/LyricsCorrector.py

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Literal

from src.domain.LyricsCorrection import (
    LyricsCorrectionResult,
    LyricsSource,
    SegmentCorrection,
)
from src.domain.Transcription import Transcription, TranscriptSegment


@dataclass(frozen=True)
class _LyricLine:
    text: str
    tokens: tuple[str, ...]
    start: int
    end: int
    section_occurrence: int


@dataclass(frozen=True)
class _Anchor:
    segment_position: int
    lyric_start: int
    lyric_end: int
    length: int
    score: float


@dataclass(frozen=True)
class _SpanScore:
    total_cost: float
    normalized_alignment_cost: float
    support_ratio: float
    restored_ratio: float
    end_is_line_boundary: bool


class LyricsCorrector:
    """Assign canonical lyric spans to noisy ASR segments in performed order.

    The implementation intentionally solves segment allocation jointly.  It does
    not independently choose a best lyric window for each segment, which is the
    failure mode that causes a hallucinated segment to shift all later matches.

    Output text always comes from the supplied lyric sheet.  Segment indices and
    timestamps are preserved; word timestamps are cleared for later forced
    alignment.
    """

    _INF = float("inf")

    def __init__(
        self,
        minimum_similarity: float = 0.42,
        adlib_policy: Literal["drop", "keep"] = "drop",
        candidate_radius_lines: int = 4,
        max_span_lines: int = 12,
        allow_empty_spans: bool = False,
        require_full_lyric_coverage: bool = True,
        line_breaks_in_output: bool = False,
        duration_weight: float = 0.22,
        line_boundary_reward: float = 0.12,
        restore_weight: float = 0.20,
        empty_span_penalty: float = 1.40,
    ) -> None:
        if not 0.0 <= minimum_similarity <= 1.0:
            raise ValueError("minimum_similarity must be between 0.0 and 1.0.")
        if adlib_policy not in {"drop", "keep"}:
            raise ValueError("adlib_policy must be either 'drop' or 'keep'.")
        if candidate_radius_lines < 0:
            raise ValueError("candidate_radius_lines must be non-negative.")
        if max_span_lines < 1:
            raise ValueError("max_span_lines must be at least 1.")

        self.minimum_similarity = minimum_similarity
        self.adlib_policy = adlib_policy
        self.candidate_radius_lines = candidate_radius_lines
        self.max_span_lines = max_span_lines
        self.allow_empty_spans = allow_empty_spans
        self.require_full_lyric_coverage = require_full_lyric_coverage
        self.line_breaks_in_output = line_breaks_in_output
        self.duration_weight = duration_weight
        self.line_boundary_reward = line_boundary_reward
        self.restore_weight = restore_weight
        self.empty_span_penalty = empty_span_penalty

        # Affine local-alignment costs.  They are deliberately asymmetric:
        # discard an ASR hallucination more readily than invent a long lyric span.
        self.asr_gap_open = 0.44
        self.asr_gap_extend = 0.12
        self.loop_asr_gap_open = 0.16
        self.loop_asr_gap_extend = 0.025
        self.lyric_gap_open = 0.62
        self.lyric_gap_extend = 0.31
        self.optional_lyric_gap_open = 0.12
        self.optional_lyric_gap_extend = 0.06

    def correct(
        self,
        transcription: Transcription,
        reference_lyrics: str | None,
    ) -> LyricsCorrectionResult:
        """Return canonical lyrics allocated monotonically across ASR segments.

        A first affine global alignment establishes a rough lyric position for
        each source-segment boundary.  A second dynamic program chooses all
        segment boundaries together, scoring each candidate span with affine
        token alignment, a broad duration prior, and lyric-line boundary reward.
        """
        if reference_lyrics is None or not reference_lyrics.strip():
            return self._fallback_for_all_segments(
                transcription,
                "No usable reference lyrics were available.",
            )

        lines, lyric_tokens = self._parse_lyrics(reference_lyrics)
        if not lyric_tokens:
            return self._fallback_for_all_segments(
                transcription,
                "Reference lyrics contained no matchable words.",
            )

        if not transcription.segments:
            return LyricsCorrectionResult(
                transcription=transcription,
                source=LyricsSource.WHISPER_FALLBACK,
                corrections=[],
                reference_lyrics_found=True,
                accepted_correction_count=0,
                fallback_segment_count=0,
            )

        asr_by_segment = [self._tokenize(segment.text) for segment in transcription.segments]
        if not any(asr_by_segment):
            return self._fallback_for_all_segments(
                transcription,
                "Initial transcription contained no matchable words.",
            )

        flat_asr, segment_asr_ends = self._flatten_asr(asr_by_segment)
        global_path = self._global_affine_alignment(flat_asr, lyric_tokens)
        projected_boundaries = self._project_segment_boundaries(
            global_path,
            segment_asr_ends,
            len(lyric_tokens),
        )
        anchors = self._find_monotonic_anchors(asr_by_segment, lyric_tokens)
        candidates = self._build_candidate_boundaries(
            lines=lines,
            lyric_count=len(lyric_tokens),
            projected=projected_boundaries,
            anchors=anchors,
            segment_count=len(transcription.segments),
        )

        boundaries, span_scores = self._segment_boundary_dp(
            segments=transcription.segments,
            asr_by_segment=asr_by_segment,
            lyric_tokens=lyric_tokens,
            lines=lines,
            candidates=candidates,
            anchors=anchors,
        )

        if boundaries is None:
            return self._fallback_for_all_segments(
                transcription,
                "Could not find a monotonic lyrics-to-segment allocation.",
            )

        corrected_segments: list[TranscriptSegment] = []
        corrections: list[SegmentCorrection] = []

        for position, segment in enumerate(transcription.segments):
            left, right = boundaries[position], boundaries[position + 1]
            score = span_scores[position]
            text = self._render_span(lines, left, right)
            similarity = max(0.0, min(1.0, score.support_ratio))
            applied = bool(text) and similarity >= self.minimum_similarity

            if applied:
                corrected = replace(segment, text=text, words=None)
                reason = None
            else:
                corrected = segment
                reason = self._rejection_reason(left, right, score, text)

            corrected_segments.append(corrected)
            corrections.append(
                SegmentCorrection(
                    segment_index=segment.index,
                    original_text=segment.text,
                    corrected_text=corrected.text,
                    similarity_score=round(similarity, 4),
                    applied=applied,
                    lyric_token_start=left,
                    lyric_token_end=right,
                    reason=reason,
                )
            )

        corrected_transcription = replace(transcription, segments=corrected_segments)
        accepted_count = sum(correction.applied for correction in corrections)
        fallback_count = len(corrections) - accepted_count

        return LyricsCorrectionResult(
            transcription=corrected_transcription,
            source=(
                LyricsSource.REFERENCE_CORRECTED
                if accepted_count
                else LyricsSource.WHISPER_FALLBACK
            ),
            corrections=corrections,
            reference_lyrics_found=True,
            accepted_correction_count=accepted_count,
            fallback_segment_count=fallback_count,
        )

    def _parse_lyrics(self, raw: str) -> tuple[list[_LyricLine], list[str]]:
        """Parse displayed lyric lines and preserve repeated section occurrences."""
        lines: list[_LyricLine] = []
        all_tokens: list[str] = []
        section_occurrence = -1
        saw_content_in_section = False

        for raw_line in raw.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            if re.fullmatch(r"\[[^\]]+]", line):
                section_occurrence += 1
                saw_content_in_section = False
                continue

            if section_occurrence < 0:
                section_occurrence = 0
            if saw_content_in_section is False and lines:
                # An unlabelled block is still a distinct occurrence after blank
                # sections only if a label introduced it; otherwise retain order.
                saw_content_in_section = True

            rendered = self._strip_or_keep_adlibs(line)
            tokens = tuple(self._tokenize(rendered))
            if not tokens:
                continue

            start = len(all_tokens)
            all_tokens.extend(tokens)
            lines.append(
                _LyricLine(
                    text=rendered,
                    tokens=tokens,
                    start=start,
                    end=len(all_tokens),
                    section_occurrence=section_occurrence,
                )
            )
            saw_content_in_section = True

        return lines, all_tokens

    def _strip_or_keep_adlibs(self, line: str) -> str:
        if self.adlib_policy == "keep":
            return re.sub(r"\s+", " ", line).strip()
        without_adlibs = re.sub(r"\s*\([^)]*\)", "", line)
        return re.sub(r"\s+", " ", without_adlibs).strip()

    def _flatten_asr(self, asr_by_segment: list[list[str]]) -> tuple[list[str], list[int]]:
        flat: list[str] = []
        ends: list[int] = []
        for tokens in asr_by_segment:
            flat.extend(tokens)
            ends.append(len(flat))
        return flat, ends

    def _global_affine_alignment(
        self,
        asr_tokens: list[str],
        lyric_tokens: list[str],
    ) -> list[tuple[int | None, int | None]]:
        """Needleman-Wunsch-style affine alignment used only as a coarse path."""
        n, m = len(asr_tokens), len(lyric_tokens)
        mtx = [[self._INF] * (m + 1) for _ in range(n + 1)]
        xgap = [[self._INF] * (m + 1) for _ in range(n + 1)]
        ygap = [[self._INF] * (m + 1) for _ in range(n + 1)]
        pm = [[None] * (m + 1) for _ in range(n + 1)]
        px = [[None] * (m + 1) for _ in range(n + 1)]
        py = [[None] * (m + 1) for _ in range(n + 1)]
        mtx[0][0] = 0.0

        for i in range(1, n + 1):
            open_cost, extend_cost = self._asr_gap_cost(asr_tokens, i - 1)
            choices = (
                (mtx[i - 1][0] + open_cost, "M"),
                (xgap[i - 1][0] + extend_cost, "X"),
                (ygap[i - 1][0] + open_cost, "Y"),
            )
            xgap[i][0], px[i][0] = min(choices, key=lambda item: item[0])

        for j in range(1, m + 1):
            choices = (
                (mtx[0][j - 1] + self.lyric_gap_open, "M"),
                (ygap[0][j - 1] + self.lyric_gap_extend, "Y"),
                (xgap[0][j - 1] + self.lyric_gap_open, "X"),
            )
            ygap[0][j], py[0][j] = min(choices, key=lambda item: item[0])

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                sub_choices = (
                    (mtx[i - 1][j - 1], "M"),
                    (xgap[i - 1][j - 1], "X"),
                    (ygap[i - 1][j - 1], "Y"),
                )
                prior, state = min(sub_choices, key=lambda item: item[0])
                mtx[i][j] = prior + self._substitution_cost(asr_tokens[i - 1], lyric_tokens[j - 1])
                pm[i][j] = state

                asr_open, asr_extend = self._asr_gap_cost(asr_tokens, i - 1)
                x_choices = (
                    (mtx[i - 1][j] + asr_open, "M"),
                    (xgap[i - 1][j] + asr_extend, "X"),
                    (ygap[i - 1][j] + asr_open, "Y"),
                )
                xgap[i][j], px[i][j] = min(x_choices, key=lambda item: item[0])

                y_choices = (
                    (mtx[i][j - 1] + self.lyric_gap_open, "M"),
                    (ygap[i][j - 1] + self.lyric_gap_extend, "Y"),
                    (xgap[i][j - 1] + self.lyric_gap_open, "X"),
                )
                ygap[i][j], py[i][j] = min(y_choices, key=lambda item: item[0])

        _, state = min(
            ((mtx[n][m], "M"), (xgap[n][m], "X"), (ygap[n][m], "Y")),
            key=lambda item: item[0],
        )
        path: list[tuple[int | None, int | None]] = []
        i, j = n, m
        while i > 0 or j > 0:
            if state == "M":
                path.append((i - 1, j - 1))
                state = pm[i][j]
                i -= 1
                j -= 1
            elif state == "X":
                path.append((i - 1, None))
                state = px[i][j]
                i -= 1
            else:
                path.append((None, j - 1))
                state = py[i][j]
                j -= 1
        path.reverse()
        return path

    def _project_segment_boundaries(
        self,
        path: list[tuple[int | None, int | None]],
        segment_asr_ends: list[int],
        lyric_count: int,
    ) -> list[int]:
        """Project each ASR boundary onto the coarse lyric path conservatively."""
        projected = [0]
        matched_lyrics_by_asr: dict[int, int] = {
            asr: lyric for asr, lyric in path if asr is not None and lyric is not None
        }
        consumed_lyrics = 0
        asr_seen = 0
        end_iter = iter(segment_asr_ends)
        target = next(end_iter, None)

        for asr, lyric in path:
            if lyric is not None:
                consumed_lyrics = max(consumed_lyrics, lyric + 1)
            if asr is not None:
                asr_seen = asr + 1
            while target is not None and asr_seen >= target:
                direct = matched_lyrics_by_asr.get(target - 1)
                projected.append((direct + 1) if direct is not None else consumed_lyrics)
                target = next(end_iter, None)

        while len(projected) <= len(segment_asr_ends):
            projected.append(lyric_count)
        projected[-1] = lyric_count
        return self._monotonic_clamp(projected, lyric_count)

    def _find_monotonic_anchors(
        self,
        asr_by_segment: list[list[str]],
        lyric_tokens: list[str],
    ) -> list[_Anchor]:
        """Find unambiguous exact phrase anchors and select a monotonic chain."""
        candidates: list[_Anchor] = []
        for segment_position, asr in enumerate(asr_by_segment):
            if len(asr) < 3:
                continue
            for width in range(6, 2, -1):
                for start in range(0, len(asr) - width + 1):
                    phrase = tuple(asr[start : start + width])
                    matches = [
                        lyric_start
                        for lyric_start in range(0, len(lyric_tokens) - width + 1)
                        if tuple(lyric_tokens[lyric_start : lyric_start + width]) == phrase
                    ]
                    if len(matches) == 1:
                        candidates.append(
                            _Anchor(
                                segment_position=segment_position,
                                lyric_start=matches[0],
                                lyric_end=matches[0] + width,
                                length=width,
                                score=float(width),
                            )
                        )

        candidates.sort(key=lambda anchor: (anchor.segment_position, anchor.lyric_start, -anchor.length))
        best_score = [anchor.score for anchor in candidates]
        previous = [-1] * len(candidates)
        for current, anchor in enumerate(candidates):
            for prior in range(current):
                old = candidates[prior]
                if (
                    old.segment_position <= anchor.segment_position
                    and old.lyric_end <= anchor.lyric_start
                    and best_score[prior] + anchor.score > best_score[current]
                ):
                    best_score[current] = best_score[prior] + anchor.score
                    previous[current] = prior

        if not candidates:
            return []
        last = max(range(len(candidates)), key=lambda index: best_score[index])
        chain: list[_Anchor] = []
        while last >= 0:
            chain.append(candidates[last])
            last = previous[last]
        return list(reversed(chain))

    def _build_candidate_boundaries(
        self,
        lines: list[_LyricLine],
        lyric_count: int,
        projected: list[int],
        anchors: list[_Anchor],
        segment_count: int,
    ) -> list[set[int]]:
        line_boundaries = sorted({0, lyric_count, *(line.end for line in lines)})
        all_candidates: list[set[int]] = [{0}]

        for boundary_position in range(1, segment_count):
            center = projected[boundary_position]
            nearby = self._nearby_line_boundaries(line_boundaries, center)
            allowed = set(nearby)
            allowed.add(max(0, min(lyric_count, center)))
            for anchor in anchors:
                if anchor.segment_position < boundary_position:
                    allowed.add(anchor.lyric_end)
                if anchor.segment_position >= boundary_position:
                    allowed.add(anchor.lyric_start)
            all_candidates.append({value for value in allowed if 0 <= value <= lyric_count})

        all_candidates.append({lyric_count})
        return all_candidates

    def _nearby_line_boundaries(self, boundaries: list[int], center: int) -> list[int]:
        nearest = min(range(len(boundaries)), key=lambda index: abs(boundaries[index] - center))
        left = max(0, nearest - self.candidate_radius_lines)
        right = min(len(boundaries), nearest + self.candidate_radius_lines + 1)
        return boundaries[left:right]

    def _segment_boundary_dp(
        self,
        segments: list[TranscriptSegment],
        asr_by_segment: list[list[str]],
        lyric_tokens: list[str],
        lines: list[_LyricLine],
        candidates: list[set[int]],
        anchors: list[_Anchor],
    ) -> tuple[list[int] | None, list[_SpanScore]]:
        expected_rate = self._expected_token_rate(segments, asr_by_segment)
        cache: dict[tuple[int, int, int], _SpanScore] = {}
        states: dict[int, tuple[float, list[int], list[_SpanScore]]] = {0: (0.0, [0], [])}

        for position, segment in enumerate(segments):
            next_states: dict[int, tuple[float, list[int], list[_SpanScore]]] = {}
            for left, (prior_cost, prior_boundaries, prior_scores) in states.items():
                for right in candidates[position + 1]:
                    if right < left:
                        continue
                    if not self.allow_empty_spans and right == left:
                        continue
                    if not self._span_line_limit(lines, left, right):
                        continue
                    if not self._anchor_span_is_valid(anchors, position, left, right):
                        continue

                    key = (position, left, right)
                    if key not in cache:
                        cache[key] = self._score_span(
                            asr_tokens=asr_by_segment[position],
                            lyric_tokens=lyric_tokens[left:right],
                            global_start=left,
                            global_end=right,
                            lines=lines,
                            duration_ms=segment.end_ms - segment.start_ms,
                            expected_rate=expected_rate,
                        )
                    score = cache[key]
                    total = prior_cost + score.total_cost
                    if right == left:
                        total += self.empty_span_penalty
                    old = next_states.get(right)
                    if old is None or total < old[0]:
                        next_states[right] = (
                            total,
                            prior_boundaries + [right],
                            prior_scores + [score],
                        )
            states = next_states
            if not states:
                return None, []

        terminal = len(lyric_tokens)
        if self.require_full_lyric_coverage:
            result = states.get(terminal)
        else:
            result = min(states.values(), key=lambda item: item[0], default=None)
        if result is None:
            return None, []
        _, boundaries, scores = result
        return boundaries, scores

    def _score_span(
        self,
        asr_tokens: list[str],
        lyric_tokens: list[str],
        global_start: int,
        global_end: int,
        lines: list[_LyricLine],
        duration_ms: int,
        expected_rate: float,
    ) -> _SpanScore:
        alignment_cost, support_ratio, restored_ratio = self._local_affine_cost(asr_tokens, lyric_tokens)
        expected_tokens = max(1.0, expected_rate * max(1, duration_ms) / 1000.0)
        duration_cost = abs(len(lyric_tokens) - expected_tokens) / expected_tokens
        end_is_line_boundary = any(line.end == global_end for line in lines)
        boundary_cost = -self.line_boundary_reward if end_is_line_boundary else 0.08
        total = (
            alignment_cost
            + self.duration_weight * duration_cost
            + boundary_cost
            + self.restore_weight * restored_ratio
        )
        return _SpanScore(
            total_cost=total,
            normalized_alignment_cost=alignment_cost,
            support_ratio=support_ratio,
            restored_ratio=restored_ratio,
            end_is_line_boundary=end_is_line_boundary,
        )

    def _local_affine_cost(
        self,
        asr_tokens: list[str],
        lyric_tokens: list[str],
    ) -> tuple[float, float, float]:
        """Affine alignment for a candidate span, including loop-aware ASR gaps."""
        n, m = len(asr_tokens), len(lyric_tokens)
        if not lyric_tokens:
            return (0.0 if not asr_tokens else 1.0, 0.0, 0.0)
        if not asr_tokens:
            return (1.0, 0.0, 1.0)

        mtx = [[self._INF] * (m + 1) for _ in range(n + 1)]
        xgap = [[self._INF] * (m + 1) for _ in range(n + 1)]
        ygap = [[self._INF] * (m + 1) for _ in range(n + 1)]
        supported = [[0] * (m + 1) for _ in range(n + 1)]
        restored = [[0] * (m + 1) for _ in range(n + 1)]
        state_data: dict[tuple[str, int, int], tuple[int, int]] = {("M", 0, 0): (0, 0)}
        mtx[0][0] = 0.0

        def set_state(state: str, i: int, j: int, choices: list[tuple[float, str]], extra_cost: float, add_support: int = 0, add_restored: int = 0) -> None:
            value, previous = min(choices, key=lambda item: item[0])
            matrix = {"M": mtx, "X": xgap, "Y": ygap}[state]
            matrix[i][j] = value + extra_cost
            if state == "M":
                source_i, source_j = i - 1, j - 1
            elif state == "X":
                source_i, source_j = i - 1, j
            else:
                source_i, source_j = i, j - 1
            prior_support, prior_restored = state_data.get((previous, source_i, source_j), (0, 0))
            state_data[(state, i, j)] = (prior_support + add_support, prior_restored + add_restored)

        for i in range(1, n + 1):
            gap_open, gap_extend = self._asr_gap_cost(asr_tokens, i - 1)
            set_state(
                "X", i, 0,
                [(mtx[i - 1][0], "M"), (xgap[i - 1][0], "X"), (ygap[i - 1][0], "Y")],
                gap_extend if xgap[i - 1][0] <= min(mtx[i - 1][0], ygap[i - 1][0]) else gap_open,
            )
        for j in range(1, m + 1):
            set_state(
                "Y", 0, j,
                [(mtx[0][j - 1] + self.lyric_gap_open, "M"), (xgap[0][j - 1] + self.lyric_gap_open, "X"), (ygap[0][j - 1] + self.lyric_gap_extend, "Y")],
                0.0,
                add_restored=1,
            )

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                substitution = self._substitution_cost(asr_tokens[i - 1], lyric_tokens[j - 1])
                set_state(
                    "M", i, j,
                    [(mtx[i - 1][j - 1], "M"), (xgap[i - 1][j - 1], "X"), (ygap[i - 1][j - 1], "Y")],
                    substitution,
                    add_support=int(substitution <= 0.42),
                )

                open_cost, extend_cost = self._asr_gap_cost(asr_tokens, i - 1)
                set_state(
                    "X", i, j,
                    [(mtx[i - 1][j] + open_cost, "M"), (ygap[i - 1][j] + open_cost, "Y"), (xgap[i - 1][j] + extend_cost, "X")],
                    0.0,
                )
                set_state(
                    "Y", i, j,
                    [(mtx[i][j - 1] + self.lyric_gap_open, "M"), (xgap[i][j - 1] + self.lyric_gap_open, "X"), (ygap[i][j - 1] + self.lyric_gap_extend, "Y")],
                    0.0,
                    add_restored=1,
                )

        total, state = min(
            ((mtx[n][m], "M"), (xgap[n][m], "X"), (ygap[n][m], "Y")),
            key=lambda item: item[0],
        )
        supported_count, restored_count = state_data.get((state, n, m), (0, m))
        return (
            total / max(n, m, 1),
            supported_count / max(m, 1),
            restored_count / max(m, 1),
        )

    def _asr_gap_cost(self, tokens: list[str], index: int) -> tuple[float, float]:
        if self._is_probable_loop_token(tokens, index):
            return self.loop_asr_gap_open, self.loop_asr_gap_extend
        return self.asr_gap_open, self.asr_gap_extend

    @staticmethod
    def _is_probable_loop_token(tokens: list[str], index: int) -> bool:
        if not 0 <= index < len(tokens):
            return False
        token = tokens[index]
        left = max(0, index - 8)
        right = min(len(tokens), index + 9)
        neighborhood = tokens[left:right]
        return neighborhood.count(token) >= 4 or (
            index >= 2 and tokens[index] == tokens[index - 1] == tokens[index - 2]
        )

    def _substitution_cost(self, asr: str, lyric: str) -> float:
        if asr == lyric:
            return 0.0
        character_distance = 1.0 - SequenceMatcher(None, asr, lyric).ratio()
        phonetic_distance = 1.0 - SequenceMatcher(None, self._phonetic_key(asr), self._phonetic_key(lyric)).ratio()
        prefix_bonus = 0.12 if asr[:3] == lyric[:3] else 0.0
        return max(0.0, min(1.0, 0.60 * character_distance + 0.40 * phonetic_distance - prefix_bonus))

    @staticmethod
    @lru_cache(maxsize=4096)
    def _phonetic_key(token: str) -> str:
        """Small dependency-free phonetic approximation suitable for ASR errors."""
        value = token.lower()
        value = re.sub(r"[^a-z0-9]", "", value)
        value = re.sub(r"(tion|sion)", "shun", value)
        value = re.sub(r"ph", "f", value)
        value = re.sub(r"ck", "k", value)
        value = re.sub(r"qu", "kw", value)
        value = re.sub(r"[aeiouy]+", "A", value)
        value = re.sub(r"(.)\1+", r"\1", value)
        return value

    def _expected_token_rate(
        self,
        segments: list[TranscriptSegment],
        asr_by_segment: list[list[str]],
    ) -> float:
        rates = [
            len(tokens) / max(0.5, (segment.end_ms - segment.start_ms) / 1000.0)
            for segment, tokens in zip(segments, asr_by_segment)
            if tokens and segment.end_ms > segment.start_ms
        ]
        if not rates:
            return 2.0
        rates.sort()
        middle = len(rates) // 2
        return rates[middle] if len(rates) % 2 else (rates[middle - 1] + rates[middle]) / 2.0

    def _span_line_limit(self, lines: list[_LyricLine], left: int, right: int) -> bool:
        overlapping = sum(1 for line in lines if line.end > left and line.start < right)
        return overlapping <= self.max_span_lines

    @staticmethod
    def _anchor_span_is_valid(
        anchors: list[_Anchor],
        segment_position: int,
        left: int,
        right: int,
    ) -> bool:
        for anchor in anchors:
            if anchor.segment_position == segment_position:
                if not (left <= anchor.lyric_start and anchor.lyric_end <= right):
                    return False
            elif anchor.segment_position < segment_position and right <= anchor.lyric_end:
                return False
            elif anchor.segment_position > segment_position and left >= anchor.lyric_start:
                return False
        return True

    def _render_span(self, lines: list[_LyricLine], left: int, right: int) -> str:
        selected = [line.text for line in lines if line.end > left and line.start < right]
        separator = "\n" if self.line_breaks_in_output else " "
        return separator.join(selected).strip()

    def _rejection_reason(
        self,
        left: int,
        right: int,
        score: _SpanScore,
        text: str,
    ) -> str:
        if not text or right <= left:
            return "No canonical lyric span was allocated to this segment."
        if score.support_ratio < self.minimum_similarity:
            return (
                "Canonical span was allocated globally, but direct ASR support "
                f"was below the minimum similarity threshold ({self.minimum_similarity:.2f})."
            )
        return "Canonical lyric span could not be rendered."

    @staticmethod
    def _monotonic_clamp(values: list[int], maximum: int) -> list[int]:
        result: list[int] = []
        previous = 0
        for value in values:
            previous = max(previous, min(maximum, value))
            result.append(previous)
        return result

    @staticmethod
    def _normalize_for_matching(text: str) -> str:
        text = unicodedata.normalize("NFKD", text)
        text = "".join(char for char in text if not unicodedata.combining(char))
        text = text.lower().replace("’", "'").replace("‘", "'").replace("-", " ")
        text = re.sub(r"[^a-z0-9']+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _tokenize(self, text: str) -> list[str]:
        normalized = self._normalize_for_matching(text)
        return re.findall(r"[a-z0-9']+", normalized)

    def _fallback_for_all_segments(
        self,
        transcription: Transcription,
        reason: str,
    ) -> LyricsCorrectionResult:
        corrections = [
            SegmentCorrection(
                segment_index=segment.index,
                original_text=segment.text,
                corrected_text=segment.text,
                similarity_score=0.0,
                applied=False,
                reason=reason,
            )
            for segment in transcription.segments
        ]
        return LyricsCorrectionResult(
            transcription=transcription,
            source=LyricsSource.WHISPER_FALLBACK,
            corrections=corrections,
            reference_lyrics_found=False,
            accepted_correction_count=0,
            fallback_segment_count=len(transcription.segments),
        )