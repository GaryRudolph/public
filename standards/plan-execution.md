# Plan Execution

How multi-step plans are executed across models of different cost and capability: tagging steps by tier, grouping them, stopping (or delegating to a subagent) at tier boundaries, tracking progress across chat handoffs, and the STOP-gate semantics that keep human oversight intact. This file is the canonical reference; the operational skills (`personal-plan-model-tiers`, `personal-plan-orchestrate`) implement it.

## Model-tier stop points

Plans are executed by agents of different cost and capability. To make the most of both, tag every executable step with one of three tiers, group consecutive same-tier steps, and emit a STOP marker at every tier boundary so the model can be swapped (or the group delegated to a subagent) before continuing.

This section is the canonical reference for the convention. The `personal-plan-model-tiers` skill (and the equivalent in any harness) is the operational layer that implements it.

### Tiers

- `[deep]` — top-tier reasoning. Architecture decisions, ambiguous requirements, non-obvious debugging, security-sensitive review, library/stack trade-offs, anywhere the cost of getting it wrong is high.
- `[exec]` — standard implementation. Multi-file changes with cross-file reasoning, refactors with a clear target but real judgment, test writing where cases need thought, work that must read repo patterns first to extend them.
- `[fast]` — mechanical, fully-specified, single-concern work. Renames, format changes, applying a decided design line-by-line, doc updates, well-bounded ports.

**Default-up bias**: when in doubt, tag `[deep]` > `[exec]` > `[fast]`. A misclassified `[fast]` produces bad output; a misclassified `[deep]` wastes a little money.

### `[fast]` downgrade checklist

A step only earns `[fast]` if **all** of these are true:

- The step lists exact files and the change is fully spec'd at line-level.
- No cross-file invariants — the change is scoped to a single concern.
- An existing similar pattern in the repo can be copied from.
- Tests cover the change (fast feedback if the model misses).
- Reversal cost is low (small diff, easy revert).
- A later `[deep]` or `[exec]` group will review this output before it ships.

Any `no` → tag `[exec]`.

### Tag placement

Tag **executable steps only** — not milestone, phase, or section headings.
The executable level is typically the deepest heading level in the plan. If
the plan uses only one heading level, tag every heading at that level.

**One rule:** the tag goes immediately after the title separator (the first
`-`, `:`, or `.` followed by whitespace) and before the title text. If the
heading has no separator, the tag goes immediately after the heading marker.

Do not rewrite IDs, renumber, change casing, add separators, or coin new
identifiers. This convention works with any plan structure — `m{N}`/`s{N}`
is the recommended naming shape for new plans (see "Steps within a milestone"
in [documentation.md](documentation.md)), but the skill adapts to whatever
structure already exists.

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

### No-thrash rule

Walk the tagged steps in order and collect consecutive same-tier steps into groups. Then:

1. Always insert a STOP at any `[deep]` ↔ `[exec]` boundary.
2. Always insert a STOP at any `[deep]` ↔ `[fast]` boundary.
3. **Conditionally** insert a STOP at an `[exec]` ↔ `[fast]` boundary:
   - If the `[fast]` block has **≥ 3 contiguous fast steps**, emit the STOP.
   - Otherwise, **promote those fast steps to `[exec]`** (no STOP) so you don't spend more time swapping models than working.
4. After promotions, re-merge adjacent same-tier groups before deciding STOP placement.

### Model picker

| Tier | Cursor | Claude Code | Thinking level |
|---|---|---|---|
| `[deep]` | `claude-opus-4-8-thinking-xhigh` (alt: `gpt-5.5`) | `/model opus` | xhigh / max |
| `[exec]` | `claude-4.6-sonnet-medium-thinking` (alt: `gpt-5.5-medium`) | `/model sonnet` | medium |
| `[fast]` | `composer-2.5` (standard) | `/model haiku` | off / none |

