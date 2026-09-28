# Plugins

This repo is a plugin marketplace for Claude, Codex, and Cursor, with two
plugins that also work as Gemini CLI extensions. Every skill lives in exactly
one of them, and every tool reads that one copy: through its plugin system,
or through the symlinks `make install` creates.

| Tool | Marketplace | Plugin manifest |
| --- | --- | --- |
| Claude (Code, Cowork, chat) | `.claude-plugin/marketplace.json` | `plugins/<name>/.claude-plugin/plugin.json` |
| Codex / ChatGPT | `.agents/plugins/marketplace.json` | `plugins/<name>/.codex-plugin/plugin.json` |
| Cursor | `.cursor-plugin/marketplace.json` | `plugins/<name>/.cursor-plugin/plugin.json` |
| Gemini CLI | none (installed from a local path) | `plugins/<name>/gemini-extension.json` |

All four use the same `skills/<name>/SKILL.md` layout, so the manifests are
the only per-vendor files. `make -C agents test` fails if their names,
descriptions, or marketplace listings drift apart.

```
.claude-plugin/marketplace.json     <- marketplace "personal"
plugins/
  personal/                         <- portable: works anywhere Claude runs
    .claude-plugin/plugin.json  .codex-plugin/plugin.json
    .cursor-plugin/plugin.json  gemini-extension.json
    hooks/hooks.json                <- SessionStart for Claude, Codex, Gemini
    hooks/cursor-hooks.json         <- empty; keeps Cursor off hooks.json
    scripts/session-start.sh
    skills/
      personal-standards/
        SKILL.md                    <- index; loads standards on demand
        core.md                     <- always-on core (agents/AGENTS.md -> here)
        standards/                  <- full standards (repo-root standards/ -> here)
      personal-handoff/             <- handoff and saved-plan files
      personal-new-project/         <- new repos on current stable versions
      personal-secrets/             <- SOPS + age secrets repo: procedures + tested kit
      personal-plan-tag-tiers/ personal-plan-model-tiers/
      personal-plan-orchestrate/ personal-makefile/
  personal-workstation/             <- needs this Mac's files
    .claude-plugin/  .codex-plugin/  .cursor-plugin/  gemini-extension.json
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
- **One hook file, three dialects.** Claude Code, Codex, and Gemini read
  `hooks/hooks.json` in the same shape. The command uses
  `${CLAUDE_PLUGIN_ROOT:-${extensionPath}}`: Claude and Codex export the
  first, and Gemini substitutes the second. `session-start.sh` prints plain
  text for Claude and Codex and a single JSON object for Gemini, which
  rejects anything else. Cursor's hook format differs, so its manifest points
  at the empty `hooks/cursor-hooks.json` instead.
- **No `version` field** in the Claude, Codex, or Cursor manifests. Without one, the version is the commit SHA, so
  every push to `main` is an update. Pin a version only if you want to hold
  everyone on a release.
- **Cite files relative to the skill.** Use `../personal-standards/standards/<file>`,
  not `~/Projects/...`, so the path works in the plugin cache and through
  `~/.agents/skills` symlinks.

## Surfaces and what they load

| Surface | Skills | Always-on core | How it gets the plugin |
| --- | --- | --- | --- |
| Claude Code, this Mac | Yes | Hook (the old `~/.claude/CLAUDE.md` block is removed by `make install`) | Local marketplace for live edits, or claude.ai sync |
| Claude Code cloud and self-hosted runner | Yes | Hook | claude.ai sync |
| Cowork | Yes | Hook | claude.ai account |
| Claude chat | Yes | None (chat ignores hooks) | claude.ai account |
| Codex CLI / ChatGPT | Yes | Hook, or the `~/.codex/AGENTS.md` block | `codex plugin marketplace add GaryRudolph/public`, or `~/.agents/skills` |
| Cursor, including Cloud Agents | Yes | `~/AGENTS.md` on the Mac only | Customize > From GitHub Repository, or `~/.cursor/skills` |
| Gemini CLI | Yes | Hook, or the `~/.gemini/GEMINI.md` block | `gemini extensions link <path>`, or `~/.agents/skills` |

On the Mac, pick one route per tool. Codex and Cursor don't merge two copies
of a skill with the same name, so installing their plugin on top of the
`make install` symlinks shows each skill twice. Gemini does: user skills
(the symlinks) override extension skills.

## Adding a skill

1. Create `plugins/personal/skills/personal-<name>/SKILL.md` with `name` and
   `description` frontmatter. The name is lowercase with hyphens and starts
   with `personal-`. Use `personal-workstation` instead if the skill needs
   local files.
2. Keep everything the skill reads inside its own folder or its plugin.
3. Run `make -C agents validate test install`. A new plugin also needs an
   entry in all three marketplaces and all four manifests.
4. Push to `main`. Claude surfaces pick it up at their next session start.

## Removing a skill

Delete the folder, run `make -C agents install` so orphaned symlinks are
cleaned up, then push.

## Current skills

| Plugin | Skill | What it does |
| --- | --- | --- |
| `personal` | `personal-standards` | Index of the personal standards; loads core rules and topic standards on demand |
| `personal` | `personal-handoff` | Write session handoffs and saved plans to `.scratch/`, and milestone handoffs to `specs/handoffs/`, with the right names and contents |
| `personal` | `personal-new-project` | Start a new project on a boring stack at current stable versions (looked up from each registry, with EOL dates), laid out to the standards |
| `personal` | `personal-secrets` | Run a SOPS + age secrets repo: set up from a tested kit, add secrets, grant access, mint and rotate consumer keys, wire consumer CI with least privilege |
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
