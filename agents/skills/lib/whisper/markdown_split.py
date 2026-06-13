"""Post-processing split logic for rendered whisper markdown notes.

Two-stage pipeline
------------------
1. **scan** — parse a note's transcript lines and run four independent
   detection tests that each emit raw evidence (facts only, no verdicts).

2. **apply** — take agent-confirmed partition decisions and write the
   resulting split files.

No external dependencies; stdlib-only (same constraint as the rest of this
package).

Detection tests
---------------
T1 — silence gap (start-to-start delta between consecutive lines)
T2 — speaker membership turnover (sliding-window Jaccard on non-self speakers)
T3 — farewell → greeting lexical cue (closing cluster then opening cluster)
T4 — dead-air span (sustained sparse transcription density)

Candidates from different tests within 60s of each other are merged, each
accumulating the evidence from every test that fired at that boundary.

Mixed-mode partitions
---------------------
A single note can have several boundaries and dead-air spans.  The scan
returns an *ordered* list of boundary candidates per note; the agent builds
a partition plan: N contiguous parts, each `keep` (becomes a note) or
`discard` (no file written, range recorded for auditability).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Re-use helpers from the rest of the whisper package
# ---------------------------------------------------------------------------

from . import canonical
from .historical import split_frontmatter

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------

DEFAULT_MIN_GAP_S = 600          # T1: 10 min silence gap
DEFAULT_T2_WINDOW_LINES = 30     # T2: lines each side of boundary
DEFAULT_T2_JACCARD_MAX = 0.2     # T2: turnover threshold
DEFAULT_T3_MAX_GAP_S = 180       # T3: greeting must follow farewell within 3 min
DEFAULT_T4_MAX_DENSITY = 2.0     # T4: lines per minute (sparse = dead air)
DEFAULT_T4_MIN_SPAN_S = 900      # T4: must sustain 15 min to count
MERGE_WINDOW_S = 60              # candidates within 60s merge into one

FAREWELL_PHRASES = frozenset([
    "bye", "goodbye", "good bye", "bye bye", "take care", "talk soon",
    "see you", "see ya", "have a good one", "have a good day",
    "have a good rest", "thanks everyone", "thank you everyone",
    "thanks all", "thank you all", "have a good", "good night",
    "good evening", "good afternoon", "nice to meet you", "nice talking",
    "nice speaking", "great talking", "great meeting",
])

GREETING_PHRASES = frozenset([
    "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
    "hi everyone", "hello everyone", "hey everyone", "can you hear me",
    "are you there", "is everyone here", "is everyone on", "is anyone there",
    "who's on", "who is on", "let's get started", "let us get started",
    "shall we start", "should we start", "ready to start", "ready to begin",
    "quick intro", "let me introduce", "first time", "joining us today",
])

# ---------------------------------------------------------------------------
# Parsed-note data structures
# ---------------------------------------------------------------------------


class TranscriptLine:
    """One line from the `## Transcript` section."""

    __slots__ = ("ts_s", "speaker", "text", "raw")

    def __init__(self, ts_s: int, speaker: str | None, text: str, raw: str):
        self.ts_s = ts_s          # seconds from recording start
        self.speaker = speaker    # None for single-speaker notes
        self.text = text
        self.raw = raw            # original rendered line, kept for context


class ParsedNote:
    """Everything extracted from a rendered whisper markdown note."""

    __slots__ = (
        "path", "meta", "title_line", "summary_body", "action_items_body",
        "original_notes_body", "transcript_lines", "is_single_speaker",
    )

    def __init__(
        self,
        path: Path,
        meta: dict,
        title_line: str,
        summary_body: str,
        action_items_body: str,
        original_notes_body: str,
        transcript_lines: list[TranscriptLine],
        is_single_speaker: bool,
    ):
        self.path = path
        self.meta = meta
        self.title_line = title_line
        self.summary_body = summary_body
        self.action_items_body = action_items_body
        self.original_notes_body = original_notes_body
        self.transcript_lines = transcript_lines
        self.is_single_speaker = is_single_speaker


# ---------------------------------------------------------------------------
# Note parsing
# ---------------------------------------------------------------------------

_TS_LINE_WITH_SPEAKER = re.compile(
    r"^\[(\d{1,2}):(\d{2}):(\d{2})\]\s+(.+?):\s+(.*)$"
)
_TS_LINE_NO_SPEAKER = re.compile(
    r"^\[(\d{1,2}):(\d{2}):(\d{2})\]\s+(.*)$"
)


def _parse_ts(h: str, m: str, s: str) -> int:
    return int(h) * 3600 + int(m) * 60 + int(s)


def _parse_meta_speakers(meta: dict) -> list[str]:
    """Extract speaker list from the frontmatter `speakers:` YAML value."""
    raw = meta.get("speakers", "")
    if not raw or raw in ("{}", "[]", ""):
        return []
    # Strip surrounding brackets and split by comma, unquoting each item.
    inner = raw.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]
    parts = [p.strip().strip('"').strip("'") for p in inner.split(",")]
    return [p for p in parts if p]


def parse_note(path: Path) -> ParsedNote | None:
    """Parse a whisper-generated markdown note.

    Returns None when the file lacks our frontmatter or has no transcript.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    meta, body = split_frontmatter(text)
    if not meta or not meta.get("content_hash"):
        return None

    # Skip notes that are already a split part — they're products of a
    # prior run of this skill and should not be re-scanned.
    if meta.get("split_part"):
        return None

    # Identify the major body sections by heading.
    _SEC_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
    sections: dict[str, tuple[int, int]] = {}  # heading_text -> (start, end) in body
    headings_list: list[tuple[int, str]] = []  # (pos, heading_text)
    for m in _SEC_RE.finditer(body):
        headings_list.append((m.end(), m.group(2).strip()))

    # Build section content map: heading -> text until next heading.
    section_content: dict[str, str] = {}
    for i, (pos, heading) in enumerate(headings_list):
        next_pos = headings_list[i + 1][0] - len(headings_list[i + 1][1]) - 5 if i + 1 < len(headings_list) else len(body)
        content = body[pos:next_pos].strip()
        section_content[heading] = content

    # Title line (the `# Title` heading text, first h1).
    title_line = ""
    for _, heading in headings_list:
        if heading and heading == heading:  # first heading in body
            title_line = heading
            break

    # Walk headings to find canonical sections.
    summary_body = ""
    action_items_body = ""
    original_notes_body = ""
    transcript_raw = ""
    in_transcript = False

    # Section text extraction: scan body line by line.
    lines_body = body.splitlines()
    current_section: str | None = None
    section_lines: dict[str, list[str]] = {}

    for line in lines_body:
        hm = re.match(r"^(#{1,3})\s+(.+)$", line)
        if hm:
            current_section = hm.group(2).strip()
            section_lines.setdefault(current_section, [])
        elif current_section is not None:
            section_lines.setdefault(current_section, []).append(line)

    summary_body = "\n".join(section_lines.get("Summary", [])).strip()
    action_items_body = "\n".join(section_lines.get("Action Items", [])).strip()
    original_notes_body = "\n".join(section_lines.get("Original notes", [])).strip()
    transcript_raw = "\n".join(section_lines.get("Transcript", [])).strip()

    # Parse transcript lines.
    transcript_lines: list[TranscriptLine] = []
    has_speaker_labels = False
    for raw_line in transcript_raw.splitlines():
        raw_line = raw_line.rstrip()
        if not raw_line:
            continue
        m2 = _TS_LINE_WITH_SPEAKER.match(raw_line)
        if m2:
            ts_s = _parse_ts(m2.group(1), m2.group(2), m2.group(3))
            transcript_lines.append(
                TranscriptLine(
                    ts_s=ts_s,
                    speaker=m2.group(4).strip(),
                    text=m2.group(5).strip(),
                    raw=raw_line,
                )
            )
            has_speaker_labels = True
            continue
        m3 = _TS_LINE_NO_SPEAKER.match(raw_line)
        if m3:
            ts_s = _parse_ts(m3.group(1), m3.group(2), m3.group(3))
            transcript_lines.append(
                TranscriptLine(
                    ts_s=ts_s,
                    speaker=None,
                    text=m3.group(4).strip(),
                    raw=raw_line,
                )
            )

    if not transcript_lines:
        return None

    is_single_speaker = not has_speaker_labels

    return ParsedNote(
        path=path,
        meta=meta,
        title_line=title_line,
        summary_body=summary_body,
        action_items_body=action_items_body,
        original_notes_body=original_notes_body,
        transcript_lines=transcript_lines,
        is_single_speaker=is_single_speaker,
    )