Notes:
- For Claude Code, toggle extended thinking with `/think` (or the equivalent in the version installed). Haiku doesn't meaningfully benefit from extended thinking on bounded mechanical tasks — it just adds latency.
- Cursor's Auto mode tends to pick Composer for routine and Sonnet for ambiguous; Auto is fine inside an `[exec]` block but pin the model explicitly inside `[deep]` blocks.
- `[fast]` uses **Composer 2.5 standard** ($0.50/$2.50): same intelligence as the Fast variant ($3/$15) at ~6× lower cost and tuned for unattended/background runs — prefer it for mechanical `[fast]` work, since Fast's premium only pays back when a human is watching tokens stream live. Caveat: `personal-plan-orchestrate` dispatches `[fast]` groups via `Task(model=...)`, whose enum currently exposes only `composer-2.5-fast`, so orchestrated `[fast]` subagents run on Fast until Cursor adds a standard Task slug; the manual `personal-plan-model-tiers` flow can pick standard directly in the model picker.
- For `[deep]`, the ChatGPT alt is `gpt-5.5` (xhigh) — it leads terminal/agentic and computer-use work and emits far fewer output tokens than Opus on long loops; keep Opus as the primary for multi-file architecture and tool-heavy MCP orchestration.
- This table will need periodic refresh as Cursor and Anthropic ship new versions; that maintenance cost is the price of having one source of truth for tier-to-model mapping.

### Model price table

Cursor usage-based rates for the three planning tiers. Refresh alongside the Model picker above when rates change.

| Cursor slug | Input ($/Mtok) | Output ($/Mtok) |
|---|---|---|
| `claude-opus-4-8-thinking-xhigh` | $5.00 | $25.00 |
| `claude-4.6-sonnet-medium-thinking` | $3.00 | $15.00 |
| `composer-2.5` (standard) | $0.50 | $2.50 |
| `composer-2.5-fast` | $3.00 | $15.00 |

