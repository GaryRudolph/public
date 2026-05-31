"""Materialize a `TargetBundle` into concrete MacWhisper rows + audio files.

This is the write core. It is split into a **pure** planning phase and an
**IO** apply phase so a plan can be assembled, serialized, shown, and approved
before anything is mutated:

- `plan_clone(target, ...)` assigns new BLOB UUIDs, generates filenames,
  rebases/normalizes transcript lines, recomputes `fullText`/`textPreview`,
  clears the stale AI columns, applies the title suffix, and produces a
  fully-resolved, JSON-serializable `ClonePlan`. No database, no filesystem.
- `apply_clone(conn, plan, ...)` inserts the rows in FK-safe order (parent ->
  session -> media -> speakers -> lines) and moves the staged audio into
  `ExternalMedia/`, all inside one transaction with best-effort file cleanup on
  failure.

Two unverified assumptions from `specs/macwhisper-database.md` §10 are isolated
so they can be validated against a backup later without disturbing this logic:

- the **8-hex filename suffix** is produced by an injected `HexSuffixStrategy`
  (default random; §10.1), and
- whether the **`mergedMultitrack`** track is emitted at all is controlled by
  `TargetBundle.include_merged_multitrack` upstream (§10.2).

FTS stays correct for free: a plain ``INSERT INTO session`` fires
`__sessionFTS_ai`, so populating `fullText`/`textPreview` is all that is needed —
the `sessionFTS_*` shadow tables are never touched (§6).
"""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import db, media
from .model import (
    MediaType,
    OwnerKind,
    SessionKind,
    TargetBundle,
)

UuidFactory = Callable[[], bytes]

TEXT_PREVIEW_LIMIT = 280

# Columns the engine sets explicitly (everything else is carried from source for
# full fidelity, §full-fidelity goal). Carried values that are BLOBs are never
# propagated — identity/FK columns are always assigned here.
_MANAGED_SESSION = frozenset({
    "id", "dateCreated", "dateUpdated", "dateLastOpened", "dateRetranscribed",
    "fullText", "textPreview", "aiSummary", "aiSummaryShort", "aiTitle",
    "userChosenTitle", "playbackDuration", "duration", "isMergedFromMultipleTracks",
    "recordedMeetingID", "voiceMemoID", "systemAudioRecordingID", "podcastID",
    "downloadMetadataID", "dateDeleted", "isTransient", "isBeingRetranscribed",
})
_MANAGED_RECORDEDMEETING = frozenset({
    "id", "date", "title", "duration", "dateCreated", "dateUpdated", "dateDeleted",
})
_MANAGED_VOICEMEMO = frozenset({"id", "dateCreated", "mediaFileID", "title", "dateDeleted"})
_MANAGED_SYSTEMAUDIO = frozenset({
    "id", "date", "title", "duration", "dateCreated", "dateUpdated", "dateDeleted",
})

_SESSION_BLOB = frozenset({
    "id", "recordedMeetingID", "voiceMemoID", "systemAudioRecordingID",
    "podcastID", "downloadMetadataID",
})
_RECORDEDMEETING_BLOB = frozenset({"id"})
_VOICEMEMO_BLOB = frozenset({"id", "mediaFileID"})
_SYSTEMAUDIO_BLOB = frozenset({"id"})
_MEDIAFILE_BLOB = frozenset({
    "id", "sessionID", "recordedMeetingID", "voiceMemoID", "systemAudioRecordingID",
    "podcastID", "dictationID", "speakerID",
})
_TRANSCRIPTLINE_BLOB = frozenset({"id", "sessionId", "speakerID"})
_SESSION_SPEAKER_BLOB = frozenset({"sessionID", "speakerID"})

_PARENT_BLOB = {
    "recordedmeeting": _RECORDEDMEETING_BLOB,
    "voicememos": _VOICEMEMO_BLOB,
    "systemaudiorecording": _SYSTEMAUDIO_BLOB,
}

