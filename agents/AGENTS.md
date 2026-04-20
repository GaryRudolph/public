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

## Standards Precedence

When guidance conflicts, follow this order (highest priority first):

1. **Project standards** — the current repository's own conventions, README, or local rules
2. **Organization standards** — the organization's shared standards for that repo, if present
3. **Personal standards** — these instructions and the `standards/` files referenced below

A project or organization rule can override a personal preference if there's a documented reason.

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

- **Never commit unless asked** — do not create commits unless I explicitly ask you to; this applies even during multi-step plans
- **Verify git email** — before any commit, run `git config user.email` and confirm it matches the expected email for this repo's organization; flag a mismatch and wait for me to fix it
- **Pause after each step** — stop and show me what changed before moving on
- **Wait for approval** — do not proceed to the next step until I confirm
- **Wait for answers** — if you ask a question, always wait for a response before proceeding; never assume an answer and continue
- **Always use virtual environments** — when installing Python packages, use the project's existing venv (or create one with `python -m venv .venv`) from the start; never install with global or user-level pip
- **Use project-local package management** — for Node, prefer `npx` over `npm install -g`; for Ruby, use `bundle exec` and never bare `gem install`
- **Use `.scratch/` for quick tasks** — when asked to draft, research, or spike on something that isn't ready to commit, write it to `.scratch/` (gitignored). If `.scratch/` doesn't exist, create it and verify it's in `.gitignore`
- **Check `.gitignore` when creating new directories** — when creating directories meant to hold working files, drafts, or local artifacts, confirm they're covered by `.gitignore` before writing to them
- **Write handoff files** — when asked to `handoff` or "write a handoff", summarize the session to `.scratch/handoff-{topic}.md` where `{topic}` is a short kebab-case name you derive from the work (e.g. `handoff-auth-api.md`, `handoff-pipeline-refactor.md`). Include: what was done, what's pending, key decisions made, and gotchas for the next session. Keep it short and actionable
- **Use milestone naming (`m{N}`, lowercase) for implementation phases** — when planning or writing specs, break multi-step projects into ordered milestones prefixed `m1`, `m2`, …, `m13`. Section headings use `### m{N} - Title`; cross-references use `m7` (not "Step 7"). Reserve the word "step" for procedural steps inside a milestone, algorithm steps, or onboarding-flow steps. See `standards/documentation.md` "Implementation Milestones"
- **Write a milestone handoff when transitioning milestones** — when moving from `m{N}` to `m{N+1}` on a project with a `specs/` folder, write `{project-root}/specs/handoffs/handoff-m{N+1}-{topic}.md` before starting the next milestone. Contents: where we are (done / not done), what the next milestone needs to deliver, key decisions already made, suggested plan, gotchas, files to reference. These handoffs are version-controlled (unlike `.scratch/` handoffs). See `standards/documentation.md` "Handoffs between milestones"
- **Write specs to `{project-root}/specs/`** — new product specs, technical designs, RFCs, and ADRs go in `{project-root}/specs/{topic}.md` (lowercase-kebab, no `-spec` suffix — the folder already implies it; e.g. `specs/product.md`, `specs/search-engine.md`). Do not scatter spec-level documents across the repo root or language-specific folders. Scratch-only drafts still go to `.scratch/`
- **Follow filename case conventions** — ALL_CAPS reserved for well-established root-level meta files (`README.md`, `LICENSE`, `AGENTS.md`, `CLAUDE.md`, `TODO.md`, etc.); companion docs mirror the casing of the file they document (`Makefile.md`, `Dockerfile.md`); everything else is lowercase-kebab-case (`apple-developer.md`, `deployment-guide.md`). See `standards/documentation.md` "Filename Case Conventions"

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
