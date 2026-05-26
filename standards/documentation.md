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

Plans are executed by agents of different cost and capability. To make the most of both, tag every executable step with one of three tiers, group consecutive same-tier steps, and emit a STOP marker at every tier boundary so the model can be swapped (or the group delegated to a subagent) before continuing.

This section is the canonical reference for the convention. The `personal-plan-model-tiers` skill (and the equivalent in any harness) is the operational layer that implements it.

#### Tiers

- `[deep]` — top-tier reasoning. Architecture decisions, ambiguous requirements, non-obvious debugging, security-sensitive review, library/stack trade-offs, anywhere the cost of getting it wrong is high.
- `[exec]` — standard implementation. Multi-file changes with cross-file reasoning, refactors with a clear target but real judgment, test writing where cases need thought, work that must read repo patterns first to extend them.
- `[fast]` — mechanical, fully-specified, single-concern work. Renames, format changes, applying a decided design line-by-line, doc updates, well-bounded ports.

**Default-up bias**: when in doubt, tag `[deep]` > `[exec]` > `[fast]`. A misclassified `[fast]` produces bad output; a misclassified `[deep]` wastes a little money.

#### `[fast]` downgrade checklist

A step only earns `[fast]` if **all** of these are true:

- The step lists exact files and the change is fully spec'd at line-level.
- No cross-file invariants — the change is scoped to a single concern.
- An existing similar pattern in the repo can be copied from.
- Tests cover the change (fast feedback if the model misses).
- Reversal cost is low (small diff, easy revert).
- A later `[deep]` or `[exec]` group will review this output before it ships.

Any `no` → tag `[exec]`.

#### Tag placement

Tag **executable steps only** — not milestone, phase, or section headings.
The executable level is typically the deepest heading level in the plan. If
the plan uses only one heading level, tag every heading at that level.

**One rule:** the tag goes immediately after the title separator (the first
`-`, `:`, or `.` followed by whitespace) and before the title text. If the
heading has no separator, the tag goes immediately after the heading marker.

Do not rewrite IDs, renumber, change casing, add separators, or coin new
identifiers. This convention works with any plan structure — `m{N}`/`s{N}`
is the recommended naming shape for new plans (see "Steps within a milestone"
above), but the skill adapts to whatever structure already exists.

    #### s1 - [deep] Decide debounce strategy
    #### s2 - [exec] Wire search results to view model
    #### s3 - [fast] Bump search-event version string
    #### Phase 1: [exec] Auth
    #### 3. [exec] Add tests
    #### [exec] Wire Redis client

Edge cases:

- **Internal `.` inside a prefix** (`m3.s2 - Foo`): the `.` between `m3`
  and `s2` has no whitespace after it, so it isn't the separator — the `-`
  is. Result: `#### m3.s2 - [exec] Foo`.
- **Multiple separators in one heading** (`#### m3 - Search UI: Detail`):
  the first separator wins; the tag slots after the `-`.
- **No prefix, no separator**: tag goes right after `####`.

To find tagged headings use the regex: `^#+\s+.*\[(deep|exec|fast)\]`

#### No-thrash rule

Walk the tagged steps in order and collect consecutive same-tier steps into groups. Then:

1. Always insert a STOP at any `[deep]` ↔ `[exec]` boundary.
2. Always insert a STOP at any `[deep]` ↔ `[fast]` boundary.
3. **Conditionally** insert a STOP at an `[exec]` ↔ `[fast]` boundary:
   - If the `[fast]` block has **≥ 3 contiguous fast steps**, emit the STOP.
   - Otherwise, **promote those fast steps to `[exec]`** (no STOP) so you don't spend more time swapping models than working.
4. After promotions, re-merge adjacent same-tier groups before deciding STOP placement.

#### Model picker

| Tier | Cursor | Claude Code | Thinking level |
|---|---|---|---|
| `[deep]` | `claude-opus-4-7-thinking-xhigh` (alt: `gpt-5.3-codex`) | `/model opus` | xhigh / max |
| `[exec]` | `claude-4.6-sonnet-medium-thinking` (alt: `gpt-5.5-medium`) | `/model sonnet` | medium |
| `[fast]` | `composer-2.5-fast` | `/model haiku` | off / none |

