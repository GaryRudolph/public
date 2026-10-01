# Plan Execution

How multi-step plans are executed across models of different cost and capability: tagging steps by tier, grouping them into execution waves, stopping (or delegating to a subagent) at tier boundaries, tracking progress across chat handoffs, and the STOP-gate semantics that keep human oversight intact. This file is the canonical reference. The operational skills implement it in two layers: a shared **tagging** skill (`personal-plan-tag-tiers`) that only tags executable steps with honest complexity tiers, and two **execution drivers** (`personal-plan-model-tiers`, `personal-plan-orchestrate`) that group the tagged steps into waves, apply the no-thrash rule, and either emit STOP markers or dispatch subagents.

## Model-tier stop points

Plans are executed by agents of different cost and capability. To make the most of both, tag every executable step with one of four tiers, group consecutive same-tier steps into execution waves, and emit a STOP marker at every tier boundary so the model can be swapped (or the wave delegated to a subagent) before continuing.

This section is the canonical reference for the convention. The work splits into two responsibilities:

- **Tagging** — assigning each executable step its honest `[xdeep]` / `[deep]` / `[exec]` / `[fast]` tier. This is owned by `personal-plan-tag-tiers`, a small shared skill. Tags reflect true complexity and are **never** rewritten for thrash reasons, so a tagged plan always shows how hard the work actually is. Run it first when you just want to see the complexity of a plan before deciding how to execute it.
- **Execution** — grouping the tagged steps into waves (the no-thrash rule), then either emitting STOP markers for a human-driven model swap or dispatching subagents. This is owned by the two driver skills, which call `personal-plan-tag-tiers` automatically when a plan is not tagged yet.

`personal-plan-model-tiers` is the passive driver (any harness that supports skills — Cursor, Claude Code — stopping at each tier boundary for a human model swap); `personal-plan-orchestrate` is the active Cursor counterpart where the `[deep]` parent delegates each wave via `Task(model=...)` subagents.

### Tiers

- `[xdeep]` — frontier reasoning, one rung above `[deep]`. For steps where a strong `[deep]` model is likely to be wrong, or already was: novel designs with nothing to copy from, security and correctness arguments (auth, crypto, concurrency, distributed consistency), migrations that can't be rolled back, and long-horizon analysis over a very large context. For now it runs Opus 5.5 at max effort, with ultracode in Claude Code (see [Model picker](#model-picker)). Max effort (plus many agents in Claude Code) spends far more tokens than a `[deep]` wave, so the tag has to pass the [upgrade checklist](#xdeep-upgrade-checklist).
- `[deep]` — top-tier reasoning. Architecture decisions, ambiguous requirements, non-obvious debugging, security-sensitive review, library/stack trade-offs, anywhere the cost of getting it wrong is high.
- `[exec]` — standard implementation. Multi-file changes with cross-file reasoning, refactors with a clear target but real judgment, test writing where cases need thought, work that must read repo patterns first to extend them.
- `[fast]` — mechanical, fully-specified, single-concern work. Renames, format changes, applying a decided design line-by-line, doc updates, well-bounded ports.

**Default-up bias**: when in doubt, tag `[deep]` > `[exec]` > `[fast]`. A misclassified `[fast]` produces bad output; a misclassified `[deep]` wastes a little money. The bias stops at `[deep]`: doubt between `[deep]` and `[xdeep]` resolves to `[deep]`. A misclassified `[xdeep]` wastes real money, and a `[deep]` review beat or a failed attempt escalates the step anyway.

### `[xdeep]` upgrade checklist

A step only earns `[xdeep]` if it is clearly `[deep]` work **and** at least one of these is true:

- A `[deep]` attempt already failed it, or its review beat returned `CONCERNS` on the same design question twice.
- A mistake would be expensive and quiet: a security boundary, auth or crypto design, a data migration that can't be rolled back, concurrency or consistency correctness.
- The design is novel: nothing in the repo, the standards, or the dependencies to copy from, and it spans more than one system.
- The step needs sustained reasoning over a very large context (a whole-codebase audit, a cross-repo plan) where a `[deep]` model loses the thread.

None true → tag `[deep]`.

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

    #### s1 - [xdeep] Design token-revocation protocol
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

To find tagged headings use the regex: `^#+\s+.*\[(xdeep|deep|exec|fast)\]`

### No-thrash rule

The no-thrash rule runs at the **execution-grouping layer**, not the tagging layer. Tagging (owned by `personal-plan-tag-tiers`) records the honest complexity of each step and is **never** rewritten for thrash reasons — a `[fast]` step stays `[fast]` in the plan so the true shape of the work stays visible. The no-thrash rule only decides how the tagged steps are grouped into **execution waves** and which model tier each wave runs on. The driver skills (`personal-plan-model-tiers`, `personal-plan-orchestrate`) apply it; the tagging skill does not.

