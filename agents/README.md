# AI Agent Configuration

This directory contains instruction files for AI coding agents. Each tool
(Claude Code, Codex CLI, Gemini CLI, Cursor) has its own entry point that references
shared coding standards from `standards/`.

## Files

| File | Tool | How it works |
|------|------|--------------|
| `CLAUDE.md` | Claude Code | Imports `SHARED.md` via `@` syntax |
| `GEMINI.md` | Gemini CLI | Imports `SHARED.md` via `@` syntax |
| `AGENTS.md` | Codex CLI | Inlined content (Codex does not support `@` imports) |
| `SHARED.md` | — | Common instructions (no `@` imports to standards — agents load on demand) |
| `cursor/` | Cursor | MDC files with `~` `@file` paths — symlink into `.cursor/rules/` |

## How It Works

`SHARED.md` contains core preferences inline and lists standards files by path.
Claude Code and Gemini CLI import `SHARED.md` via `@` syntax and load standards
on demand. Codex CLI gets an inlined copy in `AGENTS.md`. Cursor uses `.cursor/rules/`
MDC files with `@file` references so standards content is attached as context.

## Global Setup

Each tool reads a global config file from your home directory:

```bash
# Claude Code (~/.claude/CLAUDE.md)
echo '@~/Projects/personal/public/agents/CLAUDE.md' > ~/.claude/CLAUDE.md

# Gemini CLI (~/.gemini/GEMINI.md)
mkdir -p ~/.gemini
echo '@~/Projects/personal/public/agents/GEMINI.md' > ~/.gemini/GEMINI.md

# Codex CLI (~/.codex/AGENTS.md) — symlink since Codex lacks @ imports
mkdir -p ~/.codex
ln -s ~/Projects/personal/public/agents/AGENTS.md ~/.codex/AGENTS.md

# Cursor — no file-based global config; paste AGENTS.md content into:
# Cursor → Settings → General → Rules for AI
```

## Cursor Project Setup

Pre-built MDC files live in `agents/cursor/`. They use `~` paths for `@file`
references so they work correctly when symlinked into any project.

In each new project:

```bash
cursor-rules
```

> Requires `${HOME}/Projects/personal/public/bin` (or `${HOME}/bin`) on your `$PATH`.

| File | Applies when |
|------|-------------|
| `agents/cursor/personal-main.mdc` | Always — core preferences + general standards |
| `agents/cursor/personal-python.mdc` | `**/*.py` |
| `agents/cursor/personal-swift.mdc` | `**/*.swift` |
| `agents/cursor/personal-kotlin.mdc` | `**/*.kt` |

Add to `.gitignore` in each project to keep personal rules out of version control:

```
.cursor/rules/personal-*
```

For global Cursor rules (across all projects), paste `AGENTS.md` content into:
**Cursor → Settings → General → Rules for AI**

## Editing

Edit `SHARED.md` for shared instructions. Changes propagate to Claude Code and
Gemini CLI automatically. For Codex CLI, also update `AGENTS.md` to keep it in
sync (its content is inlined). For Cursor, update `.cursor/rules/` in each project.