# ---------------------------------------------------------------------------
# Candidate data structures
# ---------------------------------------------------------------------------


class BoundaryCandidate:
    """A potential meeting-boundary point in a note's transcript."""

    __slots__ = (
        "split_ts_s", "signals", "gap_s", "jaccard_before", "jaccard_after",
        "speakers_before", "speakers_after", "context_before", "context_after",
        "confidence",
    )

    def __init__(self, split_ts_s: int):
        self.split_ts_s = split_ts_s
        self.signals: list[str] = []      # e.g. ["T1", "T3"]
        self.gap_s: int | None = None
        self.jaccard_before: float | None = None
        self.jaccard_after: float | None = None
        self.speakers_before: list[str] = []
        self.speakers_after: list[str] = []
        self.context_before: list[str] = []   # a few raw lines before boundary
        self.context_after: list[str] = []    # a few raw lines after boundary
        self.confidence: str = "low"          # "high" | "medium" | "low"

    def to_dict(self) -> dict:
        return {
            "split_ts_s": self.split_ts_s,
            "split_ts": canonical.ms_to_hhmmss(self.split_ts_s * 1000),
            "signals": self.signals,
            "gap_s": self.gap_s,
            "jaccard_before": self.jaccard_before,
            "jaccard_after": self.jaccard_after,
            "speakers_before": self.speakers_before,
            "speakers_after": self.speakers_after,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "confidence": self.confidence,
        }


