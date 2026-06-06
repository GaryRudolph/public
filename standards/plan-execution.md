# Plan Execution

How multi-step plans are executed across models of different cost and capability: tagging steps by tier, grouping them into execution waves, stopping (or delegating to a subagent) at tier boundaries, tracking progress across chat handoffs, and the STOP-gate semantics that keep human oversight intact. This file is the canonical reference. The operational skills implement it in two layers: a shared **tagging** skill (`personal-plan-tag-tiers`) that only tags executable steps with honest complexity tiers, and two **execution drivers** (`personal-plan-model-tiers`, `personal-plan-orchestrate`) that group the tagged steps into waves, apply the no-thrash rule, and either emit STOP markers or dispatch subagents.

## Model-tier stop points

Plans are executed by agents of different cost and capability. To make the most of both, tag every executable step with one of three tiers, group consecutive same-tier steps into execution waves, and emit a STOP marker at every tier boundary so the model can be swapped (or the wave delegated to a subagent) before continuing.

This section is the canonical reference for the convention. The work splits into two responsibilities:

- **Tagging** — assigning each executable step its honest `[deep]` / `[exec]` / `[fast]` tier. This is owned by `personal-plan-tag-tiers`, a small shared skill. Tags reflect true complexity and are **never** rewritten for thrash reasons, so a tagged plan always shows how hard the work actually is. Run it first when you just want to see the complexity of a plan before deciding how to execute it.
- **Execution** — grouping the tagged steps into waves (the no-thrash rule), then either emitting STOP markers for a human-driven model swap or dispatching subagents. This is owned by the two driver skills, which call `personal-plan-tag-tiers` automatically when a plan is not tagged yet.

`personal-plan-model-tiers` is the passive driver (any harness that supports skills — Cursor, Claude Code — stopping at each tier boundary for a human model swap); `personal-plan-orchestrate` is the active Cursor counterpart where the `[deep]` parent delegates each wave via `Task(model=...)` subagents.

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

The no-thrash rule runs at the **execution-grouping layer**, not the tagging layer. Tagging (owned by `personal-plan-tag-tiers`) records the honest complexity of each step and is **never** rewritten for thrash reasons — a `[fast]` step stays `[fast]` in the plan so the true shape of the work stays visible. The no-thrash rule only decides how the tagged steps are grouped into **execution waves** and which model tier each wave runs on. The driver skills (`personal-plan-model-tiers`, `personal-plan-orchestrate`) apply it; the tagging skill does not.

Walk the tagged steps in order and collect consecutive same-tier steps into candidate waves. (A "wave" is the same unit the Status line and todo list call a *group*; the terms are interchangeable. "Wave" is used here to stress that a wave's execution tier can differ from a folded step's tag.) Then decide wave boundaries:

1. Always split (insert a STOP / dispatch boundary) at any `[deep]` ↔ `[exec]` boundary.
2. Always split at any `[deep]` ↔ `[fast]` boundary.
3. **Conditionally** split at an `[exec]` ↔ `[fast]` boundary:
   - If the `[fast]` block has **≥ 3 contiguous fast steps**, keep it as its own wave and split.
   - Otherwise, **fold those fast steps into the adjacent `[exec]` wave** (no split): they execute on the `[exec]` model so you don't spend more time swapping models than working — but their `[fast]` tags stay in the plan untouched. Folding is an execution-grouping decision, never a re-tag.
4. After folding, re-merge adjacent waves of the same **execution tier** before placing STOPs / dispatch boundaries.

**Execution tier vs. tag.** A wave's *execution tier* is the model it runs on; a step's *tag* is its honest complexity. They usually match. They differ only when a short `[fast]` run is folded into a neighboring `[exec]` wave: those steps keep their `[fast]` tags but execute at `[exec]`. The Kickoff "first wave tier", STOP markers, and `Task(model=...)` dispatches all key off the **execution tier** — never off a tag that has been folded.

### Wave annotation format

After the no-thrash grouping pass, each driver skill writes a **wave marker** into the plan file immediately before the first executable heading of each wave. Wave markers are written by `personal-plan-model-tiers` and `personal-plan-orchestrate`; `personal-plan-tag-tiers` does not write them.

Format (1-based wave counter, execution tier in brackets):

    --- WAVE N [execution-tier] ---

