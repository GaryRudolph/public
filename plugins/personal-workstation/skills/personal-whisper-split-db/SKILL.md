---
name: personal-whisper-split-db
description: >-
  Split a MacWhisper recording into two sessions directly in the SQLite
  database. Identifies the source session by title and/or date/time, proposes
  or accepts an explicit split point in milliseconds, and writes two new
  sessions ("Split 1" / "Split 2") with the transcript rebased and audio cut
  at the boundary. The original session is never modified or deleted.
  Operates via a dry-run plan (identify → plan → apply) so every write is
  previewed before committing. NEVER runs apply against the live MacWhisper
  database while MacWhisper is running.
---

# Whisper Split — DB engine

Split one MacWhisper recording into two new sessions directly in
`main.sqlite` + `ExternalMedia/`. The original is left untouched; you
delete it manually inside MacWhisper once you've verified the new sessions.

Read [`../../../../specs/macwhisper-database.md`](../../../../specs/macwhisper-database.md)
for the schema, time model, soft-delete, FTS triggers, the §1 safety
contract, and the §10 unverified assumptions the engine is designed to
validate against a backup before any live run.

The shared engine lives in [`../lib/whisper_edit/`](../lib/whisper_edit/);
this skill is a thin entry point that calls it in-process.

## Safety (mandatory — read before using)

- **MacWhisper must be fully quit** before `apply`. The engine checks this
  and refuses with a hard error if MacWhisper is running.
- **Always validate first against a backup copy**, not the live DB.
  Pass `--db <backup-path>` and `--no-process-check` when running against
  a copy so the process guard is bypassed and the live file is never touched.
- The `apply` step takes a **mandatory timestamped backup** of `main.sqlite`
  + all referenced audio before any mutation. If the backup fails, nothing
  is written.
- This tool **never deletes** the source session. Delete originals manually
  inside MacWhisper after verifying the new sessions.

## How to run

```bash
# Step 1 — find the session to split
python3 scripts/run.py identify --title "Team standup" --date 2026-05-30

# Step 2 — build the plan (auto-detect split point, or pass --split-ms)
python3 scripts/run.py plan --session-id <hex> --split-ms 1800000

# Step 2a — auto-detect split point (review candidates, pick an index)
python3 scripts/run.py plan --session-id <hex> --candidate 0

# Step 3 — review the plan summary, then apply
python3 scripts/run.py apply

# Validation against a backup copy (safe even while MacWhisper runs)
python3 scripts/run.py plan --session-id <hex> --split-ms 1800000 \
    --db /tmp/whisper-backup/main.sqlite
python3 scripts/run.py apply --no-process-check \
    --db /tmp/whisper-backup/main.sqlite
```

## Subcommands

| Subcommand | Purpose |
|---|---|
| `identify` | Read-only scan: rank sessions matching title/date/time hints. Prints a numbered list so you can pick a `--session-id`. |
| `plan` | Build a dry-run plan: load the bundle, determine the split point (explicit or auto-detected), stage audio, write `plan.json`. No live writes. |
| `apply` | Execute the latest `plan.json`: backup → insert rows → move staged audio → verify. Requires MacWhisper to be fully quit (override with `--no-process-check` for backup-copy validation). |

### `identify` options

| Flag | Default | Notes |
|---|---|---|
| `--db PATH` | Live MacWhisper DB | Path to `main.sqlite`. Override for backup testing. |
| `--title STR` | — | Free-text title fragment (fuzzy matched). |
| `--date YYYY-MM-DD` | — | Boost sessions recorded on this date. |
| `--time HH:MM` | — | Boost sessions near this time of day (local). |
| `--limit N` | 10 | Max candidates to print. |

### `plan` options

| Flag | Default | Notes |
|---|---|---|
| `--session-id HEX` | required | 32-char lowercase hex session ID from `identify`. |
| `--db PATH` | Live MacWhisper DB | Override for backup testing. |
| `--split-ms MS` | — | Split boundary in milliseconds from session start. |
| `--candidate N` | 0 | Use the Nth auto-detected split candidate (0 = highest score). Ignored when `--split-ms` is given. |
| `--no-merged-multitrack` | off | Skip reconstructing the `mergedMultitrack` audio track (§10.2). |
| `--plan-root DIR` | `/tmp/whisper_edit` | Directory for `plan.json` and staged audio. |

### `apply` options

| Flag | Default | Notes |
|---|---|---|
| `--plan PATH` | `<plan-root>/plan.json` | Path to the `plan.json` written by `plan`. |
| `--no-process-check` | off | Bypass the MacWhisper-running guard. **Only for backup-copy validation.** |
| `--backup-root DIR` | `~/Library/Application Support/MacWhisper/Backups-whisper-edit` | Where the pre-write backup is stored. |

## Output

**`plan`** prints:
- The two new session titles, IDs, line counts, audio filenames, and durations.
- A count of media files that will be backed up.
- The staging directory path (safe to delete after apply).

**`apply`** prints:
- A confirmation that the backup was taken (with backup path).
- Inserted row counts and written audio file paths.
- Verification status (all checks pass / failures).
- A "Retain vs. delete" section: originals to keep (the source session is
  always in this list), staging temp files safe to delete.

## Schema reference

See [`../../../../specs/macwhisper-database.md`](../../../../specs/macwhisper-database.md)
for the full schema. Relevant tables:

| Table | Purpose |
|---|---|
| `session` | One row per recording. UUID `id` (BLOB), `dateCreated`, titles, duration. |
| `transcriptline` | Per-segment transcript. `start`/`end` in ms, `text`, `speakerID`. |
| `speaker`, `session_speaker` | Speaker definitions and many-to-many links. |
| `recordedmeeting`, `voicememos` | Meeting/memo metadata linked from `session`. |
| `sessionFTS` | FTS5 mirror — updated by triggers on insert/delete of `transcriptline`. |
| `mediafile` | Audio file records. Filename prefix is `<UUID-uppercase>_<8hex>.<ext>` (§7.1, §10.1). |