class DeadAirSpan:
    """A span of sparse transcription (ambient noise / recording left running)."""

    __slots__ = (
        "from_ts_s", "to_ts_s", "density_lines_per_min",
        "context_before", "context_after",
    )

    def __init__(
        self,
        from_ts_s: int,
        to_ts_s: int,
        density_lines_per_min: float,
    ):
        self.from_ts_s = from_ts_s
        self.to_ts_s = to_ts_s
        self.density_lines_per_min = density_lines_per_min
        self.context_before: list[str] = []
        self.context_after: list[str] = []

    def to_dict(self) -> dict:
        return {
            "from_ts_s": self.from_ts_s,
            "to_ts_s": self.to_ts_s,
            "from_ts": canonical.ms_to_hhmmss(self.from_ts_s * 1000),
            "to_ts": canonical.ms_to_hhmmss(self.to_ts_s * 1000),
            "duration_s": self.to_ts_s - self.from_ts_s,
            "density_lines_per_min": round(self.density_lines_per_min, 2),
            "context_before": self.context_before,
            "context_after": self.context_after,
        }


class ScanResult:
    """All detection output for a single note."""

    __slots__ = ("path", "boundaries", "dead_air_spans", "total_duration_s")

    def __init__(
        self,
        path: Path,
        boundaries: list[BoundaryCandidate],
        dead_air_spans: list[DeadAirSpan],
        total_duration_s: int,
    ):
        self.path = path
        self.boundaries = boundaries
        self.dead_air_spans = dead_air_spans
        self.total_duration_s = total_duration_s

    def to_dict(self, workspace: Path | None = None) -> dict:
        rel = str(self.path.relative_to(workspace)) if workspace else str(self.path)
        return {
            "note_path": rel,
            "total_duration_s": self.total_duration_s,
            "total_duration": canonical.ms_to_hhmmss(self.total_duration_s * 1000),
            "boundaries": [b.to_dict() for b in self.boundaries],
            "dead_air_spans": [d.to_dict() for d in self.dead_air_spans],
            "flagged": bool(self.boundaries or self.dead_air_spans),
        }


# ---------------------------------------------------------------------------
# Detection tests
# ---------------------------------------------------------------------------

_CONTEXT_LINES = 3  # lines of context to include either side of a boundary


def _context_lines(
    lines: list[TranscriptLine], idx: int, *, before: bool, span: int = _CONTEXT_LINES
) -> list[str]:
    if before:
        return [l.raw for l in lines[max(0, idx - span):idx]]
    else:
        return [l.raw for l in lines[idx:idx + span]]


def t1_silence_gap(
    lines: list[TranscriptLine],
    min_gap_s: int = DEFAULT_MIN_GAP_S,
) -> list[BoundaryCandidate]:
    """T1: large start-to-start silence gap between consecutive lines."""
    out: list[BoundaryCandidate] = []
    for i in range(len(lines) - 1):
        gap = lines[i + 1].ts_s - lines[i].ts_s
        if gap >= min_gap_s:
            # Split point = the timestamp of the first line after the gap.
            cand = BoundaryCandidate(split_ts_s=lines[i + 1].ts_s)
            cand.signals.append("T1")
            cand.gap_s = gap
            cand.context_before = _context_lines(lines, i + 1, before=True)
            cand.context_after = _context_lines(lines, i + 1, before=False)
            out.append(cand)
    return out


def _speaker_set(
    lines: Iterable[TranscriptLine],
    self_mic_speakers: frozenset[str],
) -> frozenset[str]:
    return frozenset(
        l.speaker
        for l in lines
        if l.speaker and l.speaker not in self_mic_speakers
    )


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / len(union)