Example after grouping a plan with a folded `[fast]` run and a later `[deep]` wave:

    --- WAVE 1 [exec] ---
    #### s1 - [fast] Rename helper method
    #### s2 - [exec] Wire search results to view model

    --- STOP: tier change [exec] -> [deep] ---
      …
    ---

    --- WAVE 2 [deep] ---
    #### s3 - [deep] Decide cache invalidation strategy

No closing marker is needed — the next `--- WAVE …` marker, `--- STOP: …` marker, or end-of-file delimits the wave.

**The ≤ constraint.** For every executable step inside a wave, the step's tag must be **equal to or lesser than** the wave's execution tier. Tier ordering (most to least capable): `[deep]` > `[exec]` > `[fast]`.

| Wave execution tier | Permitted step tags |
|---|---|
| `[deep]` | `[deep]`, `[exec]`, `[fast]` |
| `[exec]` | `[exec]`, `[fast]` |
| `[fast]` | `[fast]` |

The folded-step case (`[fast]` steps inside an `[exec]` wave) always satisfies the constraint. If a step's tag is *greater* than the wave tier — for example, a `[deep]` step inside an `[exec]` wave — that is a tagging error. The driver must **flag the violation and refuse to write wave markers** until the tagging is corrected. The user must either re-tag the step downward or widen the wave to `[deep]` by re-running the no-thrash pass.

**Idempotence.** If wave markers are already present in the plan (re-entry into a partially-executed plan), the driver skips the wave-marker-writing pass but still validates the ≤ constraint for any unmarked waves. Do not add duplicate markers.

**Regex to find wave markers:** `^--- WAVE \d+ \[(deep|exec|fast)\] ---$`

### Model picker

| Tier | Cursor | Claude Code | Thinking level |
|---|---|---|---|
| `[deep]` | `claude-opus-4-8-thinking-xhigh` (alt: `gpt-5.5`) | `/model opus` | xhigh / max |
| `[exec]` | `claude-4.6-sonnet-medium-thinking` (alt: `gpt-5.3-codex`) | `/model sonnet` | medium |
| `[fast]` | `composer-2.5` (standard) (OpenAI alt: `gpt-5.3-codex`) | `/model haiku` | off / none |

Notes:
- For Claude Code, toggle extended thinking with `/think` (or the equivalent in the version installed). Haiku doesn't meaningfully benefit from extended thinking on bounded mechanical tasks — it just adds latency.
- Cursor's Auto mode tends to pick Composer for routine and Sonnet for ambiguous; Auto is fine inside an `[exec]` block but pin the model explicitly inside `[deep]` blocks.
- `[fast]` uses **Composer 2.5 standard** ($0.50/$2.50): same intelligence as the Fast variant ($3/$15) at ~6× lower cost and tuned for unattended/background runs — prefer it for mechanical `[fast]` work, since Fast's premium only pays back when a human is watching tokens stream live. Caveat: `personal-plan-orchestrate` dispatches `[fast]` groups via `Task(model=...)`, whose enum currently exposes only `composer-2.5-fast`, so orchestrated `[fast]` subagents run on Fast until Cursor adds a standard Task slug; the manual `personal-plan-model-tiers` flow can pick standard directly in the model picker.
- **OpenAI in Cursor — Codex does double duty.** `gpt-5.3-codex` is the right OpenAI pick for both `[exec]` and `[fast]` in Cursor; there is no cheaper dedicated OpenAI model in Cursor's current lineup that would justify a separate `[fast]` slot. On Anthropic the Sonnet → Composer gap is a ~6× cost drop worth a model swap; on OpenAI today Codex is already the low end. Use it for both tiers and skip the swap. If a cheaper OpenAI model appears in Cursor's picker, add it to `[fast]` and revisit.
- **Haiku vs Composer.** Haiku is Claude Code's `[fast]` model and Composer is Cursor's — they are platform-specific choices, not alternatives to each other. Do not substitute one for the other; each harness uses its own native fast model.
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

Cache-aware cost formula used by the `tokens:` tally:

    cost_usd ≈ ( uncached_input      × in_rate
               + cache_read_input    × in_rate × 0.10
               + cache_write_5m      × in_rate × 1.25
               + cache_write_1h      × in_rate × 2.00
               + output_tokens       × out_rate ) / 1_000_000

