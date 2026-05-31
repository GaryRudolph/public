"""Resolve a session from fuzzy title / date / time hints.

The skill asks the user which recording to split or combine; they rarely know
the UUID. This module reads the (live, non-deleted) session index read-only and
ranks candidates so the skill can present a short, ordered disambiguation list.

IO and ranking are split: `load_session_index` does the read-only query;
`rank_candidates` is pure and is what the tests exercise. Scoring blends title
similarity (`difflib`), same-day match, and time-of-day proximity — all
best-effort hints, never a hard filter, so a good title match still ranks even
if the date is fuzzy.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import Sequence

from . import db


@dataclass(frozen=True)
class SessionRecord:
    """The minimal session metadata used for ranking (read-only projection)."""

    id_hex: str
    title: str
    date_created: str | None
    kind: str


@dataclass(frozen=True)
class SessionCandidate:
    """A ranked match for the user's hints."""

    record: SessionRecord
    score: float
    reasons: tuple[str, ...] = field(default_factory=tuple)


def load_session_index(conn: sqlite3.Connection) -> list[SessionRecord]:
    """Read all live (non-soft-deleted) sessions with a best-effort title.

    Filters `dateDeleted IS NULL` on both the session and its joined
    `recordedmeeting` (§3.3). Title falls back through user title, meeting
    title, voice-memo title, AI title, then the session id.
    """
    cur = conn.execute(
        "SELECT lower(hex(s.id)) AS id_hex, s.dateCreated AS date_created, "
        "s.userChosenTitle AS user_title, s.aiTitle AS ai_title, "
        "s.voiceMemoID AS voice_memo_id, s.recordedMeetingID AS recorded_meeting_id, "
        "s.systemAudioRecordingID AS system_audio_id, "
        "rm.title AS meeting_title, vm.title AS memo_title "
        "FROM session s "
        "LEFT JOIN recordedmeeting rm "
        "  ON rm.id = s.recordedMeetingID AND rm.dateDeleted IS NULL "
        "LEFT JOIN voicememos vm "
        "  ON vm.id = s.voiceMemoID AND vm.dateDeleted IS NULL "
        "WHERE s.dateDeleted IS NULL "
        "ORDER BY s.dateCreated DESC"
    )
    out: list[SessionRecord] = []
    for row in cur.fetchall():
        title = (
            (row["user_title"] or "").strip()
            or (row["meeting_title"] or "").strip()
            or (row["memo_title"] or "").strip()
            or (row["ai_title"] or "").strip()
            or row["id_hex"]
        )
        out.append(
            SessionRecord(
                id_hex=row["id_hex"],
                title=title,
                date_created=row["date_created"],
                kind=_kind_of(row),
            )
        )
    return out


def _kind_of(row: sqlite3.Row) -> str:
    if row["voice_memo_id"] is not None:
        return "voice-memo"
    if row["recorded_meeting_id"] is not None:
        return "meeting"
    if row["system_audio_id"] is not None:
        return "system-audio"
    return "other"


def rank_candidates(
    records: Sequence[SessionRecord],
    *,
    title: str | None = None,
    date: str | None = None,
    time: str | None = None,
    limit: int = 10,
    min_score: float = 0.05,
) -> list[SessionCandidate]:
    """Rank `records` against the hints. Pure; no IO.

    Args:
        records: Candidate sessions (from `load_session_index`).
        title: Free-text title hint (fuzzy matched).
        date: ``YYYY-MM-DD`` hint; same-day matches are boosted.
        time: ``HH:MM`` (24h) hint; closeness in the day is boosted.
        limit: Max candidates to return.
        min_score: Drop candidates below this score unless no hint was given.

    Returns:
        Candidates sorted by descending score (ties broken newest-first).
    """
    no_hints = not (title or date or time)
    scored: list[SessionCandidate] = []
    for rec in records:
        score = 0.0
        reasons: list[str] = []
        dt = db.parse_db_datetime(rec.date_created)

        if title:
            ratio = _title_ratio(title, rec.title)
            if ratio > 0:
                score += ratio * 0.6
                reasons.append(f"title~{ratio:.2f}")
        if date and dt is not None:
            if dt.strftime("%Y-%m-%d") == date.strip():
                score += 0.3
                reasons.append("same-day")
        if time and dt is not None:
            proximity = _time_proximity(time, dt)
            if proximity > 0:
                score += proximity * 0.2
                reasons.append(f"time~{proximity:.2f}")

        if no_hints:
            score = 1.0  # surface everything newest-first when nothing to match on
        scored.append(SessionCandidate(record=rec, score=score, reasons=tuple(reasons)))

    def sort_key(c: SessionCandidate) -> tuple:
        dt = db.parse_db_datetime(c.record.date_created)
        epoch = dt.timestamp() if dt else 0.0
        return (-c.score, -epoch)

    scored.sort(key=sort_key)
    if not no_hints:
        scored = [c for c in scored if c.score >= min_score]
    return scored[:limit]


def _title_ratio(query: str, candidate: str) -> float:
    q = " ".join(query.lower().split())
    c = " ".join(candidate.lower().split())
    if not q or not c:
        return 0.0
    if q in c:
        return 1.0
    return SequenceMatcher(None, q, c).ratio()


def _time_proximity(time_hint: str, dt: datetime) -> float:
    """1.0 at an exact HH:MM match, decaying to 0 at 12h apart. Local time."""
    try:
        hh, mm = time_hint.strip().split(":")
        target_minutes = int(hh) * 60 + int(mm)
    except (ValueError, IndexError):
        return 0.0
    try:
        local = dt.astimezone()
    except (ValueError, OSError):
        local = dt
    actual_minutes = local.hour * 60 + local.minute
    delta = abs(actual_minutes - target_minutes)
    delta = min(delta, 1440 - delta)  # wrap around midnight
    return max(0.0, 1.0 - delta / 720.0)
