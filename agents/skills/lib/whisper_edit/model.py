"""Immutable domain model + the read-only `Bundle` loader.

Two families of value types live here:

- **Source types** (`SessionRow`, `RecordedMeeting`, `VoiceMemo`, `MediaFile`,
  `TranscriptLine`, `Speaker`, `Bundle`) describe what we read out of an
  existing MacWhisper session. `Bundle.load` is the only function that touches
  the database, and it does so read-only.
- **Target types** (`TargetLine`, `AudioCut`, `TargetAudio`, `TargetBundle`)
  describe a *new* session we intend to materialize. They carry no UUIDs and no
  database state — `clone.py` turns a `TargetBundle` into concrete rows + files.
  Keeping targets UUID-free makes `split`/`combine` pure and trivially testable.

Everything is frozen (immutable by default). `SessionRow`/`RecordedMeeting`/
`VoiceMemo` keep the full raw column map so `clone.py` can faithfully carry
forward unknown/extra columns (full fidelity) while explicitly clearing the
identity, AI, and text columns.

See `specs/macwhisper-database.md` §4-§7 for the schema this mirrors.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from . import db


# ---------------------------------------------------------------------------
# Enums (3.9-compatible: str + Enum rather than 3.11 StrEnum)
# ---------------------------------------------------------------------------


class SessionKind(str, Enum):
    """How a session attaches its audio (inferred from which FK is set, §5.1)."""

    MEETING = "meeting"
    VOICE_MEMO = "voice-memo"
    SYSTEM_AUDIO = "system-audio"
    OTHER = "other"


class MediaType(str, Enum):
    """The `mediafile.type` enum (§7.2). Distinct from the filename token."""

    MEETING_MIC_AUDIO = "meetingMicAudio"
    MEETING_APP_AUDIO = "meetingAppAudio"
    MULTITRACK_ITEM = "multitrackItem"
    MERGED_MULTITRACK = "mergedMultitrack"
    ORIGINAL = "original"


class OwnerKind(str, Enum):
    """Which parent row a media file / new object hangs off of (§7.2)."""

    SESSION = "session"  # mediafile.sessionID set
    PARENT = "parent"  # mediafile.recordedMeetingID / voiceMemoID / systemAudioRecordingID


# `mediafile.type` -> default filename token (§7.2). `multitrackItem` is special
# (track-0 vs track-1) and so is not auto-derivable from type alone — callers
# must read the token off the existing filename for those.
MEDIA_TYPE_DEFAULT_TOKEN: dict[str, str] = {
    MediaType.MEETING_MIC_AUDIO.value: "mic-audio",
    MediaType.MEETING_APP_AUDIO.value: "app-audio",
    MediaType.MERGED_MULTITRACK.value: "merged-audio",
    MediaType.ORIGINAL.value: "voicememo",
}

# Media types whose owning FK is the recordedmeeting (raw meeting audio), with
# `sessionID` NULL (§7.3). Everything else with a sessionID hangs off the session.
PARENT_OWNED_MEETING_TYPES = frozenset(
    {MediaType.MEETING_MIC_AUDIO.value, MediaType.MEETING_APP_AUDIO.value}
)

DEFAULT_PLAYBACK_TYPE = "audioOnly"
DEFAULT_FILE_EXTENSION = "m4a"


# ---------------------------------------------------------------------------
# Source value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Speaker:
    """A global speaker row (§5.3). Reused across sessions by id."""

    id_hex: str
    name: str
    color: str | None
    is_stub: bool


@dataclass(frozen=True)
class TranscriptLine:
    """One transcript segment (§5.2). `start`/`end` are ms relative to session start."""

    id_hex: str
    start_ms: int
    end_ms: int
    text: str
    speaker_id_hex: str | None
    words_json: str | None
    is_favorite: bool


@dataclass(frozen=True)
class MediaFile:
    """A `mediafile` row (§5.5) plus its parsed filename token and resolved path."""

    id_hex: str
    filename: str
    type: str
    playback_type: str
    file_extension: str | None
    owner_kind: OwnerKind
    owner_id_hex: str
    path: Path

    @property
    def token(self) -> str:
        """Filename role token parsed from ``<UUID>_<token>_<8HEX>.<ext>`` (§7.1)."""
        return parse_filename_token(self.filename)


@dataclass(frozen=True)
class SessionRow:
    """A `session` row (§5.1). `raw` keeps every column for faithful cloning."""

    id_hex: str
    date_created: str | None
    user_chosen_title: str | None
    ai_title: str | None
    recorded_meeting_id_hex: str | None
    voice_memo_id_hex: str | None
    system_audio_recording_id_hex: str | None
    playback_duration: float | None
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class RecordedMeeting:
    """A `recordedmeeting` row (§5.6). Raw meeting audio attaches here, not the session."""

    id_hex: str
    title: str | None
    duration: float | None
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class VoiceMemo:
    """A `voicememos` row (§5.7) — the simplest single-track parent."""

    id_hex: str
    title: str | None
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class Bundle:
    """Everything needed to reconstruct one session, loaded read-only.

    `media_files` includes both session-owned tracks (track-0/track-1/merged)
    and parent-owned raw audio (mic/app) for meetings (§7.3).
    """

    session: SessionRow
    recorded_meeting: RecordedMeeting | None
    voice_memo: VoiceMemo | None
    media_files: tuple[MediaFile, ...]
    transcript_lines: tuple[TranscriptLine, ...]
    speakers: tuple[Speaker, ...]
    external_media_dir: Path

    @property
    def kind(self) -> SessionKind:
        if self.recorded_meeting is not None:
            return SessionKind.MEETING
        if self.voice_memo is not None:
            return SessionKind.VOICE_MEMO
        if self.session.system_audio_recording_id_hex is not None:
            return SessionKind.SYSTEM_AUDIO
        return SessionKind.OTHER

    @property
    def title(self) -> str:
        return (
            (self.session.user_chosen_title or "").strip()
            or (self.recorded_meeting.title if self.recorded_meeting else None)
            or (self.voice_memo.title if self.voice_memo else None)
            or (self.session.ai_title or "").strip()
            or "untitled"
        )

    def duration_ms(self) -> int | None:
        """Best-effort duration in ms: explicit duration, else last line end (§3.2)."""
        if self.session.playback_duration:
            return int(self.session.playback_duration * 1000)
        if self.recorded_meeting and self.recorded_meeting.duration:
            return int(self.recorded_meeting.duration * 1000)
        if self.transcript_lines:
            return max(line.end_ms for line in self.transcript_lines)
        return None

    def session_audio(self) -> tuple[MediaFile, ...]:
        return tuple(m for m in self.media_files if m.owner_kind == OwnerKind.SESSION)

    def parent_audio(self) -> tuple[MediaFile, ...]:
        return tuple(m for m in self.media_files if m.owner_kind == OwnerKind.PARENT)


# ---------------------------------------------------------------------------
# Target value types (no UUIDs; clone.py assigns them)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetLine:
    """A transcript line for a new session, already rebased to the new time base."""

    start_ms: int
    end_ms: int
    text: str
    speaker_id_hex: str | None
    words_json: str | None
    is_favorite: bool


@dataclass(frozen=True)
class AudioCut:
    """A single source-relative cut. `end_ms=None` means "to end of source"."""

    source_path: Path
    start_ms: int
    end_ms: int | None


@dataclass(frozen=True)
class TargetAudio:
    """How to produce one output track for a new session.

    A single cut is a trim; multiple cuts are concatenated in order (used by
    `combine`). `media_type`/`track_token`/`owner` reproduce the §7.2 mapping so
    `clone` can generate the correct filename and FK wiring.
    """

    media_type: str
    track_token: str
    owner: OwnerKind
    cuts: tuple[AudioCut, ...]
    playback_type: str = DEFAULT_PLAYBACK_TYPE
    file_extension: str = DEFAULT_FILE_EXTENSION


@dataclass(frozen=True)
class TargetBundle:
    """A complete description of a new session to materialize.

    `title`/`title_suffix` are kept separate so `clone` owns the suffixing rule
    (` - Split 1` etc., §clone bullet). `carried_session_fields` and
    `carried_parent_fields` hold extra source columns to preserve for fidelity;
    `clone` clears the identity/AI/text columns regardless.
    """

    kind: SessionKind
    title: str
    title_suffix: str
    date_created: str
    duration_ms: int | None
    lines: tuple[TargetLine, ...]
    speaker_ids: tuple[str, ...]
    audio: tuple[TargetAudio, ...]
    is_merged_from_multiple_tracks: bool
    source_session_id_hex: str
    carried_session_fields: Mapping[str, Any] = field(default_factory=dict)
    carried_parent_fields: Mapping[str, Any] = field(default_factory=dict)
    include_merged_multitrack: bool = True


# ---------------------------------------------------------------------------
# Filename parsing (§7.1)
# ---------------------------------------------------------------------------


def parse_filename_token(filename: str) -> str:
    """Extract `<token>` from ``<UUID>_<token>_<8HEX>.<ext>`` (§7.1).

    Canonical UUIDs use dashes (not underscores) and the 8-hex suffix has no
    underscores, so the token is everything between the first and last
    underscore. Returns "" if the filename does not match the grammar.
    """
    stem = filename.rsplit(".", 1)[0]
    parts = stem.split("_")
    if len(parts) < 3:
        return ""
    return "_".join(parts[1:-1])


# ---------------------------------------------------------------------------
# Bundle loader (read-only)
# ---------------------------------------------------------------------------


def _owner_for_media(row: Mapping[str, Any]) -> tuple[OwnerKind, str | None]:
    """Resolve which FK owns a media row and its hex id (§5.5: exactly one set)."""
    session_id = row.get("sessionID")
    if session_id is not None:
        return OwnerKind.SESSION, db.to_hex(session_id)
    for col in (
        "recordedMeetingID",
        "voiceMemoID",
        "systemAudioRecordingID",
        "podcastID",
        "dictationID",
    ):
        value = row.get(col)
        if value is not None:
            return OwnerKind.PARENT, db.to_hex(value)
    return OwnerKind.SESSION, None


def load_bundle(
    conn: sqlite3.Connection,
    session_id_hex: str,
    *,
    external_media_dir: Path,
) -> Bundle:
    """Load a full `Bundle` for `session_id_hex` from a read-only connection.

    Pulls the session row, its parent (`recordedmeeting`/`voicememos`), all
    linked `mediafile` rows (both session- and parent-owned), the transcript
    lines in order, and the participating speakers.

    Raises:
        WhisperEditError: If the session does not exist.
    """
    sid = db.hex_to_bytes(session_id_hex)
    session = _load_session_row(conn, sid)
    if session is None:
        raise db.WhisperEditError(f"session {session_id_hex} not found")

    recorded_meeting = None
    if session.recorded_meeting_id_hex:
        recorded_meeting = _load_recorded_meeting(
            conn, db.hex_to_bytes(session.recorded_meeting_id_hex)
        )
    voice_memo = None
    if session.voice_memo_id_hex:
        voice_memo = _load_voice_memo(
            conn, db.hex_to_bytes(session.voice_memo_id_hex)
        )

    media_files = _load_media_files(
        conn,
        session_hex=session.id_hex,
        recorded_meeting_hex=session.recorded_meeting_id_hex,
        voice_memo_hex=session.voice_memo_id_hex,
        system_audio_hex=session.system_audio_recording_id_hex,
        external_media_dir=external_media_dir,
    )
    transcript_lines = _load_transcript_lines(conn, sid)
    speakers = _load_speakers(conn, sid)

    return Bundle(
        session=session,
        recorded_meeting=recorded_meeting,
        voice_memo=voice_memo,
        media_files=media_files,
        transcript_lines=transcript_lines,
        speakers=speakers,
        external_media_dir=external_media_dir,
    )


def _load_session_row(conn: sqlite3.Connection, sid: bytes) -> SessionRow | None:
    cur = conn.execute("SELECT * FROM session WHERE id = ?", (sid,))
    row = cur.fetchone()
    if row is None:
        return None
    raw = dict(row)
    cols = set(raw.keys())
    duration_col = db.resolve_session_duration_column(cols)
    duration = raw.get(duration_col) if duration_col else None
    return SessionRow(
        id_hex=db.to_hex(raw["id"]),
        date_created=raw.get("dateCreated"),
        user_chosen_title=raw.get("userChosenTitle"),
        ai_title=raw.get("aiTitle"),
        recorded_meeting_id_hex=db.to_hex(raw.get("recordedMeetingID")),
        voice_memo_id_hex=db.to_hex(raw.get("voiceMemoID")),
        system_audio_recording_id_hex=db.to_hex(raw.get("systemAudioRecordingID")),
        playback_duration=float(duration) if duration is not None else None,
        raw=raw,
    )


def _load_recorded_meeting(conn: sqlite3.Connection, rid: bytes) -> RecordedMeeting | None:
    cur = conn.execute("SELECT * FROM recordedmeeting WHERE id = ?", (rid,))
    row = cur.fetchone()
    if row is None:
        return None
    raw = dict(row)
    duration = raw.get("duration")
    return RecordedMeeting(
        id_hex=db.to_hex(raw["id"]),
        title=raw.get("title"),
        duration=float(duration) if duration is not None else None,
        raw=raw,
    )


def _load_voice_memo(conn: sqlite3.Connection, vid: bytes) -> VoiceMemo | None:
    cur = conn.execute("SELECT * FROM voicememos WHERE id = ?", (vid,))
    row = cur.fetchone()
    if row is None:
        return None
    raw = dict(row)
    return VoiceMemo(id_hex=db.to_hex(raw["id"]), title=raw.get("title"), raw=raw)


def _load_media_files(
    conn: sqlite3.Connection,
    *,
    session_hex: str,
    recorded_meeting_hex: str | None,
    voice_memo_hex: str | None,
    system_audio_hex: str | None,
    external_media_dir: Path,
) -> tuple[MediaFile, ...]:
    clauses: list[str] = ["sessionID = ?"]
    params: list[bytes] = [db.hex_to_bytes(session_hex)]
    for col, value in (
        ("recordedMeetingID", recorded_meeting_hex),
        ("voiceMemoID", voice_memo_hex),
        ("systemAudioRecordingID", system_audio_hex),
    ):
        if value:
            clauses.append(f"{col} = ?")
            params.append(db.hex_to_bytes(value))
    sql = "SELECT * FROM mediafile WHERE " + " OR ".join(clauses)
    cur = conn.execute(sql, params)

    out: list[MediaFile] = []
    for row in cur.fetchall():
        raw = dict(row)
        owner_kind, owner_hex = _owner_for_media(raw)
        filename = raw["filename"]
        out.append(
            MediaFile(
                id_hex=db.to_hex(raw["id"]),
                filename=filename,
                type=raw["type"],
                playback_type=raw.get("playbackType") or DEFAULT_PLAYBACK_TYPE,
                file_extension=raw.get("fileExtension"),
                owner_kind=owner_kind,
                owner_id_hex=owner_hex or session_hex,
                path=external_media_dir / filename,
            )
        )
    out.sort(key=lambda m: m.filename)
    return tuple(out)


def _load_transcript_lines(conn: sqlite3.Connection, sid: bytes) -> tuple[TranscriptLine, ...]:
    cur = conn.execute(
        "SELECT id, start, end, text, speakerID, wordsJson, isFavorite "
        "FROM transcriptline WHERE sessionId = ? "
        "ORDER BY start ASC, dateCreated ASC",
        (sid,),
    )
    out: list[TranscriptLine] = []
    for row in cur.fetchall():
        out.append(
            TranscriptLine(
                id_hex=db.to_hex(row["id"]),
                start_ms=int(row["start"] or 0),
                end_ms=int(row["end"] or 0),
                text=(row["text"] or ""),
                speaker_id_hex=db.to_hex(row["speakerID"]),
                words_json=row["wordsJson"],
                is_favorite=bool(row["isFavorite"]),
            )
        )
    return tuple(out)


def _load_speakers(conn: sqlite3.Connection, sid: bytes) -> tuple[Speaker, ...]:
    cur = conn.execute(
        "SELECT id, name, color, isStub FROM speaker WHERE id IN "
        "(SELECT speakerID FROM session_speaker WHERE sessionID = ?)",
        (sid,),
    )
    out: list[Speaker] = []
    for row in cur.fetchall():
        out.append(
            Speaker(
                id_hex=db.to_hex(row["id"]),
                name=row["name"] or "",
                color=row["color"],
                is_stub=bool(row["isStub"]),
            )
        )
    out.sort(key=lambda s: s.name.lower())
    return tuple(out)


# ---------------------------------------------------------------------------
# wordsJson rebasing (per-word ms timings shift with the line, §5.2)
# ---------------------------------------------------------------------------


def shift_words_json(words_json: str | None, delta_ms: int) -> str | None:
    """Shift every per-word ``startTime``/``endTime`` by `delta_ms`.

    Returns None (dropping the word timings rather than corrupting them) if the
    payload is missing or not the expected ``[{"text","startTime","endTime"}]``
    shape. A zero delta passes the original payload through unchanged.
    """
    if not words_json:
        return None
    if delta_ms == 0:
        return words_json
    try:
        words = json.loads(words_json)
    except (ValueError, TypeError):
        return None
    if not isinstance(words, list):
        return None
    shifted: list[dict[str, Any]] = []
    for word in words:
        if not isinstance(word, dict):
            return None
        new_word = dict(word)
        for key in ("startTime", "endTime"):
            if key in new_word and isinstance(new_word[key], (int, float)):
                new_word[key] = new_word[key] + delta_ms
        shifted.append(new_word)
    return json.dumps(shifted, ensure_ascii=False, separators=(",", ":"))