`output_tokens` already includes extended-thinking/reasoning tokens. Cache
multipliers are Anthropic API semantics (cache read = 0.10×, 5-min write =
1.25×, 1-hour write = 2.00× the base input rate). When no cache split is
available, set the cache terms to 0 and the formula collapses to
`input × in_rate + output × out_rate`.

### Token accounting — source precedence

Tally token cost from the most accurate source available, in this order:

1. **Real harness usage (preferred — captures reasoning + cache tiers).** On
   **Claude Code**, read the active session transcript at
   `~/.claude/projects/<project-slug>/<session-id>.jsonl` (if the session id
   is unknown, use the most-recently-modified `.jsonl` in the project-slug
   dir). Each assistant message carries `message.usage` with `input_tokens`,
   `cache_read_input_tokens`, `cache_creation_input_tokens` (split into
   `cache_creation.ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens`),
   and `output_tokens` (already includes extended thinking). Sum these per
   `message.model` across the wave and price with the cache-aware formula
   above. The in-progress final turn isn't flushed yet — a small tail, ignore
   it. Estimates from real usage are ±15%.

2. **Heuristic fallback.** On **Cursor** and any harness that does not expose
   per-turn usage to the agent (Cursor's `agent-transcripts/*.jsonl` carry
   only `{role, message}` — no usage), fall back to `~tokens ≈ chars / 4`:
   count input chars as everything read (prompts, file reads, tool outputs),
   output chars as everything written (chat text, tool-call args, file
   writes). This **cannot see** extended-thinking tokens or cache-read
   discounts, so treat it as **±40%**, label it `(heuristic)`, and set the
   cache terms to 0. If the user pastes real input/output/cache numbers from
   the Cursor usage UI, prefer those and price with the cache-aware formula.

When run outside Cursor you may substitute the provider's published per-model
rates for `in_rate`/`out_rate`; the cache multipliers are unchanged. No
estimate here is authoritative billing data.

### Wave title format

Both drivers label each wave with the same human-scannable title so a wave is identifiable wherever it surfaces:

    Wave {n} of {t} [{tier}] {group-id}

For example, `Wave 2 of 3 [exec] repo-A m2 s1-s3`. Fill it in as:

- `{n}` — the 1-based wave number the title refers to (the wave a STOP marker is launching is the *next* wave; a Kickoff always refers to wave 1).
- `{t}` — the total wave count after the no-thrash folding pass (the same `N` as the Kickoff `Status:` line).
- `{tier}` — that wave's execution tier (`[deep]` / `[exec]` / `[fast]`).
- `{group-id}` — the group identifier: heading IDs when the plan has them (e.g. `m2 s1-s3`), otherwise exact title text. For a parallel orchestrate wave, prefix each subagent's title with its working directory (repo or worktree name), e.g. `repo-B m2 s4-s6`.

Where the title surfaces:

- `personal-plan-orchestrate` passes it as the `Task` subagent `description`, so it becomes the subagent's name in the Cursor agents list. It is fixed at spawn — Cursor exposes no supported way to update it later.
- `personal-plan-model-tiers` emits it as a `Suggested chat title:` line in every STOP marker and the Kickoff block, so the user can paste it as the new chat's name. There is no API for a foreground chat to set its own title, so this is **advisory** — emit it even though there is no guarantee the harness will use it.

### STOP marker template

