---
name: personal-whisper-db-markdown
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
content hash, what-to-process decision tree, self-mic dedup, manual
truncation, historical equivalents, title/slug rules, output template
(including the `## Original notes` section), tag vocabulary, and reporting
format. This file adds DB-source specifics and the orchestration runbook.

For Cowork install (workspace, file access, prompts, scheduling), see
[`./COWORK.md`](./COWORK.md).

## How to run

The skill does **not** require you to derive plan/write/merge logic from
scratch each session. Both whisper skills ship a pre-built Python library
under [`../lib/whisper/`](../lib/whisper) and a thin entry point at
[`./scripts/run.py`](./scripts/run.py). Drive the entire pipeline through
those subcommands:

```bash
python3 scripts/run.py housekeep     --workspace ~/Projects/personal/notes
python3 scripts/run.py plan          --workspace ~/Projects/personal/notes
python3 scripts/run.py merge         --workspace ~/Projects/personal/notes
python3 scripts/run.py lookup-tags propose --workspace ~/Projects/personal/notes
python3 scripts/run.py lookup-tags apply   --workspace ~/Projects/personal/notes
python3 scripts/run.py write         --workspace ~/Projects/personal/notes
python3 scripts/run.py report        --workspace ~/Projects/personal/notes
```

The standard flow is:

0. `housekeep` — **always run this first.** Wipes stale `/tmp/whisper_plan/`
   state left over from a prior or interrupted run (per-session JSONs,
   content batches, queue/report files) so this run starts from a clean
   slate. See *Housekeeping* below for why this matters. Never run it
   between the two `plan` calls in step 1/3 — only once, at the very start.
1. `plan` — opens the MacWhisper DB read-only, builds canonical structures,
   hashes, provisional titles for every non-deleted session. Writes
   per-session JSONs under `/tmp/whisper_plan/sessions/`. Consults the
   processed-sessions ledger (see below) to fast-path sessions that are
   already written and unchanged.
