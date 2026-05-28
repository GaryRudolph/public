# Whisper to Markdown — canonical spec

Shared behavior for `personal-whisper-to-markdown` (file source) and
`personal-whisper-to-markdown-db` (DB source). Each SKILL.md wraps this spec
and adds its own source-specific guidance only.

## Folder layout

The workspace root contains `whisper/` and dated output folders as siblings:

```
<workspace root>/
├── whisper/                      # MacWhisper auto-exports .whisper files here
└── YYYY/
    └── MM/
        └── YYYY-MM-DD-<slug>.md  # generated note, filed by RECORDING date
```

`YYYY`, `MM`, and the date in the filename always come from the recording's own
timestamp inside the source data — never from today's date or the file's
modification time. Create year/month directories as needed.

## Canonical recording structure

Both the file and DB skills extract a recording into the same canonical
Python-style dict before doing any work:

```
{
  "date":     <ISO 8601 UTC timestamp of the recording start, millisecond precision>,
  "speakers": <sorted list of unique speaker names>,
  "segments": [
    {
      "start_ms": <int>,
      "end_ms":   <int>,
      "speaker":  <name or null>,
      "text":     <utterance text, whitespace-stripped>,
    },
    ...   # sorted by (start_ms, end_ms) ascending
  ],
}
```

Each source-specific SKILL.md is responsible for producing this structure from
its source. Once produced, everything downstream (hashing, template generation,
historical comparison) is identical.

**No top-level `recording_id`.** Different sources surface different identifiers
(`session.id` UUID from the DB, no equivalent in `.whisper` files), and the
`content_hash` already serves as a unique recording identity. Origin lives in
the `source:` and `source_type:` frontmatter fields, not in the canonical
structure.

**Self-mic segment de-duplication.** MacWhisper captures meetings via two
parallel audio paths: the user's local microphone (which appears in MacWhisper
as a single `"Microphone"` speaker, unless the user has renamed it) and the
diarized remote audio (`"Speaker 1"`, `"Speaker 2"`, etc., or renamed). When
both paths are present, the same utterance is transcribed twice with nearly
identical timings — once on the local track, once on the diarized remote.

The dedup rule:

1. The set of *self-mic speakers* is configurable per workspace via
   `<workspace>/.whisper-config.json` (key `self_mic_speakers`, default
   `["Microphone", "Gary"]`). This generalization is necessary because users
   commonly rename the local-mic track to their own name inside MacWhisper
   (e.g. `"Microphone"` → `"Gary"`); without the rename, a literal `name ==
   "Microphone"` rule misses every renamed self segment.
2. For each segment whose speaker is in the self-mic list, drop it iff a
   non-self speaker has a segment within +/- 2.5 seconds whose text similarity
   (via `difflib.SequenceMatcher`) is >= 0.7.
3. If a recording contains **only** self-mic speakers (e.g. a solo voice
   memo where the local track is the only signal), the dedup is skipped
   and all segments are kept. This covers the voice-memo case.

The dedup happens before `content_hash` is computed, so user-driven changes
to the self-mic list (or to MacWhisper speaker names) propagate through the
hash → trigger regeneration as designed.

**Stub speakers.** MacWhisper assigns generic `"Speaker N"` names until the
user renames them. Treat these as valid speaker labels — they're stable
identifiers for hashing purposes. Speaker renames in MacWhisper change the
canonical structure and therefore change `content_hash`, triggering a
regeneration as designed.

## Manual truncation

Some recordings end up much longer than the meeting they captured — a Zoom
window left open after a 30-minute call may accumulate hours of ambient
laptop audio. To trim them without editing inside MacWhisper, place a
truncate rule in `<workspace>/.whisper-config.json`:

```json
{
  "truncate": {
    "6b8f97a8e5cd44238b61397a6c79c14e": { "after_ms": 2030000,
      "note": "left recording running" }
  }
}
```

Keys may be either the MacWhisper session UUID (32 hex characters, no dashes
— from the DB skill) or the `.whisper` filename (file skill). The runner
checks both. Every segment whose `start_ms` is at or after `after_ms` is
dropped, and the rendered note's `duration` is recomputed from the last
surviving segment's `end_ms`. Truncation is applied **after** self-mic
dedup, so `after_ms` values reflect timestamps you actually see in the
rendered transcript.

