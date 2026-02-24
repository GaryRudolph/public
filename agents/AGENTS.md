# AI Agent Instructions

Guidelines for AI coding agents working with me.

## Core Preferences

- **Simplicity first** — solve the current problem; prefer boring, established technology
- **Readability over cleverness** — descriptive names, self-documenting code
- **Consistency** — follow existing patterns in the codebase
- **Constructor injection** — all dependencies via constructor; a single factory/composition root wires them
- **Test behavior, not implementation** — prefer fakes over mocks, DI over patching
- **Comments explain why, not what** — no narration of obvious code
- **Immutable by default** — prefer value types and immutable data

## Code Style Quick Rules

- PascalCase for types; snake_case or camelCase per language convention
- Prefix booleans: `is`, `has`, `can`, `should`
- File name matches primary export; colocate related files
- Imports ordered: stdlib, third-party, local
- Functions < 50 lines; extract complex logic

## Git Conventions

- **Branching**: GitHub Flow — `feature/name`, `fix/name`, `release/vN`
- **Versioning**: simplified — `v1`, `v2`, `v3`; hotfixes only: `v2.1`
- **Commits**: imperative mood, optional ticket prefix, 72-char subject, no period
  - `add login endpoint` or `PROJ-123 add login endpoint`
- **PRs**: squash-and-merge preferred; one feature/fix per PR

## Standards Reference

Load these only when the current task is relevant to the standard's topic:

- `standards/code-style.md` — naming, formatting, imports, anti-patterns
- `standards/architecture.md` — layering, DI, API design, error handling
- `standards/platform-parity.md` — cross-platform Swift/Kotlin naming and layer conventions
- `standards/testing.md` — coverage targets, test structure, mocking rules
- `standards/documentation.md` — what to document, ADR format, TODO conventions
- `standards/git.md` — branching, versioning, commit format, PR workflow
- `standards/security.md` — auth, encryption, input validation, checklists

### Language-Specific Standards

Load when working in that language:

- **Python**: `standards/python/` (code-style, architecture, testing, documentation, security)
- **Swift**: `standards/swift/` (code-style, architecture, testing, documentation, security)
- **Kotlin**: `standards/kotlin/` (code-style, architecture, testing, documentation, security)