2. **Content generation** — see the decision tree below. Either fill the
   per-session JSONs inline (1 session) or dispatch Sonnet subagent(s)
   (2+ sessions) that emit `content_<batch>.json` files. Only sessions
   needing attention (`plan`'s `sessions` list, not the `unchanged_count`)
   need content generation.
3. `plan` again — content-aware second pass. Picks up the final titles
   from the content files and locks in final slugs / final paths.
4. `merge` — reconciles raw tags across content batches against the
   workspace vocabulary (`tags.md`).
5. `lookup-tags propose` — emits `lookup_queue.json` of newly-proposed
   person tags. For each one, use WebSearch to find candidates and
   AskQuestion (one prompt per tag) for the user's choice; write the
   answers to `/tmp/whisper_plan/lookup_decisions.json`.
6. `lookup-tags apply` — rewrites session tags and appends to `tags.md`.
7. `write` — renders and writes at the final paths. Handles
   `git mv`/`git rm` for historical replacements, then rewrites the
   processed-sessions ledger from this run's outcomes.
8. `report` — print the run summary. Sessions the ledger fast-pathed as
   unchanged are reported as a single count, not enumerated.

All shared state lives under `/tmp/whisper_plan/`. Subagents only read
per-session JSON files there and write `content_*.json` back; they never
edit scripts or move files.

## Housekeeping

`/tmp/whisper_plan/` is meant to hold exactly one run's working state.
Left alone across runs it accumulates two classes of stale data that leak
into a later run's decisions:

- **Stale `content_*.json` overlays.** `plan` merges *every* content file it
  finds in `/tmp/whisper_plan/content/`, with no notion of "this run's
  batch." A leftover file from an earlier or interrupted run can silently
  overlay onto the wrong session.
- **Stale per-session JSONs.** `write` iterates every file under
  `/tmp/whisper_plan/sessions/` — including entries for recordings deleted
  from MacWhisper since, or notes already written days ago — needlessly
  re-touching them.

`housekeep` wipes the whole `/tmp/whisper_plan/` tree and recreates it
empty. It does **not** touch `<workspace>/.whisper.json` (see
next section) — that ledger is what makes it safe to wipe `/tmp` on every
run without losing track of what's already been processed.

## Processed-sessions ledger

`<workspace>/.whisper.json` is a small, workspace-local, persistent
record of every session this pipeline has successfully written a note for:
`session_key → {content_hash, out_path, title, status}`. It survives
`housekeep` (and reboots, and disk cleanup — it's not in `/tmp`) precisely
so that `plan` doesn't have to re-derive "has this already been processed?"
from scratch on every run.

Two things it fixes:

- **Speed.** For a session whose ledger `content_hash` matches the freshly
  computed one, `plan` confirms the note is still on disk at the recorded
  path and immediately calls it unchanged — no same-day-directory scan, no
  historical-equivalent search. Only sessions that are new or actually
  changed pay the full resolution cost.
- **Chattiness.** Unchanged sessions are bucketed into a single
  `unchanged_count` instead of one detailed entry per session in `plan`'s
  output, and `report` prints that as one line instead of enumerating every
  already-processed recording. With months or years of recordings behind
  it, a run finding nothing new should say so in one line, not one line per
  historical session.

It's purely a cache, not a source of truth: if it's missing, stale, or the
recorded path no longer has a note, `plan` transparently falls back to the
same filesystem resolution it always used (`content_hash` match against the
actual note's frontmatter). Deleting it is always safe — the next run just
does the slower full resolution once and rebuilds it. Never edit it by
hand; `write` rewrites it in full from that run's outcomes on every run,
which also prunes entries for sessions no longer present (e.g. deleted from
MacWhisper).

## Run-size decision tree

| Sessions to process | Execution | Subagent model |
|---|---|---|
| 1 | **Inline.** Read the per-session JSON, generate title/summary/action items/tags yourself, write a single `content/inline.json`, then run `merge` + `write`. | none |
| 2–5 | **One Sonnet subagent** producing one `content_a.json` for all of them. | `claude-4.5-sonnet-thinking` |
| 6+ | **Parallel Sonnet subagents.** Deterministic batching: group by date (within a day), cap each batch at ~5 sessions. Each subagent writes its own `content_<batch>.json`. | `claude-4.5-sonnet-thinking` |

A single recording isn't worth subagent overhead. A small batch fits in one
Sonnet context. Large batches benefit from parallelism but must stay below
the rate where coordinating tag-additions becomes more expensive than the
parallelism saves.

## Subagent guidance

When dispatching content-generation subagents:

- **Model**: `claude-4.5-sonnet-thinking`.
- **Inputs**: pass the list of `session_key`s in the batch. The subagent
  reads its assigned per-session JSON files from
  `/tmp/whisper_plan/sessions/<key>.json` (each contains `canonical.segments`
  for the transcript, `macwhisper_title_hint`, `macwhisper_tags`,
  `historical.body` when a hand-written equivalent matched, etc.) and
  reads `<workspace>/tags.md` for the vocabulary.
- **Output**: exactly one file written to
  `/tmp/whisper_plan/content/content_<batch_id>.json` with this shape:

  ```json
  {
    "sessions": {
      "<session_key>": {
        "title": "Hobart Rowing Coach Call",
        "summary": "...",
        "action_items": ["..."],
        "tags": ["rowing", "college-recruiting", "hobart"]
      }
    },
    "tag_additions": {
      "new-tag-name": "gloss for the new tag"
    }
  }
  ```

- **When a historical match is present** (`historical.body` is non-empty
  in the per-session JSON), prompt the subagent with: *"The user wrote
  these notes around the time of the meeting. Treat them as one more
  signal — they may flag decisions, side observations, follow-ups they
  cared about, or just personal reactions. There are many reasons something
  might have been written down. The transcript remains the source of truth
  for what was said; let the notes inform what to emphasize, not override
  the transcript."* The hand-written body itself is rendered verbatim in
  the final note's `## Original notes` section by `write`; the subagent
  only uses it to inform its summary.
- **Hard constraints**: subagents NEVER edit `scripts/run.py`, never edit
  `lib/whisper/`, never move files, never write outside
  `/tmp/whisper_plan/content/`. This is enforced by construction — they
  are pure content producers. Coordination races (two subagents both
  editing the planner) are impossible.

## Post-processing: splitting multi-meeting notes

When a recording captures two or more meetings (back-to-back calls, a
recording left running, etc.) the note it produces can be split into separate
files without touching the MacWhisper database.

Use the [`personal-whisper-md-consolidation`](../personal-whisper-md-consolidation/SKILL.md)
skill after this skill completes. It detects large transcript gaps, speaker
membership changes, farewell/greeting cue pairs, and dead-air spans, then
splits the note with rebased timestamps.

Notes produced by that skill carry `split_part: N/M` frontmatter. The upstream
planner recognises these via the original `content_hash` and correctly skips
the source recording on re-runs — no configuration required.

## Source: MacWhisper SQLite

MacWhisper stores all live state in a single SQLite database at:

```
~/Library/Application Support/MacWhisper/Database/main.sqlite
```

Companion files `main.sqlite-shm` and `main.sqlite-wal` are SQLite WAL-mode
sidecars — leave them alone; SQLite reads them transparently.

**Open the DB read-only.** `scripts/run.py` uses
`sqlite3.connect("file:...?mode=ro", uri=True)`. Never open it read-write —
that risks corrupting MacWhisper's state if the app is running concurrently.

If MacWhisper is currently running, the WAL may contain uncommitted writes
visible to a read-only connection — that's fine and expected. If a query
fails with a lock error, wait briefly and retry.

The `source:` frontmatter value is `macwhisper-db:<recording-id-hex>`
(e.g. `macwhisper-db:d9393ef207004356bd779b90e2336a82`). The `source_type:`
value is `db`.

## Workspace root

Like the file skill, this skill writes notes under `<workspace>/YYYY/MM/`.
The user points the agent at a notes workspace (e.g. `~/Projects/personal/notes/`);
the DB is read from the fixed Library path above regardless of cwd.

## Schema overview (reference)

> The full MacWhisper database reference (every table, the FTS5 mirror +
> triggers, BLOB-UUID/hex and time conventions, soft-delete, media-file
> naming/`type` enums, schema-drift handling, and the read-only/write safety
> contract) lives in [`../../../../specs/macwhisper-database.md`](../../../../specs/macwhisper-database.md).

`scripts/run.py` handles the SQL internally. The relevant tables for
debugging or schema-drift triage:

| Table | Purpose |
|---|---|
| `session` | One row per recording. UUID `id` (BLOB), `dateCreated`, titles, model, deletion flag. |
| `transcriptline` | Per-segment transcript. `sessionId` FK, `start`/`end` in ms, `text`, `speakerID` FK. |
| `speaker` | Speaker definitions. `id` (BLOB), `name`, `isStub` (1 = "Speaker N" placeholder). |
| `session_speaker` | Many-to-many: which speakers appear in which session. |
| `recordedmeeting` | Metadata for sessions linked via `session.recordedMeetingID` (title, calendar match, app/browser). |
| `voicememos` | Metadata for sessions linked via `session.voiceMemoID`. |
| `tag`, `session_tag` | MacWhisper's built-in tag system. Pulled as supplementary tag input for subagents. |

**ID format.** All `id` columns are BLOB UUIDs. The entry point converts
them to a stable hex string via `lower(hex(id))`. The lowercase hex form
(32 chars, no dashes) is what goes into the `source:` frontmatter.

**Soft-delete.** Every query filters by `dateDeleted IS NULL` on `session`
and joined tables. Trashed recordings are ignored (never deleted on disk
by this skill — that's MacWhisper's job).

**Schema drift.** MacWhisper occasionally changes column spellings between
releases (e.g. `modelIdentifer` vs `modelIdentifier`, `playbackDuration` vs
`duration`). `scripts/run.py` queries `PRAGMA table_info(session)` at
startup and adapts. If the entry point produces empty output, run
`sqlite3 -readonly "<path>"` and `.schema session` to see what changed.

## What changes vs. the file skill

|  | File skill | DB skill |
|---|---|---|
| Source location | `<workspace>/whisper/*.whisper` | `~/Library/Application Support/MacWhisper/Database/main.sqlite` |
| Source format | One JSON file per recording | One DB with N session rows |
| Detection of speaker rename | Requires re-export of `.whisper` | Picked up on next run, no export needed |
| Detection of transcript edit | Requires re-export | Picked up on next run, no export needed |
| Tracks deletions | No (export persists after delete) | Yes — sessions with `dateDeleted IS NOT NULL` skipped |
| `source:` value | `<filename>.whisper` | `macwhisper-db:<uuid-hex>` |
| `source_type:` value | `file` | `db` |

Everything else — canonical structure, dedup, truncation, slug rules,
historical equivalents, output template, tag vocabulary, reporting — is
identical and lives in SPEC.md plus `lib/whisper/`.

## Reporting addition

In addition to the standard reporting categories in SPEC.md, include:

- **DB connection:** path of the DB, total sessions found (non-deleted),
  how many were considered for processing.
- **Housekeeping:** whether stale `/tmp/whisper_plan/` state was found and
  cleared, and how many sessions are tracked in the processed-sessions
  ledger.
