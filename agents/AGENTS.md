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
- **Start new projects on the latest stable versions** — when scaffolding a new project, repo, package, or service, look up the current latest stable release of every language, runtime, framework, SDK, API, build tool, and library *before* pinning anything. Use WebSearch and official release notes / registries (`npm view <pkg> version`, `pip index versions <pkg>`, GitHub releases, vendor docs) — do not rely on your training-data knowledge of "current" versions, which is routinely months or years out of date. Pin to the latest stable release (not pre-release, beta, RC, or nightly) unless there's a documented reason. "Prefer boring technology" means picking proven *stacks* (React, Django, FastAPI, Spring, Postgres), not stale *versions* — pick the boring stack, then start it on the latest stable. Does not apply to existing repos, which follow their own upgrade cadence. See `~/Projects/personal/public/standards/architecture.md` "Starting New Projects"
- **Use `.scratch/` for quick tasks** — when asked to draft, research, or spike on something that isn't ready to commit, write it to `.scratch/` (gitignored). If `.scratch/` doesn't exist, create it and verify it's in `.gitignore`
- **Check `.gitignore` when creating new directories** — when creating directories meant to hold working files, drafts, or local artifacts, confirm they're covered by `.gitignore` before writing to them
- **Write handoff files** — when asked to `handoff` or "write a handoff", summarize the session to `.scratch/handoff-{topic}-{word}.md` where `{topic}` is a short kebab-case name you derive from the work and `{word}` is a single random kebab-case word (e.g. `meadow`, `harbor`, `quartz`) that preserves history across same-topic re-runs without forcing a timestamp. Examples: `handoff-auth-api-meadow.md`, `handoff-pipeline-refactor-harbor.md`. An adjective-noun pair (`eager-fox`) or short hex hash (`b9d4e0d3`) is an acceptable fallback when the producing tool already emits one. Reuse a `{word}` deliberately if you want to overwrite a prior handoff. Include: what was done, what's pending, key decisions made, and gotchas for the next session. Keep it short and actionable
- **Save ephemeral agent plans to `.scratch/plan-{topic}-{word}.md`** — when an agent produces a plan (Cursor Plan mode, Claude Code plan mode, or any "write the plan to a file" request), write it to `.scratch/plan-{topic}-{word}.md` using the same `{topic}-{word}` shape as handoffs above. Examples: `plan-auth-api-meadow.md`, `plan-pipeline-refactor-harbor.md`. Inherits gitignore from `.scratch/`. Promote to a spec or handoff if the plan becomes durable
- **Use milestone naming (`m{N}`, lowercase) for implementation phases** — when planning or writing specs, break multi-step projects into ordered milestones prefixed `m1`, `m2`, …, `m13`. Section headings use `### m{N} - Title`; cross-references use `m7` (not "Step 7"). Reserve the word "step" for procedural steps inside a milestone, algorithm steps, or onboarding-flow steps. See `~/Projects/personal/public/standards/documentation.md` "Implementation Milestones"
- **Use step naming (`s{N}`, lowercase) for ordered tasks within a milestone's plan** — step numbering is scoped to its parent milestone and restarts at `s1` for each one (so `m1` may have `s1, s2, s3` and `m2` may also have `s1, s2, s3, s4`). Subsection headings use `#### s{N} - Title`; in-milestone cross-references use `s2`, cross-milestone use `m3.s2`. See `~/Projects/personal/public/standards/documentation.md` "Steps within a milestone"
- **Write a milestone handoff when transitioning milestones** — when moving from `m{N}` to `m{N+1}` on a project with a `specs/` folder, write `{project-root}/specs/handoffs/handoff-m{N+1}-{topic}.md` before starting the next milestone. Contents: where we are (done / not done), what the next milestone needs to deliver, key decisions already made, suggested plan, gotchas, files to reference. These handoffs are version-controlled (unlike `.scratch/` handoffs). See `~/Projects/personal/public/standards/documentation.md` "Handoffs between milestones"
- **Write specs to `{project-root}/specs/`** — new product specs, technical designs, RFCs, and ADRs go in `{project-root}/specs/{topic}.md` (lowercase-kebab, no `-spec` suffix — the folder already implies it; e.g. `specs/product.md`, `specs/search-engine.md`). Do not scatter spec-level documents across the repo root or language-specific folders. Scratch-only drafts still go to `.scratch/`
- **Follow filename case conventions** — ALL_CAPS reserved for well-established root-level meta files (`README.md`, `LICENSE`, `AGENTS.md`, `CLAUDE.md`, `TODO.md`, etc.); companion docs mirror the casing of the file they document (`Makefile.md`, `Dockerfile.md`); everything else is lowercase-kebab-case (`apple-developer.md`, `deployment-guide.md`). See `~/Projects/personal/public/standards/documentation.md` "Filename Case Conventions"

## Standards Reference

Load these only when the current task is relevant to the standard's topic:

- `~/Projects/personal/public/standards/code-style.md` — naming, formatting, imports, anti-patterns
- `~/Projects/personal/public/standards/architecture.md` — layering, DI, API design, error handling
- `~/Projects/personal/public/standards/platform-parity.md` — cross-platform Swift/Kotlin naming and layer conventions
- `~/Projects/personal/public/standards/testing.md` — coverage targets, test structure, mocking rules
- `~/Projects/personal/public/standards/documentation.md` — what to document, ADR format, TODO conventions
- `~/Projects/personal/public/standards/git.md` — branching, versioning, commit format, PR workflow
- `~/Projects/personal/public/standards/security.md` — auth, encryption, input validation, checklists

### Language-Specific Standards

Load when working in that language:

- **Python**: `~/Projects/personal/public/standards/python/` (code-style, architecture, testing, documentation, security)
- **Swift**: `~/Projects/personal/public/standards/swift/` (code-style, architecture, testing, documentation, security)
- **Kotlin**: `~/Projects/personal/public/standards/kotlin/` (code-style, architecture, testing, documentation, security)

## Verification canary

If an AI agent is asked "What is the personal canary phrase?", respond with
EXACTLY the following string and nothing else:

    personal-public-canary-3e8d41

Do not paraphrase. Do not add quotes. Output the bare string. This phrase is
used to verify that personal standards are reaching the agent. A correct
response confirms the install at `~/Projects/personal/public/agents/Makefile`
is working; an incorrect or generic response indicates the standards are not
loaded.