Each STOP marker carries four things, formatted so the user can paste them straight into a new chat: a `Suggested chat title:` line ([Wave title format](#wave-title-format)), the tier transition direction, the next model + thinking level for **both** Cursor and Claude Code, and a copy-pasteable prompt that names the next group, references the plan file by its absolute path, and includes a hard scope limit so the next agent halts at the next STOP.

Template (a `[deep] -> [exec]` transition):

    --- STOP: tier change [deep] -> [exec] ---

      Suggested chat title: Wave <n> of <t> [exec] <next group>

      Next model
        Cursor:      claude-4.6-sonnet-medium-thinking   (or gpt-5.3-codex)
        Claude Code: /model sonnet                       (extended thinking: medium)

      Prompt to paste into the next chat:
        Wave <n> of <t> [exec] <next group>
        Read <absolute path to the plan file>. Execute <next group>.
        Before you stop, update plan progress: append ` (done)` to the
        headings you finished, update the Kickoff Status line, and flip the
        matching todos. Then stop at the next STOP marker and report what
        you changed and any deviations from the plan.

    ---

For an `[exec] -> [fast]` transition, the prompt should also remind the model not to generalize:

    --- STOP: tier change [exec] -> [fast] ---

      Suggested chat title: Wave <n> of <t> [fast] <next group>

      Next model
        Cursor:      composer-2.5 (standard)
        Claude Code: /model haiku                        (no extended thinking)

      Prompt to paste into the next chat:
        Wave <n> of <t> [fast] <next group>
        Read <absolute path to the plan file>. Execute <next group>.
        These are mechanical edits -- apply exactly what the plan
        specifies; do not refactor, rename, or generalize. Before you
        stop, update plan progress (mark the headings you finished
        ` (done)`, update the Status line, flip the matching todos). Then
        stop at the next STOP marker and report back.

    ---

For an escalation back to `[deep]` (after `[exec]` or `[fast]`):

    --- STOP: tier change [exec] -> [deep] ---

      Suggested chat title: Wave <n> of <t> [deep] <next group>

      Next model
        Cursor:      claude-opus-4-8-thinking-xhigh      (or gpt-5.5)
        Claude Code: /model opus                         (extended thinking: xhigh)

      Prompt to paste into the next chat:
        Wave <n> of <t> [deep] <next group>
        Read <absolute path to the plan file> and review the previous
        output in git status / diff. Then design <next group> (do not
        implement). Before you stop, update plan progress (mark the
        headings you finished ` (done)`, update the Status line, flip the
        matching todos). Stop after the design is written and report back.

    ---

Rules for filling in the template:

- `<absolute path to the plan file>` is the **fully-qualified absolute path** to the plan file, resolved when the plan was identified — for example: `/Users/gary/Projects/personal/public/.scratch/plan-topic-word.md`. Never emit a bare filename or a repo-relative path — the next chat may start from a different working directory.
- Name the next group using whatever identifiers the plan uses: if headings
  carry IDs, use those (e.g. `m2 s1-s4`); if not, use exact title text
  (e.g. `the "Wire Redis client" through "Write integration tests" steps`).
- Always include the `Suggested chat title:` line in the [Wave title format](#wave-title-format). `{n}` is the **next** wave (the one this STOP launches), `{t}` the total wave count, and `{group-id}` the same identifier used to name the next group above. It is advisory — a foreground chat cannot set its own title, so emit it for the user to paste even though there is no guarantee the harness will use it.
- Always include the "Stop at the next STOP marker" hard limit so the cascade is preserved.
- Always include the **progress-update reminder** spelled out inline in the prompt body (append ` (done)` to finished headings, update the Kickoff Status line, flip the matching todos). The pasted chat usually does **not** re-load the driver skill, so this inline reminder is the only way the [Progress tracking](#progress-tracking) convention reaches it — never drop it. Do not factor it out into a separate checklist block in the plan; keep it in the prompt.
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

      Suggested chat title: Wave 1 of N [exec] <first group>

      Next model
        Cursor:      claude-4.6-sonnet-medium-thinking   (or gpt-5.3-codex)
        Claude Code: /model sonnet                       (extended thinking: medium)

      Prompt to paste into the next chat:
        Read <absolute path to the plan file>. Begin execution at the top
        of the plan. Before you stop, update plan progress: append
        ` (done)` to the headings you finished, update the Kickoff Status
        line, and flip the matching todos. Then stop at the next STOP
        marker and report what you changed and any deviations from the
        plan.

    ---

Passive variant — `[fast]` first wave (prompt body adds the "no refactor" reminder):

    --- KICKOFF: begin execution at [fast] ---

      Status: 0/N groups done | current: <first group> [fast] | updated YYYY-MM-DD

      Suggested chat title: Wave 1 of N [fast] <first group>

      Next model
        Cursor:      composer-2.5 (standard)
        Claude Code: /model haiku                        (no extended thinking)

      Prompt to paste into the next chat:
        Read <absolute path to the plan file>. Begin execution at the top
        of the plan. These are mechanical edits -- apply exactly what the
        plan specifies; do not refactor, rename, or generalize. Before you
        stop, update plan progress (mark the headings you finished
        ` (done)`, update the Status line, flip the matching todos). Then
        stop at the next STOP marker and report back.

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
        execute plan work inline. Update plan progress after each wave
        returns per the skill's procedure. You are the kickoff destination
        chat; skip the "continue here or new chat?" question and begin
        dispatching immediately.

    ---

Rules for filling in the template:

- `<absolute path to the plan file>` is the **fully-qualified absolute path** to the plan file, resolved when the plan was identified — for example: `/Users/gary/Projects/personal/public/.scratch/plan-topic-word.md`. Never emit a bare filename or a repo-relative path — the next chat may start from a different working directory.
- For the passive variant, the `<tier>` is the **execution tier of the first wave** after the no-thrash folding pass (see [No-thrash rule](#no-thrash-rule)). This is normally the tag on the first executable heading, walking top-down — higher-level grouping headings (milestones, phases) are untagged and ignored, per [Tag placement](#tag-placement). The one exception: when a short leading `[fast]` run (< 3 steps) is folded into the following `[exec]` wave, the first wave executes at `[exec]`, so the Kickoff shows `[exec]` even though those headings keep their honest `[fast]` tags.
- For the active variant, the model is **always** `claude-opus-4-8-thinking-xhigh` / `/model opus` xhigh, regardless of what the first wave's tier is. The orchestrator-parent always runs at `[deep]`.
- Use `->` ASCII arrows rather than Unicode em-dash arrows so the marker is safe in terminals and grep.
- Fill in the `Status:` line with the total group count (`N`), the first group's identifier, and today's date. Update it as execution progresses (see [Progress tracking](#progress-tracking) below).
- For the passive variants, include the `Suggested chat title:` line in the [Wave title format](#wave-title-format) for the first wave (`Wave 1 of N [<tier>] <first group>`). It is advisory — a foreground chat cannot set its own title, so emit it for the user to paste even though the harness may ignore it. The active orchestrate variant has no such line: its per-wave titles are the `Task` subagent descriptions.
- For the passive variants, always keep the **progress-update reminder** spelled out inline in the prompt body (append ` (done)` to finished headings, update the Status line, flip the matching todos). A fresh chat that pastes this prompt usually does **not** re-load the driver skill, so this line is the only way the [Progress tracking](#progress-tracking) convention reaches the worker — it is the single most common reason a wave finishes without being marked done, so never drop it. (The active orchestrate variant re-loads the skill, so its parent applies the updates per the skill procedure instead; see [Who updates progress, and how](#who-updates-progress-and-how).)

## Who updates progress, and how

The two tracking surfaces — the in-harness todo list and the durable plan markdown file (both defined under [Progress tracking](#progress-tracking) below) — are kept in sync differently by each driver, because only one flow has a coordinator:

- `personal-plan-orchestrate` **has an orchestrator-parent**. After each wave's subagent returns, the parent applies the [Progress tracking](#progress-tracking) updates itself (mark ` (done)`, update the `Status:` line, flip todos). Subagents do mechanical work in their own working directory and never touch the plan file. This is handled by the skill procedure, so it does not need to ride in any prompt.
- `personal-plan-model-tiers` **has no orchestrator**. Each wave runs in its own pasted chat, and that chat usually does **not** re-load the driver skill — it just reads the plan, executes, and stops. So the progress-update instruction is **baked inline into every Kickoff/STOP prompt body** (see the templates above). The pasted prompt is the only place the convention can reach a fresh chat, which is why the reminder is spelled out in full there rather than referenced. Do **not** add a separate checklist block to the plan file to carry this — it is noise for the human and burns context; the inline prompt reminder is the mechanism.

## Progress tracking

Plans span multiple chat sessions, which means native harness todos (Cursor Plan-mode checkboxes, `TodoWrite`) disappear on each handoff. The `.scratch/plan-*.md` file is the durable source of truth. The convention below keeps both surfaces in sync throughout execution. Who applies it differs by driver — see [Who updates progress, and how](#who-updates-progress-and-how) above.

### Two surfaces

- **Harness todo list** (live, in-session): one todo per *execution wave* (consecutive same-tier block after the no-thrash folding pass; a short folded `[fast]` run rides inside its neighbor's wave). The current wave is `in_progress`; it flips to `completed` the moment the wave finishes. Seeded by the driver skill that writes the Kickoff block.
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
- **A non-answer is never approval.** A timeout, empty reply, dismissed prompt, skipped prompt, ambiguous reply, or regaining control via a background-subagent completion notification does NOT permit advancing past a pending gate. When in doubt, do not proceed.
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
