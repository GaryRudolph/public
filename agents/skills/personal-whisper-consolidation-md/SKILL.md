---
name: personal-whisper-consolidation-md
description: >-
  Post-process whisper markdown notes that contain multiple meetings in one
  recording. Scans for large transcript gaps, speaker membership changes,
  farewell/greeting cue pairs, and dead-air spans; then splits the note into
  separate files with rebased timestamps and adjusted start times. Works on the
  rendered markdown output of personal-whisper-to-markdown or
  personal-whisper-to-markdown-db — never touches the MacWhisper database or
  .whisper files. Use when you notice a note covers two meetings, when a
  recording was left running for hours, or when you want to run a periodic
  consolidation pass over recent notes.
---

# Whisper Consolidation — Markdown Split

Post-processing skill for splitting a whisper markdown note that turns out to
contain two or more meetings. Operates purely on the rendered markdown files;
never touches the MacWhisper database or `.whisper` files.

## Triggers

Use this skill when the user says:
- "This note was actually two meetings"
- "This recording was left running, split it"
- "Split that into two notes"
- "Consolidation pass" / "run consolidation"
- "This call ended and another started right after"

## Safety

- **Reads markdown files only.** No MacWhisper database access, no audio
  mutation, no `.whisper` ZIP modification.
- **The original note is removed only after all split files are
  successfully written.** If writing fails, the original is untouched.
- **Re-run safe.** Split files carry `split_part:` frontmatter; the scanner
  skips them automatically on future runs.
- **Upstream skills stay stable.** Each split file keeps the original
  `content_hash`, `source`, and `source_type`. The upstream planner's
  `_resolve_existing_note` lookup still finds a hash match and skips the
  source recording on re-runs. If MacWhisper edits regenerate the merged
  source note, re-run this skill to re-split it.

## How to run

```bash
python3 scripts/run.py scan   --workspace ~/Projects/personal/notes
python3 scripts/run.py apply  --workspace ~/Projects/personal/notes
python3 scripts/run.py report
```

### Scan options

```bash
# Single note only:
python3 scripts/run.py scan --workspace ~/Projects/personal/notes \
    --path 2026/04/2026-04-27-some-meeting.md

# Tighter T1 gap threshold (5 min instead of 10):
python3 scripts/run.py scan --workspace ... --min-gap-min 5

# Full options:
#   --min-gap-min N       T1 silence gap in minutes (default 10)
#   --t2-window-lines N   T2 window size in lines (default 30)
#   --t2-jaccard-max X    T2 Jaccard threshold (default 0.2, lower = stricter)
#   --t3-max-gap-min N    T3 farewell-to-greeting max gap in minutes (default 3)
#   --t4-max-density X    T4 lines/min threshold for dead air (default 2)
#   --t4-min-span-min N   T4 minimum sustained sparse span in minutes (default 15)
```

## Standard flow

1. `scan` — walk notes, run detection tests, write `candidates.json`.
2. **Agent review** — read candidates, judge each flagged note, propose
   partitions, confirm with user via AskQuestion, write `decisions.json`.
3. `apply` — write split files, remove originals.
4. `report` — print summary.

All state lives under `/tmp/whisper_consolidate/`.

---

## Detection tests

Four independent tests each emit raw evidence; candidates within 60 seconds
of each other are merged, accumulating signals from every test that fired.

| Test | Signal | Default threshold | Confidence when alone |
|---|---|---|---|
| T1 — silence gap | Start-to-start pause between consecutive lines | ≥ 10 min | medium |
| T2 — speaker turnover | Jaccard similarity of non-self speaker sets before vs after | ≤ 0.2 | low–medium |
| T3 — farewell → greeting | Closing phrase then opening phrase | within 3 min | low |
| T4 — dead-air span | Sustained sparse transcription | < 2 lines/min for ≥ 15 min | span (not a point boundary) |

**Self-mic exclusion.** The user's own speakers (`self_mic_speakers` from
`.whisper-config.json`, default `["Microphone", "Gary"]`) are excluded from
all T2 membership comparisons — the user is present in every meeting, so
their presence can't distinguish meetings.

