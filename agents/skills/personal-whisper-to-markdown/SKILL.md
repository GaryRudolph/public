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
decision tree, historical equivalents, title/slug rules, output template, tag
vocabulary, and reporting format. This file adds file-source specifics only.

For Cowork install (workspace, file access, prompts, scheduling), see
[`./COWORK.md`](./COWORK.md).

## Source: .whisper ZIP archives

A `.whisper` file is a **ZIP archive** (not a raw JSON file) containing three
entries:

```
metadata.json    # the transcript and metadata — this is what we read
originalAudio    # raw audio bytes — ignore; we never re-transcribe
version          # format version string (e.g. "2")
```

Extract `metadata.json` to a temp directory and parse it as JSON. Never read,
decode, or transcribe `originalAudio`. MacWhisper has already done the
transcription; re-running speech-to-text is wasteful and risks producing
different results than what the user sees in MacWhisper.

The `source:` frontmatter value is the `.whisper` filename (e.g.
`Meeting - Zoom 2026-04-27 07_32_47.whisper`). The `source_type:` value is `file`.

### metadata.json schema (version 2)

Top-level fields used by this skill:

| Field | Meaning |
|---|---|
| `dateCreated` | Recording start time in **Mac Absolute Time** (seconds since 2001-01-01 00:00:00 UTC). Convert: `datetime(2001,1,1,tzinfo=UTC) + timedelta(seconds=dateCreated)`. |
| `dateUpdated` | Last edit time, same format. |
| `originalMediaFilename` | Often empty; falls back to filename for hints. |
| `modelEngine` | e.g. `parakeetKitPro` |
| `modelQualityID` | e.g. `nvidia_parakeet-v3` — use this as the `model:` frontmatter value (more specific). |
| `detectedLanguageRaw` | e.g. `en` |
| `speakers` | Array of `{id, name, color}`. Names are uppercase-with-dashes UUIDs. May include both `"Microphone"` and `"Speaker 1..N"` for meetings; see SPEC.md for de-duplication. |
| `transcripts` | Array of segments — see below. |
| `startTimeOffset` | Usually 0. |
| `wasTranslatedToEnglish` | Boolean. |

Segment (entry in `transcripts`):

| Field | Meaning |
|---|---|
| `id` | UUID string (uppercase with dashes). |
| `start`, `end` | Integer milliseconds since recording start. |
| `text` | Segment text. |
| `speaker` | Nested `{id, name, color}` if diarized; absent for voice memos. |
| `words` | Per-word timings (ignore — not needed for canonical output). |
| `favorited`, `unEven` | UI state (ignore). |

### Session type inference

The filename and originalMediaFilename hint at type:

- Filename starts with `Meeting - ` (e.g. `Meeting - Chrome ...`, `Meeting - Zoom ...`) → `meeting`. The substring after `Meeting - ` is the source app (Chrome, Slack, Teams, Webex, Zoom).
- `originalMediaFilename` is `"Voice Memo"` or empty + no `Meeting - ` prefix → `voice-memo`.
- Otherwise → `other`.

### First-run sanity check

The schema can shift between MacWhisper versions. Before processing a batch
for the first time (or when output is empty/garbled), inspect one file's
`metadata.json` and confirm the keys listed above still exist. Report briefly
what you found, then proceed. Degrade gracefully if per-segment timestamps or
speakers are absent.
