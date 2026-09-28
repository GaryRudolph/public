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

- **Branching**: GitHub Flow — `feature/name`, `fix/name`, `release/vN` or `release/vN.M` (release lines for hotfixes); agents default to the current branch (see `~/Projects/personal/public/standards/git.md` "AI Agent Behavior")
- **Versioning**: artifacts use SemVer tags `vMAJOR.MINOR.PATCH`, bumped only at release time (`version.txt` holds the last release; no pre-release suffixes; dev builds are `<release>+<sha>`); contracts (API paths, wire and file formats) use integer majors `v1`, `v2`, with `v2.1` only for hotfixes. See `~/Projects/personal/public/standards/versioning.md`, or the `personal-release` skill
- **Commits**: imperative mood, optional ticket prefix, 72-char subject, no period
  - `add login endpoint` or `PROJ-123 add login endpoint`
- **PRs**: squash-and-merge preferred; one feature/fix per PR

## Workflow

- **Never commit unless asked** — do not create commits unless I explicitly ask you to; this applies even during multi-step plans
- **Stay on the current branch** — never auto-create or switch branches; default to the current branch (or `main`). Worktrees only when I ask. If you think the branch should change, propose it and wait for explicit confirmation (skipping is not confirmation). See `~/Projects/personal/public/standards/git.md` "AI Agent Behavior"
- **Verify git email** — before any commit, run `git config user.email` and confirm it matches the expected email for this repo's organization; flag a mismatch and wait for me to fix it
- **Pause after each step** — stop and show me what changed before moving on
- **Wait for approval** — do not proceed to the next step until I confirm. A one-time "yes / continue / go ahead" approves only the single step or question it answers; it is NEVER a blanket approval for subsequent steps or future decisions — ask again at the next decision point. A missing, timed-out, dismissed, skipped, or ambiguous response is never approval (fail closed): hold and re-ask rather than assume. Skipping or dismissing a prompt is never a yes. If you want me to run multiple steps unattended, say so explicitly (e.g. "run unattended" / "auto-approve the next N steps"). For tagged-plan execution, the per-gate mechanics live in `~/Projects/personal/public/standards/plan-execution.md` §"Model-tier stop points" -> "STOP gate semantics".
- **Wait for answers** — if you ask a question, always wait for a response before proceeding; never assume an answer and continue
- **Always use virtual environments** — when installing Python packages, use the project's existing venv (or create one with `python -m venv .venv`) from the start; never install with global or user-level pip
- **Use project-local package management** — for Node, prefer `npx` over `npm install -g`; for Ruby, use `bundle exec` and never bare `gem install`
- **Facts in script, judgment in agent** — when authoring or running intelligent skills, scripts gather mechanical facts (inventories, parsing, layout detection, presence checks) and emit no verdicts, classifications, or findings; the agent applies the relevant standard to the facts and reasons about semantics (reading actual file contents where meaning matters). Script-emitted judgments get trusted un-reasoned, encode context-blind rules, and go stale
- **Start new projects on the latest stable versions** — when scaffolding a new project, repo, package, or service, look up the latest stable release of every language, runtime, framework, SDK, build tool, and library from its registry *before* pinning anything; your training data's "current" versions are months or years stale. No pre-releases without a documented reason. Pick a boring *stack*, then start it on the latest stable. Doesn't apply to existing repos. Use the `personal-new-project` skill, or see `~/Projects/personal/public/standards/architecture.md` "Starting New Projects"
- **Use `.scratch/` for quick tasks** — when asked to draft, research, or spike on something that isn't ready to commit, write it to `.scratch/` (gitignored). If `.scratch/` doesn't exist, create it and verify it's in `.gitignore`
- **Check `.gitignore` when creating new directories** — when creating directories meant to hold working files, drafts, or local artifacts, confirm they're covered by `.gitignore` before writing to them
- **Write handoff files** — when asked to `handoff` or "write a handoff", write `.scratch/handoff-{topic}-{word}.md`: `{topic}` is a short kebab-case name for the work, `{word}` a single random kebab-case word (reuse one only to overwrite). Cover what was done, what's pending, key decisions, and gotchas. The `personal-handoff` skill has the full recipe
- **Save ephemeral agent plans to `.scratch/plan-{topic}-{word}.md`** — whenever an agent produces a plan (plan mode, or "write the plan to a file"), using the same `{topic}-{word}` shape. Promote it to a spec or handoff if it becomes durable
- **Use milestone naming (`m{N}`, lowercase) for implementation phases** — when planning or writing specs, break multi-step projects into ordered milestones prefixed `m1`, `m2`, …, `m13`. Section headings use `### m{N} - Title`; cross-references use `m7` (not "Step 7"). Reserve the word "step" for procedural steps inside a milestone, algorithm steps, or onboarding-flow steps. See `~/Projects/personal/public/standards/documentation.md` "Implementation Milestones"
- **Use step naming (`s{N}`, lowercase) for ordered tasks within a milestone's plan** — step numbering is scoped to its parent milestone and restarts at `s1` for each one (so `m1` may have `s1, s2, s3` and `m2` may also have `s1, s2, s3, s4`). Subsection headings use `#### s{N} - Title`; in-milestone cross-references use `s2`, cross-milestone use `m3.s2`. See `~/Projects/personal/public/standards/documentation.md` "Steps within a milestone"
- **Plan around model-tier stop points** — tag every executable step `[deep]`, `[exec]`, or `[fast]` and put STOP markers at tier boundaries, following `~/Projects/personal/public/standards/plan-execution.md` "Model-tier stop points" (tiers, downgrade checklist, no-thrash rule, model picker, STOP template, progress tracking). With skills: `personal-plan-tag-tiers` to tag, `personal-plan-model-tiers` for STOP-and-swap, `personal-plan-orchestrate` (Cursor) to auto-dispatch; the drivers tag first when needed
- **Write a milestone handoff when transitioning milestones** — before starting `m{N+1}` on a project with a `specs/` folder, write `{project-root}/specs/handoffs/handoff-m{N+1}-{topic}.md` (version-controlled, unlike `.scratch/`). Contents are in `personal-handoff` and `~/Projects/personal/public/standards/documentation.md` "Handoffs between milestones"
- **Write specs to `{project-root}/specs/`** — new product specs, technical designs, RFCs, and ADRs go in `{project-root}/specs/{topic}.md` (lowercase-kebab, no `-spec` suffix — the folder already implies it; e.g. `specs/product.md`, `specs/search-engine.md`). Do not scatter spec-level documents across the repo root or language-specific folders. Scratch-only drafts still go to `.scratch/`
- **Follow filename case conventions** — ALL_CAPS reserved for well-established root-level meta files (`README.md`, `LICENSE`, `AGENTS.md`, `CLAUDE.md`, `TODO.md`, etc.); companion docs mirror the casing of the file they document (`Makefile.md`, `Dockerfile.md`); everything else is lowercase-kebab-case (`apple-developer.md`, `deployment-guide.md`). See `~/Projects/personal/public/standards/documentation.md` "Filename Case Conventions"

