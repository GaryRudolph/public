#!/usr/bin/env python3
"""DB-source entry point for personal-whisper-to-markdown-db.

This is a thin wrapper around the shared whisper runner library. It only
knows how to enumerate MacWhisper sessions from the live SQLite DB;
everything downstream (canonical building, dedup, truncation, hash,
slug, historical search, render, write, tag merge, lookup-tags) lives
in `skills/lib/whisper/`.

Run from a shell as:

    python3 scripts/run.py plan          --workspace ~/Projects/personal/notes
    python3 scripts/run.py merge         --workspace ~/Projects/personal/notes
    python3 scripts/run.py lookup-tags propose --workspace ~/Projects/personal/notes
    python3 scripts/run.py lookup-tags apply   --workspace ~/Projects/personal/notes
    python3 scripts/run.py write         --workspace ~/Projects/personal/notes
    python3 scripts/run.py report        --workspace ~/Projects/personal/notes

`python -m run <cmd>` also works when invoked from this directory.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Resolve the shared library path. Both this skill and the lib are symlinked
# under ~/.cursor/skills/ and ~/.claude/skills/, but `__file__` always points
# at the real path inside the public agents repo, so `../../lib` reaches the
# shared library no matter where the skill is invoked from.
HERE = Path(__file__).resolve().parent
LIB_ROOT = HERE.parent.parent / "lib"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from whisper import runner  # noqa: E402  (after sys.path insert)


DB_PATH = Path.home() / "Library/Application Support/MacWhisper/Database/main.sqlite"


# ---------------------------------------------------------------------------
# SQLite -> source records
# ---------------------------------------------------------------------------


def _open_db_readonly(path: Path) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _hex(b: bytes | None) -> str | None:
    if b is None:
        return None
    if isinstance(b, str):
        return b.lower()
    return b.hex()


def _format_iso_utc(date_str: str) -> str:
    """MacWhisper stores `dateCreated` as 'YYYY-MM-DD HH:MM:SS.fff' UTC.

    Sometimes the millisecond fragment is missing; sometimes it's a `T`
    separator. We accept both and always emit ISO-8601 with explicit UTC.
    """
    if not date_str:
        return ""
    s = date_str.strip().replace("T", " ")
    fmts = (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    )
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            return dt.isoformat(timespec="milliseconds")
        except ValueError:
            continue
    return s  # last resort — let downstream best-effort parse handle it


def _resolve_speaker_name(speakers_by_id: dict, speaker_id_hex: str | None) -> str | None:
    if not speaker_id_hex:
        return None
    sp = speakers_by_id.get(speaker_id_hex)
    if not sp:
        return None
    if int(sp["isStub"] or 0):
        return None  # stub -> handled downstream as Speaker N? we keep None here
    name = (sp["name"] or "").strip()
    return name or None


def _pick_title(row: dict) -> tuple[str, str]:
    """Return (provisional_title, macwhisper_title_hint).

    Both are best-effort hints; the final title is decided by the
    content-generation step. We keep the raw MacWhisper title separately
    so subagents can reason about whether to use it.
    """
    user = (row.get("user_title") or "").strip()
    ai = (row.get("ai_title") or "").strip()
    rm = (row.get("recorded_meeting_title") or "").strip()
    orig = (row.get("original_filename") or "").strip()
    hint = user or ai or rm or orig or ""
    if user and user.lower() != "test":
        return user, hint
    if rm:
        return rm, hint
    if ai:
        return ai, hint
    if orig:
        return orig, hint
    return "untitled", hint


def _session_type(row: dict) -> str:
    if row.get("voiceMemoID") is not None:
        return "voice-memo"
    if row.get("recordedMeetingID") is not None:
        return "meeting"
    if row.get("systemAudioRecordingID") is not None:
        return "meeting"
    return "other"


def iter_db_sessions(workspace: Path):
    """Yield one source_record per non-deleted MacWhisper session.

    See `runner.py` "Source-record contract" for the dict shape.
    """
    if not DB_PATH.exists():
        sys.stderr.write(
            f"[db] MacWhisper DB not found at {DB_PATH}\n"
        )
        return
    conn = _open_db_readonly(DB_PATH)
    cur = conn.cursor()
    # Some MacWhisper schemas have a typo (`modelIdentifer`) — query both
    # spellings tolerantly.
    cur.execute("PRAGMA table_info(session)")
    cols = {r["name"] for r in cur.fetchall()}
    model_col = "modelIdentifer" if "modelIdentifer" in cols else (
        "modelIdentifier" if "modelIdentifier" in cols else None
    )
    duration_col = "playbackDuration" if "playbackDuration" in cols else (
        "duration" if "duration" in cols else None
    )
    has_succeeded = "transcriptionDidSucceed" in cols

    select_cols = [
        "lower(hex(s.id)) AS session_id",
        "s.dateCreated AS date_created",
        "s.userChosenTitle AS user_title",
        "s.aiTitle AS ai_title",
        "s.originalFilename AS original_filename",
        "s.modelEngine AS model_engine",
        f"{('s.' + model_col + ' AS model_identifier') if model_col else 'NULL AS model_identifier'}",
        f"{('s.' + duration_col + ' AS duration_sec') if duration_col else 'NULL AS duration_sec'}",
        "s.voiceMemoID AS voiceMemoID",
        "s.recordedMeetingID AS recordedMeetingID",
        "s.systemAudioRecordingID AS systemAudioRecordingID",
        "rm.title AS recorded_meeting_title",
        "rm.appName AS recorded_meeting_app",
    ]
    where = ["s.dateDeleted IS NULL"]
    if has_succeeded:
        where.append("s.transcriptionDidSucceed = 1")
    sql = (
        f"SELECT {', '.join(select_cols)} "
        f"FROM session s "
        f"LEFT JOIN recordedmeeting rm "
        f"ON rm.id = s.recordedMeetingID AND rm.dateDeleted IS NULL "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY s.dateCreated ASC"
    )
    cur.execute(sql)
    sessions = [dict(r) for r in cur.fetchall()]

    for row in sessions:
        sk = row["session_id"]
        cur.execute(
            "SELECT lower(hex(t.speakerID)) AS speaker_id, t.start AS start_ms, "
            "t.end AS end_ms, t.text AS text "
            "FROM transcriptline t "
            "WHERE t.sessionId = ? "
            "ORDER BY t.start ASC, t.dateCreated ASC",
            (bytes.fromhex(sk),),
        )
        seg_rows = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT lower(hex(sp.id)) AS speaker_id, sp.name AS name, sp.isStub AS isStub "
            "FROM speaker sp WHERE sp.id IN (SELECT speakerID FROM session_speaker WHERE sessionID = ?)",
            (bytes.fromhex(sk),),
        )
        speakers_by_id = {r["speaker_id"]: dict(r) for r in cur.fetchall()}

        cur.execute(
            "SELECT t.name FROM tag t JOIN session_tag st ON st.tagID = t.id "
            "WHERE st.sessionID = ?",
            (bytes.fromhex(sk),),
        )
        macwhisper_tags = [r["name"] for r in cur.fetchall() if r["name"]]

        # Resolve segment speaker names, falling back to "Speaker N" for stubs.
        stub_index: dict[str, str] = {}
        next_stub_n = 1
        for sid, sp in speakers_by_id.items():
            if int(sp["isStub"] or 0):
                stub_index[sid] = f"Speaker {next_stub_n}"
                next_stub_n += 1

        raw_segments = []
        for seg in seg_rows:
            sid = seg["speaker_id"]
            name = None
            if sid:
                if sid in stub_index:
                    name = stub_index[sid]
                else:
                    sp = speakers_by_id.get(sid)
                    if sp:
                        name = (sp["name"] or "").strip() or None
            raw_segments.append({
                "start_ms": int(seg["start_ms"] or 0),
                "end_ms": int(seg["end_ms"] or 0),
                "speaker": name,
                "text": (seg["text"] or "").strip(),
            })

        provisional_title, title_hint = _pick_title(row)
        all_speakers = sorted({s["speaker"] for s in raw_segments if s.get("speaker")})

        yield {
            "session_key": sk,
            "source": f"macwhisper-db:{sk}",
            "source_type": "db",
            "date_iso_utc": _format_iso_utc(row["date_created"]),
            "type": _session_type(row),
            "model": (row.get("model_identifier") or row.get("model_engine") or "").strip(),
            "raw_segments": raw_segments,
            "all_speakers": all_speakers,
            "duration_sec": int(row["duration_sec"]) if row.get("duration_sec") is not None else None,
            "provisional_title": provisional_title,
            "macwhisper_title_hint": title_hint,
            "macwhisper_tags": macwhisper_tags,
            "truncate_keys": [sk, (row.get("original_filename") or "").strip()],
            "source_mtime": None,
        }

    conn.close()


def main() -> int:
    return runner.main(sys.argv[1:], iter_db_sessions)


if __name__ == "__main__":
    raise SystemExit(main())
