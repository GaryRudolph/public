# AI Agent Configuration

This directory contains instruction files for AI coding agents. Each tool
(Claude Code, Codex CLI, Gemini CLI) has its own entry point that references
shared coding standards from `standards/`.

## Files

| File | Tool | How it works |
|------|------|--------------|
| `CLAUDE.md` | Claude Code | Imports `SHARED.md` via `@` syntax |
| `GEMINI.md` | Gemini CLI | Imports `SHARED.md` via `@` syntax |
| `AGENTS.md` | Codex CLI / Cursor | Inlined content (neither tool supports `@` imports) |
| `SHARED.md` | — | Common instructions (no `@` imports to standards — agents load on demand) |

## How It Works

`SHARED.md` contains core preferences inline and lists standards files by path.
Agents load specific standards only when the task is relevant, keeping context
efficient. Claude Code and Gemini CLI import `SHARED.md` via `@` syntax. Codex
CLI gets an inlined copy in `AGENTS.md`.

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

Cursor reads rules per-project. Symlink into the repo root:

```bash
# Option A: .cursorrules (simple, widely supported)
ln -s ~/Projects/personal/public/agents/AGENTS.md .cursorrules

# Option B: .cursor/rules/ (newer MDC format)
mkdir -p .cursor/rules
ln -s ~/Projects/personal/public/agents/AGENTS.md .cursor/rules/main.mdc
```

## Editing

Edit `SHARED.md` for shared instructions. Changes propagate to Claude Code and
Gemini CLI automatically. For Codex CLI, also update `AGENTS.md` to keep it in
sync (its content is inlined).