def t2_speaker_turnover(
    lines: list[TranscriptLine],
    self_mic_speakers: frozenset[str] = frozenset(["Microphone", "Gary"]),
    window_lines: int = DEFAULT_T2_WINDOW_LINES,
    jaccard_threshold: float = DEFAULT_T2_JACCARD_MAX,
) -> list[BoundaryCandidate]:
    """T2: sliding-window Jaccard comparison of non-self speakers.

    Requires at least one non-self speaker on each side of the boundary.
    Skipped when all speakers are self-mic (single-speaker notes).
    """
    non_self = [l for l in lines if l.speaker and l.speaker not in self_mic_speakers]
    if not non_self:
        return []

    out: list[BoundaryCandidate] = []
    half = max(1, window_lines // 2)
    for i in range(half, len(lines) - half):
        before_window = lines[max(0, i - half):i]
        after_window = lines[i:min(len(lines), i + half)]
        before_set = _speaker_set(before_window, self_mic_speakers)
        after_set = _speaker_set(after_window, self_mic_speakers)
        if not before_set or not after_set:
            continue
        j = _jaccard(before_set, after_set)
        if j <= jaccard_threshold:
            cand = BoundaryCandidate(split_ts_s=lines[i].ts_s)
            cand.signals.append("T2")
            cand.jaccard_before = round(j, 3)
            cand.speakers_before = sorted(before_set)
            cand.speakers_after = sorted(after_set)
            cand.context_before = _context_lines(lines, i, before=True)
            cand.context_after = _context_lines(lines, i, before=False)
            out.append(cand)

    # Deduplicate: keep only the lowest-Jaccard candidate per 60s bucket.
    deduped: dict[int, BoundaryCandidate] = {}
    for c in out:
        bucket = c.split_ts_s // 60
        existing = deduped.get(bucket)
        if existing is None:
            deduped[bucket] = c
        else:
            ej = existing.jaccard_before if existing.jaccard_before is not None else 1.0
            cj = c.jaccard_before if c.jaccard_before is not None else 1.0
            if cj < ej:
                deduped[bucket] = c

    return list(deduped.values())


def _norm_text(text: str) -> str:
    return " ".join(text.lower().split())


def _matches_phrases(text: str, phrases: frozenset[str]) -> bool:
    t = _norm_text(text)
    for phrase in phrases:
        if phrase in t:
            return True
    return False


def t3_farewell_greeting(
    lines: list[TranscriptLine],
    max_gap_s: int = DEFAULT_T3_MAX_GAP_S,
) -> list[BoundaryCandidate]:
    """T3: farewell cluster followed within `max_gap_s` by a greeting cluster.

    The split point is the first greeting line.  Emitted as low-confidence
    (callers should check whether T1/T2 fire at a nearby point to upgrade it).
    """
    out: list[BoundaryCandidate] = []
    last_farewell_idx: int | None = None
    last_farewell_ts_s: int | None = None

    for i, line in enumerate(lines):
        text = line.text
        if _matches_phrases(text, FAREWELL_PHRASES):
            last_farewell_idx = i
            last_farewell_ts_s = line.ts_s
        elif (
            last_farewell_idx is not None
            and last_farewell_ts_s is not None
            and _matches_phrases(text, GREETING_PHRASES)
        ):
            gap = line.ts_s - last_farewell_ts_s
            if gap <= max_gap_s:
                cand = BoundaryCandidate(split_ts_s=line.ts_s)
                cand.signals.append("T3")
                cand.gap_s = gap
                cand.context_before = _context_lines(lines, i, before=True)
                cand.context_after = _context_lines(lines, i, before=False)
                out.append(cand)
                # Reset so the next farewell starts fresh.
                last_farewell_idx = None
                last_farewell_ts_s = None

    return out


def t4_dead_air(
    lines: list[TranscriptLine],
    max_density_per_min: float = DEFAULT_T4_MAX_DENSITY,
    min_span_s: int = DEFAULT_T4_MIN_SPAN_S,
) -> list[DeadAirSpan]:
    """T4: sustained sparse transcription — recording left running.

    Uses a sliding minute-window over the transcript.  A contiguous run of
    sub-threshold windows that spans >= `min_span_s` becomes a DeadAirSpan.
    """
    if not lines:
        return []

    total_s = lines[-1].ts_s - lines[0].ts_s
    if total_s < min_span_s:
        return []

    # Build a set of 1-minute buckets and the line count in each.
    start_s = lines[0].ts_s
    end_s = lines[-1].ts_s
    bucket_counts: dict[int, int] = {}
    for line in lines:
        b = (line.ts_s - start_s) // 60
        bucket_counts[b] = bucket_counts.get(b, 0) + 1

    n_buckets = (end_s - start_s) // 60 + 1
    sparse_buckets = [
        b for b in range(n_buckets)
        if bucket_counts.get(b, 0) < max_density_per_min
    ]

    # Find contiguous runs of sparse buckets that meet the minimum span.
    spans: list[DeadAirSpan] = []
    if not sparse_buckets:
        return []

    run_start = sparse_buckets[0]
    run_end = sparse_buckets[0]
    for b in sparse_buckets[1:]:
        if b == run_end + 1:
            run_end = b
        else:
            span_s = (run_end + 1) * 60 - run_start * 60
            if span_s >= min_span_s:
                from_ts = start_s + run_start * 60
                to_ts = start_s + (run_end + 1) * 60
                density = sum(bucket_counts.get(bb, 0) for bb in range(run_start, run_end + 1)) / max(1, run_end - run_start + 1)
                span = DeadAirSpan(from_ts, to_ts, density)
                # Context: last few lines before and first few after the span.
                before_lines = [l for l in lines if l.ts_s < from_ts]
                after_lines = [l for l in lines if l.ts_s >= to_ts]
                span.context_before = [l.raw for l in before_lines[-_CONTEXT_LINES:]]
                span.context_after = [l.raw for l in after_lines[:_CONTEXT_LINES]]
                spans.append(span)
            run_start = b
            run_end = b

    # Last run.
    span_s = (run_end + 1) * 60 - run_start * 60
    if span_s >= min_span_s:
        from_ts = start_s + run_start * 60
        to_ts = min(start_s + (run_end + 1) * 60, end_s)
        density = sum(bucket_counts.get(bb, 0) for bb in range(run_start, run_end + 1)) / max(1, run_end - run_start + 1)
        span = DeadAirSpan(from_ts, to_ts, density)
        before_lines = [l for l in lines if l.ts_s < from_ts]
        after_lines = [l for l in lines if l.ts_s >= to_ts]
        span.context_before = [l.raw for l in before_lines[-_CONTEXT_LINES:]]
        span.context_after = [l.raw for l in after_lines[:_CONTEXT_LINES]]
        spans.append(span)

    return spans


# ---------------------------------------------------------------------------
# Candidate merging
# ---------------------------------------------------------------------------


def _assign_confidence(cand: BoundaryCandidate) -> str:
    """Assign confidence based on which tests fired."""
    signals = set(cand.signals)
    # T1 + anything = high
    if "T1" in signals and len(signals) > 1:
        return "high"
    # T1 alone or T2 alone with strong Jaccard = medium
    if "T1" in signals:
        return "medium"
    if "T2" in signals:
        j = cand.jaccard_before
        if j is not None and j <= 0.1:
            return "medium"
        return "low"
    # T3 alone, or T3+T2 = low (farewell/greeting alone is weak)
    return "low"


def merge_candidates(
    candidates: list[BoundaryCandidate],
    merge_window_s: int = MERGE_WINDOW_S,
) -> list[BoundaryCandidate]:
    """Merge candidates within `merge_window_s` of each other.

    When two candidates merge, the one with the earlier split point wins
    (keeps split point) and both sets of signals + evidence are combined.
    """
    if not candidates:
        return []

    sorted_cands = sorted(candidates, key=lambda c: c.split_ts_s)
    merged: list[BoundaryCandidate] = [sorted_cands[0]]

    for cand in sorted_cands[1:]:
        last = merged[-1]
        if cand.split_ts_s - last.split_ts_s <= merge_window_s:
            # Merge into `last`.
            for sig in cand.signals:
                if sig not in last.signals:
                    last.signals.append(sig)
            if cand.gap_s is not None and last.gap_s is None:
                last.gap_s = cand.gap_s
            if cand.jaccard_before is not None and last.jaccard_before is None:
                last.jaccard_before = cand.jaccard_before
                last.speakers_before = cand.speakers_before
                last.speakers_after = cand.speakers_after
            # Keep context from the first candidate; add T3 context if needed.
            if not last.context_before and cand.context_before:
                last.context_before = cand.context_before
            if not last.context_after and cand.context_after:
                last.context_after = cand.context_after
        else:
            merged.append(cand)

    for c in merged:
        c.confidence = _assign_confidence(c)

    return merged


# ---------------------------------------------------------------------------
# Main scan function
# ---------------------------------------------------------------------------


def scan_note(
    note: ParsedNote,
    *,
    self_mic_speakers: frozenset[str] = frozenset(["Microphone", "Gary"]),
    min_gap_s: int = DEFAULT_MIN_GAP_S,
    t2_window_lines: int = DEFAULT_T2_WINDOW_LINES,
    t2_jaccard_max: float = DEFAULT_T2_JACCARD_MAX,
    t3_max_gap_s: int = DEFAULT_T3_MAX_GAP_S,
    t4_max_density: float = DEFAULT_T4_MAX_DENSITY,
    t4_min_span_s: int = DEFAULT_T4_MIN_SPAN_S,
    merge_window_s: int = MERGE_WINDOW_S,
) -> ScanResult:
    """Run all four detection tests on a parsed note; return a ScanResult."""
    lines = note.transcript_lines
    total_s = (lines[-1].ts_s - lines[0].ts_s) if lines else 0

    all_candidates: list[BoundaryCandidate] = []
    all_candidates.extend(t1_silence_gap(lines, min_gap_s=min_gap_s))
    all_candidates.extend(
        t2_speaker_turnover(
            lines,
            self_mic_speakers=self_mic_speakers,
            window_lines=t2_window_lines,
            jaccard_threshold=t2_jaccard_max,
        )
    )
    all_candidates.extend(t3_farewell_greeting(lines, max_gap_s=t3_max_gap_s))

    boundaries = merge_candidates(all_candidates, merge_window_s=merge_window_s)

    dead_air = t4_dead_air(
        lines,
        max_density_per_min=t4_max_density,
        min_span_s=t4_min_span_s,
    )

    return ScanResult(
        path=note.path,
        boundaries=boundaries,
        dead_air_spans=dead_air,
        total_duration_s=total_s,
    )


# ---------------------------------------------------------------------------
# Workspace scan helper
# ---------------------------------------------------------------------------

def _load_self_mic_speakers(workspace: Path) -> frozenset[str]:
    cfg = canonical.load_workspace_config(workspace)
    return frozenset(cfg.get("self_mic_speakers") or ["Microphone", "Gary"])


def scan_workspace(
    workspace: Path,
    *,
    min_gap_s: int = DEFAULT_MIN_GAP_S,
    t2_window_lines: int = DEFAULT_T2_WINDOW_LINES,
    t2_jaccard_max: float = DEFAULT_T2_JACCARD_MAX,
    t3_max_gap_s: int = DEFAULT_T3_MAX_GAP_S,
    t4_max_density: float = DEFAULT_T4_MAX_DENSITY,
    t4_min_span_s: int = DEFAULT_T4_MIN_SPAN_S,
    specific_path: Path | None = None,
) -> list[ScanResult]:
    """Scan all whisper notes under `workspace/YYYY/MM/` (or a single file).

    Returns only ScanResults where boundaries or dead-air spans were found.
    """
    self_mic = _load_self_mic_speakers(workspace)

    def _process(path: Path) -> ScanResult | None:
        note = parse_note(path)
        if note is None:
            return None
        result = scan_note(
            note,
            self_mic_speakers=self_mic,
            min_gap_s=min_gap_s,
            t2_window_lines=t2_window_lines,
            t2_jaccard_max=t2_jaccard_max,
            t3_max_gap_s=t3_max_gap_s,
            t4_max_density=t4_max_density,
            t4_min_span_s=t4_min_span_s,
        )
        if result.boundaries or result.dead_air_spans:
            return result
        return None

    if specific_path:
        r = _process(specific_path)
        return [r] if r else []

    results: list[ScanResult] = []
    for year_dir in sorted(workspace.iterdir()):
        if not year_dir.is_dir() or not re.fullmatch(r"\d{4}", year_dir.name):
            continue
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir() or not re.fullmatch(r"\d{2}", month_dir.name):
                continue
            for md_path in sorted(month_dir.glob("*.md")):
                r = _process(md_path)
                if r:
                    results.append(r)
    return results


# ---------------------------------------------------------------------------
# Partition apply helpers
# ---------------------------------------------------------------------------


def _hhmmss_to_s(ts: str) -> int:
    """Parse 'HH:MM:SS' into total seconds."""
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def _add_offset_to_time(date_str: str, time_str: str, offset_s: int) -> tuple[str, str]:
    """Add `offset_s` to a `HH:MM` wall-clock time on `YYYY-MM-DD`.

    Returns (new_date_str, new_time_str) handling midnight rollover.
    `time_str` may be 'HH:MM' or '' (empty = no adjustment).
    """
    if not time_str:
        return date_str, time_str
    try:
        hour, minute = [int(x) for x in time_str.split(":")]
        dt = datetime(
            *[int(x) for x in date_str.split("-")],
            hour, minute, 0,
            tzinfo=timezone.utc,
        )
        dt2 = dt + timedelta(seconds=offset_s)
        return dt2.strftime("%Y-%m-%d"), dt2.strftime("%H:%M")
    except (ValueError, TypeError):
        return date_str, time_str


def _rebase_ts(ts_s: int, base_s: int) -> str:
    """Rebase a timestamp by subtracting `base_s`, emit 'HH:MM:SS'."""
    rebased = max(0, ts_s - base_s)
    return canonical.ms_to_hhmmss(rebased * 1000)


def _render_part_note(
    original_meta: dict,
    part: dict,
    part_lines: list[TranscriptLine],
    is_single_speaker: bool,
    original_notes_body: str,
    workspace: Path,
) -> tuple[str, str]:
    """Render one split part as a markdown string.

    Returns (markdown_text, out_path_relative_to_workspace).
    """
    from_ts_s = _hhmmss_to_s(part["from_ts"])
    to_ts_s = _hhmmss_to_s(part["to_ts"])

    # Filter lines to this part's window.
    kept = [l for l in part_lines if from_ts_s <= l.ts_s < to_ts_s]

    # Recompute speakers from kept lines.
    speakers = sorted({l.speaker for l in kept if l.speaker})

    # Recompute duration from last kept line's rebased timestamp.
    if kept:
        last_ts_s = kept[-1].ts_s - from_ts_s
        duration = canonical.format_duration_ms(last_ts_s * 1000)
    else:
        duration = ""

    # New date/time.
    orig_date = original_meta.get("date", "").strip()
    orig_time = original_meta.get("time", "").strip().strip('"').strip("'")
    new_date, new_time = _add_offset_to_time(orig_date, orig_time, from_ts_s)

    # Slug.
    title = part.get("title", "untitled")
    slug = canonical.slugify(title)
    year, month, day = new_date.split("-")
    out_path_rel = f"{year}/{month}/{new_date}-{slug}.md"

    # Split part marker.
    total_parts = part.get("_total_kept", "?")
    part_n = part.get("_part_n", "?")
    split_range = f"{part['from_ts']}-{part['to_ts']}"

    # Frontmatter.
    meta_lines = [
        f"title: {_yaml_str(title)}",
        f"date: {new_date}",
    ]
    if new_time:
        meta_lines.append(f"time: {_yaml_str(new_time)}")
    if duration:
        meta_lines.append(f"duration: {duration}")
    meta_lines.append(f"type: {original_meta.get('type', 'other').strip()}")
    meta_lines.append(f"speakers: {_yaml_list(speakers)}")
    model = original_meta.get("model", "").strip().strip('"').strip("'")
    if model:
        meta_lines.append(f"model: {model}")
    tags = part.get("tags") or []
    meta_lines.append(f"tags: {_yaml_list(tags)}")
    source = original_meta.get("source", "").strip().strip('"').strip("'")
    source_type = original_meta.get("source_type", "").strip()
    content_hash = original_meta.get("content_hash", "").strip()
    meta_lines.append(f"source: {_yaml_str(source)}")
    meta_lines.append(f"source_type: {source_type}")
    meta_lines.append(f"content_hash: {content_hash}")
    meta_lines.append(f"split_part: {part_n}/{total_parts}")
    meta_lines.append(f"split_range: {split_range}")

    body: list[str] = ["---", "\n".join(meta_lines), "---", "", f"# {title}", ""]

    # Summary.
    body.append("## Summary")
    body.append("")
    body.append((part.get("summary") or "").strip())
    body.append("")

    # Action items (omit if empty).
    action_items = [a.strip() for a in (part.get("action_items") or []) if a and a.strip()]
    if action_items:
        body.append("## Action Items")
        body.append("")
        for item in action_items:
            body.append(f"- {item}")
        body.append("")

    # Original notes (only if this part is assigned them).
    assigned_original = (part.get("include_original_notes") and original_notes_body)
    if assigned_original:
        body.append("## Original notes")
        body.append("")
        for line in original_notes_body.splitlines():
            body.append(line)
        body.append("")

    # Transcript — with rebased timestamps.
    body.append("## Transcript")
    body.append("")
    distinct_speakers = sorted({l.speaker for l in kept if l.speaker})
    single = len(distinct_speakers) <= 1 or is_single_speaker
    for line in kept:
        ts_rebased = _rebase_ts(line.ts_s, from_ts_s)
        text = line.text
        if single or not line.speaker:
            body.append(f"[{ts_rebased}] {text}")
        else:
            body.append(f"[{ts_rebased}] {line.speaker}: {text}")
    body.append("")

    return "\n".join(body), out_path_rel


def _yaml_str(s: str) -> str:
    """Minimal YAML scalar quoting (mirrors render.py)."""
    if s is None:
        return '""'
    s = str(s)
    needs_quote = (
        not s
        or s[0] in "!&*?|>%@`#-:,[]{}"
        or s.lower() in ("yes", "no", "true", "false", "null", "~")
        or any(ch in s for ch in [":", "#", "\n", "\t"])
        or s.strip() != s
    )
    if needs_quote:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def _yaml_list(items: list[str]) -> str:
    if not items:
        return "[]"
    return "[" + ", ".join(_yaml_str(i) for i in items) + "]"


def _is_git_repo(workspace: Path) -> bool:
    return (workspace / ".git").exists()


def _git(workspace: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", "-C", str(workspace), *args],
        capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


# ---------------------------------------------------------------------------
# apply_partition
# ---------------------------------------------------------------------------


class ApplyResult:
    """Outcome of applying one partition decision."""

    __slots__ = ("original_path", "written", "discarded", "errors")

    def __init__(self, original_path: str):
        self.original_path = original_path
        self.written: list[str] = []
        self.discarded: list[dict] = []
        self.errors: list[str] = []


def apply_partition(workspace: Path, decision: dict) -> ApplyResult:
    """Write split note files for one confirmed partition decision.

    `decision` shape (mirrors decisions.json):

        {
          "note_path": "2026/04/2026-04-27-some-meeting.md",
          "parts": [
            {
              "from_ts": "00:00:00",
              "to_ts": "01:05:00",
              "action": "keep",
              "title": "Sales Q2 Review",
              "summary": "...",
              "action_items": ["..."],
              "tags": ["sales", "q2"],
              "include_original_notes": false
            },
            {
              "from_ts": "01:05:00",
              "to_ts": "04:10:00",
              "action": "discard"
            },
            {
              "from_ts": "04:10:00",
              "to_ts": "05:30:00",
              "action": "keep",
              "title": "Eng Sync",
              ...
            }
          ]
        }
    """
    note_path_rel = decision.get("note_path", "")
    abs_path = (workspace / note_path_rel).resolve()
    result = ApplyResult(note_path_rel)

    note = parse_note(abs_path)
    if note is None:
        result.errors.append(f"could not parse note at {note_path_rel}")
        return result

    parts = decision.get("parts") or []
    if not parts:
        result.errors.append("no parts in decision")
        return result

    kept_parts = [p for p in parts if p.get("action") == "keep"]
    discarded_parts = [p for p in parts if p.get("action") == "discard"]
    total_kept = len(kept_parts)

    # Annotate each kept part with its index and total.
    for i, p in enumerate(kept_parts, start=1):
        p["_part_n"] = i
        p["_total_kept"] = total_kept

    # Track which slugs have been used per date to avoid collisions.
    slugs_used: dict[str, list[str]] = {}

    for p in kept_parts:
        markdown, out_path_rel = _render_part_note(
            original_meta=note.meta,
            part=p,
            part_lines=note.transcript_lines,
            is_single_speaker=note.is_single_speaker,
            original_notes_body=note.original_notes_body,
            workspace=workspace,
        )

        # Resolve slug collisions: if out_path_rel is already used, disambiguate.
        out_path_abs = (workspace / out_path_rel).resolve()
        base_date = out_path_abs.parent.name  # YYYY-MM
        date_part = out_path_abs.stem[:10]    # YYYY-MM-DD
        slug_part = out_path_abs.stem[11:]    # the slug after date-
        same_date_slugs = slugs_used.get(date_part, [])
        final_slug = canonical.disambiguate_slug(slug_part, same_date_slugs)
        if final_slug != slug_part:
            out_path_rel = "/".join(out_path_rel.split("/")[:-1]) + f"/{date_part}-{final_slug}.md"
            out_path_abs = (workspace / out_path_rel).resolve()
        slugs_used.setdefault(date_part, []).append(final_slug)

        out_path_abs.parent.mkdir(parents=True, exist_ok=True)
        out_path_abs.write_text(markdown, encoding="utf-8")

        # Match mtime to original note.
        try:
            st = abs_path.stat()
            os.utime(out_path_abs, (st.st_atime, st.st_mtime))
        except OSError:
            pass

        result.written.append(out_path_rel)

    # Record discarded ranges.
    for p in discarded_parts:
        result.discarded.append({
            "from_ts": p.get("from_ts"),
            "to_ts": p.get("to_ts"),
        })

    # Remove the original note — but only if it wasn't overwritten in place by
    # a kept part that resolved to the same path (single-keep trims reuse the
    # original title/date, so the new file IS the original file; deleting it
    # would destroy the trimmed content we just wrote).
    if result.written and note_path_rel not in result.written:
        if _is_git_repo(workspace):
            rc, _, err = _git(workspace, "rm", "-f", note_path_rel)
            if rc != 0:
                try:
                    abs_path.unlink()
                except OSError as e:
                    result.errors.append(f"git rm failed ({err.strip()}); unlink also failed: {e}")
        else:
            try:
                abs_path.unlink()
            except OSError as e:
                result.errors.append(f"could not remove original: {e}")

    return result