Notes:
- For Claude Code, toggle extended thinking with `/think` (or the equivalent in the version installed). Haiku doesn't meaningfully benefit from extended thinking on bounded mechanical tasks — it just adds latency.
- Cursor's Auto mode tends to pick Composer for routine and Sonnet for ambiguous; Auto is fine inside an `[exec]` block but pin the model explicitly inside `[deep]` blocks.
- This table will need periodic refresh as Cursor and Anthropic ship new versions; that maintenance cost is the price of having one source of truth for tier-to-model mapping.

#### STOP marker template

Each STOP marker carries three things, formatted so the user can paste them straight into a new chat: the tier transition direction, the next model + thinking level for **both** Cursor and Claude Code, and a copy-pasteable prompt that names the next group, references the plan file, and includes a hard scope limit so the next agent halts at the next STOP.

Template (a `[deep] -> [exec]` transition):

    --- STOP: tier change [deep] -> [exec] ---

      Next model
        Cursor:      claude-4.6-sonnet-medium-thinking   (or gpt-5.5-medium)
        Claude Code: /model sonnet                       (extended thinking: medium)

      Prompt to paste into the next chat:
        Read .scratch/plan-<topic>-<word>.md. Execute <next group>.
        Stop at the next STOP marker and report back what you changed
        and any deviations from the plan.

    ---

For an `[exec] -> [fast]` transition, the prompt should also remind the model not to generalize:

    --- STOP: tier change [exec] -> [fast] ---

      Next model
        Cursor:      composer-2.5-fast
        Claude Code: /model haiku                        (no extended thinking)

      Prompt to paste into the next chat:
        Read .scratch/plan-<topic>-<word>.md. Execute <next group>.
        These are mechanical edits -- apply exactly what the plan
        specifies; do not refactor, rename, or generalize. Stop at the
        next STOP marker and report back.

    ---

For an escalation back to `[deep]` (after `[exec]` or `[fast]`):

    --- STOP: tier change [exec] -> [deep] ---

      Next model
        Cursor:      claude-opus-4-7-thinking-xhigh      (or gpt-5.3-codex)
        Claude Code: /model opus                         (extended thinking: xhigh)

      Prompt to paste into the next chat:
        Read .scratch/plan-<topic>-<word>.md and review the previous
        output in git status / diff. Then design <next group> (do not
        implement). Stop after the design is written and report back.

    ---

Rules for filling in the template:

- Substitute the actual plan filename (resolved when the plan is identified).
- Name the next group using whatever identifiers the plan uses: if headings
  carry IDs, use those (e.g. `m2 s1-s4`); if not, use exact title text
  (e.g. `the "Wire Redis client" through "Write integration tests" steps`).
- Always include the "Stop at the next STOP marker" hard limit so the cascade is preserved.
- Use `->` ASCII arrows rather than Unicode em-dash arrows so the marker is safe in terminals and grep.
- If the next group is a `[deep]` block being delegated to a parent, the prompt should say "design only, do not implement"; if it's `[exec]` or `[fast]`, the prompt should say "implement <next group>, stop at next STOP marker."

#### Kickoff template

A Kickoff block tells the next agent how to **start** executing a tagged plan: which model to run on and what prompt to paste. Same shape as a STOP marker, but emitted once at the top of the plan file rather than at each tier transition. Every plan that has been processed by `personal-plan-model-tiers` or `personal-plan-orchestrate` should carry exactly one Kickoff block at the top.

Placement and idempotence:

- The skill writes the Kickoff block at the **top of the plan file**, above the first heading, inside a fenced code block so it pastes cleanly.
- The block is idempotent: if a Kickoff block already exists at the top of the file (matching the marker line `--- KICKOFF: ... ---`), the skill **replaces** it with the appropriate variant rather than appending. A plan never carries more than one Kickoff block.
- Skills must not modify any other content in the plan when writing the Kickoff. Tagging rules, STOP markers, and existing prose all stay where they are.

Ask-user rule (after writing the Kickoff):

> Continue execution in this chat, or hand off to a new chat for clean context? (default: new chat)

