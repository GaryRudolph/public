# Agent Extensions: Skills and Commands

This directory (and the sibling `../commands/` directory) hold agent extensions
that are distributed alongside AGENTS.md via `make install`.

```
agents/
  skills/           <- Cursor + Claude Code skills (folder per skill)
  commands/         <- Claude Code slash commands (one .md file per command)
  lib/extensions.sh <- installer for both
```

## How it works

Cursor and Claude Code discover skills and commands by scanning a directory,
but they don't support `@`-import for those files. A **symlink** serves the
same role: the source of truth stays in this repo; both harnesses read the live
file via the symlink.

`make install` creates and maintains three symlink sets:

| Source (this repo)                                | Home symlink                              | Harness          |
| ------------------------------------------------- | ----------------------------------------- | ---------------- |
| `agents/skills/<name>/`                           | `~/.cursor/skills/<name>`                 | Cursor           |
| `agents/skills/<name>/`                           | `~/.claude/skills/<name>`                 | Claude Code      |
| `agents/commands/<name>.md`                       | `~/.claude/commands/<name>.md`            | Claude Code (`/` typeahead) |

Codex CLI and Gemini CLI have no skills/commands system. Those harnesses are
covered by the AGENTS.md bullet that references these extensions.

## Naming convention

All extensions managed by this installer are prefixed `personal-`. This matches
the installer's `ORG=personal` identity (same as the block markers and the repo
path) and keeps our extensions visually distinct from anything installed by
another org-keyed installer sharing the same home directories.

## State model

The installer runs two install passes: a **unix-side pass** that always runs
against `$HOME`, and a **windows-host pass** that runs against `$WIN_HOME`
whenever WSL exposes a Windows user profile (auto-detected the same way
`blocks.sh` does it).

**Unix-side pass — symlink targets as ownership markers.** A symlink whose
resolved target falls under this repo's `skills/` or `commands/` directory is
"ours"; anything else is left untouched.

**Windows-host pass — `.personal-managed` marker files as ownership markers.**
Windows-native Cursor / Claude Code can't read WSL paths, so on the Windows
side we copy each skill directory into `%USERPROFILE%\.cursor\skills\` /
`%USERPROFILE%\.claude\skills\` / `%USERPROFILE%\.claude\commands\` and drop a
hidden `.personal-managed` file inside each managed skill directory. Managed
commands get a `<name>.md.personal-managed` sidecar next to the `.md` file.
Anything without the marker is foreign content and is left untouched.

For each pass, `make install` runs:

1. **Orphan cleanup** — remove any of our entries whose source folder/file no
   longer exists in the repo. This is how deleted skills clean themselves up
   automatically. (Unix: by symlink target. Windows: by marker file.)
2. **Source reconcile** — for each current source, ensure the destination
   exists and matches the source. On Windows, the reconcile pass diffs source
   vs. destination (excluding the marker) and only re-copies when content
   actually changed, so repeated `make install` is a no-op.

`make uninstall` removes every entry owned by this installer regardless of
whether the source still exists.

Trade-off: the Windows-side copies are stale until the next `make install` from
WSL. Same trade-off that `blocks.sh` already documents for its inlined Windows-
side files.

## Empirical assumptions

Both Cursor and Claude Code follow symlinks when scanning their skills and
commands directories. This is not explicitly documented by either vendor but is
empirically confirmed. If a vendor changes this behavior, only the symlink
targets need to change — the source files in this repo are unaffected.

This assumption is analogous to the two undocumented Cursor behaviors noted in
`../README.md` that the block installer relies on.

## Adding a new skill

1. Create `agents/skills/personal-<name>/SKILL.md` with frontmatter `name` and
   `description`. Name must be `personal-` prefixed, lowercase, hyphens only.
2. Run `make install` — symlinks appear automatically.
4. Run `make uninstall` then `make install` to test the round-trip.

## Removing a skill

Delete the source folder/file from the repo. Run `make install` — the orphan
cleanup pass removes the symlinks.

## Current extensions

| Name                              | Kind    | Description                                             |
| --------------------------------- | ------- | ------------------------------------------------------- |
| `personal-plan-model-tiers`            | skill   | Tag plan steps as [deep] or [exec] and insert STOP markers at tier boundaries |
| `personal-whisper-combine-db`          | skill   | Combine two MacWhisper recordings into one new session in `main.sqlite` (A then B; transcript offset; audio concatenated; sources untouched) |
| `personal-whisper-split-combine-db`    | skill   | Orchestrate split-then-combine for the overlapping-recording scenario (recording1=meeting1+head, recording2=tail); prints retain-vs-delete summary; never deletes |
| `personal-whisper-split-db`            | skill   | Split a MacWhisper recording into two sessions in `main.sqlite` (Split 1 / Split 2; transcript rebased; audio cut; original untouched) |
| `personal-whisper-to-markdown`         | skill   | Convert MacWhisper `.whisper` exports into dated Markdown notes (incremental + idempotent; replaces historical equivalents) |
| `personal-whisper-to-markdown-db`      | skill   | Same output as `personal-whisper-to-markdown` but sourced from MacWhisper's live SQLite DB (picks up speaker renames without re-export) |
