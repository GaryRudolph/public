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
- **Marking complete:** when a milestone ships, wrap the name and title of its spec heading in `~~…~~` so the whole `m{N} - {Title}` reads as struck through; leave the `###` outside the strikethrough so the heading still renders. Example: `### ~~m3 - Search UI (Noop Models)~~`. Apply the same treatment to any tracking lists or tables of contents that enumerate milestones (e.g. a `specs/README.md` checklist). Don't strike through inline `m{N}` cross-references in prose — only the milestone's own heading and list entries.

### Steps within a milestone

When a milestone's plan has ordered steps, prefix them `s{N}` (lowercase). Step numbering is **scoped to its parent milestone** and restarts at `s1` for each milestone — so an `m1` plan may have `s1, s2, s3` and an `m2` plan may also have `s1, s2, s3, s4`.

- **Naming:** prefix `s{N}` (lowercase) — `s1`, `s2`, … Use for the ordered tasks an agent will execute to complete a milestone (e.g. inside a `.scratch/plan-{topic}-{word}.md` or a `### m{N}` spec subsection).
- **Section heading:** `#### s{N} - {Short Title}` when steps live as subsections under an `### m{N}` heading
- **Cross-references:** within the same milestone, write `s2` inline. To reference a step in a different milestone, qualify it as `m{N}.s{M}` (e.g. `m3.s2`). Don't write "Step 2" or "step two" for these.
- **Commits and branches:** may reference the step alongside the milestone, e.g. `m3.s2 wire search results to view model` or `feature/m3-s2-search-results`
- **Marking complete:** same convention as milestones — wrap the name and title in `~~…~~`, leaving the heading prefix outside. Example: `#### ~~s2 - Wire search results~~`. Apply to checklists and TOC entries that enumerate steps.

Reserve plain "step" prose for procedural steps in user-facing docs (onboarding flows, tutorials, algorithm walk-throughs) — not for plan execution.

### Model-tier stop points

Plans are executed by agents of different cost and capability. To make the most of both, tag every milestone and every step with one of two tiers:

- `[deep]` — needs a top-tier reasoning model. Use for architecture and design decisions, ambiguous requirements, non-obvious debugging, security-sensitive review, library/stack trade-offs, and anywhere the cost of getting it wrong is high.
- `[exec]` — well-specified, mechanical work. Use for applying a decided design across many files, refactors with a clear target, renames, scaffolding tests for already-designed behavior, formatting/lint, doc updates, and well-bounded ports.

Tag the heading itself, after the title:

    ### m3 - Search UI [deep]
    #### s1 - Decide debounce strategy [deep]
    #### s2 - Wire search results to view model [exec]
    #### s3 - Add tests for search reducer [exec]

Stop and hand control back to the user at every boundary where the tag changes (`[deep]` -> `[exec]` or vice versa). The user can then keep the same model, swap models, or delegate to a subagent before continuing.

The tiers are intentionally model-agnostic; specific model names (Opus, GPT-5, Sonnet, Composer, Haiku, etc.) change too often to bake into the spec. Map tiers to whichever current model is the right capability/cost for that tier.

### Delegating execution to subagents

When a `[deep]` agent finishes a deep step and the next step is `[exec]`, prefer delegating the `[exec]` step to a subagent on a smaller model rather than burning the deep context on mechanical work.

- Use the harness's subagent/Task tool (Cursor `Task` with `subagent_type` and optional `model`; Claude Code `Task`; other harnesses use the equivalent).
- Pass the cheapest model that can plausibly complete the step. Only step up if the subagent fails or returns low-quality output.
- Give the subagent: the spec section, the exact files to touch, acceptance criteria, and a hard scope limit. Subagents do not see the parent conversation, so be explicit.
- The deep parent stays responsible for reviewing the subagent's output and deciding the next stop point.
- If the harness does not support per-subagent model selection, stop at the boundary instead and let the user start a fresh session on a cheaper model.

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