*As of 2026-05-29. Source: [cursor.com/docs/models-and-pricing](https://cursor.com/docs/models-and-pricing). `composer-2.5` (standard) and `composer-2.5-fast` are the same model at different inference throughput; `[fast]` uses standard, while orchestrate Task subagents are currently limited to fast (see the Model picker notes above).*

Cost formula used by the `tokens:` tally:

    cost_usd ≈ (input_tokens / 1_000_000) × in_rate + (output_tokens / 1_000_000) × out_rate

All cost estimates inherit the `~tokens ≈ chars / 4` heuristic (±15%) and are rough estimates, not authoritative billing data.

### STOP marker template

Each STOP marker carries three things, formatted so the user can paste them straight into a new chat: the tier transition direction, the next model + thinking level for **both** Cursor and Claude Code, and a copy-pasteable prompt that names the next group, references the plan file by its absolute path, and includes a hard scope limit so the next agent halts at the next STOP.

Template (a `[deep] -> [exec]` transition):

    --- STOP: tier change [deep] -> [exec] ---

      Next model
        Cursor:      claude-4.6-sonnet-medium-thinking   (or gpt-5.5-medium)
        Claude Code: /model sonnet                       (extended thinking: medium)

      Prompt to paste into the next chat:
        Read <absolute path to the plan file>. Execute <next group>.
        Stop at the next STOP marker and report back what you changed
        and any deviations from the plan.

    ---

For an `[exec] -> [fast]` transition, the prompt should also remind the model not to generalize:

    --- STOP: tier change [exec] -> [fast] ---

      Next model
        Cursor:      composer-2.5 (standard)
        Claude Code: /model haiku                        (no extended thinking)

      Prompt to paste into the next chat:
        Read <absolute path to the plan file>. Execute <next group>.
        These are mechanical edits -- apply exactly what the plan
        specifies; do not refactor, rename, or generalize. Stop at the
        next STOP marker and report back.

    ---

For an escalation back to `[deep]` (after `[exec]` or `[fast]`):

    --- STOP: tier change [exec] -> [deep] ---

      Next model
        Cursor:      claude-opus-4-8-thinking-xhigh      (or gpt-5.5)
        Claude Code: /model opus                         (extended thinking: xhigh)

      Prompt to paste into the next chat:
        Read <absolute path to the plan file> and review the previous
        output in git status / diff. Then design <next group> (do not
        implement). Stop after the design is written and report back.

    ---

Rules for filling in the template:

- `<absolute path to the plan file>` is the **fully-qualified absolute path** to the plan file, resolved when the plan was identified — for example: `/Users/gary/Projects/personal/public/.scratch/plan-topic-word.md`. Never emit a bare filename or a repo-relative path — the next chat may start from a different working directory.
- Name the next group using whatever identifiers the plan uses: if headings
  carry IDs, use those (e.g. `m2 s1-s4`); if not, use exact title text
  (e.g. `the "Wire Redis client" through "Write integration tests" steps`).
- Always include the "Stop at the next STOP marker" hard limit so the cascade is preserved.
- Use `->` ASCII arrows rather than Unicode em-dash arrows so the marker is safe in terminals and grep.
- If the next group is a `[deep]` block being delegated to a parent, the prompt should say "design only, do not implement"; if it's `[exec]` or `[fast]`, the prompt should say "implement <next group>, stop at next STOP marker."

### Kickoff template

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

      Status: 0/N groups done | current: <first group> [exec] | updated YYYY-MM-DD

      Next model
        Cursor:      claude-4.6-sonnet-medium-thinking   (or gpt-5.5-medium)
        Claude Code: /model sonnet                       (extended thinking: medium)

      Prompt to paste into the next chat:
        Read <absolute path to the plan file>. Begin execution at the top
        of the plan. Stop at the next STOP marker and report back what
        you changed and any deviations from the plan.

    ---

Passive variant — `[fast]` first wave (prompt body adds the "no refactor" reminder):

    --- KICKOFF: begin execution at [fast] ---

      Status: 0/N groups done | current: <first group> [fast] | updated YYYY-MM-DD

      Next model
        Cursor:      composer-2.5 (standard)
        Claude Code: /model haiku                        (no extended thinking)

      Prompt to paste into the next chat:
        Read <absolute path to the plan file>. Begin execution at the top
        of the plan. These are mechanical edits -- apply exactly what the
        plan specifies; do not refactor, rename, or generalize. Stop at
        the next STOP marker and report back.

    ---

For a `[deep]` first wave, use the same body as the `[exec]` example with the `[deep]` model row from the [Model picker](#model-picker) above (`claude-opus-4-8-thinking-xhigh` / `/model opus` xhigh).

Active variant — orchestrate (always `[deep]` / Opus xhigh):

    --- KICKOFF: begin orchestration at [deep] ---

      Status: 0/N groups done | current: <first group> [deep] | updated YYYY-MM-DD

      Next model
        Cursor:      claude-opus-4-8-thinking-xhigh      (or gpt-5.5)
        Claude Code: /model opus                         (extended thinking: xhigh)

      Prompt to paste into the next chat:
        Read <absolute path to the plan file>. The plan is already tagged.
        Run the personal-plan-orchestrate skill from the top: walk to
        each tier boundary, dispatch Task subagents per the skill's
        procedure, and pause only at the mandatory STOP gates. Do not
        execute plan work inline. You are the kickoff destination chat;
        skip the "continue here or new chat?" question and begin
        dispatching immediately.

    ---

Rules for filling in the template:

- `<absolute path to the plan file>` is the **fully-qualified absolute path** to the plan file, resolved when the plan was identified — for example: `/Users/gary/Projects/personal/public/.scratch/plan-topic-word.md`. Never emit a bare filename or a repo-relative path — the next chat may start from a different working directory.
- For the passive variant, the `<tier>` is the **first executable tier** in the plan — the first heading carrying a `[deep]` / `[exec]` / `[fast]` tag, walking top-down. Higher-level grouping headings (milestones, phases) are untagged and ignored, per [Tag placement](#tag-placement). Use the tier value **after** the no-thrash promotion pass, so a `[fast]` step that gets promoted to `[exec]` is reflected as `[exec]` in the Kickoff.
- For the active variant, the model is **always** `claude-opus-4-8-thinking-xhigh` / `/model opus` xhigh, regardless of what the first wave's tier is. The orchestrator-parent always runs at `[deep]`.
- Use `->` ASCII arrows rather than Unicode em-dash arrows so the marker is safe in terminals and grep.
- Fill in the `Status:` line with the total group count (`N`), the first group's identifier, and today's date. Update it as execution progresses (see [Progress tracking](#progress-tracking) below).

## Progress tracking

Plans span multiple chat sessions, which means native harness todos (Cursor Plan-mode checkboxes, `TodoWrite`) disappear on each handoff. The `.scratch/plan-*.md` file is the durable source of truth. The convention below keeps both surfaces in sync throughout execution.

### Two surfaces

- **Harness todo list** (live, in-session): one todo per *group* (consecutive same-tier block after no-thrash). The current group is `in_progress`; it flips to `completed` the moment the group finishes. Seeded by the skill that writes the Kickoff block.
- **Plan markdown file** (durable, cross-session): updated at every STOP boundary and at plan completion. Survives chat handoffs because the `.scratch/` file is on disk.

### Marking steps done

When a group finishes, append ` (done)` to the end of every executable heading in that group:

    #### s1 - [exec] Wire search results to view model  (done)

Rules:
- The marker goes at the **end of the heading line**, after all other content, so it never collides with the tier-tag regex `^#+\s+.*\[(deep|exec|fast)\]`.
- Done-step regex: `\(done\)\s*$`
- Incomplete steps: any tagged heading that does **not** match the done-step regex.
- This is the **only** sanctioned heading mutation besides the tier tag itself. The "do not rename/renumber" rule has an explicit carve-out for appending ` (done)`.

### Updating the Status line

After each group finishes, update the `Status:` line inside the Kickoff block:

    Status: 2/5 groups done | current: m2 s1-s4 [exec] | updated 2026-05-28

- `2/5` — groups completed so far out of the total group count.
- `current:` — the identifier of the **next** group yet to start (or the just-finished group if this is the last one).
- `updated` — date of the update (ISO date, no time).

When re-entering a plan in a fresh chat, re-derive the native todo list from this Status line plus the ` (done)` markers on headings. Do not assume native todos exist.

### Final completion (all groups done)

When the last group finishes:

1. Flip all remaining native todos to `completed`.
2. Ensure every executable heading carries ` (done)`.
3. Replace the Kickoff marker line with the terminal form:

       --- KICKOFF: plan complete ---

   and update the Status line to:

       Status: N/N groups done | completed YYYY-MM-DD

4. Append a **Completion summary** at the bottom of the plan file (below all existing content):

       ## Completion summary

       **Completed**: YYYY-MM-DD
       **What shipped**: <one-paragraph summary>
       **Deviations from plan**: <list, or "none">
       **Follow-ups**: <list, or "none">

   This summary dovetails with the handoff convention — promote it to a `.scratch/handoff-*.md` or `handoffs/` file if the work needs to be picked up by another engineer or session.

## STOP gate semantics (fail closed)

- **Gates block on an explicit affirmative answer.** Mandatory gates exist for human oversight.
- **A non-answer is never approval.** A timeout, empty reply, dismissed prompt, ambiguous reply, or regaining control via a background-subagent completion notification does NOT permit advancing past a pending gate. When in doubt, do not proceed.
- **Approval is per-gate.** Each mandatory gate needs its own fresh explicit answer. A one-time "continue" / "proceed" / "use what you have" applies ONLY to the gate it answers; it is not a standing waiver for future gates. (This is the orchestration-specific application of the general "Wait for approval" workflow rule in AGENTS.md.)
- **Unattended is opt-in only.** The sole way to disable gate blocking is an explicit user instruction such as "run unattended", "auto-approve all gates", or "auto-approve the next N gates". Absent that, every mandatory gate blocks.
- **On a blocked gate, do both:**
  1. Re-post the exact gate question, end the turn, and wait. Do not poll, do not dispatch.
  2. Record durable pending state in the Kickoff `Status:` line, e.g.

         Status: 2/5 groups done | BLOCKED at gate 2 ([exec]->[deep] review) | updated 2026-05-28

     On re-entry, an agent that sees a `BLOCKED at gate` status re-posts that exact question and waits — it never assumes the gate was approved.
- Cross-references: [Progress tracking](#progress-tracking) (the Status line) and the AGENTS.md "Wait for approval" workflow rule.

## Delegating execution to subagents

When a `[deep]` agent finishes a deep step and the next step is `[exec]` or `[fast]`, prefer delegating the next group to a subagent on a smaller model rather than burning the deep context on mechanical work.

- Use the harness's subagent/Task tool (Cursor `Task` with `subagent_type` and optional `model`; Claude Code `Task`; other harnesses use the equivalent).
- Pass the cheapest model that can plausibly complete the step (see the model picker in "Model-tier stop points" above). Step up only if the subagent fails or returns low-quality output.
- Give the subagent: the spec section, the exact files to touch, acceptance criteria, and a hard scope limit. Subagents do not see the parent conversation, so be explicit.
- The deep parent stays responsible for reviewing the subagent's output and deciding the next stop point.
- If the harness does not support per-subagent model selection, stop at the boundary instead and let the user start a fresh session on a cheaper model using the STOP marker's handoff prompt.
