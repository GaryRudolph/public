# personal-whisper-to-markdown — Claude Cowork setup

Install / wiring guide for running the **file-source** skill from Claude Cowork
(or any Claude-Code-based harness). Behavioral spec lives in
[`SPEC.md`](./SPEC.md); this doc only covers the harness-specific glue.

The companion DB-source skill has its own install guide:
[`../personal-whisper-to-markdown-db/COWORK.md`](../personal-whisper-to-markdown-db/COWORK.md).
See *Related skill* at the bottom for when to pick one vs. the other.

## 1. Workspace

Set Cowork's project / workspace path to:

```
~/Projects/personal/notes
```

This is the workspace root the skill assumes (where `whisper/`, `tags.md`, and
`YYYY/MM/` all live as siblings). Setting it here means prompts don't need to
mention paths.

## 2. File access

| Path | Access | Why |
|---|---|---|
| `~/Projects/personal/notes/` | Read + Write | Read existing notes and `tags.md`; write new notes; append to `tags.md` |
| `~/Projects/personal/notes/whisper/` | Read | `.whisper` ZIP exports (the source) |
| `~/.claude/skills/personal-whisper-to-markdown/` | Read | This skill (SKILL.md, SPEC.md, COWORK.md, `scripts/run.py`) |
| `~/.claude/skills/lib/whisper/` | Read | Shared library imported by `scripts/run.py` |
| `/tmp/whisper_plan/` | Read + Write | Per-session JSONs, content batches, lookup queue/decisions, report |

No `~/Library/` access needed — that's the DB skill's concern.

## 2a. Network permissions

The `lookup-tags propose` / `apply` step uses `WebSearch` to confirm new
person tags one at a time (e.g. is `nick` really `nick-holcomb` or
`nick-smith`?). The harness needs **`full_network`** for that pass. The
rest of the pipeline works offline; only flip on `full_network` for the
short interactive confirmation window.

## 2b. Workspace config

The skill reads optional per-workspace configuration from
`<workspace>/.whisper-config.json`. A documented template ships at
[`scripts/whisper-config.example.json`](./scripts/whisper-config.example.json).
Keys:

- `self_mic_speakers` — speaker names treated as the local-mic track for
  dedup against the diarized remote audio (default `["Microphone", "Gary"]`).
- `truncate` — per-recording manual truncation (key = MacWhisper session
  UUID or `.whisper` filename, value `{ "after_ms": ..., "note": "..." }`).
  Useful when a recording was left running past the actual meeting.

The file is optional; absence means "use defaults". See SPEC.md
"Self-mic segment de-duplication" and "Manual truncation" for the
exact semantics.

## 3. One-off prompts

The skill's description includes trigger phrasing for auto-discovery:

> "Process the new whisper files in my notes."

> "Convert my MacWhisper transcripts to Markdown notes."

> "Sync my whisper folder."

For explicit invocation:

> "Use `personal-whisper-to-markdown` against the `whisper/` folder. Report a
> short summary."

## 4. First-run prompt

Use this verbatim the first time, so the schema check is reviewable before the
agent processes a full batch:

> "Use `personal-whisper-to-markdown` to inspect one `.whisper` file's
> `metadata.json` schema, report what you found, and then process just ONE
> additional recording end-to-end. Stop and show me the resulting note. Do
> NOT process the full batch yet."

If that looks right, run the unconstrained version.

## 5. Scheduled (recurring)

| Schedule | Prompt | Why |
|---|---|---|
| Daily at 7am | "Run `personal-whisper-to-markdown` against the `whisper/` folder. Report a short summary." | Batches `.whisper` exports from the previous day |

Why daily and not hourly: `.whisper` files are only created when you explicitly
hit Export in MacWhisper, so they don't accumulate fast. A daily cadence catches
exports of yesterday's recordings without paying the per-run cost more than
needed.

## 6. Model

**Default: Claude Sonnet 4.6.** This is `[exec]`-tier work per the personal
model-tier rubric — cross-file, judgment-heavy on titles / summaries / action
items / tag selection, but not architectural.

| Use case | Model |
|---|---|
| Default scheduled runs and one-off invocations | **Sonnet** |
| First-run schema confirmation + spot-check (one time) | **Opus** for the bootstrap, then drop to Sonnet |
| Triage on throwaway voice memos | Sonnet (Haiku will pad tags and invent action items) |

Per-run cost on a typical 30-min meeting: ~$0.03 on Sonnet vs ~$0.15 on Opus
vs ~$0.005 on Haiku. The Sonnet premium over Haiku pays for noticeably
better titles, fewer padded tags, and accurate action-item extraction. The
Opus premium over Sonnet is not justified for routine note generation.

## 7. Expected run summary

Per [`SPEC.md`](./SPEC.md) "Reporting":

- Created: N
- Regenerated: N (transcript or speaker changes after re-export)
- Historical replaced: N — with `old → new` paths
- Ambiguous (skipped): N
- Unparseable: N
- Tag vocabulary changes: any tags appended to `tags.md`

## 8. Sanity bookmark

Smoke-tested on install:

- `~/Projects/personal/notes/2026/05/2026-05-27-microphone-test.md` (voice memo)
- `~/Projects/personal/notes/2026/04/2026-04-27-team-sync.md` (Zoom meeting)

`content_hash` cross-source match was also verified against the DB skill — the
same recording from either source produces an identical hash, so switching
between skills does not duplicate notes.

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Notes generated under today's date instead of recording date | Skill is using mtime instead of `metadata.json` `dateCreated` | Confirm SPEC.md "Folder layout" is being followed — date comes from `dateCreated` (Mac Absolute Time), not the filesystem |
| `Microphone` speaker shows up in meeting notes | De-duplication step skipped | See SPEC.md "Segment de-duplication" — meetings drop `Microphone`-named segments |
| Speaker rename in MacWhisper not picked up | The `.whisper` file you exported is stale | Re-export from MacWhisper, then run the skill — OR use the DB skill (no re-export needed) |
| Same recording duplicated after switching from DB skill | `content_hash` extraction is asymmetric | Inspect both canonical dicts; should serialize byte-identical with `sort_keys=True` |
| `metadata.json` missing keys | MacWhisper version drift | Re-run the first-run schema confirmation prompt to see what changed |

## Related skill: when to also use the DB skill

The DB skill (`personal-whisper-to-markdown-db`) operates on the same workspace
and produces identical output, but reads MacWhisper's live SQLite directly. Use
it instead of (or alongside) this skill when:

- You don't want to re-export `.whisper` files after every speaker rename
- You want hourly catch-up runs while you're working
- You want to track recordings even after you delete them from MacWhisper (only
  this file skill keeps a copy of the export; the DB drops deleted sessions)

This skill is still useful for processing archived `.whisper` exports of
recordings that no longer exist in the live DB. The two skills don't conflict:
matching `content_hash` short-circuits to a frontmatter-only `source` /
`source_type` rewrite, never a duplicate.
