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
path) and keeps our extensions visually distinct from those installed by other
orgs (e.g., `agerpoint-*`).

## State model

The installer uses **symlink targets as ownership markers** — no sidecar
manifest. A symlink whose resolved target falls under this repo's `skills/` or
`commands/` directory is "ours"; anything else is left untouched.

`make install` runs two passes per destination:

1. **Orphan cleanup** — remove any of our symlinks whose source folder/file no
   longer exists in the repo. This is how deleted skills clean themselves up
   automatically.
2. **Source reconcile** — for each current source, ensure the symlink exists
   and points to the right place.

`make uninstall` removes every symlink owned by this installer regardless of
whether the source still exists.

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

| Name                          | Kind    | Description                                             |
| ----------------------------- | ------- | ------------------------------------------------------- |
| `personal-plan-model-tiers`   | skill   | Tag plan steps as [deep] or [exec] and insert STOP markers at tier boundaries |
