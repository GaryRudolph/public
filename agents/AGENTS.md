# AI Agent Instructions

<!-- SYNC: This is a flat copy of SHARED.md (with ../standards/ paths changed
     to standards/) because Codex cannot follow @-includes. Do not edit this
     file directly — edit SHARED.md and copy here. -->

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

## Workflow

When executing a multi-step plan:

1. **Pause after each step** — stop and show me what changed before moving on
2. **Verify git email** — before any commit, run `git config user.email` and confirm it matches the expected email for this repo's organization; flag a mismatch and wait for me to fix it
3. **Ask to commit** — after I've reviewed, ask if I want to commit before continuing to the next step
4. **Wait for approval** — do not proceed to the next step until I confirm

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
