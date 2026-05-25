# AI Agent Configuration

This directory holds a home-directory installer that lets agents (Cursor,
Claude Code, Gemini CLI, Codex CLI, and the Xcode coding assistants) pick up
personal standards no matter which repository you're working in. There is
nothing for you to commit per repo — the installer never writes inside
sibling repos.

## How it works

`agents/AGENTS.md` is the canonical source of truth. The Makefile installs a
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

`make install` also manages agent extensions — skills and slash commands — via
symlinks from harness-specific home directories back to source files in this
repo. Extensions are sourced from `agents/skills/` (one folder per skill) and
`agents/commands/` (one `*.md` per command).

| Source (this repo)                          | Home symlink                              | Harness                  |
| ------------------------------------------- | ----------------------------------------- | ------------------------ |
| `agents/skills/<name>/`                     | `~/.cursor/skills/<name>`                 | Cursor                   |
| `agents/skills/<name>/`                     | `~/.claude/skills/<name>`                 | Claude Code              |
| `agents/commands/<name>.md`                 | `~/.claude/commands/<name>.md`            | Claude Code (`/` typeahead) |

Codex CLI and Gemini CLI have no skills/commands system; they are covered by
the AGENTS.md bullet that references these extensions by name.

All managed extensions are prefixed `personal-` to match the installer's
`ORG=personal` identity and to stay visually distinct from extensions installed
by other orgs (e.g., `agerpoint-*`).

### Currently managed extensions

| Name                            | Kind    | Description                                                       |
| ------------------------------- | ------- | ----------------------------------------------------------------- |
| `personal-plan-model-tiers`     | skill   | Tag plan steps as `[deep]`/`[exec]` and insert STOP markers at tier boundaries |
| `personal-plan-model-tiers`     | command | Claude Code `/personal-plan-model-tiers` typeahead handle to the skill |

### Adding or removing extensions

- **Add**: create `agents/skills/personal-<name>/SKILL.md` (and optionally
  `agents/commands/personal-<name>.md`), then run `make install`.
- **Remove**: delete the source folder/file, then run `make install`. The
  orphan-cleanup pass removes the stale symlinks automatically.
- **Full details**: see [skills/README.md](skills/README.md).

### Empirical assumption

Both Cursor and Claude Code follow symlinks when scanning their skills and
commands directories. This is not explicitly documented by either vendor but is
empirically confirmed. The same posture applies here as for the two undocumented
Cursor behaviors described below: if a vendor changes this, only the install
mechanic changes — the source files in this repo are unaffected.

## Setup

```bash
cd ~/Projects/personal/public/agents
make install      # idempotent: writes/updates blocks + installs extension symlinks
make status       # show install state for blocks and extensions
make uninstall    # remove blocks and extension symlinks
make dry-run      # preview all install actions, no disk writes
make test         # sandboxed test of install/uninstall and preservation
```

Re-run `make install` after editing `agents/AGENTS.md`. The `@`-imported
files refresh automatically; the inlined Codex block is re-rendered on
each install.

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

| Tool        | Where to ask                                                    | How standards get there                 |
| ----------- | --------------------------------------------------------------- | --------------------------------------- |
| Cursor      | Any project under `~` (ancestor walk picks up `~/AGENTS.md`)    | `@`-import from `~/AGENTS.md`           |
| Claude Code | Anywhere (CLI or extension)                                     | `~/.claude/CLAUDE.md` block             |
| Gemini CLI  | Anywhere                                                        | `~/.gemini/GEMINI.md` block             |
| Codex CLI   | Anywhere                                                        | Inlined block in `~/.codex/AGENTS.md`   |
| Xcode       | A Swift project, Coding Assistant panel                         | `~/Library/.../ClaudeAgentConfig` block |

If the canary fails, run `make status` to confirm the block is present in
the relevant home file, then run `make install` again. If the block is
present but the agent still gives a wrong answer, restart the agent — most
load configuration once on startup.

## Windows / WSL

The installer runs from inside WSL. On macOS and Linux it writes only to
`$HOME`. When `/proc/version` contains `microsoft`, a second pass also
writes to the Windows host's `%USERPROFILE%` (resolved via
`wslpath "$(cmd.exe /c 'echo %USERPROFILE%')"`).

Windows-side blocks contain the **full inlined** `AGENTS.md` content (not
`@`-imports), because Windows-native tools like `Cursor.exe` resolve `~`
to `C:\Users\<user>\` and can't easily reach the WSL checkout. Inlining
sidesteps the WSL ↔ Windows path-resolution problem.

Trade-off: the Windows-side content is stale until you re-run
`make install` from WSL after editing `agents/AGENTS.md`. The canary
phrase makes drift visible — ask the canary in a Windows-native Cursor
session; if it returns an old value, re-install from WSL.

## Coexistence with other home-dir installers

The block-marker pattern (`# >>> <name> >>>` … `# <<< <name> <<<` with a
distinctive name per installer) is self-contained: another installer
following the same pattern with a different name can manage its own block
in the same home file without conflict. This installer manages only its
own block and never reads, writes, or comments on any other content.

## Standards path layout

`agents/AGENTS.md` references standards using absolute `~/`-paths
(e.g., `~/Projects/personal/public/standards/code-style.md`). The same
paths resolve correctly through every install pathway — `@`-import
(Claude, Gemini, Cursor) or inlined (Codex, Xcode Codex, Windows host).
No path-rewrite step is needed on install.

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