# Which session FK column points at the parent, per kind.
_PARENT_FK_COLUMN = {
    SessionKind.MEETING: "recordedMeetingID",
    SessionKind.VOICE_MEMO: "voiceMemoID",
    SessionKind.SYSTEM_AUDIO: "systemAudioRecordingID",
}
_PARENT_TABLE = {
    SessionKind.MEETING: "recordedmeeting",
    SessionKind.VOICE_MEMO: "voicememos",
    SessionKind.SYSTEM_AUDIO: "systemaudiorecording",
}


# ---------------------------------------------------------------------------
# Plan value types (immutable, JSON-serializable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MediaPlan:
    """One `mediafile` row + the staged audio it will be backed by."""

    id_hex: str
    owner_column: str
    owner_id_hex: str
    filename: str
    media_type: str
    playback_type: str
    file_extension: str
    staged_source: str
    expected_duration_ms: int


@dataclass(frozen=True)
class LinePlan:
    """One `transcriptline` row for the new session (already rebased)."""

    id_hex: str
    start_ms: int
    end_ms: int
    text: str
    speaker_id_hex: str | None
    words_json: str | None
    is_favorite: bool


@dataclass(frozen=True)
class ClonePlan:
    """A fully-resolved, write-ready plan for one new session. No IO performed."""

    kind: str
    source_session_id_hex: str
    new_session_id_hex: str
    final_title: str
    created_at: str
    parent_table: str | None
    parent_id_hex: str | None
    session_row: Mapping[str, Any]
    parent_row: Mapping[str, Any] | None
    media: tuple[MediaPlan, ...]
    speaker_links: tuple[str, ...]
    lines: tuple[LinePlan, ...]
    voice_memo_media_id_hex: str | None
    full_text: str
    text_preview: str
    expected_duration_ms: int | None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "source_session_id_hex": self.source_session_id_hex,
            "new_session_id_hex": self.new_session_id_hex,
            "final_title": self.final_title,
            "created_at": self.created_at,
            "parent_table": self.parent_table,
            "parent_id_hex": self.parent_id_hex,
            "session_row": dict(self.session_row),
            "parent_row": dict(self.parent_row) if self.parent_row else None,
            "media": [vars(m) for m in self.media],
            "speaker_links": list(self.speaker_links),
            "lines": [vars(l) for l in self.lines],
            "voice_memo_media_id_hex": self.voice_memo_media_id_hex,
            "full_text": self.full_text,
            "text_preview": self.text_preview,
            "expected_duration_ms": self.expected_duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ClonePlan":
        return cls(
            kind=data["kind"],
            source_session_id_hex=data["source_session_id_hex"],
            new_session_id_hex=data["new_session_id_hex"],
            final_title=data["final_title"],
            created_at=data["created_at"],
            parent_table=data.get("parent_table"),
            parent_id_hex=data.get("parent_id_hex"),
            session_row=dict(data["session_row"]),
            parent_row=dict(data["parent_row"]) if data.get("parent_row") else None,
            media=tuple(MediaPlan(**m) for m in data.get("media", [])),
            speaker_links=tuple(data.get("speaker_links", [])),
            lines=tuple(LinePlan(**l) for l in data.get("lines", [])),
            voice_memo_media_id_hex=data.get("voice_memo_media_id_hex"),
            full_text=data.get("full_text", ""),
            text_preview=data.get("text_preview", ""),
            expected_duration_ms=data.get("expected_duration_ms"),
        )


@dataclass(frozen=True)
class CloneResult:
    """Outcome of `apply_clone`."""

    new_session_id_hex: str
    parent_id_hex: str | None
    inserted_lines: int
    inserted_media: int
    inserted_speaker_links: int
    written_files: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Planning (pure)
# ---------------------------------------------------------------------------


