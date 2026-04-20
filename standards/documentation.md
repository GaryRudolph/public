# Documentation Standards

## What to Document

**Always**: public APIs, complex business logic, architecture decisions, setup/configuration, non-obvious behavior, workarounds

**Don't**: self-explanatory code, implementation details that may change, what the code does (code should be self-documenting)

## Code Comments

- Explain **why**, not what
- Document non-obvious algorithms, performance trade-offs, and workarounds

### TODO Format

- `TODO:` — work to be done
- `TODO(username):` — assigned to someone
- `TODO: [TICKET-123]` — linked to a ticket
- `FIXME:` — known bug or broken behavior
- `HACK:` — temporary workaround, explain why and when to remove
- `NOTE:` — important context for the reader

## Filename Case Conventions

Markdown (and other doc) filenames follow three patterns, in priority order:

1. **Well-established root-level meta filenames → `ALL_CAPS.md`.** Reserved for filenames that tools, platforms, or long-standing Unix/open-source convention expect by that exact name:
   - `README.md`, `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `AUTHORS`, `NOTICE`, `COPYING`, `TODO.md`
   - AI tool entry points: `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`
   - Do **not** invent new ALL_CAPS names for project-specific docs — those go in bucket 3
2. **Companion docs for a non-Markdown file → mirror that file's casing.** When a Markdown doc documents a specific tool/config file, use the same casing as the file it describes plus `.md`:
   - `Makefile.md` (documents `Makefile`)
   - `Dockerfile.md` (documents `Dockerfile`)
   - `Procfile.md`, `Brewfile.md`, etc.
3. **Everything else → `lowercase-kebab-case.md`.** All other docs — guides, project-specific setup docs, specs, architecture notes, handoffs, FAQs — use lowercase letters with `-` as the separator:
   - `apple-developer.md`, `deployment-guide.md`, `getting-started.md`
   - `specs/product.md`, `specs/search-engine.md`, `specs/handoffs/handoff-m3-search-ui.md`

Case-sensitivity note: macOS is case-insensitive by default but Linux is case-sensitive. Lowercase-kebab is safe everywhere; `README.md` vs. `readme.md` would conflict on macOS but be distinct on Linux. Stick to the buckets above and this won't come up.

## Product and Technical Specs

Substantive project documents — product specs, technical designs, RFCs, and ADRs that describe "what we are building and why" — live in `{project-root}/specs/`. Keep them in version control alongside the code they describe. Handoff notes between milestones live in `{project-root}/specs/handoffs/`.

- New spec → `{project-root}/specs/{topic}.md` (e.g. `specs/product.md`, `specs/search-engine.md`, `specs/data-model.md`). The `specs/` folder already implies "this is a spec" — don't append a `-spec` or `_SPEC` suffix.
- Specs folder landing page (optional) → `specs/README.md` — a table of contents or short orientation for the folder. This is the one `ALL_CAPS.md` filename allowed inside `specs/` (see "Filename Case Conventions" bucket 1).
- Milestone handoffs → `{project-root}/specs/handoffs/handoff-m{N}-{topic}.md` (see "Implementation Milestones" below)
- Throwaway drafts, research, spikes → `.scratch/` (gitignored)

Do not scatter spec-level docs across the repo root or language-specific folders. The only exception is when a tool expects a fixed filename at the root (e.g. `README.md`, `AGENTS.md`, `CLAUDE.md`).

### Spec Structure Conventions

- Use `##` for top-level sections, `###` for subsections. Don't duplicate section numbers (e.g. avoid two `## 8.` headings)
- Prefer tables over long prose wherever data is tabular
- Code samples in fenced blocks with a language tag
- Cross-reference spec sections with `§{N}` or `§{N.M}` (e.g. "see §6.2 for details")
- Don't embed absolute filesystem paths or machine-specific values — keep specs portable

### Spec Authoring Workflow

- Pause for review after substantive spec edits; specs are long-lived documents
- When in doubt about scope, ask before adding content — it's cheaper to agree on the outline than to rewrite prose

## Implementation Milestones

Large projects are broken into ordered milestones, each producing a user- or developer-visible deliverable before the next starts.

- **Naming:** prefix `m{N}` (lowercase) — `m1`, `m2`, …, `m13`. Avoid ambiguous generic terms like "Step" or "Phase" for this concept; reserve those for procedural steps within a milestone, algorithm steps, or onboarding-flow steps.
- **Section heading in specs:** `### m{N} - {Short Title}` (e.g. `### m3 - Search UI (Noop Models)`)
- **Cross-references:** write `m7` inline (not "Step 7", not "milestone 7")
- **Commits and branches:** may reference the milestone tag, e.g. `m3 add floating search panel` or `feature/m3-search-ui`

### Handoffs between milestones

When work transitions from one milestone to the next (m{N} → m{N+1}), the agent finishing m{N} writes a handoff file to `{project-root}/specs/handoffs/handoff-m{N+1}-{topic}.md` describing:

- **Where we are** — what landed in m{N} that the next milestone depends on, and what was left partially done or skipped
- **What m{N+1} needs to deliver** — concrete deliverables pulled from the spec
- **Key decisions already made** — so the next session doesn't re-debate them
- **Suggested plan** — a short ordered task list to start from
- **Gotchas** — traps, known bugs, dependencies not yet wired, platform quirks
- **Files to reference** — specific paths the next agent should read first

Handoff files go in version control; they are part of the project's working record.

This rule supersedes the general-purpose `.scratch/handoff-{topic}.md` convention only for **milestone transitions on a project that has a `specs/` folder**. Ad-hoc handoffs (session wrap-ups, research, one-off spikes) still go to `.scratch/`.

## Architecture Decision Records

```markdown
# ADR-001: Title

## Status
Accepted | Proposed | Deprecated

## Context
Why a decision was needed.

## Decision
What was decided.

## Consequences
### Positive
### Negative

## Alternatives Considered
```

## Changelog

Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`

## Documentation Review Checklist

- [ ] Accurate and up-to-date with code?
- [ ] Examples working and tested?
- [ ] Clear and easy to understand?
- [ ] Links working?
- [ ] Formatting consistent?

Include documentation changes in code reviews. Update docs in the same PR as code changes.

## Language-Specific Guidelines

- **[Python](python/documentation.md)**
- **[Swift](swift/documentation.md)**
- **[Kotlin](kotlin/documentation.md)**
