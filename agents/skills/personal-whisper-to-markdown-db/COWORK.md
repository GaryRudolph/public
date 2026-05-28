# personal-whisper-to-markdown-db — Claude Cowork setup

Install / wiring guide for running the **DB-source** skill from Claude Cowork
(or any Claude-Code-based harness). Behavioral spec lives in
[`../personal-whisper-to-markdown/SPEC.md`](../personal-whisper-to-markdown/SPEC.md);
this doc only covers the harness-specific glue.

The companion file-source skill has its own install guide:
[`../personal-whisper-to-markdown/COWORK.md`](../personal-whisper-to-markdown/COWORK.md).
See *Related skill* at the bottom for when to pick one vs. the other.

## 1. Workspace

Set Cowork's project / workspace path to:

```
~/Projects/personal/notes
```

This is the workspace root the skill assumes (where `tags.md` and `YYYY/MM/`
live; the DB itself is read from a fixed Library path regardless of cwd). Setting
the workspace here means prompts don't need to mention output paths.

## 2. File access

| Path | Access | Why |
|---|---|---|
| `~/Projects/personal/notes/` | Read + Write | Read existing notes and `tags.md`; write new notes; append to `tags.md` |
| `~/Library/Application Support/MacWhisper/Database/` | **Read** | `main.sqlite` + `main.sqlite-shm` + `main.sqlite-wal` |
| `~/.claude/skills/personal-whisper-to-markdown-db/` | Read | This skill (SKILL.md, COWORK.md, `scripts/run.py`) |
| `~/.claude/skills/personal-whisper-to-markdown/` | Read | The shared `SPEC.md` (cross-referenced via `../personal-whisper-to-markdown/SPEC.md`) |
| `~/.claude/skills/lib/whisper/` | Read | Shared library imported by `scripts/run.py` |
| `/tmp/whisper_plan/` | Read + Write | Per-session JSONs, content batches, lookup queue/decisions, report |

No `~/Projects/personal/notes/whisper/` access needed — that's the file
skill's source folder, irrelevant for the DB skill.

## 2a. Network permissions

The `lookup-tags propose` / `apply` step uses `WebSearch` to confirm new
person tags one at a time (e.g. is `nick` really `nick-holcomb` or
`nick-smith`?). The harness needs **`full_network`** for that pass. The
rest of the pipeline works offline; only flip on `full_network` for the
short interactive confirmation window.

## 2b. Workspace config

The skill reads optional per-workspace configuration from
`<workspace>/.whisper-config.json`. A documented template ships in the
file skill at
[`../personal-whisper-to-markdown/scripts/whisper-config.example.json`](../personal-whisper-to-markdown/scripts/whisper-config.example.json).
Keys:

- `self_mic_speakers` — speaker names treated as the local-mic track for
  dedup against the diarized remote audio (default `["Microphone", "Gary"]`).
- `truncate` — per-recording manual truncation. Keys are MacWhisper session
  UUIDs (32 hex chars, no dashes) or `.whisper` filenames; value is
  `{ "after_ms": ..., "note": "..." }`. Useful when a recording was left
  running past the actual meeting.

The file is optional; absence means "use defaults". See SPEC.md
"Self-mic segment de-duplication" and "Manual truncation" for the
exact semantics.

### macOS sandbox

`~/Library/Application Support/` is gated by macOS even when Cowork has
explicit access to its workspace. If the first run fails with a permission
error reading the DB:

1. Open **System Settings → Privacy & Security → Files & Folders** (or **Full
   Disk Access**).
2. Find Cowork in the list and grant it access to the MacWhisper Library
   folder (or, more permissively, Full Disk Access).
3. Restart Cowork if the new permission doesn't take effect immediately.

### MacWhisper running concurrently

The skill must open the DB **read-only** (`sqlite3 -readonly` or
`sqlite3.connect("file:...?mode=ro", uri=True)`). The `-wal` / `-shm` sidecars
are read transparently. Never open the DB read-write — that risks corrupting
MacWhisper's state. If you see a `database is locked` error, wait briefly and
retry; do not pass `IMMEDIATE` or any write transaction.

## 3. One-off prompts

The skill's description includes trigger phrasing focused on the DB's
strengths — speaker renames, live edits, no-re-export workflows:

> "Sync my MacWhisper recordings from the database."

> "Update my whisper notes — pick up any speaker renames I made in MacWhisper."

> "Process MacWhisper recordings directly from the DB, no `.whisper` export needed."

For explicit invocation:

> "Use `personal-whisper-to-markdown-db` to scan MacWhisper for any non-deleted
> sessions, and write or update notes for them. Report a short summary."

## 4. First-run prompt

Use this verbatim the first time, so the DB connection and schema mapping are
reviewable before the agent processes the whole table:

> "Use `personal-whisper-to-markdown-db` to open MacWhisper's SQLite read-only,
> report the schema overview and the count of non-deleted sessions, and then
> process just ONE session end-to-end. Stop and show me the resulting note.
> Do NOT process the full DB yet."

If that looks right, run the unconstrained version.

## 5. Scheduled (recurring)

| Schedule | Prompt | Why |
|---|---|---|
| Hourly, 9am–7pm weekdays | "Run `personal-whisper-to-markdown-db` against MacWhisper. Report a short summary." | Catches speaker renames, transcript edits, and new sessions while you work |

Why hourly: the DB is live state, so any change you make in MacWhisper (renaming
`Speaker 4` → `Kevin`, merging two speakers, fixing a misheard word) is reflected
on the next run with no extra steps from you. Hourly is frequent enough that
edits feel instant; daily would feel slow.

If hourly is too noisy for your taste, drop to every 2–4 hours. Don't go more
frequent than every 15 minutes — the per-run overhead isn't worth it.

## 6. Model

**Default: Claude Sonnet 4.6.** This is `[exec]`-tier work per the personal
model-tier rubric — cross-file, judgment-heavy on titles / summaries / action
items / tag selection, but not architectural.

| Use case | Model |
|---|---|
| Default scheduled runs and one-off invocations | **Sonnet** |
| First-run schema confirmation + spot-check (one time) | **Opus** for the bootstrap, then drop to Sonnet |
| Triage on throwaway voice memos | Sonnet (Haiku will pad tags and invent action items) |

Hourly scheduling cost note: most hourly runs find no changes and exit cheaply
regardless of model. Only the runs that actually generate or regenerate a note
incur material cost. Typical 30-min meeting note: ~$0.03 on Sonnet, ~$0.15 on
Opus, ~$0.005 on Haiku. Sonnet's premium over Haiku is worth it for
materially better titles, less-padded tags, and accurate action items. Opus's
premium over Sonnet is not justified for routine note generation.

## 7. Expected run summary

Per [SPEC.md "Reporting"](../personal-whisper-to-markdown/SPEC.md) plus the
DB-skill-specific addition:

- Created: N
- Regenerated: N (transcript or speaker changes — the main DB-skill use case)
- Historical replaced: N — with `old → new` paths
- Ambiguous (skipped): N
- Unparseable: N
- Tag vocabulary changes: any tags appended to `tags.md`
- **DB connection:** path of the DB, total non-deleted sessions, how many were
  considered for processing

## 8. Sanity bookmark

Cross-source `content_hash` match was verified between the DB skill and the
file skill for recording `d9393ef207004356bd779b90e2336a82`
(`Test.whisper` / `2026-05-27-microphone-test.md`). Both produced:

```
d763366ebba544ad4cb3cb38c790ab73b4be790be976901afbbaad6a3f3bb084
```

This confirms that if you've run the file skill previously, switching to the DB
skill will not create duplicate notes — it'll just update each existing note's
`source:` / `source_type:` frontmatter and move on.

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `permission denied` opening DB | macOS sandbox blocking Cowork from `~/Library/` | Grant Files & Folders or Full Disk Access in System Settings |
| `database is locked` | MacWhisper holding a writer lock momentarily | Retry — skill should already open read-only; check it isn't accidentally write-mode |
| Note shows `Speaker 4` even after I renamed it to a real name | Skill ran before the rename, or rename wasn't saved in MacWhisper yet | Re-run; confirm MacWhisper has flushed the rename to disk (close the recording panel) |
| Duplicate notes after switching from file skill | `content_hash` mismatch between sources | Both should produce identical canonical dicts; check date format (UTC ISO with milliseconds), segment ordering, and `Microphone` de-dup |
| Recording deleted from MacWhisper trashed my note too | Skill is honoring `dateDeleted IS NULL` correctly, but it won't re-create notes for deleted sessions | Use the file skill against your archived `.whisper` export to recover |
| Hourly run is creating churn in git | Most runs find no changes and produce empty diffs, but `mtime` updates can show up | Run summary's "Created / Regenerated" counts of 0/0 mean the skill is being a good citizen — only frontmatter / body content matters |

## Related skill: when to also use the file skill

The file skill (`personal-whisper-to-markdown`) operates on the same workspace
and produces identical output, but reads `.whisper` ZIP exports from
`<workspace>/whisper/`. Use it alongside this skill when:

- You want a copy of the transcript that survives deleting the recording from
  MacWhisper (the DB drops deleted sessions; `.whisper` exports persist
  independently)
- You're processing recordings from a different machine where you only have the
  export, not the live DB
- You want to verify a recording's `content_hash` matches across both sources

The two skills don't conflict: matching `content_hash` short-circuits to a
frontmatter-only `source` / `source_type` rewrite, never a duplicate.