Treat any non-affirmative answer (silence, dismissal, ambiguous reply) as **new chat**. On new chat, halt and let the user copy the Kickoff into a fresh session. On current chat, continue per the skill's procedure.

Two variants. The **passive** variant (used by `personal-plan-model-tiers`) picks the model from the first tagged group's tier; the **active** variant (used by `personal-plan-orchestrate`) is always Opus xhigh because the orchestrator-parent always runs at `[deep]`.

Passive variant — `[exec]` first wave (the most common shape):

    --- KICKOFF: begin execution at [exec] ---

      Next model
        Cursor:      claude-4.6-sonnet-medium-thinking   (or gpt-5.5-medium)
        Claude Code: /model sonnet                       (extended thinking: medium)

      Prompt to paste into the next chat:
        Read .scratch/plan-<topic>-<word>.md. Begin execution at the top
        of the plan. Stop at the next STOP marker and report back what
        you changed and any deviations from the plan.

    ---

Passive variant — `[fast]` first wave (prompt body adds the "no refactor" reminder):

    --- KICKOFF: begin execution at [fast] ---

      Next model
        Cursor:      composer-2.5-fast
        Claude Code: /model haiku                        (no extended thinking)

      Prompt to paste into the next chat:
        Read .scratch/plan-<topic>-<word>.md. Begin execution at the top
        of the plan. These are mechanical edits -- apply exactly what the
        plan specifies; do not refactor, rename, or generalize. Stop at
        the next STOP marker and report back.

    ---

For a `[deep]` first wave, use the same body as the `[exec]` example with the `[deep]` model row from the [Model picker](#model-picker) above (`claude-opus-4-7-thinking-xhigh` / `/model opus` xhigh).

Active variant — orchestrate (always `[deep]` / Opus xhigh):

    --- KICKOFF: begin orchestration at [deep] ---

      Next model
        Cursor:      claude-opus-4-7-thinking-xhigh      (or gpt-5.3-codex)
        Claude Code: /model opus                         (extended thinking: xhigh)

      Prompt to paste into the next chat:
        Read .scratch/plan-<topic>-<word>.md. The plan is already tagged.
        Run the personal-plan-orchestrate skill from the top: walk to
        each tier boundary, dispatch Task subagents per the skill's
        procedure, and pause only at the mandatory STOP gates. Do not
        execute plan work inline.

    ---

Rules for filling in the template:

- Substitute the actual plan filename (resolved when the plan is identified).
- For the passive variant, the `<tier>` is the **first executable tier** in the plan — the first heading carrying a `[deep]` / `[exec]` / `[fast]` tag, walking top-down. Higher-level grouping headings (milestones, phases) are untagged and ignored, per [Tag placement](#tag-placement). Use the tier value **after** the no-thrash promotion pass, so a `[fast]` step that gets promoted to `[exec]` is reflected as `[exec]` in the Kickoff.
- For the active variant, the model is **always** `claude-opus-4-7-thinking-xhigh` / `/model opus` xhigh, regardless of what the first wave's tier is. The orchestrator-parent always runs at `[deep]`.
- Use `->` ASCII arrows rather than Unicode em-dash arrows so the marker is safe in terminals and grep.

### Delegating execution to subagents

When a `[deep]` agent finishes a deep step and the next step is `[exec]` or `[fast]`, prefer delegating the next group to a subagent on a smaller model rather than burning the deep context on mechanical work.

- Use the harness's subagent/Task tool (Cursor `Task` with `subagent_type` and optional `model`; Claude Code `Task`; other harnesses use the equivalent).
- Pass the cheapest model that can plausibly complete the step (see the model picker in "Model-tier stop points" above). Step up only if the subagent fails or returns low-quality output.
- Give the subagent: the spec section, the exact files to touch, acceptance criteria, and a hard scope limit. Subagents do not see the parent conversation, so be explicit.
- The deep parent stays responsible for reviewing the subagent's output and deciding the next stop point.
- If the harness does not support per-subagent model selection, stop at the boundary instead and let the user start a fresh session on a cheaper model using the STOP marker's handoff prompt.

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