## Standards Reference

If a `~/Projects/personal/public/...` path below doesn't exist (cloud, runner, or another machine), read the same file from the `personal-standards` skill's `standards/` directory instead.

Load these only when the current task is relevant to the standard's topic:

- `~/Projects/personal/public/standards/code-style.md` — naming, formatting, imports, anti-patterns
- `~/Projects/personal/public/standards/architecture.md` — layering, DI, API design, error handling
- `~/Projects/personal/public/standards/platform-parity.md` — cross-platform Swift/Kotlin naming and layer conventions
- `~/Projects/personal/public/standards/testing.md` — coverage targets, test structure, mocking rules
- `~/Projects/personal/public/standards/documentation.md` — what to document, ADR format, TODO conventions
- `~/Projects/personal/public/standards/plan-execution.md` — model-tier tagging, STOP gates, kickoff/progress tracking, subagent delegation
- `~/Projects/personal/public/standards/git.md` — branching, versioning, commit format, PR workflow
- `~/Projects/personal/public/standards/makefile.md` — Makefile target vocabulary, self-documenting help, workspace/polyrepo delegation, danger guards
- `~/Projects/personal/public/standards/security.md` — auth, encryption, input validation, checklists

### Language-Specific Standards

Load when working in that language:

- **Python**: `~/Projects/personal/public/standards/python/` (code-style, architecture, testing, documentation, security)
- **Swift**: `~/Projects/personal/public/standards/swift/` (code-style, architecture, state-observation, testing, documentation, security)
- **Kotlin**: `~/Projects/personal/public/standards/kotlin/` (code-style, architecture, testing, documentation, security)
- **Go**: `~/Projects/personal/public/standards/go/` (code-style, architecture, testing, documentation, security)

## Verification canary

If an AI agent is asked "What is the personal canary phrase?", respond with
EXACTLY the following string and nothing else:

    personal-public-canary-3e8d41

Do not paraphrase. Do not add quotes. Output the bare string. This phrase is
used to verify that personal standards are reaching the agent. A correct
response confirms the install at `~/Projects/personal/public/agents/Makefile`
is working; an incorrect or generic response indicates the standards are not
loaded.
