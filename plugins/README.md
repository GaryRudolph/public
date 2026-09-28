# Plugins

This repo is a Claude plugin marketplace
([`../.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json))
with two plugins. Every skill lives in exactly one of them, and every tool
reads that one copy: Claude surfaces through plugin sync, local tools through
the symlinks `make install` creates.

```
.claude-plugin/marketplace.json     <- marketplace "personal"
plugins/
  personal/                         <- portable: works anywhere Claude runs
    .claude-plugin/plugin.json
    hooks/hooks.json                <- SessionStart: inject core.md
    scripts/session-start.sh
    skills/
      personal-standards/
        SKILL.md                    <- index; loads standards on demand
        core.md                     <- always-on core (agents/AGENTS.md -> here)
        standards/                  <- full standards (repo-root standards/ -> here)
      personal-plan-tag-tiers/ personal-plan-model-tiers/
      personal-plan-orchestrate/ personal-makefile/
  personal-workstation/             <- needs this Mac's files
    .claude-plugin/plugin.json
    skills/
      personal-whisper-*/ personal-allowlist-scout/
      lib/                          <- shared Python for the whisper skills
```

## Why two plugins

`personal` only needs what's inside it, so it works in a cloud VM, on the
self-hosted runner, in Cowork, and in chat. `personal-workstation` reads the
MacWhisper database, notes under `~/Projects/personal/notes`, and local
harness config files. Anywhere else it would only add skill descriptions to
every session's context, so enable it only on this Mac.

## Rules a plugin has to follow

These come from the Claude plugin loader and claude.ai. Breaking one fails
quietly on some surfaces, so `make validate` runs before every push.

- **Nothing outside the plugin folder.** Installed plugins are copied into a
  cache without anything above their root, and symlinks that point outside
  are rejected. That's why the standards live inside `personal-standards`,
  with the repo-root `standards` symlink pointing in rather than out.
- **No top-level `bin/`.** claude.ai and Cowork refuse a plugin that has one.
  Put scripts in `scripts/` and call them as `${CLAUDE_PLUGIN_ROOT}/scripts/…`.
- **Hook output is capped at 10,000 characters.** Past the cap, Claude sees
  a 2,000-character preview. `core.md` is longer, so `hooks.json` runs
  `session-start.sh` three times and each run prints one part.
- **No `version` field.** Without one, the version is the commit SHA, so
  every push to `main` is an update. Pin a version only if you want to hold
  everyone on a release.
- **Cite files relative to the skill.** Use `../personal-standards/standards/<file>`,
  not `~/Projects/...`, so the path works in the plugin cache and through
  `~/.agents/skills` symlinks.

## Surfaces and what they load

| Surface | Skills | SessionStart hook (core.md) | How it gets the plugin |
| --- | --- | --- | --- |
| Claude Code, this Mac | Yes | Skipped when `~/.claude/CLAUDE.md` has the `personal` block | claude.ai sync, or the local marketplace for live edits |
| Claude Code cloud and self-hosted runner | Yes | Yes | claude.ai sync |
| Cowork | Yes | Yes | claude.ai account |
| Claude chat | Yes | No (chat ignores hooks) | claude.ai account |
| Codex, Gemini CLI | Yes, via `~/.agents/skills` | No; they read their own `AGENTS.md`/`GEMINI.md` block | `make install` |
| Cursor | Yes, via `~/.cursor/skills` | No; reads `~/AGENTS.md` | `make install` |

## Adding a skill

1. Create `plugins/personal/skills/personal-<name>/SKILL.md` with `name` and
   `description` frontmatter. The name is lowercase with hyphens and starts
   with `personal-`. Use `personal-workstation` instead if the skill needs
   local files.
2. Keep everything the skill reads inside its own folder or its plugin.
3. Run `make -C agents validate test install`.
4. Push to `main`. Claude surfaces pick it up at their next session start.

## Removing a skill

Delete the folder, run `make -C agents install` so orphaned symlinks are
cleaned up, then push.

## Current skills

| Plugin | Skill | What it does |
| --- | --- | --- |
| `personal` | `personal-standards` | Index of the personal standards; loads core rules and topic standards on demand |
| `personal` | `personal-plan-tag-tiers` | Shared tagging layer: tag plan steps `[deep]` / `[exec]` / `[fast]` to show complexity. Tags only; the two drivers call it automatically |
| `personal` | `personal-plan-model-tiers` | Passive driver: group tagged steps into waves (no-thrash) and insert STOP markers with handoff blocks at tier boundaries |
| `personal` | `personal-plan-orchestrate` | Active driver: same tagging and waves, but delegates each wave to a subagent on the right model and pauses only at mandatory STOP gates. Cursor-only today |
| `personal` | `personal-makefile` | Audit and align Makefiles to the personal standard. Dry-run first; apply repo by repo with confirmation |
| `personal-workstation` | `personal-whisper-to-markdown` | Convert MacWhisper `.whisper` exports into dated Markdown notes (incremental, idempotent) |
| `personal-workstation` | `personal-whisper-to-markdown-db` | Same output, sourced from MacWhisper's live SQLite DB |
| `personal-workstation` | `personal-whisper-split-db` | Split a MacWhisper recording into two sessions in `main.sqlite` |
| `personal-workstation` | `personal-whisper-combine-db` | Combine two MacWhisper recordings into one new session |
| `personal-workstation` | `personal-whisper-split-combine-db` | Split-then-combine for overlapping recordings; never deletes |
| `personal-workstation` | `personal-whisper-consolidation-md` | Split a rendered whisper note that covers several meetings |
| `personal-workstation` | `personal-allowlist-scout` | Propose safe build commands missing from the per-harness allowlists, repo by repo |
