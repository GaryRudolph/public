# Makefile Reference

Automates installation and removal of AI agent configurations across
Claude Code, Gemini CLI, Codex CLI, Cursor, and Xcode.

## Targets

| Target | Description |
|--------|-------------|
| `install` | Install all global configs and per-project Cursor rules (default); runs `sync` first |
| `uninstall` | Remove all global configs and per-project Cursor rules |
| `sync` | Regenerate `AGENTS.md` from `SHARED.md` (inlined copy for Codex CLI) |
| `sync-check` | Verify `AGENTS.md` matches `SHARED.md`; non-zero exit if stale |
| `status` | Show what's currently installed and detected |
| `test` | Run `sync-check` + automated tests against isolated fixture repos |
| `clean-test` | Remove the test build directory |

## Usage

```bash
cd ~/Projects/personal/public/agents

make              # same as make install
make install      # install everything (runs sync first)
make uninstall    # remove everything
make sync         # regenerate AGENTS.md from SHARED.md
make sync-check   # fail if AGENTS.md is out of sync
make status       # check installation state
make test         # run test suite (includes sync-check)
```

## What install does

### Global configs

| Tool | File written | Method |
|------|-------------|--------|
| Claude Code | `~/.claude/CLAUDE.md` | Writes `@` import pointing to `agents/CLAUDE.md` |
| Gemini CLI | `~/.gemini/GEMINI.md` | Writes `@` import pointing to `agents/GEMINI.md` |
| Codex CLI | `~/.codex/AGENTS.md` | Symlink to `agents/AGENTS.md` |
| Xcode Claude Agent | `~/Library/.../ClaudeAgentConfig/CLAUDE.md` | Writes `@` import |
| Xcode Codex | `~/Library/.../codex/AGENTS.md` | Symlink to `agents/AGENTS.md` |

Xcode targets are skipped automatically if Xcode is not installed.

### Per-project Cursor rules

For every git repository found under `PROJECTS_DIR`:

1. Creates `.cursor/rules/` if it doesn't exist
2. Symlinks each `agents/cursor/personal-*.mdc` file into it
3. Adds `.cursor/rules/personal-*.mdc` to the project's `.gitignore`

Skipped repos:
- This repository itself (the one containing the Makefile)
- Nested git repos (e.g. submodules or repos inside other repos)

Cursor targets are skipped entirely if Cursor is not installed.

## Overridable variables

All paths use `?=` and can be overridden via environment or make arguments:

| Variable | Default | Purpose |
|----------|---------|---------|
| `PROJECTS_DIR` | `~/Projects` | Root directory to scan for git repos |
| `CLAUDE_HOME` | `~/.claude` | Claude Code config directory |
| `GEMINI_HOME` | `~/.gemini` | Gemini CLI config directory |
| `CODEX_HOME` | `~/.codex` | Codex CLI config directory |
| `XCODE_CLAUDE` | `~/Library/.../ClaudeAgentConfig` | Xcode Claude Agent config |
| `XCODE_CODEX` | `~/Library/.../codex` | Xcode Codex config |
| `CURSOR_SRC` | `agents/cursor` | Source directory for `.mdc` rule files |

Example — install for a different projects tree:

```bash
PROJECTS_DIR=~/Code make install
```

## Design notes

### SHARED.md is the single source of truth

`SHARED.md` is edited by hand. `AGENTS.md` is generated from it by `make sync`:

```
sed 's|\.\./standards/|standards/|g' SHARED.md > AGENTS.md
```

Codex CLI does not support `@` imports, so `AGENTS.md` must be a fully
inlined copy of `SHARED.md`. The only difference is path resolution:
`SHARED.md` uses `../standards/` (correct from `agents/`), while `AGENTS.md`
uses `standards/` (correct from the repo root, where Codex expects the file).

`make install` runs `sync` automatically before writing any config files, so
the installed copy is always fresh. `make test` runs `sync-check` first and
fails if `AGENTS.md` is stale — that makes it impossible to commit the two
files out of sync as long as tests pass in CI (or locally).

### Symlink-safe PROJECTS_DIR

