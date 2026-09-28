---
name: personal-whisper-split-combine-db
description: >-
  Orchestrate a split-then-combine workflow for MacWhisper recordings directly
  in the SQLite database. Handles the common case where recording 1 captured
  meeting 1 plus the head of meeting 2, and recording 2 captured the tail of
  meeting 2. Splits recording 1 at the meeting boundary, then combines the head
  fragment with recording 2 to produce the full meeting 2. Both source
  recordings and the intermediate fragment are left in place; the skill prints
  a retain-vs-delete summary and never deletes anything itself. Operates
  in-process (calls the shared engine directly — does NOT re-invoke the split or
  combine skills). NEVER runs apply against the live MacWhisper database while
  MacWhisper is running.
---

# Whisper Split-Combine — DB engine (orchestrator)

Handle the canonical recording-overlap scenario:

```
Recording 1:  [======= Meeting 1 =======][== Meeting 2 head ==]
Recording 2:                              [== Meeting 2 tail ==]
```

This skill splits Recording 1 at the boundary → `Split 1` (Meeting 1) + a
head fragment, then combines that head fragment with Recording 2 → `Meeting 2
Combined`. It calls the shared `whisper_edit` engine in-process for both
operations; it does NOT shell out to or re-invoke the split or combine skills.

Read [`../../../../specs/macwhisper-database.md`](../../../../specs/macwhisper-database.md)
for the schema, safety contract, and the §10 unverified assumptions the engine
validates before any live run.

The shared engine lives in [`../lib/whisper_edit/`](../lib/whisper_edit/).

## Safety (mandatory — read before using)

- **MacWhisper must be fully quit** before `apply`. The engine checks this
  and refuses with a hard error if MacWhisper is running.
- **Always validate first against a backup copy**, not the live DB.
  Pass `--db <backup-path>` and `--no-process-check` when running against
  a copy so the process guard is bypassed and the live file is never touched.
- The `apply` step takes a **mandatory timestamped backup** of `main.sqlite`
  + all referenced audio before any mutation. If the backup fails, nothing
  is written.
- This tool **never deletes** anything: not the source recordings, not the
  intermediate head fragment, not any audio. The retain-vs-delete summary
  in the apply output tells you what to remove manually inside MacWhisper.

## How to run

```bash
# Step 1 — identify recording 1 (meeting1 + head of meeting2)
python3 scripts/run.py identify --recording 1 --title "Long recording" --date 2026-05-30

# Step 1b — identify recording 2 (tail of meeting 2)
python3 scripts/run.py identify --recording 2 --title "Second recording" --date 2026-05-30

# Step 2 — plan both operations (split + combine) in one call
python3 scripts/run.py plan \
    --recording1 <hex1> --recording2 <hex2> \
    --split-ms 3600000

# Step 2 — auto-detect split point (review candidates, pick index)
python3 scripts/run.py plan --recording1 <hex1> --recording2 <hex2> --candidate 0

# Step 3 — review the plan summary, then apply
python3 scripts/run.py apply

# Validation against a backup copy (safe even while MacWhisper runs)
python3 scripts/run.py plan \
    --recording1 <hex1> --recording2 <hex2> --split-ms 3600000 \
    --db /tmp/whisper-backup/main.sqlite
python3 scripts/run.py apply --no-process-check \
    --db /tmp/whisper-backup/main.sqlite
```

## Subcommands

| Subcommand | Purpose |
|---|---|
| `identify` | Read-only scan: rank sessions matching title/date/time hints. Use `--recording 1` or `--recording 2` to clarify which you're identifying. |
| `plan` | Build BOTH dry-run plans in-process (split recording 1, then combine head + recording 2). Writes `split-plan.json` and `combine-plan.json`. No live writes. |
| `apply` | Execute both plans in sequence: backup → split apply → combine apply → verify → retain-vs-delete summary. Requires MacWhisper to be fully quit (override with `--no-process-check` for backup-copy validation). |

### `identify` options

| Flag | Default | Notes |
|---|---|---|
| `--recording 1\|2` | — | Which recording you're identifying (display + guidance only). |
| `--db PATH` | Live MacWhisper DB | Path to `main.sqlite`. Override for backup testing. |
| `--title STR` | — | Free-text title fragment (fuzzy matched). |
| `--date YYYY-MM-DD` | — | Boost sessions recorded on this date. |
| `--time HH:MM` | — | Boost sessions near this time of day (local). |
| `--limit N` | 10 | Max candidates to print. |

### `plan` options

| Flag | Default | Notes |
|---|---|---|
| `--recording1 HEX` | required | Recording 1 (meeting1 + head of meeting2). 32-char hex. |
| `--recording2 HEX` | required | Recording 2 (tail of meeting2). 32-char hex. |
| `--db PATH` | Live MacWhisper DB | Override for backup testing. |
| `--split-ms MS` | — | Split boundary in ms from recording 1 start. |
| `--candidate N` | 0 | Auto-detected split candidate index (0 = highest score). |
| `--meeting1-title STR` | Derived from recording 1 title + "Split 1" | Title for the Meeting 1 output. |
| `--meeting2-title STR` | Derived from recording 2 title + "Combined" | Title for the Meeting 2 combined output. |
| `--no-merged-multitrack` | off | Skip reconstructing the `mergedMultitrack` audio track (§10.2). |
| `--plan-root DIR` | `/tmp/whisper_edit` | Directory for plan JSON files and staged audio. |

### `apply` options

| Flag | Default | Notes |
|---|---|---|
| `--split-plan PATH` | `<plan-root>/split-plan.json` | Path to the split plan written by `plan`. |
| `--combine-plan PATH` | `<plan-root>/combine-plan.json` | Path to the combine plan written by `plan`. |
| `--no-process-check` | off | Bypass the MacWhisper-running guard. **Only for backup-copy validation.** |
| `--backup-root DIR` | `~/Library/Application Support/MacWhisper/Backups-whisper-edit` | Where the pre-write backup is stored. |

## Output

**`plan`** prints a combined summary of both operations:
- Split plan: Split 1 (Meeting 1) and head fragment titles, IDs, line counts.
- Combine plan: Meeting 2 Combined title, ID, line count, audio filename.
- A "Retain vs. delete" forecast (none deleted by this tool).

**`apply`** prints:
- Backup confirmation (path).
- Split result: session IDs, rows inserted, audio files written, verification.
- Combine result: session ID, rows inserted, audio file written, verification.
- Final retain-vs-delete summary:
  - **Retain** (do NOT delete): Recording 1, Recording 2 (both originals),
    Split 1 / Meeting 1 (new).
  - **You may delete** (after verifying in MacWhisper): the head fragment
    (intermediate) and both source recordings.
  - **Engine temp files safe to delete** right now: staging directories.

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
