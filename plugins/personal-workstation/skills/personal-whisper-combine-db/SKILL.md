---
name: personal-whisper-combine-db
description: >-
  Combine two MacWhisper recordings into a single new session directly in the
  SQLite database. Identifies session A then session B by title and/or
  date/time, concatenates them in order (B's transcript offset by A's
  duration, audio concatenated), and writes one new combined session. Both
  source sessions are left untouched. Operates via a dry-run plan
  (identify → plan → apply) so every write is previewed before committing.
  NEVER runs apply against the live MacWhisper database while MacWhisper is
  running.
---

# Whisper Combine — DB engine

Combine two MacWhisper recordings (A then B) into one new session directly
in `main.sqlite` + `ExternalMedia/`. Both originals are left untouched; you
delete them manually inside MacWhisper once you've verified the combined
session.

Read [`../../../../specs/macwhisper-database.md`](../../../../specs/macwhisper-database.md)
for the schema, time model, soft-delete, FTS triggers, the §1 safety
contract, and the §10 unverified assumptions the engine validates against a
backup before any live run.

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
- This tool **never deletes** source sessions. Delete originals manually
  inside MacWhisper after verifying the combined session.
- Sessions A and B **must be the same kind** (both meetings, or both
  voice memos) and expose the same audio track roles; the engine raises if
  they don't match.

## How to run

```bash
# Step 1 — find session A
python3 scripts/run.py identify --label a --title "Morning standup" --date 2026-05-30

# Step 1b — find session B
python3 scripts/run.py identify --label b --title "Team sync" --date 2026-05-30

# Step 2 — plan the combine
python3 scripts/run.py plan --session-a <hexA> --session-b <hexB>

# Step 2 — optional custom title
python3 scripts/run.py plan --session-a <hexA> --session-b <hexB> \
    --title "Morning standup + Team sync"

# Step 3 — review the plan summary, then apply
python3 scripts/run.py apply

# Validation against a backup copy (safe even while MacWhisper runs)
python3 scripts/run.py plan --session-a <hexA> --session-b <hexB> \
    --db /tmp/whisper-backup/main.sqlite
python3 scripts/run.py apply --no-process-check \
    --db /tmp/whisper-backup/main.sqlite
```

## Subcommands

| Subcommand | Purpose |
|---|---|
| `identify` | Read-only scan: rank sessions matching title/date/time hints. Use `--label a` or `--label b` to clarify which session you're identifying. |
| `plan` | Build a dry-run plan: load bundles A and B, combine them, stage audio, write `plan.json`. No live writes. |
| `apply` | Execute the latest `plan.json`: backup → insert rows → move staged audio → verify. Requires MacWhisper to be fully quit (override with `--no-process-check` for backup-copy validation). |

### `identify` options

| Flag | Default | Notes |
|---|---|---|
| `--label a\|b` | — | Which session you're identifying (for display clarity only). |
| `--db PATH` | Live MacWhisper DB | Path to `main.sqlite`. Override for backup testing. |
| `--title STR` | — | Free-text title fragment (fuzzy matched). |
| `--date YYYY-MM-DD` | — | Boost sessions recorded on this date. |
| `--time HH:MM` | — | Boost sessions near this time of day (local). |
| `--limit N` | 10 | Max candidates to print. |

### `plan` options

| Flag | Default | Notes |
|---|---|---|
| `--session-a HEX` | required | Session A (plays first). 32-char lowercase hex ID from `identify`. |
| `--session-b HEX` | required | Session B (plays second, transcript offset by A's duration). |
| `--db PATH` | Live MacWhisper DB | Override for backup testing. |
| `--title STR` | Derived from A's title | Custom title for the combined session. |
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
- The combined session title, ID, line count, audio filenames, and duration.
- A count of media files that will be backed up.
- The staging directory path (safe to delete after apply).

**`apply`** prints:
- A confirmation that the backup was taken (with backup path).
- Inserted row counts and written audio file paths.
- Verification status (all checks pass / failures).
- A "Retain vs. delete" section: both originals stay (always in the retain
  list), staging temp files safe to delete.

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