Walk the tagged steps in order and collect consecutive same-tier steps into candidate waves. (A "wave" is the same unit the Status line and todo list call a *group*; the terms are interchangeable. "Wave" is used here to stress that a wave's execution tier can differ from a folded step's tag.) Then decide wave boundaries:

1. Always split (insert a STOP / dispatch boundary) at any boundary involving `[xdeep]`. `[xdeep]` work stays in its own waves, so its premium is spent only on the steps that earned the tag.
2. Always split at any `[deep]` ↔ `[exec]` boundary.
3. Always split at any `[deep]` ↔ `[fast]` boundary.
4. **Conditionally** split at an `[exec]` ↔ `[fast]` boundary:
   - If the `[fast]` block has **≥ 3 contiguous fast steps**, keep it as its own wave and split.
   - Otherwise, **fold those fast steps into the adjacent `[exec]` wave** (no split): they execute on the `[exec]` model so you don't spend more time swapping models than working — but their `[fast]` tags stay in the plan untouched. Folding is an execution-grouping decision, never a re-tag.
5. After folding, re-merge adjacent waves of the same **execution tier** before placing STOPs / dispatch boundaries.

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

**The ≤ constraint.** For every executable step inside a wave, the step's tag must be **equal to or lesser than** the wave's execution tier. Tier ordering (most to least capable): `[xdeep]` > `[deep]` > `[exec]` > `[fast]`.

| Wave execution tier | Permitted step tags |
|---|---|
| `[xdeep]` | `[xdeep]` only (rule 1 never folds into or out of it) |
| `[deep]` | `[deep]`, `[exec]`, `[fast]` |
| `[exec]` | `[exec]`, `[fast]` |
| `[fast]` | `[fast]` |

The folded-step case (`[fast]` steps inside an `[exec]` wave) always satisfies the constraint. If a step's tag is *greater* than the wave tier — for example, a `[deep]` step inside an `[exec]` wave — that is a tagging error. The driver must **flag the violation and refuse to write wave markers** until the tagging is corrected. The user must either re-tag the step downward or widen the wave to `[deep]` by re-running the no-thrash pass. A lower-tagged step inside an `[xdeep]` wave is also an error, since rule 1 always splits there: re-run the no-thrash pass.

**Idempotence.** If wave markers are already present in the plan (re-entry into a partially-executed plan), the driver skips the wave-marker-writing pass but still validates the ≤ constraint for any unmarked waves. Do not add duplicate markers.

**Regex to find wave markers:** `^--- WAVE \d+ \[(xdeep|deep|exec|fast)\] ---$`

### Model picker

One row per harness, one column per tier, effort in parentheses. "Switch harness" means the harness has nothing at that tier: run that wave in Claude Code, Codex, or Cursor.

| Harness | `[xdeep]` | `[deep]` | `[exec]` | `[fast]` |
|---|---|---|---|---|
| Claude Code | `/model opus` (max) + ultracode (alt: `/model fable` (max)) | `/model opus` (high) | `/model sonnet` (high) | `/model haiku` (none) |
| Cursor | `claude-opus-5-5[effort=max]` (alt: `claude-fable-5-1[effort=max]`) | `claude-opus-5-5[effort=high]` | `grok-4-7[effort=high]` (alt: `claude-sonnet-5-5[effort=high]`) | `composer-2.5[fast=false]` |
| Codex | `gpt-6-astra` (xhigh) | `gpt-6.1-sol` (xhigh) | `gpt-6.1-sol` (medium) | `gpt-6-luna` (low) |
| Gemini CLI | switch harness | `gemini-3.1-pro-preview` (high) | `gemini-3.8-flash` (high) | `gemini-3.5-flash-lite` (low) |
| Muse Code | switch harness | `muse-spark-1.3` (xhigh) | `muse-spark-1.3` (medium) | `muse-spark-1.3` (low) |
| Grok Build | switch harness | `grok-4.7` (xhigh) | `grok-4.7` (high) | `grok-build-0.1` |

*As of 2026-10-01.* Refresh the rows that pin versions (everything but Claude Code) when a harness adds a model.