**T1 + T2 or T1 + T3** → high confidence boundary.
**T1 alone** → medium confidence.
**T2 alone, T3 alone** → low confidence; surface to user but do not auto-confirm.
**T4** → spans, not point boundaries; overlaps with T1 when the dead air is followed by a meeting.

---

## `candidates.json` schema

Written to `/tmp/whisper_consolidate/candidates.json` by `scan`:

```json
{
  "workspace": "/Users/.../notes",
  "flagged_count": 2,
  "notes": [
    {
      "note_path": "2026/04/2026-04-27-some-meeting.md",
      "total_duration_s": 12600,
      "total_duration": "03:30:00",
      "flagged": true,
      "boundaries": [
        {
          "split_ts_s": 3900,
          "split_ts": "01:05:00",
          "signals": ["T1", "T3"],
          "gap_s": 680,
          "jaccard_before": null,
          "jaccard_after": null,
          "speakers_before": ["Alice", "Bob"],
          "speakers_after": ["Carol", "Dave"],
          "context_before": ["[01:04:20] Bob: Thanks everyone, bye!"],
          "context_after": ["[01:05:00] Carol: Good morning, can you hear me?"],
          "confidence": "high"
        }
      ],
      "dead_air_spans": [
        {
          "from_ts_s": 6300,
          "to_ts_s": 12600,
          "from_ts": "01:45:00",
          "to_ts": "03:30:00",
          "duration_s": 6300,
          "density_lines_per_min": 0.3,
          "context_before": ["[01:44:55] Dave: Great, talk soon."],
          "context_after": []
        }
      ]
    }
  ]
}
```

---

## Agent review step

For each flagged note:

1. Read the note's boundary candidates and dead-air spans from `candidates.json`.
2. Look up the note's actual transcript content at the listed context lines
   (reading the file directly when more context is needed).
3. Judge which candidates are genuine meeting boundaries, weighing:
   - Gap size and confidence
   - Speaker membership change (T2 evidence)
   - Farewell/greeting cue pairs (T3 evidence)
   - Dead-air spans (T4 evidence)
4. Assemble a **partition** — an ordered list of contiguous parts, each:
   - `action: keep` → becomes a separate note
   - `action: discard` → no file; range recorded for auditability
5. Confirm with the user via `AskQuestion` (one prompt per flagged note).
   Show the proposed partition clearly: part boundaries, signals, and which
   parts will be kept vs discarded.