def plan_clone(
    target: TargetBundle,
    *,
    staged_audio: Sequence["media.StagedAudio"],
    uuid_factory: UuidFactory = db.new_uuid_bytes,
    hex_suffix: media.HexSuffixStrategy | None = None,
    clock: db.Clock | None = None,
) -> ClonePlan:
    """Resolve `target` into a write-ready `ClonePlan` (no IO).

    Args:
        target: The new session description from `split`/`combine`.
        staged_audio: One `StagedAudio` per `target.audio`, in the same order
            (produced by `media.stage_target_audio`). Provides the probed
            duration and the temp path each track will be moved from.
        uuid_factory: Injected UUID source (deterministic in tests).
        hex_suffix: Injected 8-hex filename-suffix strategy (§10.1; default random).
        clock: Injected clock for `dateCreated`/`dateUpdated` (§3.2).

    Raises:
        ValueError: If `staged_audio` length does not match `target.audio`.
    """
    if len(staged_audio) != len(target.audio):
        raise ValueError(
            f"staged_audio count {len(staged_audio)} != target.audio count {len(target.audio)}"
        )
    clock = clock or db.SystemClock()
    suffix_strategy = hex_suffix or media.RandomHexSuffix()
    kind = SessionKind(target.kind)
    now = db.format_db_datetime(clock.now())

    new_session_hex = db.to_hex(uuid_factory())
    final_title = (target.title + target.title_suffix).strip()
    full_text = "\n".join(l.text.strip() for l in target.lines if l.text.strip())
    text_preview = full_text.replace("\n", " ").strip()[:TEXT_PREVIEW_LIMIT]

    duration_ms = _resolve_duration_ms(target, staged_audio)
    duration_sec = (duration_ms / 1000.0) if duration_ms is not None else None

    parent_table = _PARENT_TABLE.get(kind)
    parent_hex: str | None = None
    parent_row: dict[str, Any] | None = None
    if parent_table is not None:
        parent_hex = db.to_hex(uuid_factory())
        parent_row = _build_parent_row(kind, parent_hex, target, final_title, duration_sec, now)

    session_row = _build_session_row(
        target, kind, new_session_hex, parent_hex, final_title, full_text,
        text_preview, duration_sec, now,
    )

    media_plans, voice_memo_media_hex = _build_media_plans(
        target, kind, new_session_hex, parent_hex, staged_audio, suffix_strategy,
    )

    lines = tuple(
        LinePlan(
            id_hex=db.to_hex(uuid_factory()),
            start_ms=max(0, l.start_ms),
            end_ms=max(0, l.end_ms),
            text=l.text,
            speaker_id_hex=l.speaker_id_hex,
            words_json=l.words_json,
            is_favorite=l.is_favorite,
        )
        for l in target.lines
    )

    return ClonePlan(
        kind=kind.value,
        source_session_id_hex=target.source_session_id_hex,
        new_session_id_hex=new_session_hex,
        final_title=final_title,
        created_at=now,
        parent_table=parent_table,
        parent_id_hex=parent_hex,
        session_row=session_row,
        parent_row=parent_row,
        media=media_plans,
        speaker_links=tuple(target.speaker_ids),
        lines=lines,
        voice_memo_media_id_hex=voice_memo_media_hex,
        full_text=full_text,
        text_preview=text_preview,
        expected_duration_ms=duration_ms,
    )


def _resolve_duration_ms(
    target: TargetBundle, staged_audio: Sequence["media.StagedAudio"]
) -> int | None:
    if staged_audio:
        return max(s.duration_ms for s in staged_audio)
    return target.duration_ms


def _build_session_row(
    target: TargetBundle,
    kind: SessionKind,
    session_hex: str,
    parent_hex: str | None,
    final_title: str,
    full_text: str,
    text_preview: str,
    duration_sec: float | None,
    now: str,
) -> dict[str, Any]:
    carried = _carry(target.carried_session_fields, _MANAGED_SESSION)
    managed: dict[str, Any] = {
        "id": session_hex,
        "dateCreated": target.date_created or now,
        "dateUpdated": now,
        "dateLastOpened": now,
        "dateRetranscribed": None,
        "fullText": full_text,
        "textPreview": text_preview,
        "aiSummary": None,
        "aiSummaryShort": None,
        "aiTitle": None,
        "userChosenTitle": final_title,
        "playbackDuration": duration_sec,
        "isMergedFromMultipleTracks": 1 if target.is_merged_from_multiple_tracks else 0,
        "recordedMeetingID": parent_hex if kind == SessionKind.MEETING else None,
        "voiceMemoID": parent_hex if kind == SessionKind.VOICE_MEMO else None,
        "systemAudioRecordingID": parent_hex if kind == SessionKind.SYSTEM_AUDIO else None,
        "podcastID": None,
        "downloadMetadataID": None,
        "dateDeleted": None,
        "isTransient": 0,
        "isBeingRetranscribed": 0,
    }
    return {**carried, **managed}