See `personal-whisper-to-markdown/scripts/whisper-config.example.json` for
a documented template.

## Content hash

`content_hash` is a SHA-256 over the canonical recording structure, serialized
as JSON with sorted keys and no extra whitespace:

```python
import hashlib, json

def content_hash(recording: dict) -> str:
    payload = json.dumps(
        recording, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

Because both skills produce the same canonical structure for the same recording
state, they produce the same `content_hash`. This is the idempotency key.

Speaker renames, speaker curation (merging two MacWhisper-assigned speakers),
and transcript edits all change the canonical structure → hash differs → both
skills regenerate the note. Cosmetic-only changes (file mtime, audio sidecar,
MacWhisper UI state) do not change the hash.

If a note already exists at the canonical path with the same `content_hash` but
a different `source` / `source_type` than the current run, do not regenerate —
instead update only the `source` and `source_type` fields in the existing
frontmatter to record the current origin, leaving body and `content_hash`
untouched. This lets the user switch between the file and DB skills without
producing duplicates.

## What to process each run

For every source recording, determine the action:

1. **No existing note and no historical equivalent** → generate at the
   canonical path `YYYY/MM/YYYY-MM-DD-<slug>.md`. (Before concluding there is
   no historical equivalent, see *Historical equivalents* below.)
2. **Existing note with matching `content_hash`** → skip (unchanged).
3. **Existing note with different `content_hash`** → regenerate in place
   (transcript was edited in MacWhisper).
4. **Historical equivalent found** → replace it (see *Historical equivalents*).

After writing or overwriting a note, set its filesystem modification time to
the source file's mtime so notes sort chronologically in Finder:

```
touch -r "whisper/<source>.whisper" "YYYY/MM/YYYY-MM-DD-<slug>.md"
```

## Pipeline (content-aware planner)

Both skills implement the canonical-build and write logic in
`skills/lib/whisper/` and expose it via a per-skill `scripts/run.py` with
the following subcommands:

```
plan                  build/refresh per-session JSONs from source +
                      overlay any content_*.json that already exists
merge                 reconcile raw tags across content batches against
                      the workspace vocabulary
lookup-tags propose   emit lookup_queue.json for the agent's WebSearch +
                      AskQuestion confirmation pass
lookup-tags apply     write the agent's decisions back into per-session
                      JSONs and append to tags.md
