"""Shared test scaffolding: in-memory schema, seed data, and fakes.

Nothing here touches the live MacWhisper database or real audio. We build a
minimal SQLite schema mirroring `specs/macwhisper-database.md` (including the
`sessionFTS` external-content table + triggers when the SQLite build has FTS5),
seed a realistic meeting and voice memo, and provide deterministic fakes for
every injected boundary.

Run the suite with:

    python3 -m unittest discover -s agents/skills/lib/whisper_edit/tests -p '*_test.py'
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make `whisper_edit` importable no matter where the suite is launched from.
LIB_ROOT = Path(__file__).resolve().parents[2]
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from whisper_edit import db, media  # noqa: E402


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE recordedmeeting (
    id BLOB PRIMARY KEY NOT NULL,
    date DATETIME,
    title TEXT,
    bundleIdentifier TEXT NOT NULL,
    appName TEXT NOT NULL,
    matchedCalendarTitle TEXT,
    duration DOUBLE,
    dateCreated DATETIME,
    dateUpdated DATETIME,
    dateDeleted DOUBLE
);

CREATE TABLE voicememos (
    id BLOB PRIMARY KEY NOT NULL,
    dateCreated DATETIME,
    mediaFileID BLOB REFERENCES mediafile(id),
    title TEXT,
    dateDeleted DOUBLE
);

CREATE TABLE systemaudiorecording (
    id BLOB PRIMARY KEY NOT NULL,
    date DATETIME,
    title TEXT,
    bundleIdentifier TEXT,
    appName TEXT NOT NULL,
    duration DOUBLE,
    dateCreated DATETIME,
    dateUpdated DATETIME,
    dateDeleted DOUBLE
);

CREATE TABLE session (
    id BLOB PRIMARY KEY NOT NULL,
    dateCreated DATETIME NOT NULL,
    dateUpdated DATETIME,
    dateLastOpened DATETIME,
    dateRetranscribed DATETIME,
    textPreview TEXT,
    aiSummary TEXT,
    aiSummaryShort TEXT,
    fullText TEXT,
    userChosenTitle TEXT,
    aiTitle TEXT,
    transcriptionDidSucceed BOOLEAN,
    modelEngine TEXT,
    modelIdentifer TEXT,
    modelInputLanguage TEXT,
    detectedLanguage TEXT,
    hasBeenDiarized BOOLEAN,
    isMergedFromMultipleTracks BOOLEAN,
    isFromYoutube BOOLEAN,
    originalFilename TEXT,
    originalExtension TEXT,
    originalFileHash TEXT,
    startTimeOffset DOUBLE,
    wasTranslatedToEnglishDuringTranscription BOOLEAN,
    wasImportedFromWhisperFile BOOLEAN,
    timeTakenToTranscribe DOUBLE,
    playbackDuration DOUBLE,
    sourceAppBundleID TEXT,
    recordedMeetingID BLOB REFERENCES recordedmeeting(id),
    voiceMemoID BLOB REFERENCES voicememos(id),
    systemAudioRecordingID BLOB REFERENCES systemaudiorecording(id),
    podcastID BLOB,
    downloadMetadataID BLOB,
    isTransient BOOLEAN,
    isBeingRetranscribed BOOLEAN,
    importedFromDefaults BOOLEAN,
    dateDeleted DOUBLE
);

CREATE TABLE speaker (
    id BLOB PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    color TEXT,
    isStub BOOLEAN,
    photoData BLOB
);

CREATE TABLE session_speaker (
    sessionID BLOB NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    speakerID BLOB NOT NULL REFERENCES speaker(id) ON DELETE CASCADE,
    PRIMARY KEY (sessionID, speakerID)
);

CREATE TABLE mediafile (
    id BLOB PRIMARY KEY NOT NULL,
    filename TEXT NOT NULL,
    type TEXT NOT NULL,
    playbackType TEXT NOT NULL DEFAULT 'audioOnly',
    fileExtension TEXT,
    dateCreated DATETIME,
    sessionID BLOB REFERENCES session(id) ON DELETE CASCADE,
    recordedMeetingID BLOB REFERENCES recordedmeeting(id) ON DELETE CASCADE,
    voiceMemoID BLOB REFERENCES voicememos(id) ON DELETE CASCADE,
    systemAudioRecordingID BLOB REFERENCES systemaudiorecording(id) ON DELETE CASCADE,
    podcastID BLOB,
    dictationID BLOB,
    speakerID BLOB REFERENCES speaker(id)
);

CREATE TABLE transcriptline (
    id BLOB PRIMARY KEY NOT NULL,
    sessionId BLOB NOT NULL REFERENCES session(id) ON DELETE CASCADE ON UPDATE CASCADE,
    start INTEGER NOT NULL,
    end INTEGER NOT NULL,
    text TEXT NOT NULL,
    speakerID BLOB REFERENCES speaker(id),
    isFavorite BOOLEAN NOT NULL DEFAULT 0,
    wordsJson TEXT,
    dateCreated DATETIME,
    dateUpdated DATETIME
);
"""

