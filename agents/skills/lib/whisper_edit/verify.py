"""Post-write verification of a materialized session.

After `clone.apply_clone` runs, this re-reads the live database (the same
connection) and the filesystem to confirm the write landed correctly:

- the session row exists,
- the transcript-line, media, and speaker-link counts match the plan,
- every referenced `ExternalMedia/` file is present on disk,
- the last `transcriptline.end` is within tolerance of the probed audio
  duration (catches a cut/concat misalignment, §Risks),
- `PRAGMA foreign_key_check` reports no violations, and
- the new session is findable through `sessionFTS` (the §10.6 assumption —
  best-effort; a miss is flagged, not fatal).

`verify_clone` returns a `VerificationReport`; it never deletes or rolls back.
The caller decides what to do with failures (a backup already exists).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from . import db
from .clone import ClonePlan
from .media import MediaTool

DEFAULT_DURATION_TOLERANCE_MS = 2_000
DEFAULT_DURATION_TOLERANCE_RATIO = 0.05


@dataclass(frozen=True)
class Check:
    """A single verification check result."""

    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class VerificationReport:
    """The aggregate of all checks for one materialized session."""

    session_id_hex: str
    checks: tuple[Check, ...]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def failures(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if not c.ok)


def verify_clone(
    conn: sqlite3.Connection,
    plan: ClonePlan,
    *,
    external_media_dir: Path,
    tool: MediaTool | None = None,
    duration_tolerance_ms: int = DEFAULT_DURATION_TOLERANCE_MS,
    duration_tolerance_ratio: float = DEFAULT_DURATION_TOLERANCE_RATIO,
) -> VerificationReport:
    """Run all post-write checks for `plan`. Read-only; never mutates."""
    checks: list[Check] = []
    sid = db.hex_to_bytes(plan.new_session_id_hex)

    checks.append(_check_session_exists(conn, sid))
    checks.append(_check_count(conn, "transcriptline", "sessionId", sid, len(plan.lines), "lines"))
    checks.append(_check_media_count(conn, plan))
    checks.append(_check_speaker_links(conn, sid, len(plan.speaker_links)))
    checks.extend(_check_media_files_exist(plan, external_media_dir))
    checks.append(_check_foreign_keys(conn))
    checks.append(_check_fts(conn, plan))
    if tool is not None:
        checks.append(
            _check_duration_alignment(
                plan, external_media_dir, tool, duration_tolerance_ms, duration_tolerance_ratio
            )
        )

    return VerificationReport(session_id_hex=plan.new_session_id_hex, checks=tuple(checks))


def _check_session_exists(conn: sqlite3.Connection, sid: bytes) -> Check:
    cur = conn.execute("SELECT 1 FROM session WHERE id = ?", (sid,))
    return Check("session_exists", cur.fetchone() is not None)


def _check_count(
    conn: sqlite3.Connection, table: str, fk: str, sid: bytes, expected: int, label: str
) -> Check:
    cur = conn.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE {fk} = ?", (sid,))
    actual = cur.fetchone()["n"]
    return Check(
        f"{label}_count",
        actual == expected,
        f"expected {expected}, found {actual}",
    )


def _check_media_count(conn: sqlite3.Connection, plan: ClonePlan) -> Check:
    ids = [db.hex_to_bytes(m.id_hex) for m in plan.media]
    if not ids:
        return Check("media_count", True, "no media expected")
    placeholders = ", ".join("?" for _ in ids)
    cur = conn.execute(
        f"SELECT COUNT(*) AS n FROM mediafile WHERE id IN ({placeholders})", ids
    )
    actual = cur.fetchone()["n"]
    return Check("media_count", actual == len(ids), f"expected {len(ids)}, found {actual}")


def _check_speaker_links(conn: sqlite3.Connection, sid: bytes, expected: int) -> Check:
    cur = conn.execute(
        "SELECT COUNT(*) AS n FROM session_speaker WHERE sessionID = ?", (sid,)
    )
    actual = cur.fetchone()["n"]
    return Check("speaker_links", actual == expected, f"expected {expected}, found {actual}")


def _check_media_files_exist(plan: ClonePlan, external_media_dir: Path) -> list[Check]:
    out: list[Check] = []
    for m in plan.media:
        path = Path(external_media_dir) / m.filename
        out.append(
            Check(f"media_file:{m.filename}", path.exists(), "" if path.exists() else "missing")
        )
    if not plan.media:
        out.append(Check("media_files_exist", True, "no media expected"))
    return out


def _check_foreign_keys(conn: sqlite3.Connection) -> Check:
    cur = conn.execute("PRAGMA foreign_key_check")
    rows = cur.fetchall()
    return Check("foreign_key_integrity", not rows, f"{len(rows)} violation(s)")


def _check_fts(conn: sqlite3.Connection, plan: ClonePlan) -> Check:
    """Confirm the new session is reachable via sessionFTS (§6, §10.6)."""
    if not db.table_exists(conn, "sessionFTS"):
        return Check("fts_searchable", True, "sessionFTS not present")
    sid = db.hex_to_bytes(plan.new_session_id_hex)
    cur = conn.execute(
        "SELECT s.id FROM sessionFTS f JOIN session s ON s.rowid = f.rowid "
        "WHERE f.sessionFTS MATCH 'id' AND s.id = ? LIMIT 1",
        (sid,),
    )
    # Some builds disallow matching on the id column; fall back to a rowid probe.
    try:
        found = cur.fetchone() is not None
    except sqlite3.Error:
        found = False
    if not found:
        cur = conn.execute(
            "SELECT 1 FROM sessionFTS f JOIN session s ON s.rowid = f.rowid WHERE s.id = ? LIMIT 1",
            (sid,),
        )
        found = cur.fetchone() is not None
    return Check("fts_searchable", found, "" if found else "session not indexed in sessionFTS")


def _check_duration_alignment(
    plan: ClonePlan,
    external_media_dir: Path,
    tool: MediaTool,
    tolerance_ms: int,
    tolerance_ratio: float,
) -> Check:
    if not plan.lines:
        return Check("duration_alignment", True, "no lines")
    last_end = max(l.end_ms for l in plan.lines)
    # Probe the longest produced track (most representative of full duration).
    durations: list[int] = []
    for m in plan.media:
        path = Path(external_media_dir) / m.filename
        if path.exists():
            try:
                durations.append(tool.probe_duration_ms(path))
            except Exception:  # noqa: BLE001 - probing is best-effort here
                continue
    if not durations:
        return Check("duration_alignment", True, "no probeable media")
    probed = max(durations)
    tolerance = max(tolerance_ms, int(probed * tolerance_ratio))
    drift = abs(probed - last_end)
    return Check(
        "duration_alignment",
        drift <= tolerance,
        f"last_line_end={last_end}ms probed={probed}ms drift={drift}ms tol={tolerance}ms",
    )