write                 decision tree → render → write at the FINAL path
report                print the run summary
```

`plan` is **content-aware and idempotent**. It is always run twice in the
standard flow:

1. First call: provisional title from the source (MacWhisper title / filename),
   provisional slug, canonical structure, `content_hash`. Per-session JSON
   written to `/tmp/whisper_plan/sessions/<key>.json`.
2. Content generation step (inline for a single recording or via Sonnet
   subagents for larger batches) writes `content_<batch>.json` files with
   the final titles, summaries, action items, and proposed tags.
3. Second call: re-reads source, **and** overlays the content_*.json files
   on top, so the final slug — and therefore the final path — is computed
   from the *final* title. Both calls write to the same per-session JSON,
   so the path in `plan.json` and the path in each per-session JSON never
   disagree. This eliminates the slug-then-reslug architecture and the
   duplicate-file class of bugs that came with it.

Subagents are pure content producers — they read per-session JSON files
(including `canonical.segments` for the transcript and `historical.body`
when a hand-written equivalent matched), emit one or more
`content_<batch>.json` files, and never edit scripts or move files. The
agent never needs to derive plan/write/merge logic from scratch.

## Historical equivalents

Before generating a brand-new note (case 1 above), check whether a pre-existing
Markdown file already covers the same recording. These may be hand-written notes,
exports from another tool, or earlier transcripts in a different format — they
will not have our frontmatter and may not follow our template.

**Search scope.** Only look at files matching `YYYY/MM/YYYY-MM-DD-*.md` where
`YYYY-MM-DD` is the recording date. Do not scan the rest of the workspace. If
that directory does not exist, there are no candidates; skip this step.

**Classify each candidate by frontmatter:**

- Has `content_hash` matching the current recording → already tracked;
  handled by the standard idempotency path (case 2/3 above). Not historical.
- Has `content_hash` pointing to a *different* recording → belongs to
  another recording; ignore.
- No `content_hash` (no frontmatter, frontmatter without our keys, or an
  arbitrary historical format) → **historical candidate**.

**Similarity check.** Read the candidate body (strip any leading
`---`-delimited frontmatter block if present; otherwise use the whole file).
Normalize both the candidate and the new transcript text:

- Lowercase; collapse all whitespace.
- Strip `[HH:MM:SS]` timestamp prefixes.
- Strip `Speaker N:` / known-name prefixes.

Split the normalized *new-transcript* text into sentence-like chunks of ≥ 6
words. Compute the fraction of those chunks that appear as substrings in the
normalized candidate (tolerating minor whitespace drift).

**Threshold: ≥ 70%.** Only a clear majority-overlap counts. This avoids
replacing unrelated notes that happen to share a date while still catching the
same recording in any reasonable historical format.

**On exactly one match:** do *not* silently replace. Instead:

1. Extract the hand-written body (strip leading `---` frontmatter if any).
2. Pass it to the summary-generation step as **additional input** to the
   subagent prompt — not as authoritative truth. The exact prompt language
   is: *"The user wrote these notes around the time of the meeting. Treat
   them as one more signal — they may flag decisions, side observations,
   follow-ups they cared about, or just personal reactions. There are many
   reasons something might have been written down. The transcript remains
   the source of truth for what was said; let the notes inform what to
   emphasize, not override the transcript."*
3. In the rendered note, the hand-written body is preserved verbatim as a
   blockquote under a new `## Original notes` section between Action Items
   and Transcript (see the template below).
4. Write the canonical `YYYY/MM/YYYY-MM-DD-<slug>.md` and delete the matched
   historical file via `git rm` (in a git workspace) or `rm`. If the
   canonical path is already identical to the historical path, just
   overwrite in place. Apply `touch -r` to the source mtime. Include
   `old/path.md → new/path.md` in the run summary.

**On multiple matches:** do not overwrite anything. List all candidate paths in
the run summary and skip this recording — let the user resolve manually.

**On zero matches:** proceed to generate at the canonical path (case 1).

## Title and slug

Branch on the number of **distinct speakers** in the transcript.

- **1 speaker** — generate a concise descriptive title from the content.
- **2 speakers** — if the *other* party is identified by name, lead with that
  person (e.g. "Call with Jane Doe"). Otherwise generate from content.
- **3+ speakers** — synthesize a descriptive title from the content. Do not
  lead with a single person's name.

**Never use "Gary" (or variants) in the title or slug.** Gary is the workspace
owner and is implicitly present in every recording — naming the title after him
adds no information. For 2-speaker recordings, lead with the *other* party's
name; if Gary is the only identified speaker, fall back to a content-based
title.

Prefer a meaningful MacWhisper-provided title when it genuinely describes the
content; replace when empty or unhelpful (e.g. "Test").

**Slug rules:** lowercase; spaces → hyphens; keep only `a–z`, `0–9`, `-`;
collapse repeated hyphens; trim edges; cap ~60 chars at a word boundary. Append
`-2`, `-3` for same-date collisions.

## Output template

Use this exact structure for every generated note:

```
---
title: <human-readable title>
date: <YYYY-MM-DD recording date>
time: <HH:MM local start time, if available>
duration: <e.g. 12m 30s, if available>
type: <voice-memo | meeting | other>
speakers: [<name or "Speaker 1">, ...]
model: <transcription model, e.g. nvidia_parakeet-v2>
tags: [<1-20 proposed topical tags>]
source: <original .whisper filename | macwhisper-db:<recording-uuid>>
source_type: <file | db>
content_hash: <SHA-256 of canonical recording structure>
---

# <title>

## Summary

<3-5 sentence summary in your own words>

## Action Items

- <action item>

## Original notes

> <verbatim hand-written body from the matched historical file>

## Transcript

[HH:MM:SS] <Speaker>: <line of transcript>
```

Section rules:

- **Summary and Action Items** are generated from the transcript — write in
  your own words, do not copy transcript sentences verbatim.
- **Omit Action Items** entirely if there are no concrete follow-ups.
- **Original notes** appears *only* when a historical equivalent (≥ 70%
  overlap) was matched. Render the candidate's body verbatim inside a
  Markdown blockquote. Omit the section entirely when there is no match.
- **tags** — propose **1–20** lowercase, kebab-case topical tags from content.
  Quality over quantity: one good tag beats six bad ones. Each tag should be a
  real, recognizable topic that someone might search or filter by. Prefer
  short, concrete nouns; one word is the default, multi-word is fine when
  single-word would be ambiguous. See *Tag vocabulary* below for the curated
  list to draw from. Do **not** pad with verbose, awkward, or contrived tags
  (e.g. `discussion-about-the-project`, `general-meeting-notes`,
  `things-that-came-up`) just to reach a higher count. If only one or two
  genuinely useful tags exist, use only those.

  **Good examples by category:**
  - Companies/orgs: `agerpoint`, `databricks`, `muon-space`, `rain-hail`
  - Topics: `product`, `engineering`, `hiring`, `one-on-one`, `roadmap`
  - People: `jane-doe` (kebab-case `first-last` when last name known; first-only otherwise)
  - Tools/platforms: `databricks`, `github`, `azure`, `airflow`
  - Initiatives: `crop-insurance`, `ortho`, `point-cloud`
- **Transcript** — prefix each segment with `[HH:MM:SS]`. Drop prefixes if
  timestamps are unavailable. Use assigned speaker names when available; fall
  back to Speaker 1, Speaker 2, etc. For single-speaker voice memos, omit
  labels. Reproduce spoken text faithfully; do not paraphrase.

## Tag vocabulary

The workspace root may contain a `tags.md` file (or, in older notes, `labels.md`)
with a curated tag vocabulary. **Read it once at the start of each run** and use
it as the preferred tag pool.

**File lookup order:** `<workspace root>/tags.md`, then `<workspace root>/labels.md`.
If neither exists, proceed without a vocabulary and skip the rest of this section.

**Format.** The file is a Markdown document grouped by category (Companies,
Topics, People, Tools, Initiatives, etc.). Each tag appears as a bullet with the
tag in backticks followed by a short gloss:

    ## Companies / orgs
    - `agerpoint` — current employer; ag-tech drone imagery and analytics
    - `databricks` — cloud data/AI platform vendor

**How to use the vocabulary:**

1. **Prefer existing tags** when they fit the content. Match liberally (e.g. a
   meeting about Databricks usage gets `databricks` even if it's not named in
   the title).
2. **Use the gloss as additional context** to decide whether a tag fits — the
   gloss tells you the user's intended meaning, not just the token.
3. **Add new tags as needed.** If the content clearly deserves a tag that
   doesn't yet exist (and no near-synonym in the vocabulary covers it), include
   it in the note's frontmatter AND append a new bullet to the appropriate
   section of `tags.md` with a one-line gloss describing when it should apply.
4. **Enrich existing glosses.** If a recording reveals a meaningful nuance that
   the existing gloss doesn't capture (e.g. a tag turns out to cover a broader
   topic than the original gloss implied), extend the gloss with the new color.
   Keep glosses ≤ ~15 words.
5. **Never delete or rename** existing tags. The user reviews changes via git
   history; only additive edits are safe.

**Style rules for new tags:** lowercase, kebab-case, short concrete noun. One
word preferred; multi-word only when single-word is ambiguous. Match the
established style (`one-on-one` not `1-on-1`; `first-last` for people).

In the run summary, list every tag added (`+ new-tag — gloss`) and every gloss
enriched (`~ existing-tag — old gloss → new gloss`).

## Reporting

After each run, give a short summary:

- **Created:** N new notes
- **Regenerated:** N updated notes (transcript changed)
- **Historical replaced:** N — list each as `old/path.md → new/path.md`
- **Ambiguous (skipped):** N — list candidate paths for each skipped recording
- **Unparseable:** N — list filenames that could not be parsed
- **Tag vocabulary changes:** new tags added and glosses enriched (or "none")
