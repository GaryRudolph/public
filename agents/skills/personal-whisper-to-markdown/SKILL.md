---
name: personal-whisper-to-markdown
description: >-
  Convert MacWhisper .whisper transcript exports into organized, dated Markdown
  notes with YAML frontmatter, a generated summary, action items, proposed tags,
  and a timestamped transcript. Use this skill whenever the user asks to process,
  convert, sync, or organize MacWhisper transcripts, .whisper files, or a
  "whisper folder" into Markdown or notes — even if they don't say "convert"
  explicitly (e.g. "process my new recordings", "turn my transcripts into
  notes", "update my whisper notes"). Re-runs are safe and incremental.
---

# Whisper to Markdown — file source

Read [`./SPEC.md`](./SPEC.md) for all canonical behavior: folder layout,
canonical recording structure, content hash definition, what-to-process
decision tree, self-mic dedup, manual truncation, historical equivalents,
title/slug rules, output template (including the `## Original notes`
section), tag vocabulary, and reporting format. This file adds file-source
specifics and the orchestration runbook.

For Cowork install (workspace, file access, prompts, scheduling), see
[`./COWORK.md`](./COWORK.md).

## How to run

The skill does **not** require you to derive plan/write/merge logic from
scratch each session. Both whisper skills ship a pre-built Python library
under [`../lib/whisper/`](../lib/whisper) and a thin entry point at
[`./scripts/run.py`](./scripts/run.py). Drive the entire pipeline through
those subcommands:

```bash
python3 scripts/run.py plan          --workspace ~/Projects/personal/notes
python3 scripts/run.py merge         --workspace ~/Projects/personal/notes
python3 scripts/run.py lookup-tags propose --workspace ~/Projects/personal/notes
python3 scripts/run.py lookup-tags apply   --workspace ~/Projects/personal/notes
python3 scripts/run.py write         --workspace ~/Projects/personal/notes
python3 scripts/run.py report        --workspace ~/Projects/personal/notes
```

The standard flow is:

1. `plan` — bootstraps canonical structures, hashes, provisional titles.
2. **Content generation** — see the decision tree below. Either fill the
   per-session JSONs inline (1 session) or dispatch Sonnet subagent(s)
   (2+ sessions) that emit `content_<batch>.json` files.
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
   `git mv`/`git rm` for historical replacements and `touch -r` for mtime.
8. `report` — print the run summary.

All shared state lives under `/tmp/whisper_plan/`. Subagents only read
per-session JSON files there and write `content_*.json` back; they never
edit scripts or move files.

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
  for the transcript, `macwhisper_title_hint`, `historical.body` when a
  hand-written equivalent matched, etc.) and reads `<workspace>/tags.md`
  for the vocabulary.
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

## Source: .whisper ZIP archives

A `.whisper` file is a **ZIP archive** containing three entries:

```
metadata.json    # the transcript and metadata — this is what we read
originalAudio    # raw audio bytes — ignore; we never re-transcribe
version          # format version string (e.g. "2")
```

`scripts/run.py` extracts `metadata.json` in-memory and parses it as JSON.
Never read or decode `originalAudio` — MacWhisper has already done the
transcription and re-running speech-to-text would risk producing different
results than what the user sees in MacWhisper.

The `source:` frontmatter value is the `.whisper` filename (e.g.
`Meeting - Zoom 2026-04-27 07_32_47.whisper`). The `source_type:` value
is `file`.

### metadata.json schema (version 2)

Top-level fields the entry point reads:

| Field | Meaning |
|---|---|
| `dateCreated` | Recording start time in **Mac Absolute Time** (seconds since 2001-01-01 00:00:00 UTC). Converted to ISO 8601 UTC inside `scripts/run.py`. |
| `dateUpdated` | Last edit time, same format. |
| `originalMediaFilename` | Often empty; falls back to filename for hints. |
| `modelEngine` | e.g. `parakeetKitPro` |
| `modelQualityID` | e.g. `nvidia_parakeet-v3` — used as the `model:` frontmatter value (more specific than `modelEngine`). |
| `detectedLanguageRaw` | e.g. `en` |
| `speakers` | Array of `{id, name, color}`. Names may include both `"Microphone"` and `"Speaker 1..N"` for meetings; see SPEC.md "Self-mic segment de-duplication". |
| `transcripts` | Array of segments. Each has `start`/`end` in ms, `text`, optional `speaker`. |
| `startTimeOffset` | Usually 0. |
| `wasTranslatedToEnglish` | Boolean. |

### Session type inference

The filename hints at type:

- `Meeting - <App>` prefix → `meeting`
- `Voice Memo` → `voice-memo`
- otherwise → `other`

### First-run sanity check

The schema can shift between MacWhisper versions. Before running the full
pipeline for the first time (or when output is empty/garbled), open one
`.whisper` file in a Python REPL and inspect its `metadata.json` to confirm
the keys above still exist. Report briefly what you found, then proceed.
The entry point degrades gracefully when per-segment timestamps or speakers
are absent.