6. For each kept part, generate:
   - **title** — follow SPEC.md rules (descriptive; never "Gary" in title/slug;
     lead with the other party's name for 2-speaker parts)
   - **summary** — 3-5 sentences from the part's transcript
   - **action_items** — concrete follow-ups only; omit if none
   - **tags** — 1–20 kebab-case tags; use `<workspace>/tags.md` vocabulary
   - **include_original_notes** — assign the original note's `## Original notes`
     section to the part it belongs to (true for at most one kept part; false
     for others and any discard)
7. Write decisions to `/tmp/whisper_consolidate/decisions.json`.

### Run-size guidance

| Flagged notes | How to handle |
|---|---|
| 1 | Inline. Read candidates, generate content yourself, write decisions.json. |
| 2–5 | One Sonnet subagent per batch. |
| 6+ | Parallel Sonnet subagents, ~5 notes per batch. |

---

## `decisions.json` schema

Written by the agent to `/tmp/whisper_consolidate/decisions.json`:

```json
{
  "decisions": [
    {
      "note_path": "2026/04/2026-04-27-some-meeting.md",
      "action": "split",
      "parts": [
        {
          "from_ts": "00:00:00",
          "to_ts": "01:05:00",
          "action": "keep",
          "title": "Q2 Sales Review with Alice and Bob",
          "summary": "...",
          "action_items": ["Follow up with Bob on pricing proposal"],
          "tags": ["sales", "q2", "alice", "bob"],
          "include_original_notes": false
        },
        {
          "from_ts": "01:05:00",
          "to_ts": "01:45:00",
          "action": "keep",
          "title": "Eng Sync",
          "summary": "...",
          "action_items": [],
          "tags": ["engineering", "sync"],
          "include_original_notes": false
        },
        {
          "from_ts": "01:45:00",
          "to_ts": "03:30:00",
          "action": "discard"
        }
      ]
    },
    {
      "note_path": "2026/04/2026-04-28-voice-memo.md",
      "action": "skip"
    }
  ]
}
```

**`action` at the top level:**
- `"split"` — apply the partition (default when `action` is absent)
- `"skip"` — leave the note untouched; included in the report as skipped

**`action` per part:**
- `"keep"` — write this range as a new note
- `"discard"` — omit; range recorded in report

**`from_ts` / `to_ts`**: HH:MM:SS strings matching timestamps in the source
transcript. The boundary is `[from_ts, to_ts)` — a line at exactly `to_ts`
belongs to the next part. Use `"00:00:00"` for the recording start and the
last transcript timestamp + 1 second for the recording end.

---

## `apply` behavior

For each confirmed partition the `apply` command:

- **Kept parts**: writes `YYYY/MM/YYYY-MM-DD-<slug>.md` with:
  - Frontmatter: same `content_hash`, `source`, `source_type`, `model`, `type`
    as the original, plus `split_part: N/M` and `split_range: HH:MM:SS-HH:MM:SS`
    (original timeline positions).
  - Timestamps: rebased to start at `[00:00:00]` for each part.
  - `time:` and `date:`: adjusted by the part's offset from the recording
    start; midnight rollover handled automatically.
  - `speakers:`: recomputed from the lines in this part's range.
  - `duration:`: recomputed from the last kept line's rebased timestamp.
  - Agent-supplied title, summary, action items, and tags.
  - `## Original notes`: included only in the one kept part where
    `include_original_notes: true`.
- **Discarded parts**: no file written; range logged in `report.json`.
- **Original note**: removed via `git rm` in a git workspace, `rm` otherwise.
  Removal only happens after all kept parts are successfully written.
- **Mtime**: each new file inherits the original note's mtime so notes sort
  chronologically in Finder.

---

## Output template for split notes

Same structure as SPEC.md's `## Output template`, with two extra frontmatter
keys:

```
---
title: <human-readable title>
date: <YYYY-MM-DD — new date after midnight-rollover if applicable>
time: <HH:MM local start time, adjusted for part offset>
duration: <e.g. 1h 5m>
type: <voice-memo | meeting | other>
speakers: [<names from this part's transcript lines only>]
model: <transcription model>
tags: [<tags for this part>]
source: <original source value — unchanged>
source_type: <file | db>
content_hash: <SHA-256 of original recording — unchanged>
split_part: <N/M>
split_range: <HH:MM:SS>-<HH:MM:SS>
---
```

---

## Reporting

After `apply`, run:

```bash
python3 scripts/run.py report
```

Summary format:

```
Applied: N
  2026/04/2026-04-27-some-meeting.md -> 2026/04/2026-04-27-q2-sales-review.md + 2026/04/2026-04-27-eng-sync.md, 1 discarded part(s)
Skipped: N
  ...
Errors: N
  ...
```

---

## Slug collision handling

If the computed slug for a split part collides with an existing file on the
same date, `-2`, `-3`, … is appended (same rule as the upstream skills'
`disambiguate_slug`).

---

## Known limitations

- **No segment end times.** Gap sizes are measured start-to-start. A long
  monologue immediately before a break slightly inflates the apparent
  continuity; part durations are approximate (measured to the last kept
  line's start, not end).
- **Upstream skill regeneration.** If a MacWhisper transcript edit causes the
  upstream skill to regenerate the merged source note, that note will be
  re-flagged by `scan`. Re-run this skill to re-split it.
- **Single-speaker notes.** T2 (speaker turnover) is skipped for notes with
  no speaker labels. T1 and T3/T4 still run.