`PROJECTS_DIR` may be a symlink (e.g. `~/Projects` pointing elsewhere).
Both `PROJECTS_DIR` and `REPO_ROOT` are resolved through `realpath` so that
find results (which return physical paths) can be reliably compared against
them. Without this, the "skip self" check would fail when one path is a
symlink and the other is resolved.

### Idempotency

Every operation is safe to repeat:
- `ln -sf` overwrites existing symlinks
- `.gitignore` entries are checked before appending
- Global config files are overwritten with the same content
- `make install` can be re-run after installing new tools (e.g. Xcode)

### Space-safe path handling

`find` results are read line-by-line using zsh process substitution
(`< <(find ...)`) instead of word-splitting (`for x in $(find ...)`).
This correctly handles repo paths containing spaces.

### Performance

`find` prunes known-large directories (`node_modules`, `.build`, `Pods`,
`DerivedData`, `.cache`, etc.) to avoid descending into them. On a tree
with ~270 repos, install completes in ~25 seconds.

### .gitignore safety

Before appending, the Makefile checks whether the file ends with a newline.
If it doesn't, a newline is inserted first to avoid corrupting the last line.
On uninstall, `.gitignore` files that become empty are deleted.

## Tests

### Running

```bash
make test
```

### Sandboxed execution

Tests are fully sandboxed — they never touch your real `~/Projects` or global
config directories. All paths are overridden to point into `build/test/`
under the `agents/` directory:

- `PROJECTS_DIR` → `build/test/`
- All `*_HOME` / `XCODE_*` vars → `build/test/.home/...`
- `HAS_CURSOR=1 HAS_XCODE=1` forced on regardless of what's installed

The `build/` directory is git-ignored and cleaned up after tests pass.

You can also run a sandboxed install/uninstall manually against a custom
directory without affecting your real setup:

```bash
make install \
  PROJECTS_DIR=/tmp/test-repos \
  CLAUDE_HOME=/tmp/test-home/.claude \
  GEMINI_HOME=/tmp/test-home/.gemini \
  CODEX_HOME=/tmp/test-home/.codex \
  XCODE_CLAUDE=/tmp/test-home/xcode-claude \
  XCODE_CODEX=/tmp/test-home/xcode-codex \
  HAS_CURSOR=1 HAS_XCODE=1
```

### What the test suite covers

The test creates 9 fixture git repos plus 1 nested repo, then runs
install → verify → install again (idempotency) → uninstall → verify →
symlink test:

| Fixture | What it tests |
|---------|---------------|
| `normal-repo` | Repo with no `.gitignore` — entry is created from scratch, deleted on uninstall |
| `gitignore-newline` | `.gitignore` ending with newline — entry appended cleanly |
| `gitignore-no-newline` | `.gitignore` without trailing newline — newline inserted before appending |
| `already-ignored` | `.gitignore` already has the entry — not duplicated |
| `parent-repo` + `nested-repo` | Parent gets rules, nested child is skipped |
| `existing-rules` | Repo with a `team-rule.mdc` — not deleted by install or uninstall |
| `empty-gitignore` | Empty `.gitignore` file — entry added, file deleted on uninstall |
| `path with spaces` | Repo path containing spaces — handled correctly |
| `worktree-repo` | Git worktree (`.git` file, not directory) — discovered and rules installed |
| `symlink-alias` → `symlink-real` | Symlinked `PROJECTS_DIR` — repos discovered and rules installed |

Assertions verified after install:
- Every non-nested repo has `personal-main.mdc` symlink
- Every repo's `.gitignore` contains the ignore entry exactly once
- Nested repo has no `.cursor/rules/` directory
- Pre-existing `team-rule.mdc` is preserved
- No-newline `.gitignore` lines are not corrupted
- All global config files exist

Assertions verified after idempotent re-install:
- `.gitignore` entries are still exactly one per repo

Assertions verified after uninstall:
- No `personal-*.mdc` symlinks remain in any repo
- `.gitignore` entries are removed
- `.gitignore` files that only contained our entry are deleted
- Worktree `.git` file is preserved (not confused with a directory)
- Original `.gitignore` content is restored
- `team-rule.mdc` is still present
- All global config files are removed

Assertions verified for symlinked PROJECTS_DIR:
- Repos under a symlinked directory are discovered
- Cursor rules are installed through the symlink
