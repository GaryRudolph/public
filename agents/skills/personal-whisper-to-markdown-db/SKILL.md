---
name: personal-whisper-to-markdown-db
description: >-
  Convert MacWhisper recordings into organized, dated Markdown notes by reading
  MacWhisper's local SQLite database directly (no .whisper export required).
  Same output format as personal-whisper-to-markdown but sourced from the live
  DB so speaker renames, speaker curation, and transcript edits picked up
  immediately. Use this skill whenever the user asks to sync, process, or
  re-process MacWhisper recordings from the database, monitor MacWhisper for
  changes, or pick up speaker-name edits without re-exporting .whisper files.
  Re-runs are safe and incremental.
---

# Whisper to Markdown — DB source

Read [`../personal-whisper-to-markdown/SPEC.md`](../personal-whisper-to-markdown/SPEC.md)
for all canonical behavior: folder layout, canonical recording structure,
content hash, what-to-process decision tree, historical equivalents, title/slug
rules, output template, tag vocabulary, and reporting format. This file adds
DB-source specifics only.

For Cowork install (workspace, file access, prompts, scheduling), see
[`./COWORK.md`](./COWORK.md).

## Source: MacWhisper SQLite

MacWhisper stores all live state in a single SQLite database at:

```
~/Library/Application Support/MacWhisper/Database/main.sqlite
```

Companion files `main.sqlite-shm` and `main.sqlite-wal` are SQLite WAL-mode
sidecars — leave them alone; SQLite will read them transparently.

**Open the DB read-only.** Use `sqlite3` with the read-only mode (`-readonly`
flag, or the URI form `file:...?mode=ro`) or, in Python, `sqlite3.connect("file:...?mode=ro", uri=True)`.
Never open it read-write — that risks corrupting MacWhisper's state if the app
is running concurrently.

If MacWhisper is currently running, the WAL may contain uncommitted writes that
are visible to a read-only connection — that's fine and expected. If a query
fails with a lock error, wait briefly and retry; do not pass `IMMEDIATE` or any
write transaction.

The `source:` frontmatter value is `macwhisper-db:<recording-id-hex>` (e.g.
`macwhisper-db:d9393ef207004356bd779b90e2336a82`). The `source_type:` value is
`db`.

## Workspace root

Like the file skill, this skill writes notes under `<workspace root>/YYYY/MM/`.
The user points the agent at a notes workspace (e.g. `~/Projects/personal/notes/`);
the DB is read from the fixed Library path above regardless of cwd.

## Schema overview

Relevant tables (full schema lives in the DB itself — query `sqlite_master` if
unsure):

| Table | Purpose |
|---|---|
| `session` | One row per recording. UUID `id` (BLOB), `dateCreated`, titles, model, deletion flag. |
| `transcriptline` | Per-segment transcript. `sessionId` FK, `start`/`end` in ms, `text`, `speakerID` FK. |
| `speaker` | Speaker definitions. `id` (BLOB), `name`, `isStub` (1 = "Speaker N" placeholder). |
| `session_speaker` | Many-to-many: which speakers appear in which session. |
| `recordedmeeting` | Metadata for sessions linked via `session.recordedMeetingID` (title, calendar match, app/browser). |
| `voicememos` | Metadata for sessions linked via `session.voiceMemoID`. |
| `tag`, `session_tag` | MacWhisper's built-in tag system. Pull as supplementary tag input. |

**ID format.** All `id` columns are BLOB UUIDs. Convert to a stable hex string
via `lower(hex(id))` in SQL or `id.hex()` in Python. Use the lowercase hex
form (32 chars, no dashes) in the `source:` frontmatter field.

**Soft-delete.** Filter every query by `dateDeleted IS NULL` on `session`,
`voicememos`, `recordedmeeting`, etc. Trashed recordings should be ignored
(never deleted on disk by this skill — that's MacWhisper's job).

## Building the canonical recording

For each non-deleted session, build the canonical dict required by `SPEC.md`:

```sql
-- 1. Pick sessions to process
SELECT lower(hex(s.id))            AS session_id,   -- goes into source: only, not canonical
       s.dateCreated               AS date,         -- "YYYY-MM-DD HH:MM:SS.fff" UTC
       s.userChosenTitle           AS user_title,
       s.aiTitle                   AS ai_title,
       s.originalFilename          AS original_filename,
       s.modelEngine               AS model_engine,
       s.modelIdentifer            AS model_identifier,  -- note: typo in schema
       s.playbackDuration          AS duration_sec,
       s.hasBeenDiarized           AS has_been_diarized,
       CASE
         WHEN s.voiceMemoID           IS NOT NULL THEN 'voice-memo'
         WHEN s.recordedMeetingID     IS NOT NULL THEN 'meeting'
         WHEN s.systemAudioRecordingID IS NOT NULL THEN 'meeting'
         ELSE 'other'
       END                         AS session_type,
       rm.title                    AS recorded_meeting_title,
       rm.appName                  AS recorded_meeting_app
FROM session s
LEFT JOIN recordedmeeting rm ON rm.id = s.recordedMeetingID AND rm.dateDeleted IS NULL
WHERE s.dateDeleted IS NULL
  AND s.transcriptionDidSucceed = 1;

-- 2. For each session, pull segments in order
SELECT t.start          AS start_ms,
       t.end            AS end_ms,
       t.text           AS text,
       lower(hex(t.speakerID)) AS speaker_id
FROM transcriptline t
WHERE t.sessionId = ?
ORDER BY t.start ASC, t.dateCreated ASC;

-- 3. Resolve speaker IDs to names
SELECT lower(hex(id)) AS speaker_id, name, isStub
FROM speaker
WHERE id IN (SELECT speakerID FROM session_speaker WHERE sessionID = ?);

-- 4. Pull MacWhisper's built-in tags (use as supplementary tag input)
SELECT t.name
FROM tag t
JOIN session_tag st ON st.tagID = t.id
WHERE st.sessionID = ?;
```

Build the canonical dict from these rows (no `recording_id` field — see SPEC.md):

```python
# Resolve segment speakers, dropping the "Microphone" track for meetings
# (see SPEC.md "Segment de-duplication" for the rule).
def speaker_for(seg):
    if not seg.speaker_id:
        return None
    sp = speakers_by_id.get(seg.speaker_id)
    return sp.name if sp else None

segments = [
    {
        "start_ms": int(seg.start_ms),
        "end_ms":   int(seg.end_ms),
        "speaker":  speaker_for(seg),
        "text":     seg.text.strip(),
    }
    for seg in sorted(transcriptlines, key=lambda s: (s.start_ms, s.end_ms))
    if speaker_for(seg) != "Microphone" or session_type != "meeting"
]

recording = {
    "date":     session.date_iso_utc,            # ISO 8601 UTC
    "speakers": sorted({s["speaker"] for s in segments if s["speaker"]}),
    "segments": segments,
}
```

Then compute `content_hash(recording)` per SPEC.md and use the standard
decision tree.

The session UUID (`lower(hex(session.id))`) goes into the `source:` frontmatter
field as `macwhisper-db:<uuid-hex>` — it identifies the origin row, not the
canonical content.

## Filling the output template

Map DB fields into the template (full template in SPEC.md):

| Template field | DB source |
|---|---|
| `title` | `userChosenTitle` if non-empty and not `"Test"`; else `aiTitle`; else `recordedmeeting.title`; else generate per SPEC.md slug rules. |
| `date` | First 10 chars of `session.dateCreated` (UTC date). |
| `time` | `HH:MM` from `session.dateCreated` (UTC; convert to local if straightforward). |
| `duration` | `session.playbackDuration` seconds → `Nm Ms`. |
| `type` | Computed from `voiceMemoID` / `recordedMeetingID` / `systemAudioRecordingID` per SQL above. |
| `speakers` | Sorted list of `speaker.name` for the session; skip stubs (`isStub = 1`) — use `Speaker 1`, `Speaker 2` instead, mirroring the file-skill behavior. |
| `model` | `modelIdentifer` if set, else `modelEngine`. |
| `tags` | Vocabulary lookup per SPEC.md, plus any `tag.name` from `session_tag` for this session as additional candidates. |
| `source` | `macwhisper-db:<recording-id-hex>`. |
| `source_type` | `db`. |
| `content_hash` | SHA-256 of canonical recording per SPEC.md. |

For the transcript body, render each segment as `[HH:MM:SS] <speaker>: <text>`
per SPEC.md — convert `start_ms` to `HH:MM:SS`.

## What changes vs. the file skill

| | File skill | DB skill |
|---|---|---|
| Source location | `<workspace>/whisper/*.whisper` | `~/Library/Application Support/MacWhisper/Database/main.sqlite` |
| Source format | One JSON file per recording | One DB with N session rows |
| Detection of speaker rename | Requires re-export of `.whisper` | Picked up on next run, no export needed |
| Detection of transcript edit | Requires re-export | Picked up on next run, no export needed |
| Tracks deletions | No (export persists after delete) | Yes — sessions with `dateDeleted IS NOT NULL` skipped |
| `source:` value | `<filename>.whisper` | `macwhisper-db:<uuid-hex>` |
| `source_type:` value | `file` | `db` |

Everything else — slug rules, historical equivalents, output template, tag
vocabulary, reporting — is identical and lives in `SPEC.md`.

## Reporting addition

In addition to the standard reporting categories in SPEC.md, include:

- **DB connection:** path of the DB, total sessions found (non-deleted), how
  many were considered for processing.
