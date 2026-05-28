"""Source-agnostic canonical recording transforms.

Both the file-source and DB-source skills assemble the same canonical dict
shape (see SPEC.md "Canonical recording structure") and then run it through
the same dedup -> truncate -> hash -> slug pipeline. The shape is:

    {
      "date":     "<ISO 8601 UTC, millisecond precision>",
      "speakers": [<sorted unique speaker names>],
      "segments": [
        {"start_ms": int, "end_ms": int, "speaker": str|None, "text": str},
        ...                                 # sorted by (start_ms, end_ms)
      ],
    }

`content_hash()` is a SHA-256 over this dict serialized with sort_keys=True
and the compact JSON separators. It's the idempotency key the rest of the
pipeline keys off of, and (per SPEC) the algorithm is intentionally stable
across versions — changing it would invalidate every existing note's hash.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

DEFAULT_SELF_MIC_SPEAKERS = ["Microphone", "Gary"]
DEFAULT_DEDUP_WINDOW_MS = 2500
DEFAULT_DEDUP_SIMILARITY = 0.7

CONFIG_FILENAME = ".whisper-config.json"


# ---------------------------------------------------------------------------
# Workspace config
# ---------------------------------------------------------------------------


def load_workspace_config(workspace: Path) -> dict:
    """Read `<workspace>/.whisper-config.json` if present, else defaults.

    Schema (all keys optional):

        {
          "self_mic_speakers": ["Microphone", "Gary"],
          "truncate": {
            "<source-uuid-or-filename>": {
              "after_ms": 2030000,
              "note": "left recording running"
            }
          }
        }
    """
    path = Path(workspace) / CONFIG_FILENAME
    cfg: dict = {
        "self_mic_speakers": list(DEFAULT_SELF_MIC_SPEAKERS),
        "truncate": {},
    }
    if not path.exists():
        return cfg
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return cfg
    if isinstance(loaded, dict):
        if isinstance(loaded.get("self_mic_speakers"), list):
            cfg["self_mic_speakers"] = [
                str(s) for s in loaded["self_mic_speakers"] if isinstance(s, str)
            ]
        if isinstance(loaded.get("truncate"), dict):
            cfg["truncate"] = loaded["truncate"]
    return cfg


def truncate_after_ms_for(cfg: dict, *source_keys: str) -> int | None:
    """Look up the truncate.<key>.after_ms for any of the given source keys.

    Keys are matched in order — first hit wins. We accept multiple keys so
    callers can pass both a UUID and a filename (one of them will be the
    user's chosen identifier).
    """
    truncate = (cfg or {}).get("truncate") or {}
    for key in source_keys:
        if not key:
            continue
        entry = truncate.get(key)
        if isinstance(entry, dict) and isinstance(entry.get("after_ms"), int):
            return entry["after_ms"]
    return None


# ---------------------------------------------------------------------------
# Segment dedup + truncation
# ---------------------------------------------------------------------------


def _norm_for_compare(s: str) -> str:
    return " ".join(s.lower().split())


def self_mic_dedup(
    segments: list[dict],
    self_mic_speakers: Iterable[str] = DEFAULT_SELF_MIC_SPEAKERS,
    window_ms: int = DEFAULT_DEDUP_WINDOW_MS,
    similarity_threshold: float = DEFAULT_DEDUP_SIMILARITY,
) -> list[dict]:
    """Drop self-mic segments that duplicate a nearby non-self segment.

    A self-mic segment is dropped iff there's a non-self segment whose
    `start_ms` is within +-`window_ms` and whose text similarity (via
    `difflib.SequenceMatcher`) is >= `similarity_threshold`.

    Fallback: if a recording has *only* self-mic speakers, keep them all.
    This handles the voice-memo case where Gary is the only speaker and the
    track was renamed away from the default "Microphone" label.
    """
    self_set = {s for s in self_mic_speakers if s}
    speakers_present = {seg.get("speaker") for seg in segments if seg.get("speaker")}
    non_self_present = speakers_present - self_set
    if not non_self_present:
        return list(segments)

    non_self_segments = [seg for seg in segments if seg.get("speaker") not in self_set]
    kept: list[dict] = []
    for seg in segments:
        if seg.get("speaker") not in self_set:
            kept.append(seg)
            continue
        seg_text = _norm_for_compare(seg.get("text", ""))
        if not seg_text:
            kept.append(seg)
            continue
        is_dup = False
        for other in non_self_segments:
            if abs(other["start_ms"] - seg["start_ms"]) > window_ms:
                continue
            other_text = _norm_for_compare(other.get("text", ""))
            if not other_text:
                continue
            ratio = SequenceMatcher(None, seg_text, other_text).ratio()
            if ratio >= similarity_threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(seg)
    return kept


def truncate_segments(
    segments: list[dict], after_ms: int | None
) -> tuple[list[dict], int | None]:
    """Drop any segment that starts at/after `after_ms`. Recompute duration.

    Returns `(kept_segments, new_duration_ms)`. `new_duration_ms` is the
    last kept segment's `end_ms`, or None if the truncation wiped everything.
    If `after_ms` is None, returns the original list unchanged with a
    duration derived from the last segment.
    """
    if not segments:
        return list(segments), None
    if after_ms is None:
        return list(segments), int(segments[-1]["end_ms"])
    kept = [s for s in segments if s["start_ms"] < after_ms]
    duration_ms = int(kept[-1]["end_ms"]) if kept else None
    return kept, duration_ms


# ---------------------------------------------------------------------------
# Canonical structure + hash
# ---------------------------------------------------------------------------


def build_canonical(
    *,
    date_iso_utc: str,
    raw_segments: list[dict],
    self_mic_speakers: Iterable[str] = DEFAULT_SELF_MIC_SPEAKERS,
    truncate_after_ms: int | None = None,
) -> tuple[dict, int | None]:
    """Assemble the canonical recording dict from already-resolved segments.

    `raw_segments` items must have keys `start_ms`, `end_ms`, `speaker`,
    `text`. Speaker names should already be resolved (no IDs). Returns
    `(canonical_dict, duration_ms_after_truncate_or_None)`.
    """
    cleaned = [
        {
            "start_ms": int(s["start_ms"]),
            "end_ms": int(s["end_ms"]),
            "speaker": s["speaker"] if s.get("speaker") else None,
            "text": (s.get("text") or "").strip(),
        }
        for s in raw_segments
    ]
    cleaned.sort(key=lambda s: (s["start_ms"], s["end_ms"]))
    cleaned = self_mic_dedup(cleaned, self_mic_speakers=self_mic_speakers)
    cleaned, duration_ms = truncate_segments(cleaned, truncate_after_ms)
    speakers = sorted({s["speaker"] for s in cleaned if s["speaker"]})
    canonical = {
        "date": date_iso_utc,
        "speakers": speakers,
        "segments": cleaned,
    }
    return canonical, duration_ms


def content_hash(canonical: dict) -> str:
    """SHA-256 over canonical JSON with sorted keys and compact separators.

    Stable across the file and DB skills by construction. Algorithm is
    pinned per SPEC.md — do not change.
    """
    payload = json.dumps(
        canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Slug / title helpers
# ---------------------------------------------------------------------------


_SLUG_KEEP = re.compile(r"[^a-z0-9]+")
_SLUG_COLLAPSE = re.compile(r"-+")


def slugify(title: str, max_len: int = 60) -> str:
    """SPEC slug rules: lowercase, a-z0-9-, collapsed, edge-trimmed, word-cap."""
    if not title:
        return "untitled"
    s = title.lower()
    s = _SLUG_KEEP.sub("-", s)
    s = _SLUG_COLLAPSE.sub("-", s).strip("-")
    if not s:
        return "untitled"
    if len(s) <= max_len:
        return s
    cut = s[:max_len]
    if "-" in cut:
        cut = cut.rsplit("-", 1)[0]
    return cut or s[:max_len]


def disambiguate_slug(slug: str, existing_slugs_for_date: Iterable[str]) -> str:
    """Append -2, -3, ... if `slug` collides with an existing same-date slug."""
    existing = set(existing_slugs_for_date)
    if slug not in existing:
        return slug
    n = 2
    while f"{slug}-{n}" in existing:
        n += 1
    return f"{slug}-{n}"


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def ms_to_hhmmss(ms: int) -> str:
    seconds = max(0, int(ms)) // 1000
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_duration_ms(ms: int | None) -> str:
    if ms is None or ms < 0:
        return ""
    seconds = int(ms) // 1000
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m" if m else f"{h}h"
    if m:
        return f"{m}m {s}s" if s else f"{m}m"
    return f"{s}s"


def parse_iso_utc(iso_str: str) -> datetime:
    """Parse an ISO-8601 string into a UTC datetime. Accepts trailing 'Z'."""
    s = iso_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
