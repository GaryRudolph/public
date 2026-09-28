# AI Agent Configuration

This directory holds the home-directory installer for tools that read
personal standards from files on this machine: Cursor, Codex CLI, Gemini
CLI, Muse Code, the Xcode coding assistants, and Claude Code on this
workstation. It never writes inside sibling repos.

Claude surfaces that don't run on this machine (Claude Code cloud sessions,
the self-hosted runner, Cowork, and claude.ai chat) get the same standards
and skills from the `personal` plugin in [`../plugins/`](../plugins/README.md)
instead, synced from the claude.ai account. The
[runbook](runbook.md) covers setting that up, and
[`../specs/agent-distribution.md`](../specs/agent-distribution.md) explains
the design.

Canonical sources:

| What | Where |
| --- | --- |
| Always-on core standards | `plugins/personal/skills/personal-standards/core.md` (`agents/AGENTS.md` is a symlink to it) |
| Full standards | `plugins/personal/skills/personal-standards/standards/` (`standards/` at the repo root is a symlink to it) |
| Portable skills | `plugins/personal/skills/` |
| Mac-only skills | `plugins/personal-workstation/skills/` |

## How it works

`agents/AGENTS.md` (the core standards) is what every block points at. The Makefile installs a
single block in each shared home configuration file. Each block is delimited
by markers carrying this installer's identity (`# >>> personal >>>` …
`# <<< personal <<<`) and contains a one-line `@`-import of the source
file. For Codex (which does not support `@`-imports) the source is fully
inlined inside the block.

Anything outside the markers — including blocks written by other installers
that follow the same pattern — is preserved byte-for-byte across every
operation. The Makefile is unaware of any other installer, by design.

| Home file                          | Block contents                                                  |
| ---------------------------------- | --------------------------------------------------------------- |
| `~/.claude/CLAUDE.md`              | `@~/Projects/personal/public/agents/AGENTS.md`                  |
| `~/.gemini/GEMINI.md`              | `@~/Projects/personal/public/agents/AGENTS.md`                  |
| `~/AGENTS.md`                      | `@~/Projects/personal/public/agents/AGENTS.md` (Cursor ancestor walk) |
| `~/.codex/AGENTS.md`               | Inlined copy of `agents/AGENTS.md`                              |
| Xcode pair (when Xcode is present) | Same pattern (Claude=`@`-import, Codex=inlined)                 |

## Extensions (skills and commands)

`make install` also symlinks every skill folder under `plugins/*/skills/`
into each skills directory a local tool scans. Under WSL it copies them to
the Windows side as well.

| Home entry (symlink) | Windows side (copy via WSL) | Read by |
| --- | --- | --- |
| `~/.cursor/skills/<name>` | `%USERPROFILE%\.cursor\skills\<name>` | Cursor (also synced to Cursor Cloud Agents when **Sync Skills for Cloud Agents** is on) |
| `~/.agents/skills/<name>` | `%USERPROFILE%\.agents\skills\<name>` | Codex CLI, Gemini CLI (`~/.agents/skills` alias); Muse Code unconfirmed, see runbook |
| `~/.claude/skills/<name>` | `%USERPROFILE%\.claude\skills\<name>` | Claude Code, only when `CLAUDE_SKILLS_MODE=symlink` |
| `~/.claude/commands/<name>.md` | `%USERPROFILE%\.claude\commands\<name>.md` | Claude Code; sourced from `agents/commands/` (none today) |

`CLAUDE_SKILLS_MODE` defaults to `plugin`. In that mode Claude Code gets the
skills from the synced `personal` plugins, and `make install` removes any
`~/.claude/skills` symlinks this installer made earlier, so the same skill
doesn't load twice. Set `CLAUDE_SKILLS_MODE=symlink` to go back.

Symlinks that still point at the old `agents/skills/` location are swept
automatically (`LEGACY_SKILLS_SRC`) before new links are made.

