# AI Agent Configuration

This directory contains instruction files for AI coding agents. Each tool
(Claude Code, Codex CLI, Gemini CLI) has its own entry point that references
shared coding standards from `standards/`.

## Files

| File | Tool | How it works |
|------|------|--------------|
| `CLAUDE.md` | Claude Code | Imports `SHARED.md` via `@` syntax |
| `GEMINI.md` | Gemini CLI | Imports `SHARED.md` via `@` syntax |
| `AGENTS.md` | Codex CLI / Cursor | Inlined content (Codex does not support `@` imports) |
| `SHARED.md` | — | Common instructions with `@` imports to core standards |

## How It Works

`SHARED.md` contains the actual agent instructions and uses `@`
import syntax to pull in the core standards files from `standards/`. Claude Code
and Gemini CLI both support `@` imports, so their entry points simply import
`SHARED.md`. Codex CLI does not support `@` imports, so
`AGENTS.md` has the content inlined.

## Global Setup

Each tool reads a global config file from your home directory. These one-line
files point back to the entry points in this repo:

```bash
# Claude Code (~/.claude/CLAUDE.md)
echo '@~/Projects/personal/public/agents/CLAUDE.md' > ~/.claude/CLAUDE.md

# Gemini CLI (~/.gemini/GEMINI.md)
mkdir -p ~/.gemini
echo '@~/Projects/personal/public/agents/GEMINI.md' > ~/.gemini/GEMINI.md

# Codex CLI (~/.codex/AGENTS.md) — symlink since Codex lacks @ imports
mkdir -p ~/.codex
ln -s ~/Projects/personal/public/agents/AGENTS.md ~/.codex/AGENTS.md
```

## Editing

To change the shared instructions, edit `SHARED.md`. Changes
propagate to Claude Code and Gemini CLI automatically via the `@` imports.

For Codex CLI, also update `AGENTS.md` to keep it in sync (since its content
is inlined rather than imported).