def _build_parent_row(
    kind: SessionKind,
    parent_hex: str,
    target: TargetBundle,
    final_title: str,
    duration_sec: float | None,
    now: str,
) -> dict[str, Any]:
    src = target.carried_parent_fields
    if kind == SessionKind.MEETING:
        carried = _carry(src, _MANAGED_RECORDEDMEETING)
        managed = {
            "id": parent_hex,
            "date": src.get("date") or now,
            "title": final_title,
            "duration": duration_sec,
            "dateCreated": now,
            "dateUpdated": now,
            "dateDeleted": None,
        }
        return {**carried, **managed}
    if kind == SessionKind.VOICE_MEMO:
        carried = _carry(src, _MANAGED_VOICEMEMO)
        managed = {
            "id": parent_hex,
            "dateCreated": now,
            "mediaFileID": None,  # wired up after the media row is inserted
            "title": final_title,
            "dateDeleted": None,
        }
        return {**carried, **managed}
    # system audio
    carried = _carry(src, _MANAGED_SYSTEMAUDIO)
    managed = {
        "id": parent_hex,
        "date": src.get("date") or now,
        "title": final_title,
        "duration": duration_sec,
        "dateCreated": now,
        "dateUpdated": now,
        "dateDeleted": None,
    }
    return {**carried, **managed}


def _build_media_plans(
    target: TargetBundle,
    kind: SessionKind,
    session_hex: str,
    parent_hex: str | None,
    staged_audio: Sequence["media.StagedAudio"],
    suffix_strategy: media.HexSuffixStrategy,
) -> tuple[tuple[MediaPlan, ...], str | None]:
    parent_fk_column = _PARENT_FK_COLUMN.get(kind, "sessionID")
    session_canonical = db.hex_to_canonical_uuid(session_hex)
    parent_canonical = db.hex_to_canonical_uuid(parent_hex) if parent_hex else session_canonical

    media_plans: list[MediaPlan] = []
    voice_memo_media_hex: str | None = None
    for target_audio, staged in zip(target.audio, staged_audio):
        media_hex = db.to_hex(db.new_uuid_bytes())
        if target_audio.owner == OwnerKind.SESSION:
            owner_column = "sessionID"
            owner_hex = session_hex
            prefix = session_canonical
        else:
            owner_column = parent_fk_column
            owner_hex = parent_hex or session_hex
            prefix = parent_canonical
        suffix = suffix_strategy.derive(
            source_path=staged.path, output_path=staged.path
        )
        filename = media.make_media_filename(
            prefix, target_audio.track_token, suffix, target_audio.file_extension
        )
        media_plans.append(
            MediaPlan(
                id_hex=media_hex,
                owner_column=owner_column,
                owner_id_hex=owner_hex,
                filename=filename,
                media_type=target_audio.media_type,
                playback_type=target_audio.playback_type,
                file_extension=target_audio.file_extension,
                staged_source=str(staged.path),
                expected_duration_ms=staged.duration_ms,
            )
        )
        if (
            kind == SessionKind.VOICE_MEMO
            and target_audio.media_type == MediaType.ORIGINAL.value
            and target_audio.owner == OwnerKind.PARENT
        ):
            voice_memo_media_hex = media_hex
    return tuple(media_plans), voice_memo_media_hex