FTS_SCHEMA = """
CREATE VIRTUAL TABLE sessionFTS USING fts5(
    id, fullText, aiSummary, userChosenTitle, content='session'
);
CREATE TRIGGER __sessionFTS_ai AFTER INSERT ON session BEGIN
    INSERT INTO sessionFTS(rowid, id, fullText, aiSummary, userChosenTitle)
    VALUES (new.rowid, new.id, new.fullText, new.aiSummary, new.userChosenTitle);
END;
CREATE TRIGGER __sessionFTS_ad AFTER DELETE ON session BEGIN
    INSERT INTO sessionFTS(sessionFTS, rowid, id, fullText, aiSummary, userChosenTitle)
    VALUES ('delete', old.rowid, old.id, old.fullText, old.aiSummary, old.userChosenTitle);
END;
CREATE TRIGGER __sessionFTS_au AFTER UPDATE ON session BEGIN
    INSERT INTO sessionFTS(sessionFTS, rowid, id, fullText, aiSummary, userChosenTitle)
    VALUES ('delete', old.rowid, old.id, old.fullText, old.aiSummary, old.userChosenTitle);
    INSERT INTO sessionFTS(rowid, id, fullText, aiSummary, userChosenTitle)
    VALUES (new.rowid, new.id, new.fullText, new.aiSummary, new.userChosenTitle);
END;
"""


def has_fts5() -> bool:
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE _t USING fts5(x)")
        conn.close()
        return True
    except sqlite3.OperationalError:
        return False


def build_schema(conn: sqlite3.Connection, *, with_fts: bool = True) -> None:
    conn.executescript(SCHEMA)
    if with_fts and has_fts5():
        conn.executescript(FTS_SCHEMA)
    conn.commit()