All managed skills are prefixed `personal-` to match the installer's
`ORG=personal` identity and to stay distinct from anything another org-keyed
installer puts in the same directories.

Ownership marker on the Windows-side copies is a hidden `.personal-managed`
file inside each managed skill directory (and a `<name>.md.personal-managed`
sidecar next to each managed command file). `make uninstall` only removes
entries with the marker, so anything you drop into those directories
yourself survives untouched.

### Adding or removing skills

- **Add**: create `plugins/personal/skills/personal-<name>/SKILL.md` (or under
  `personal-workstation` if it needs this Mac), run `make install`, and push.
  The push reaches the Claude surfaces; the install reaches local tools.
- **Remove**: delete the folder, run `make install`, and push. Orphaned
  symlinks are cleaned up automatically.
- **Full details**: see [`../plugins/README.md`](../plugins/README.md).

### Empirical assumption

Cursor, Codex, and Gemini CLI follow symlinks when scanning their
skills directories. If one stops, only the install mechanic changes; the
source files are unaffected.

## Setup

```bash
cd ~/Projects/personal/public/agents
make install      # idempotent: writes/updates blocks + installs extension symlinks
make status       # show install state for blocks and extensions
make uninstall    # remove blocks and extension symlinks
make dry-run      # preview all install actions, no disk writes
make test         # sandboxed test of install/uninstall and preservation
make validate     # validate the marketplace and plugin manifests
make package      # zip each plugin into build/plugins/ for manual upload
```

Re-run `make install` after editing `core.md`. The `@`-imported
files refresh automatically; the inlined Codex block is re-rendered on
each install. Push to `main` to update the Claude plugin everywhere else.

## v1 → v2 migration

The previous installer wrote per-project symlinks into `.cursor/rules/` of
every repo under `~/Projects`, plus a matching `.gitignore` entry. The new
installer does the migration as part of every install or uninstall — there
is no separate "upgrade" step:

- **Auto-removed**: `.cursor/rules/personal-*.mdc` symlinks and their
  matching `.gitignore` entries. Empty `.gitignore` files are deleted.

## Verification canary

After install, open any project under `~` in your agent of choice and ask:

> What is the personal canary phrase?

The expected response is the exact string from the `Verification canary`
section of [agents/AGENTS.md](AGENTS.md). A stock model with no standards
loaded cannot produce that string. A correct response confirms standards
are reaching the agent; an incorrect or generic response indicates the
install is not loaded.

