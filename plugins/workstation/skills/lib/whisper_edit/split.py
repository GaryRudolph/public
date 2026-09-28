"""Split one `Bundle` into two `TargetBundle`s at a chosen time point.

`split_bundle` is the deterministic transform: lines before `split_ms` keep
their time base; lines at/after it are rebased to start near zero (with their
per-word `wordsJson` timings shifted to match, §5.2). Every source audio track
is cut into a ``[0, split_ms]`` half and a ``[split_ms, end]`` half so the two
new sessions reproduce the full track set (§7.3).

`detect_split_candidates` proposes where to split when the user has no exact
timestamp, ranking two signals:

- **silence gaps** — a large pause between consecutive lines, and
- **new persistent speaker onset** — the first time a speaker who then
  participates persistently appears (a new person joining ~= a new meeting).

Each candidate carries surrounding transcript context so the skill can show the
user what the boundary looks like before committing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .model import (
    AudioCut,
    Bundle,
    MediaType,
    OwnerKind,
    SessionKind,
    TargetAudio,
    TargetBundle,
    TargetLine,
    TranscriptLine,
    shift_words_json,
)

DEFAULT_MIN_GAP_MS = 30_000  # 30s pause is a strong "two recordings" signal
DEFAULT_MAX_CANDIDATES = 5
SPEAKER_PERSISTENCE_RATIO = 0.5  # speaker must cover >=50% of the post-onset tail


@dataclass(frozen=True)
class LineContext:
    """A compact transcript line for showing a split boundary to the user."""

    start_ms: int
    speaker_id_hex: str | None
    text: str


@dataclass(frozen=True)
class SplitCandidate:
    """A proposed split point with its rationale and surrounding context."""

    split_ms: int
    score: float
    reason: str
    before_context: tuple[LineContext, ...]
    after_context: tuple[LineContext, ...]


def split_bundle(
    bundle: Bundle,
    split_ms: int,
    *,
    title_suffixes: tuple[str, str] = (" - Split 1", " - Split 2"),
    include_merged_multitrack: bool = True,
) -> tuple[TargetBundle, TargetBundle]:
    """Split `bundle` at `split_ms` into (part 1, part 2) target bundles.

    Args:
        bundle: The source session.
        split_ms: Boundary in ms relative to session start. Must be > 0 and,
            when a duration is known, < the session duration.
        title_suffixes: Suffixes for the two parts (clone applies them).
        include_merged_multitrack: Reconstruct the `mergedMultitrack` track for
            meetings (§10.2 — overridable for backup testing).

    Raises:
        ValueError: If `split_ms` is out of range.
    """
    if split_ms <= 0:
        raise ValueError(f"split_ms must be positive, got {split_ms}")
    duration_ms = bundle.duration_ms()
    if duration_ms is not None and split_ms >= duration_ms:
        raise ValueError(
            f"split_ms {split_ms} is at/after the session duration {duration_ms}"
        )

    lines_a = tuple(_to_target_line(l, 0) for l in bundle.transcript_lines if l.start_ms < split_ms)
    lines_b = tuple(
        _to_target_line(l, split_ms) for l in bundle.transcript_lines if l.start_ms >= split_ms
    )

    dur_a = split_ms
    dur_b = (duration_ms - split_ms) if duration_ms is not None else None

    audio_a = _audio_for_half(bundle, start_ms=0, end_ms=split_ms,
                              include_merged_multitrack=include_merged_multitrack)
    audio_b = _audio_for_half(bundle, start_ms=split_ms, end_ms=None,
                              include_merged_multitrack=include_merged_multitrack)

    part_a = _make_target(
        bundle, lines_a, dur_a, audio_a, title_suffixes[0], include_merged_multitrack
    )
    part_b = _make_target(
        bundle, lines_b, dur_b, audio_b, title_suffixes[1], include_merged_multitrack
    )
    return part_a, part_b


def _to_target_line(line: TranscriptLine, offset_ms: int) -> TargetLine:
    return TargetLine(
        start_ms=line.start_ms - offset_ms,
        end_ms=line.end_ms - offset_ms,
        text=line.text,
        speaker_id_hex=line.speaker_id_hex,
        words_json=shift_words_json(line.words_json, -offset_ms),
        is_favorite=line.is_favorite,
    )


def _audio_for_half(
    bundle: Bundle,
    *,
    start_ms: int,
    end_ms: int | None,
    include_merged_multitrack: bool,
) -> tuple[TargetAudio, ...]:
    out: list[TargetAudio] = []
    for mf in bundle.media_files:
        if (
            not include_merged_multitrack
            and mf.type == MediaType.MERGED_MULTITRACK.value
        ):
            continue
        out.append(
            TargetAudio(
                media_type=mf.type,
                track_token=mf.token,
                owner=mf.owner_kind,
                cuts=(AudioCut(source_path=mf.path, start_ms=start_ms, end_ms=end_ms),),
                playback_type=mf.playback_type,
                file_extension=(mf.file_extension or "m4a"),
            )
        )
    return tuple(out)


def _make_target(
    bundle: Bundle,
    lines: tuple[TargetLine, ...],
    duration_ms: int | None,
    audio: tuple[TargetAudio, ...],
    title_suffix: str,
    include_merged_multitrack: bool,
) -> TargetBundle:
    speaker_ids = tuple(sorted({l.speaker_id_hex for l in lines if l.speaker_id_hex}))
    parent_raw = {}
    if bundle.recorded_meeting is not None:
        parent_raw = dict(bundle.recorded_meeting.raw)
    elif bundle.voice_memo is not None:
        parent_raw = dict(bundle.voice_memo.raw)
    return TargetBundle(
        kind=bundle.kind,
        title=bundle.title,
        title_suffix=title_suffix,
        date_created=bundle.session.date_created or "",
        duration_ms=duration_ms,
        lines=lines,
        speaker_ids=speaker_ids,
        audio=audio,
        is_merged_from_multiple_tracks=(bundle.kind == SessionKind.MEETING),
        source_session_id_hex=bundle.session.id_hex,
        carried_session_fields=dict(bundle.session.raw),
        carried_parent_fields=parent_raw,
        include_merged_multitrack=include_merged_multitrack,
    )


# ---------------------------------------------------------------------------
# Auto-detection
# ---------------------------------------------------------------------------


def detect_split_candidates(
    bundle: Bundle,
    *,
    min_gap_ms: int = DEFAULT_MIN_GAP_MS,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> list[SplitCandidate]:
    """Propose ranked split points from silence gaps and speaker onsets.

    Returns candidates sorted by descending score. Empty when the transcript is
    too short or no signal crosses the thresholds.
    """
    lines = bundle.transcript_lines
    if len(lines) < 2:
        return []
    candidates: list[SplitCandidate] = []
    candidates.extend(_silence_gap_candidates(lines, min_gap_ms))
    candidates.extend(_speaker_onset_candidates(lines))

    # Deduplicate near-identical split points, keeping the highest score.
    deduped: dict[int, SplitCandidate] = {}
    for cand in candidates:
        bucket = cand.split_ms // 1000  # collapse within the same second
        existing = deduped.get(bucket)
        if existing is None or cand.score > existing.score:
            deduped[bucket] = cand
    ranked = sorted(deduped.values(), key=lambda c: c.score, reverse=True)
    return ranked[:max_candidates]


def _silence_gap_candidates(
    lines: Sequence[TranscriptLine], min_gap_ms: int
) -> list[SplitCandidate]:
    gaps: list[tuple[int, int, int]] = []  # (gap_ms, index, split_ms)
    for i in range(len(lines) - 1):
        gap = lines[i + 1].start_ms - lines[i].end_ms
        if gap >= min_gap_ms:
            gaps.append((gap, i, lines[i + 1].start_ms))
    if not gaps:
        return []
    max_gap = max(g[0] for g in gaps)
    out: list[SplitCandidate] = []
    for gap, i, split_ms in gaps:
        score = 0.5 + 0.5 * (gap / max_gap)  # silence is a strong signal: floor 0.5
        out.append(
            SplitCandidate(
                split_ms=split_ms,
                score=round(score, 4),
                reason=f"silence gap of {gap / 1000:.1f}s",
                before_context=_context(lines, i, back=True),
                after_context=_context(lines, i + 1, back=False),
            )
        )
    return out


def _speaker_onset_candidates(lines: Sequence[TranscriptLine]) -> list[SplitCandidate]:
    out: list[SplitCandidate] = []
    seen_before: set[str] = set()
    for i, line in enumerate(lines):
        spk = line.speaker_id_hex
        if not spk or spk in seen_before:
            if spk:
                seen_before.add(spk)
            continue
        seen_before.add(spk)
        if i == 0:
            continue
        tail = lines[i:]
        tail_with_speaker = sum(1 for l in tail if l.speaker_id_hex == spk)
        ratio = tail_with_speaker / len(tail)
        if ratio >= SPEAKER_PERSISTENCE_RATIO:
            out.append(
                SplitCandidate(
                    split_ms=line.start_ms,
                    score=round(0.3 + 0.4 * ratio, 4),
                    reason="new persistent speaker joins here",
                    before_context=_context(lines, i - 1, back=True),
                    after_context=_context(lines, i, back=False),
                )
            )
    return out


def _context(
    lines: Sequence[TranscriptLine], index: int, *, back: bool, span: int = 2
) -> tuple[LineContext, ...]:
    if back:
        chosen = lines[max(0, index - span + 1) : index + 1]
    else:
        chosen = lines[index : index + span]
    return tuple(
        LineContext(start_ms=l.start_ms, speaker_id_hex=l.speaker_id_hex, text=l.text)
        for l in chosen
    )