def _carry(source: Mapping[str, Any], managed: frozenset) -> dict[str, Any]:
    """Carry forward source columns that aren't managed and aren't BLOBs.

    Dropping BLOB-valued columns guarantees no stale id/FK leaks into the new
    row; identity is always assigned explicitly by the managed map.
    """
    return {
        k: v
        for k, v in source.items()
        if k not in managed and not isinstance(v, (bytes, bytearray))
    }


# ---------------------------------------------------------------------------
# Apply (IO)
# ---------------------------------------------------------------------------


def apply_clone(
    conn: sqlite3.Connection,
    plan: ClonePlan,
    *,
    external_media_dir: Path,
    mover: Callable[[str, str], object] = shutil.move,
) -> CloneResult:
    """Insert `plan`'s rows and move its staged audio into `ExternalMedia/`.

    Insert order respects FK direction (§9): parent -> session -> session_speaker
    -> mediafile -> transcriptline, then the voice-memo `mediaFileID` back-link.
    Everything runs in one transaction; on any failure the transaction is rolled
    back and any already-moved audio files are removed (best effort). The caller
    is expected to have taken a backup first (`engine.apply` enforces this).
    """
    moved: list[Path] = []
    try:
        conn.execute("BEGIN")
        if plan.parent_table and plan.parent_row is not None:
            _insert(conn, plan.parent_table, plan.parent_row, _PARENT_BLOB[plan.parent_table])

        _insert(conn, "session", plan.session_row, _SESSION_BLOB)

        link_count = 0
        for speaker_hex in plan.speaker_links:
            _insert(
                conn,
                "session_speaker",
                {"sessionID": plan.new_session_id_hex, "speakerID": speaker_hex},
                _SESSION_SPEAKER_BLOB,
            )
            link_count += 1

        for m in plan.media:
            row = {
                "id": m.id_hex,
                "filename": m.filename,
                "type": m.media_type,
                "playbackType": m.playback_type,
                "fileExtension": m.file_extension,
                "dateCreated": plan.created_at,
                m.owner_column: m.owner_id_hex,
            }
            _insert(conn, "mediafile", row, _MEDIAFILE_BLOB)

        for line in plan.lines:
            row = {
                "id": line.id_hex,
                "sessionId": plan.new_session_id_hex,
                "start": line.start_ms,
                "end": line.end_ms,
                "text": line.text,
                "speakerID": line.speaker_id_hex,
                "wordsJson": line.words_json,
                "isFavorite": 1 if line.is_favorite else 0,
                "dateCreated": plan.created_at,
                "dateUpdated": plan.created_at,
            }
            _insert(conn, "transcriptline", row, _TRANSCRIPTLINE_BLOB)

        if plan.voice_memo_media_id_hex and plan.parent_table == "voicememos" and plan.parent_id_hex:
            conn.execute(
                "UPDATE voicememos SET mediaFileID = ? WHERE id = ?",
                (
                    db.hex_to_bytes(plan.voice_memo_media_id_hex),
                    db.hex_to_bytes(plan.parent_id_hex),
                ),
            )

        for m in plan.media:
            dest = media.move_into_external_media(
                Path(m.staged_source), external_media_dir, m.filename, mover=mover
            )
            moved.append(dest)

        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        for dest in moved:
            try:
                Path(dest).unlink()
            except OSError:
                pass
        raise

    return CloneResult(
        new_session_id_hex=plan.new_session_id_hex,
        parent_id_hex=plan.parent_id_hex,
        inserted_lines=len(plan.lines),
        inserted_media=len(plan.media),
        inserted_speaker_links=len(plan.speaker_links),
        written_files=tuple(str(p) for p in moved),
    )


def _insert(
    conn: sqlite3.Connection,
    table: str,
    row: Mapping[str, Any],
    blob_columns: frozenset,
) -> None:
    materialized: dict[str, Any] = {}
    for key, value in row.items():
        if key in blob_columns and isinstance(value, str):
            materialized[key] = db.hex_to_bytes(value)
        else:
            materialized[key] = value
    filtered = db.insertable_columns(conn, table, materialized)
    if not filtered:
        return
    sql, params = db.build_insert(table, filtered)
    conn.execute(sql, params)