def make_db_file(path: Path, *, with_fts: bool = True) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON")
    build_schema(conn, with_fts=with_fts)
    conn.close()


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FixedClock:
    """Deterministic `Clock`."""

    def __init__(self, dt: datetime | None = None) -> None:
        self._dt = dt or datetime(2026, 5, 30, 17, 0, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._dt


class FakeProcessChecker:
    """`ProcessChecker` that reports a fixed liveness."""

    def __init__(self, running: bool) -> None:
        self._running = running

    def is_macwhisper_running(self) -> bool:
        return self._running


class FixedHexSuffix:
    """`HexSuffixStrategy` returning a counter so filenames are unique + stable."""

    def __init__(self, start: int = 0) -> None:
        self._n = start

    def derive(self, *, source_path=None, output_path=None) -> str:
        value = f"{self._n:08X}"
        self._n += 1
        return value


class FakeMediaTool:
    """`MediaTool` that writes dummy files and returns a fixed probed duration."""

    def __init__(self, duration_ms: int = 5000) -> None:
        self.duration_ms = duration_ms
        self.cut_calls: list[tuple] = []
        self.concat_calls: list[tuple] = []

    def probe_duration_ms(self, path: Path) -> int:
        return self.duration_ms

    def cut(self, src: Path, dst: Path, start_ms: int, end_ms) -> None:
        self.cut_calls.append((str(src), str(dst), start_ms, end_ms))
        Path(dst).write_bytes(b"FAKEAUDIO")

    def concat(self, srcs, dst: Path) -> None:
        self.concat_calls.append(([str(s) for s in srcs], str(dst)))
        Path(dst).write_bytes(b"FAKEAUDIO" * len(list(srcs)))


def sequential_uuid_factory(start: int = 1):
    """Return a `uuid_factory` yielding deterministic, distinct 16-byte ids."""
    state = {"n": start}

    def factory() -> bytes:
        value = state["n"]
        state["n"] += 1
        return value.to_bytes(16, "big")

    return factory


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------


def _write_dummy(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"SOURCEAUDIO")


def _media_filename(owner_hex: str, token: str, suffix: str) -> str:
    return media.make_media_filename(db.hex_to_canonical_uuid(owner_hex), token, suffix)


def seed_meeting(
    conn: sqlite3.Connection, external_media_dir: Path, *, title: str = "Weekly Sync"
) -> str:
    """Seed one meeting session (5 media files, 6 lines with a 60s gap).

    Returns the session id hex. Creates dummy `ExternalMedia` files on disk.
    """
    rm_id = db.new_uuid_bytes()
    s_id = db.new_uuid_bytes()
    sp1 = db.new_uuid_bytes()
    sp2 = db.new_uuid_bytes()
    rm_hex = rm_id.hex()
    s_hex = s_id.hex()

    conn.execute(
        "INSERT INTO recordedmeeting (id, date, title, bundleIdentifier, appName, "
        "matchedCalendarTitle, duration, dateCreated, dateUpdated, dateDeleted) "
        "VALUES (?,?,?,?,?,?,?,?,?,NULL)",
        (rm_id, "2026-05-30 16:00:00.000", title, "com.google.Chrome", "Chrome",
         "Weekly Sync", 180.0, "2026-05-30 16:00:00.000", "2026-05-30 16:03:00.000"),
    )
    conn.execute(
        "INSERT INTO session (id, dateCreated, dateUpdated, textPreview, aiSummary, "
        "fullText, userChosenTitle, aiTitle, transcriptionDidSucceed, modelEngine, "
        "modelIdentifer, isMergedFromMultipleTracks, startTimeOffset, playbackDuration, "
        "recordedMeetingID, dateDeleted) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)",
        (s_id, "2026-05-30 16:00:00.000", "2026-05-30 16:03:00.000", "old preview",
         "old ai summary", "old full text", title, "AI Weekly", 1, "parakeetKitPro",
         "nvidia_parakeet-v3", 1, 0.0, 180.0, rm_id),
    )
    conn.execute("INSERT INTO speaker (id, name, color, isStub) VALUES (?,?,?,0)",
                 (sp1, "Gary", "67B9AA"))
    conn.execute("INSERT INTO speaker (id, name, color, isStub) VALUES (?,?,?,1)",
                 (sp2, "Speaker 1", "AA5577"))
    conn.executemany(
        "INSERT INTO session_speaker (sessionID, speakerID) VALUES (?,?)",
        [(s_id, sp1), (s_id, sp2)],
    )

    media_rows = [
        (s_id, "sessionID", "track-0", "multitrackItem"),
        (s_id, "sessionID", "track-1", "multitrackItem"),
        (s_id, "sessionID", "merged-audio", "mergedMultitrack"),
        (rm_id, "recordedMeetingID", "mic-audio", "meetingMicAudio"),
        (rm_id, "recordedMeetingID", "app-audio", "meetingAppAudio"),
    ]
    for i, (owner_id, owner_col, token, mtype) in enumerate(media_rows):
        owner_hex = owner_id.hex()
        fname = _media_filename(owner_hex, token, f"{i:08X}")
        _write_dummy(external_media_dir / fname)
        session_fk = owner_id if owner_col == "sessionID" else None
        rm_fk = owner_id if owner_col == "recordedMeetingID" else None
        conn.execute(
            "INSERT INTO mediafile (id, filename, type, playbackType, fileExtension, "
            "dateCreated, sessionID, recordedMeetingID) VALUES (?,?,?,?,?,?,?,?)",
            (db.new_uuid_bytes(), fname, mtype, "audioOnly", "m4a",
             "2026-05-30 16:00:00.000", session_fk, rm_fk),
        )

    # 6 lines. A 60s silence gap sits between 60000 and 120000 (so the silence
    # candidate is 120000ms). The new persistent speaker sp2 first appears later,
    # at 130000ms, so the speaker-onset candidate is a *distinct* point.
    words = '[{"text":"hello","startTime":0,"endTime":500}]'
    lines = [
        (0, 5000, "Morning everyone.", sp1, words),
        (5000, 30000, "Let us start the weekly sync.", sp1, None),
        (30000, 60000, "First topic is the release.", sp1, None),
        (120000, 130000, "Back from the break, continuing.", sp1, None),
        (130000, 150000, "Sorry I am late, what did I miss?", sp2, None),
        (150000, 178000, "We were on the release, all good.", sp2, None),
    ]
    for start, end, text, spk, wj in lines:
        conn.execute(
            "INSERT INTO transcriptline (id, sessionId, start, end, text, speakerID, "
            "isFavorite, wordsJson, dateCreated) VALUES (?,?,?,?,?,?,?,?,?)",
            (db.new_uuid_bytes(), s_id, start, end, text, spk, 0, wj,
             "2026-05-30 16:00:00.000"),
        )
    conn.commit()
    return s_hex


def seed_voice_memo(
    conn: sqlite3.Connection, external_media_dir: Path, *, title: str = "Idea memo"
) -> str:
    """Seed one single-track voice memo. Returns the session id hex."""
    vm_id = db.new_uuid_bytes()
    s_id = db.new_uuid_bytes()
    mf_id = db.new_uuid_bytes()
    sp1 = db.new_uuid_bytes()

    # FK-safe order for the circular voicememos<->mediafile link: insert the
    # parent with a NULL mediaFileID, then the media row, then back-fill the link.
    conn.execute(
        "INSERT INTO voicememos (id, dateCreated, mediaFileID, title, dateDeleted) "
        "VALUES (?,?,NULL,?,NULL)",
        (vm_id, "2026-05-30 09:00:00.000", title),
    )
    conn.execute(
        "INSERT INTO session (id, dateCreated, userChosenTitle, transcriptionDidSucceed, "
        "modelEngine, playbackDuration, voiceMemoID, dateDeleted) "
        "VALUES (?,?,?,?,?,?,?,NULL)",
        (s_id, "2026-05-30 09:00:00.000", title, 1, "parakeetKitPro", 40.0, vm_id),
    )
    conn.execute("INSERT INTO speaker (id, name, color, isStub) VALUES (?,?,?,0)",
                 (sp1, "Gary", "67B9AA"))
    conn.execute("INSERT INTO session_speaker (sessionID, speakerID) VALUES (?,?)",
                 (s_id, sp1))
    fname = _media_filename(vm_id.hex(), "voicememo", "0000ABCD")
    _write_dummy(external_media_dir / fname)
    conn.execute(
        "INSERT INTO mediafile (id, filename, type, playbackType, fileExtension, "
        "dateCreated, voiceMemoID) VALUES (?,?,?,?,?,?,?)",
        (mf_id, fname, "original", "audioOnly", "m4a", "2026-05-30 09:00:00.000", vm_id),
    )
    conn.execute("UPDATE voicememos SET mediaFileID = ? WHERE id = ?", (mf_id, vm_id))
    lines = [
        (0, 10000, "Idea about the split tool.", sp1),
        (10000, 20000, "It should reconstruct all tracks.", sp1),
        (20000, 38000, "And never delete the source.", sp1),
    ]
    for start, end, text, spk in lines:
        conn.execute(
            "INSERT INTO transcriptline (id, sessionId, start, end, text, speakerID, "
            "isFavorite, dateCreated) VALUES (?,?,?,?,?,?,?,?)",
            (db.new_uuid_bytes(), s_id, start, end, text, spk, 0, "2026-05-30 09:00:00.000"),
        )
    conn.commit()
    return s_id.hex()
