#!/usr/bin/env python3
"""File-source entry point for personal-whisper-to-markdown.

Thin wrapper around the shared whisper runner library. It only knows how
to read `.whisper` ZIP archives from `<workspace>/whisper/` and translate
each into a source_record; everything downstream lives in
`skills/lib/whisper/`.

Run from a shell as:

    python3 scripts/run.py plan          --workspace ~/Projects/personal/notes
    python3 scripts/run.py merge         --workspace ~/Projects/personal/notes
    python3 scripts/run.py lookup-tags propose --workspace ~/Projects/personal/notes
    python3 scripts/run.py lookup-tags apply   --workspace ~/Projects/personal/notes
    python3 scripts/run.py write         --workspace ~/Projects/personal/notes
    python3 scripts/run.py report        --workspace ~/Projects/personal/notes
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB_ROOT = HERE.parent.parent / "lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from whisper import runner  # noqa: E402


MAC_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)

# Filenames like "Meeting - Zoom 2026-04-27 07_32_47.whisper" - we use the
# stem (no extension) as session_key, and the "Meeting - <App>" prefix to
# infer session type.
_FILENAME_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})[ _](\d{2})[ _](\d{2})[ _](\d{2})")
_MEETING_PREFIX_RE = re.compile(r"^Meeting\s*-\s*(.+?)\s+\d{4}-\d{2}-\d{2}", re.IGNORECASE)


def _mac_absolute_to_iso(seconds: float | int | None) -> str:
    if seconds is None:
        return ""
    try:
        dt = MAC_EPOCH + timedelta(seconds=float(seconds))
    except (ValueError, TypeError, OverflowError):
        return ""
    return dt.isoformat(timespec="milliseconds")


def _session_type(name: str, original_media_filename: str) -> str:
    if _MEETING_PREFIX_RE.match(name):
        return "meeting"
    media = (original_media_filename or "").strip().lower()
    if media == "voice memo" or media == "":
        if not _MEETING_PREFIX_RE.match(name):
            return "voice-memo"
    if "voice memo" in name.lower():
        return "voice-memo"
    return "other"


def _provisional_title_from_filename(name: str) -> str:
    base = Path(name).stem
    m = _MEETING_PREFIX_RE.match(base)
    if m:
        return f"Meeting - {m.group(1)}"
    base_clean = _FILENAME_DATE_RE.sub("", base).strip(" _-")
    return base_clean or "Voice Memo"


def _resolve_speaker_name(seg_speaker: dict | None, stub_index: dict[str, str]) -> str | None:
    if not seg_speaker:
        return None
    name = (seg_speaker.get("name") or "").strip()
    spid = seg_speaker.get("id") or ""
    if not name:
        return None
    # If the source stored the speaker name as the UUID-style identifier,
    # treat it as a stub and assign a Speaker N label.
    if name == spid:
        return stub_index.setdefault(spid, f"Speaker {len(stub_index) + 1}")
    return name


def _iter_whisper_file(path: Path) -> dict | None:
    """Parse a single `.whisper` ZIP into a source_record. Returns None on
    parse failure (caller logs and skips).
    """
    try:
        with zipfile.ZipFile(path) as zf:
            with zf.open("metadata.json") as fh:
                meta = json.loads(fh.read().decode("utf-8"))
    except (zipfile.BadZipFile, KeyError, OSError, json.JSONDecodeError) as e:
        sys.stderr.write(f"[file] failed to parse {path.name}: {e}\n")
        return None

    name = path.name
    sk = path.stem  # filename without extension, safe as a filesystem key
    date_iso = _mac_absolute_to_iso(meta.get("dateCreated"))
    duration_sec = None
    if isinstance(meta.get("duration"), (int, float)):
        duration_sec = int(meta["duration"])

    stub_index: dict[str, str] = {}
    transcripts = meta.get("transcripts") or []

    raw_segments = []
    for seg in transcripts:
        name_resolved = _resolve_speaker_name(seg.get("speaker"), stub_index)
        raw_segments.append({
            "start_ms": int(seg.get("start") or 0),
            "end_ms": int(seg.get("end") or 0),
            "speaker": name_resolved,
            "text": (seg.get("text") or "").strip(),
        })

    if duration_sec is None and raw_segments:
        duration_sec = int(raw_segments[-1]["end_ms"] // 1000)

    session_type = _session_type(name, meta.get("originalMediaFilename") or "")
    provisional_title = _provisional_title_from_filename(name)
    model = (meta.get("modelQualityID") or meta.get("modelEngine") or "").strip()

    all_speakers = sorted({s["speaker"] for s in raw_segments if s.get("speaker")})

    try:
        source_mtime = path.stat().st_mtime
    except OSError:
        source_mtime = None

    return {
        "session_key": sk,
        "source": name,
        "source_type": "file",
        "date_iso_utc": date_iso,
        "type": session_type,
        "model": model,
        "raw_segments": raw_segments,
        "all_speakers": all_speakers,
        "duration_sec": duration_sec,
        "provisional_title": provisional_title,
        "macwhisper_title_hint": (meta.get("originalMediaFilename") or name),
        "macwhisper_tags": [],
        "truncate_keys": [name, sk],
        "source_mtime": source_mtime,
    }


def iter_file_sessions(workspace: Path):
    """Yield one source_record per `.whisper` ZIP under `<workspace>/whisper/`."""
    whisper_dir = Path(workspace) / "whisper"
    if not whisper_dir.is_dir():
        sys.stderr.write(f"[file] no whisper/ directory under {workspace}\n")
        return
    for path in sorted(whisper_dir.glob("*.whisper")):
        rec = _iter_whisper_file(path)
        if rec is not None:
            yield rec


def main() -> int:
    return runner.main(sys.argv[1:], iter_file_sessions)


if __name__ == "__main__":
    raise SystemExit(main())