| Tool | Where to ask | How standards and skills get there |
| --- | --- | --- |
| Claude Code (this Mac) | Anywhere | `~/.claude/CLAUDE.md` block; skills from the `personal` plugin |
| Claude Code cloud session | A new session on any repo | `personal` plugin synced from claude.ai: SessionStart hook injects `core.md`; skills load from the plugin |
| Claude Code on the self-hosted runner | A new session on any repo | Same as cloud: synced plugin |
| Cowork | A new task | Synced plugin (hooks and skills load) |
| Claude chat (web, desktop, mobile) | A new chat | Synced plugin, skills only (chat ignores hooks); ask it to use `personal-standards` |
| Cursor (unix) | Any project under `~` | `@`-import from `~/AGENTS.md`; skills symlinked under `~/.cursor/skills/` |
| Cursor (Windows-native) | Any project, after install from WSL | Inlined block in `%USERPROFILE%\AGENTS.md`; skills copied under `%USERPROFILE%\.cursor\skills\` |
| Gemini CLI | Anywhere | `~/.gemini/GEMINI.md` block; skills from `~/.agents/skills/` |
| Codex CLI | Anywhere | Inlined block in `~/.codex/AGENTS.md`; skills from `~/.agents/skills/` |
| Muse Code | A project | Reads the project `AGENTS.md`; skills via `muse skills import` (unconfirmed, see runbook) |
| Xcode | A Swift project, Coding Assistant panel | `~/Library/.../ClaudeAgentConfig` block (no skills system) |

If the canary fails on a local tool, run `make status` to confirm the block
is present in the relevant home file, then run `make install` again. If it
fails on a Claude surface, see the runbook's troubleshooting section. If the block is
present but the agent still gives a wrong answer, restart the agent — most
load configuration once on startup.

## Windows / WSL

The installer runs from inside WSL. On macOS and Linux it writes only to
`$HOME`. When `/proc/version` contains `microsoft`, a second pass also
writes to the Windows host's `%USERPROFILE%` (resolved via
`wslpath "$(cmd.exe /c 'echo %USERPROFILE%')"`). Both `blocks.sh` and
`extensions.sh` participate in this dual-pass; one `make install` from
inside WSL covers Windows-native tools too.

What changes mode between the two passes:

- **Blocks (unix-side, `$HOME`):** `@`-import lines that point at the WSL
  checkout (Claude / Gemini / Cursor) or fully inlined content (Codex,
  Xcode Codex).
- **Blocks (windows-side, `%USERPROFILE%`):** **always inlined** — Windows-
  native tools like `Cursor.exe` resolve `~` to `C:\Users\<user>\` and can't
  easily reach the WSL checkout, so inlining sidesteps the WSL ↔ Windows
  path-resolution problem.
- **Extensions (unix-side, `$HOME/.cursor/skills`, `$HOME/.agents/skills`,
  `$HOME/.claude/commands`):** symlinks back into this repo. Live.
- **Extensions (windows-side, `%USERPROFILE%\.cursor\skills\`, etc.):**
  full `cp -R` copies of each skill directory and command file, with a
  hidden `.personal-managed` marker as the ownership tag. Same staleness
  trade-off as the inlined blocks.

Both the inlined Windows-side blocks and the copied Windows-side extensions
are stale until you re-run `make install` from WSL. The canary phrase
makes block drift visible — ask the canary in a Windows-native Cursor
session; if it returns an old value, re-install from WSL. For extension
drift, the symptom is the skill simply not picking up your edits on the
Windows side; re-install resolves it.

`make install` from WSL is the **only** supported install path. Running it
from a native Windows shell (PowerShell, cmd) is not supported — there is
no PowerShell port.

## Coexistence with other home-dir installers

The block-marker pattern (`# >>> <name> >>>` … `# <<< <name> <<<` with a
distinctive name per installer) is self-contained: another installer
following the same pattern with a different name can manage its own block
in the same home file without conflict. This installer manages only its
own block and never reads, writes, or comments on any other content.

## Standards path layout

`core.md` references standards using absolute `~/`-paths
(e.g., `~/Projects/personal/public/standards/code-style.md`). On this machine
those resolve through the `standards` symlink at the repo root, whichever
install pathway loaded them: `@`-import (Claude, Gemini, Cursor) or inlined
(Codex, Xcode Codex, Windows host).

Everywhere else the `~` path doesn't exist. The plugin's SessionStart hook
and the `personal-standards` skill both tell the agent to read the same file
from the skill's own `standards/` directory instead. Skills cite standards
relative to themselves (`../personal-standards/standards/<file>`), which
resolves both inside the plugin and through the `~/.agents/skills` symlinks.

## Two undocumented Cursor behaviors this design relies on

Cursor's official documentation does not currently describe either of
these, but both are empirically confirmed:

1. **Ancestor walk for `AGENTS.md`** — when you open a project, Cursor
   reads `AGENTS.md` files in the project root and every ancestor
   directory, up through `~`. This is what makes `~/AGENTS.md` work as a
   "global" Cursor configuration.
2. **`@`-imports inside `AGENTS.md`** — Cursor follows `@path/to/file`
   references inside `AGENTS.md` the same way Claude Code and Gemini CLI
   do, including across files that live outside the project.

If Cursor changes either behavior, only the Cursor block's target file
(currently `~/AGENTS.md`) needs to change — the algorithm and other home
files are unaffected.