Notes:
- **`[xdeep]` is Opus 5.5 at max effort plus ultracode, for now.** Opus 5.5 shipped after Fable 5.1 and beats it on every benchmark Anthropic published: Terminal-Bench 4.0 66.4% vs 55.8%, CursorBench 4.0 57.8% vs 51.8% at max effort (and $13.43 vs $17.28 a task), at 40% of Fable's per-token price. Anthropic says the real-world gap is narrower than those scores. So `[xdeep]` buys depth with max effort and multi-agent fan-out rather than a pricier model; its premium is token volume, not per-token rate. A `[deep]` attempt that already failed escalates to exactly this. `[deep]` drops to `high`: on CursorBench 4.0, Opus 5.5 high scores 56.0% at $3.97 a task against max's 57.8% at $13.43. Fable 5.1 at max effort stays as the alt when a different model is wanted, a second opinion with different failure modes after Opus has already failed the step. Revisit when the next Fable ships.
- **Ultracode** is Claude Code's multi-agent orchestration mode: Claude writes and runs workflow scripts that fan the work out to many subagents in parallel, keeping intermediate results in script variables instead of its context. Turn it on for one prompt with the keyword `ultracode`, for a session with `/effort ultracode` (or launch with `claude --effort ultracode`), and off with `/effort ultracode off`. It needs Claude Code v2.1.203+; on Pro, enable it once from `/config` first. It composes with `/effort max` from v2.1.284 on; earlier versions forced `xhigh` under ultracode. It opts into large runs (no 25-agent warning, no approval prompts in auto mode, up to 1,000 agents a run), so keep it off by default and use it only on `[xdeep]` waves: don't leave `"ultracode": true` on in settings for every session. It fans out inside one wave, so the plan's wave boundaries still hold. Cursor has no ultracode equivalent; Cursor `[xdeep]` is Opus 5.5 at max effort alone.
- **Claude Code uses version-less aliases.** `opus`, `sonnet`, `haiku`, and `fable` (the `[xdeep]` alt) resolve to the newest model of each tier, so the row never needs a version bump. Set effort with `/effort <level>`. `/effort max` applies to the current session only, so each fresh `[xdeep]` chat needs it again. Opus 5.5 and Sonnet 5.5 default to `medium` and can't turn thinking off, so set it explicitly; Fable defaults to `high` and always thinks. Haiku takes no effort level and gains nothing from thinking on bounded mechanical work. On Pro, Max, and Team plans Fable bills to usage credits and asks for consent first.
- **`[exec]` runs Sonnet at `high`, not `medium`.** On CursorBench 4.0, Sonnet 5.5 scores 47.8% at high and 39.2% at medium, for $1.67 vs $0.70 a task. That gap is worth a dollar.
- **Cursor billing has two pools, and Auto no longer protects the expensive one.** "Cursor Models" (Composer, Grok) carries much more included usage. "Other Models" (Anthropic, OpenAI, Google) bills at provider list price. Every Auto request bills the routed model's list price from that model's pool, and a subagent that names a third-party model bills Other Models even under an Auto or Grok parent. Teams and Enterprise add $0.25/Mtok on third-party models; Cursor's own models are exempt. Pin the model at every tier.
- **In Cursor, prefer the Cursor pool when it's close.** Take Grok or Composer over a third-party model when it scores within about 5 points on CursorBench 4.0 (table below). That puts `[exec]` on Grok 4.7 (43.9% vs Sonnet 5.5's 47.8%, both at high) and keeps `[deep]` on Opus 5.5 (Grok 4.7 at xhigh is 46.3% vs Opus 5.5 at high 56.0%). The pool is the saving, not the per-task price: at list, Grok 4.7 high costs $4.69 a task against Sonnet 5.5 high's $1.67. Once included Cursor usage runs out and on-demand billing starts, move `[exec]` to the Sonnet alt.
- **Cursor `[fast]` is Composer 2.5 standard** ($0.50/$2.50). Fast is the product default and costs 6×; `[fast=false]` or empty brackets (`composer-2.5[]`) select standard. Composer scores 27.7% on CursorBench 4.0, which is enough for steps that pass the [`[fast]` checklist](#fast-downgrade-checklist) and nothing more.
- **Cursor slugs** use the bracket parameters from Cursor's subagent docs (`[effort=...]`, `[fast=false]`). Cursor publishes no full ID list, so confirm with `agent --list-models`. The Fable alt in Cursor needs the data-retention opt-in under Privacy Mode, and Cursor reroutes guardrail-tripped Fable requests to Opus. Cursor doesn't offer GPT-6, and GPT-5.6 Sol scores 41.7%, so the Cursor row has no OpenAI alt.
- **Review beats are a high-ROI place to pin the top model.** A [review beat](#review-beat) reads the prior wave's diff (input-heavy) and emits a short verdict (output-light). Output is the expensive half ($20/Mtok vs $4 input on Opus), so a review is one of the cheapest ways to spend `[deep]` credit. Pin it rather than letting Auto downgrade it.
- **Haiku vs Composer.** Haiku is Claude Code's `[fast]` model and Composer is Cursor's. They are platform-specific choices, not alternatives to each other; each harness uses its own native fast model.
- **Codex** runs the GPT-6 family. Set effort with `/model` → "More reasoning…", `model_reasoning_effort` in `config.toml`, or `-c model_reasoning_effort='"xhigh"'`. Skip `ultra`: it hands delegation to the model, and these plans do their own delegation (Claude Code's `[xdeep]` ultracode is the one exception, and it fans out only inside one wave). Astra costs the same as Fable. `gpt-5.5` leaves Codex for ChatGPT sign-ins on 2026-10-14.
- **Gemini CLI** defaults to `auto`, which routes between Pro and Flash; pin a model with `-m` or `/model` → Manual. Thinking is set only through `modelConfigs.overrides` in `settings.json`, and the CLI sends `HIGH` to every 3.x model by default. Since 2026-06-18 Gemini CLI needs a paid API key, Vertex, or a Code Assist licence; Google AI Pro and Ultra sign-ins moved to Antigravity CLI.
- **Muse Code** runs only Meta's Muse Spark, so its tiers differ by effort (`--reasoning-effort` or `/effort`). Skip `ultra`, as in Codex. Don't use the `-contributor` models on private code: they cost a tenth as much because Meta trains on your data.
- **Grok Build** (`grok`, xAI's CLI) sets model and effort with `/model <id> [effort]`. It can call other providers' models through `[model.<id>]` config, which is the only way to reach an `[xdeep]` model there.
- **`[deep]` outside Claude Code, Codex, and Cursor.** Grok 4.7 trails Opus 5.5 by about 10 points on CursorBench 4.0, and Gemini 3.1 Pro predates the current benchmark versions. Muse Spark 1.3 reports 75.4% on DeepSWE against Opus 5's 74.0% but has no Opus 5.5 comparison. Prefer one of the three for `[deep]` waves until that changes.

**CursorBench 4.0**, the evidence behind the Cursor row (score, and list price per task, from [cursor.com/evals](https://cursor.com/evals)):

| Model (effort) | Score | Cost/task |
|---|---|---|
| Opus 5.5 (max) | 57.8% | $13.43 |
| Opus 5.5 (high) | 56.0% | $3.97 |
| Sonnet 5.5 (xhigh) | 53.1% | $3.88 |
| Opus 5.5 (medium) | 52.5% | $2.91 |
| Fable 5.1 (max) | 51.8% | $17.28 |
| Sonnet 5.5 (high) | 47.8% | $1.67 |
| Grok 4.7 (xhigh) | 46.3% | $6.01 |
| Grok 4.7 (high) | 43.9% | $4.69 |
| Sonnet 5.5 (medium) | 39.2% | $0.70 |
| Composer 2.5 | 27.7% | $0.68 |

### Model price table

Standard list rates in USD per million tokens for every model in the picker. Cursor charges provider list price with no markup, apart from the Teams and Enterprise surcharge above. Effort and bracket parameters don't change the rate; Fast variants do.

| Model | Used by | Input | Cached input | Output |
|---|---|---|---|---|
| `claude-fable-5-1` | `[xdeep]` alt: Claude Code `fable`, Cursor | $10.00 | $0.25 | $50.00 |
| `claude-opus-5-5` | Claude Code `opus`, Cursor | $4.00 | $0.20 | $20.00 |
| `claude-sonnet-5-5` | Claude Code `sonnet`, Cursor alt | $2.00 | $0.20 | $10.00 |
| `claude-haiku-4-5` | Claude Code `haiku` | $1.00 | $0.10 | $5.00 |
| `composer-2.5` (standard) | Cursor | $0.50 | $0.20 | $2.50 |
| `composer-2.5` (Fast) | Cursor default | $3.00 | $0.50 | $15.00 |
| `grok-4-7` / `grok-4.7` | Cursor, Grok Build | $2.00 | $0.50 | $6.00 |
| `grok-build-0.1` | Grok Build | $1.00 | $0.20 | $2.00 |
| `gpt-6-astra` | Codex | $10.00 | $1.00 | $50.00 |
| `gpt-6.1-sol` | Codex | $2.00 | $0.10 | $10.00 |
| `gpt-6-luna` | Codex | $0.10 | $0.01 | $0.50 |
| `gemini-3.1-pro-preview` | Gemini CLI | $2.00 | $0.20 | $12.00 |
| `gemini-3.8-flash` | Gemini CLI | $0.75 | $0.075 | $3.75 |
| `gemini-3.5-flash-lite` | Gemini CLI | $0.30 | $0.03 | $2.50 |
| `muse-spark-1.3` | Muse Code | $1.25 | $0.15 | $4.25 |

Long-context surcharges: Grok 4.7 doubles every rate above 256k input in Cursor (200k on xAI's API). GPT-6 doubles input and cached input and charges 1.5× output above 272k. Gemini 3.1 Pro is $4.00 / $0.40 / $18.00 above 200k. Anthropic models have none. Gemini 3.8 Flash's rates double on 2027-01-01.

*As of 2026-10-01. Sources: [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Cursor models and pricing](https://cursor.com/docs/models-and-pricing), [OpenAI pricing](https://developers.openai.com/api/docs/pricing), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [Meta pricing](https://dev.meta.ai/docs/pricing-rate-limits), [xAI pricing](https://docs.x.ai/developers/pricing).*

On Claude Code, price by the model the alias resolved to (read it from `message.usage`'s model).

Cache-aware cost formula used by the `tokens:` tally:

    cost_usd ≈ ( uncached_input      × in_rate
               + cache_read_input    × cached_rate
               + cache_write_5m      × in_rate × 1.25
               + cache_write_1h      × in_rate × 2.00
               + output_tokens       × out_rate ) / 1_000_000

`output_tokens` already includes extended-thinking/reasoning tokens. `cached_rate` is the table's cached-input column. The write multipliers are Anthropic's (5-minute write = 1.25×, 1-hour write = 2.00× the input rate); GPT-6 also bills writes at 1.25×, and the other providers don't charge for them, so set those terms to 0. When no cache split is available, set the cache terms to 0 and the formula collapses to `input × in_rate + output × out_rate`.

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

The Model price table covers every harness in the picker; use its row for
the model the wave ran on. No estimate here is authoritative billing data.

### Wave title format

Both drivers label each wave with the same human-scannable title so a wave is identifiable wherever it surfaces:

    Wave {n} of {t} [{tier}] {group-id}

For example, `Wave 2 of 3 [exec] repo-A m2 s1-s3`. Fill it in as:

- `{n}` — the 1-based wave number the title refers to (the wave a STOP marker is launching is the *next* wave; a Kickoff always refers to wave 1).
- `{t}` — the total wave count after the no-thrash folding pass (the same `N` as the Kickoff `Status:` line).
- `{tier}` — that wave's execution tier (`[xdeep]` / `[deep]` / `[exec]` / `[fast]`).
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
        Cursor:      grok-4-7[effort=high]      (or claude-sonnet-5-5[effort=high])
        Claude Code: /model sonnet              (/effort high)

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
        Cursor:      composer-2.5[fast=false]
        Claude Code: /model haiku               (no extended thinking)

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
        Cursor:      claude-opus-5-5[effort=high]
        Claude Code: /model opus                (/effort high)

      Prompt to paste into the next chat:
        Wave <n> of <t> [deep] <next group>
        Read <absolute path to the plan file>. Design <next group> (do not
        implement). The previous wave is reviewed in its own REVIEW beat
        (see the Review beat section), so do not re-review it here. Before
        you stop, update plan progress (mark the headings you finished
        ` (done)`, update the Status line, flip the matching todos). Stop
        after the design is written and report back.

    ---

For an escalation to `[xdeep]` (from any tier), use the `[deep]` escalation body above with the `[xdeep]` model row from the [Model picker](#model-picker):

      Next model
        Cursor:      claude-opus-5-5[effort=max]   (Cursor has no ultracode)
        Claude Code: /model opus                (/effort max, plus ultracode)

Start the prompt with the keyword `ultracode` so that turn runs under ultracode; for a wave that may take more than one turn, run `/effort ultracode` in that chat instead. Add one line naming the [upgrade checklist](#xdeep-upgrade-checklist) condition each step met. When Opus at max has already failed the step and a different model is wanted, swap in the Fable alt (`claude-fable-5-1[effort=max]` / `/model fable` + `/effort max`).

Rules for filling in the template:

- `<absolute path to the plan file>` is the **fully-qualified absolute path** to the plan file, resolved when the plan was identified — for example: `/Users/gary/Projects/personal/public/.scratch/plan-topic-word.md`. Never emit a bare filename or a repo-relative path — the next chat may start from a different working directory.
- The `Next model` block names Cursor and Claude Code. When the plan runs in Codex, Gemini CLI, Muse Code, or Grok Build, replace the Cursor row with that harness's row from the [Model picker](#model-picker).
- Name the next group using whatever identifiers the plan uses: if headings
  carry IDs, use those (e.g. `m2 s1-s4`); if not, use exact title text
  (e.g. `the "Wire Redis client" through "Write integration tests" steps`).
- Always include the `Suggested chat title:` line in the [Wave title format](#wave-title-format). `{n}` is the **next** wave (the one this STOP launches), `{t}` the total wave count, and `{group-id}` the same identifier used to name the next group above. It is advisory — a foreground chat cannot set its own title, so emit it for the user to paste even though there is no guarantee the harness will use it.
- Always include the "Stop at the next STOP marker" hard limit so the cascade is preserved.
- Always include the **progress-update reminder** spelled out inline in the prompt body (append ` (done)` to finished headings, update the Kickoff Status line, flip the matching todos). The pasted chat usually does **not** re-load the driver skill, so this inline reminder is the only way the [Progress tracking](#progress-tracking) convention reaches it — never drop it. Do not factor it out into a separate checklist block in the plan; keep it in the prompt.
- Use `->` ASCII arrows rather than Unicode em-dash arrows so the marker is safe in terminals and grep.
- If the next group is a `[deep]` block being delegated to a parent, the prompt should say "design only, do not implement"; if it's `[exec]` or `[fast]`, the prompt should say "implement <next group>, stop at next STOP marker."

### Review beat

A **review beat** is a dedicated, read-only `[deep]` pass over the work a wave just produced, run **after every wave** before the next one starts. It exists so cheaper-tier output (`[exec]`/`[fast]`) — and even `[deep]` output — is checked by a top-tier model against the spec before the plan builds further on it. Reviewing is `[deep]` work (catching architectural drift, broken contracts, security smells), so a review beat pins the `[deep]` model for any `[deep]`, `[exec]`, or `[fast]` wave. A wave that ran at `[xdeep]` gets an `[xdeep]` review (`--- REVIEW: wave-N [xdeep] ---`, Opus 5.5 at max effort without ultracode; see the note after the template): a reviewer below the author's tier caps the review at its own level.

Cadence is recorded in the Kickoff block as a `review:` line. The default is `review: every-wave` — a beat follows every wave, including same-tier `[exec] -> [exec]` boundaries. (Contrast `personal-plan-orchestrate`, whose Opus parent reviews every returned subagent summary inline and writes the same verdict to the [Review log](#review-log) — it participates **log-only** and adds no new human review gate; see [Who updates progress, and how](#who-updates-progress-and-how).)

A review beat is **read-only and fail-closed**:

- It **reports**, it does not fix. A concern becomes a follow-up wave (or folds into the next wave's prompt) so the reviewing model and the fixing model stay separate and intentional.
- It does **not** start the next wave.
- It records a verdict line to the [Review log](#review-log).
- On `CONCERNS`, it blocks: set the Kickoff `Status:` line to `BLOCKED at gate review-wave-N`, re-post the concern, and end the turn. This is a fail-closed gate per [STOP gate semantics](#stop-gate-semantics-fail-closed) — the next wave does not start until a human resolves it.

In the passive flow, the beat is emitted as a marker immediately **after** the just-finished wave's last heading and **before** the next `--- WAVE …` / `--- STOP …` marker. It is cheap to run despite pinning Opus — see the cost note under [Model picker](#model-picker).

Template:

    --- REVIEW: wave-N [deep] ---

      Suggested chat title: Review wave <n> of <t> [deep] <just-finished group>

      Next model
        Cursor:      claude-opus-5-5[effort=high]
        Claude Code: /model opus                (/effort high)

      Prompt to paste into the next chat:
        Review wave <n> of <t> [deep] <just-finished group>
        Read <absolute path to the plan file>. Review the work completed in
        wave <n> (<group-id>) against its spec: read the diff in git status /
        diff and check it against the plan steps and any acceptance criteria.
        This is READ-ONLY -- do not fix anything yourself and do not start
        the next wave. Append one line to the "## Review log" section of the
        plan file (create the section if absent):
          review wave-<n> (<group-id>): PASS|CONCERNS - <one-line note> - <YYYY-MM-DD>
        If the verdict is CONCERNS, also set the Kickoff Status line to
        `BLOCKED at gate review-wave-<n>`, re-post the concern, and stop.
        On PASS, update the Status line `last review:` field and report back.

    ---

For a wave that ran at `[xdeep]`, change `[deep]` to `[xdeep]` in the marker, the chat title, and the prompt's first line, and use these rows:

      Next model
        Cursor:      claude-opus-5-5[effort=max]
        Claude Code: /model opus                (/effort max)

Leave ultracode off for the review, in Claude Code too: a review is one read-only verdict, and fan-out would multiply its tokens. The reviewer still matches the author's model and effort.

### Review log

The **Review log** is a durable `## Review log` section at the bottom of the plan file (parallel to the `## Token log` the drivers maintain). It persists review verdicts across separate chats so a fresh session — or the final wave — can see the full review history. Both drivers write to it: the passive driver from each review beat, `personal-plan-orchestrate` from its parent after each wave.

One line per reviewed wave:

    review wave-<n> (<group-id>): PASS|CONCERNS - <one-line note> - <YYYY-MM-DD>

For example:

    review wave-1 (m1-s1-s5): PASS - standards wording is internally consistent - 2026-06-07
    review wave-2 (m2-s1-s2): CONCERNS - s2 skips the orchestrate log-only note - 2026-06-07

- `PASS` verdicts let the next wave proceed; `CONCERNS` is fail-closed (see [Review beat](#review-beat) above).
- The verdict also surfaces in the Kickoff `Status:` line `last review:` field (see [Updating the Status line](#updating-the-status-line)) so re-entry sees the latest result without scanning the log.

### Kickoff template

A Kickoff block tells the next agent how to **start** executing a tagged plan: which model to run on and what prompt to paste. Same shape as a STOP marker, but emitted once at the top of the plan file rather than at each tier transition. Every plan that has been processed by `personal-plan-model-tiers` or `personal-plan-orchestrate` should carry exactly one Kickoff block at the top.

Placement and idempotence:

- The skill writes the Kickoff block at the **top of the plan file**, above the first heading, inside a fenced code block so it pastes cleanly.
- The block is idempotent: if a Kickoff block already exists at the top of the file (matching the marker line `--- KICKOFF: ... ---`), the skill **replaces** it with the appropriate variant rather than appending. A plan never carries more than one Kickoff block.
- Skills must not modify any other content in the plan when writing the Kickoff. Tagging rules, STOP markers, and existing prose all stay where they are.

Ask-user rule (after writing the Kickoff):

> Continue execution in this chat, or hand off to a new chat for clean context? (default: new chat)

Treat any non-affirmative answer (silence, dismissal, ambiguous reply) as **new chat**. On new chat, halt and let the user copy the Kickoff into a fresh session. On current chat, continue per the skill's procedure.

Two variants. The **passive** variant (used by `personal-plan-model-tiers`) picks the model from the first tagged group's tier; the **active** variant (used by `personal-plan-orchestrate`) is always the `[deep]` Opus row because the orchestrator-parent always runs at `[deep]`.

Passive variant — `[exec]` first wave (the most common shape):

    --- KICKOFF: begin execution at [exec] ---

      Status: 0/N groups done | last review: — | current: <first group> [exec] | updated YYYY-MM-DD

      review: every-wave

      Suggested chat title: Wave 1 of N [exec] <first group>

      Next model
        Cursor:      grok-4-7[effort=high]      (or claude-sonnet-5-5[effort=high])
        Claude Code: /model sonnet              (/effort high)

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

      Status: 0/N groups done | last review: — | current: <first group> [fast] | updated YYYY-MM-DD

      review: every-wave

      Suggested chat title: Wave 1 of N [fast] <first group>

      Next model
        Cursor:      composer-2.5[fast=false]
        Claude Code: /model haiku               (no extended thinking)

      Prompt to paste into the next chat:
        Read <absolute path to the plan file>. Begin execution at the top
        of the plan. These are mechanical edits -- apply exactly what the
        plan specifies; do not refactor, rename, or generalize. Before you
        stop, update plan progress (mark the headings you finished
        ` (done)`, update the Status line, flip the matching todos). Then
        stop at the next STOP marker and report back.

    ---

For a `[deep]` or `[xdeep]` first wave, use the same body as the `[exec]` example with that tier's model row from the [Model picker](#model-picker) above. An `[xdeep]` first wave also takes the additions from the [STOP marker](#stop-marker-template) `[xdeep]` note: the `ultracode` opt-in and the checklist line.

Active variant — orchestrate (always `[deep]` / Opus):

    --- KICKOFF: begin orchestration at [deep] ---

      Status: 0/N groups done | last review: — | current: <first group> [deep] | updated YYYY-MM-DD

      review: every-wave (log-only — parent writes Review log; no human review gate)

      Next model
        Cursor:      claude-opus-5-5[effort=high]
        Claude Code: /model opus                (/effort high)

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
- For the active variant, the model is **always** `claude-opus-5-5[effort=high]` / `/model opus` at `/effort high`, regardless of what the first wave's tier is. The orchestrator-parent always runs at `[deep]`.
- Use `->` ASCII arrows rather than Unicode em-dash arrows so the marker is safe in terminals and grep.
- Fill in the `Status:` line with the total group count (`N`), the first group's identifier, and today's date. Update it as execution progresses (see [Progress tracking](#progress-tracking) below).
- For the passive variants, include the `Suggested chat title:` line in the [Wave title format](#wave-title-format) for the first wave (`Wave 1 of N [<tier>] <first group>`). It is advisory — a foreground chat cannot set its own title, so emit it for the user to paste even though the harness may ignore it. The active orchestrate variant has no such line: its per-wave titles are the `Task` subagent descriptions.
- For the passive variants, always keep the **progress-update reminder** spelled out inline in the prompt body (append ` (done)` to finished headings, update the Status line, flip the matching todos). A fresh chat that pastes this prompt usually does **not** re-load the driver skill, so this line is the only way the [Progress tracking](#progress-tracking) convention reaches the worker — it is the single most common reason a wave finishes without being marked done, so never drop it. (The active orchestrate variant re-loads the skill, so its parent applies the updates per the skill procedure instead; see [Who updates progress, and how](#who-updates-progress-and-how).)

## Who updates progress, and how

The two tracking surfaces — the in-harness todo list and the durable plan markdown file (both defined under [Progress tracking](#progress-tracking) below) — are kept in sync differently by each driver, because only one flow has a coordinator:

- `personal-plan-orchestrate` **has an orchestrator-parent**. After each wave's subagent returns, the parent applies the [Progress tracking](#progress-tracking) updates itself (mark ` (done)`, update the `Status:` line, flip todos). Subagents do mechanical work in their own working directory and never touch the plan file. This is handled by the skill procedure, so it does not need to ride in any prompt. The parent also **reviews every returned summary** as part of that step and writes the verdict to the [Review log](#review-log) (`review wave-N (<group-id>): PASS|CONCERNS - … - <date>`) — this is the orchestrate **log-only** participation in the [review beat](#review-beat) convention. It adds **no new human review gate**: orchestrate's existing gates (the `[exec]/[fast] -> [deep]` review gate and the milestone gate) are unchanged, and the every-wave review beat that the passive driver runs as a separate human-driven chat is, in orchestrate, just the parent's inline review plus the log write.
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
- The marker goes at the **end of the heading line**, after all other content, so it never collides with the tier-tag regex `^#+\s+.*\[(xdeep|deep|exec|fast)\]`.
- Done-step regex: `\(done\)\s*$`
- Incomplete steps: any tagged heading that does **not** match the done-step regex.
- This is the **only** sanctioned heading mutation besides the tier tag itself. The "do not rename/renumber" rule has an explicit carve-out for appending ` (done)`.

### Updating the Status line

After each group finishes, update the `Status:` line inside the Kickoff block:

    Status: 2/5 groups done | last review: wave-2 PASS | current: m2 s1-s4 [exec] | updated 2026-05-28

- `2/5` — groups completed so far out of the total group count.
- `last review:` — the most recent [review beat](#review-beat) verdict as `wave-N PASS` or `wave-N CONCERNS`, or `—` when no wave has been reviewed yet. Omit the field entirely only on plans that run `review:` off. A `CONCERNS` value pairs with a `BLOCKED at gate review-wave-N` state (see [STOP gate semantics](#stop-gate-semantics-fail-closed)).
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

     or, when a [review beat](#review-beat) returns `CONCERNS`:

         Status: 2/5 groups done | last review: wave-2 CONCERNS | BLOCKED at gate review-wave-2 | updated 2026-05-28

     On re-entry, an agent that sees a `BLOCKED at gate` status re-posts that exact question and waits — it never assumes the gate was approved. A `BLOCKED at gate review-wave-N` means the wave-N review found a concern that a human must resolve (re-tag, add a fix-up wave, or waive) before the next wave starts.
- Cross-references: [Progress tracking](#progress-tracking) (the Status line) and the AGENTS.md "Wait for approval" workflow rule.

## Delegating execution to subagents

When a `[deep]` agent finishes a deep step and the next step is `[exec]` or `[fast]`, prefer delegating the next group to a subagent on a smaller model rather than burning the deep context on mechanical work.

- Use the harness's subagent/Task tool (Cursor `Task` with `subagent_type` and optional `model`; Claude Code `Task`; other harnesses use the equivalent).
- Pass the cheapest model that can plausibly complete the step (see the model picker in "Model-tier stop points" above). Step up only if the subagent fails or returns low-quality output.
- Give the subagent: the spec section, the exact files to touch, acceptance criteria, and a hard scope limit. Subagents do not see the parent conversation, so be explicit.
- The deep parent stays responsible for reviewing the subagent's output and deciding the next stop point.
- If the harness does not support per-subagent model selection, stop at the boundary instead and let the user start a fresh session on a cheaper model using the STOP marker's handoff prompt.
