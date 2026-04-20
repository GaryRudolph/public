# AI Agent Configuration

This directory contains instruction files for AI coding agents. Each tool
(Claude Code, Codex CLI, Gemini CLI, Cursor, Xcode) has its own entry point
that references shared coding standards from `standards/`.

## Files

| File | Tool | How it works |
|------|------|--------------|
| `CLAUDE.md` | Claude Code, Xcode Claude Agent | Imports `SHARED.md` via `@` syntax |
| `GEMINI.md` | Gemini CLI | Imports `SHARED.md` via `@` syntax |
| `AGENTS.md` | Codex CLI, Xcode Codex | Inlined content (no `@` imports) |
| `SHARED.md` | — | Common instructions (agents load standards on demand) |
| `cursor/` | Cursor | MDC files with `~` `@file` paths |

## How It Works

`SHARED.md` contains core preferences inline and lists standards files by path.
Claude Code and Gemini CLI import `SHARED.md` via `@` syntax and load standards
on demand. Codex CLI gets an inlined copy in `AGENTS.md`. Cursor uses `.cursor/rules/`
MDC files with `@file` references so standards content is attached as context.
Xcode's built-in Claude Agent and Codex read from their own config directories
using the same files.

## Setup

A `Makefile` in this directory handles all installation:

```bash
cd ~/Projects/personal/public/agents
make install    # set up all global configs + cursor rules in every git repo under ~/Projects
make uninstall  # remove everything
make status     # show what's currently installed
make test       # run automated tests against fixture repos
```

Override the projects scan directory via environment variable:

```bash
PROJECTS_DIR=~/Code make install
```

### What `make install` configures

| Target | Location | Method |
|--------|----------|--------|
| Claude Code | `~/.claude/CLAUDE.md` | Writes `@` import |
| Gemini CLI | `~/.gemini/GEMINI.md` | Writes `@` import |
| Codex CLI | `~/.codex/AGENTS.md` | Symlink to `agents/AGENTS.md` |
| Xcode Claude Agent | `~/Library/Developer/Xcode/CodingAssistant/ClaudeAgentConfig/CLAUDE.md` | Writes `@` import |
| Xcode Codex | `~/Library/Developer/Xcode/CodingAssistant/codex/AGENTS.md` | Symlink to `agents/AGENTS.md` |
| Cursor (per-project) | `.cursor/rules/personal-*.mdc` in each git repo | Symlinks to `agents/cursor/*.mdc` |

Xcode targets are skipped if Xcode is not installed. Cursor targets are skipped
if Cursor is not installed. Re-running `make install` is safe and incremental.

### Cursor rules

| File | Applies when |
|------|-------------|
| `cursor/personal-main.mdc` | Always — core preferences + general standards |
| `cursor/personal-python.mdc` | `**/*.py` |
| `cursor/personal-swift.mdc` | `**/*.swift` |
| `cursor/personal-kotlin.mdc` | `**/*.kt` |

`make install` automatically adds `.cursor/rules/personal-*.mdc` to each project's
`.gitignore` to keep personal rules out of version control.

## Editing

Edit `SHARED.md` — it's the single source of truth. Changes propagate to
Claude Code, Gemini CLI, and Xcode Claude Agent automatically (they chain
through `@` imports). `AGENTS.md` is a generated, inlined copy for Codex CLI
and Xcode Codex (Codex does not support `@` imports).

Regenerate `AGENTS.md` after editing `SHARED.md`:

```bash
make sync
```

`make install` runs `sync` automatically, and `make test` runs `sync-check`
which fails if `AGENTS.md` is out of date — so the two files cannot silently
drift apart.
