# Plan Execution

How multi-step plans are executed across models of different cost and capability: tagging steps by tier, grouping them into execution waves, stopping (or delegating to a subagent) at tier boundaries, tracking progress across chat handoffs, budgeting and tallying token cost, and the STOP-gate semantics that keep human oversight intact. This file is the canonical reference. The operational skills implement it in two layers: a shared **tagging** skill (`personal-plan-tag-tiers`) that only tags executable steps with honest complexity tiers, and two **execution drivers** (`personal-plan-model-tiers`, `personal-plan-orchestrate`) that group the tagged steps into waves, apply the no-thrash rule, and either emit STOP markers or dispatch subagents.

## Model-tier stop points

Plans are executed by agents of different cost and capability. To make the most of both, tag every executable step with one of four tiers, group consecutive same-tier steps into execution waves, and emit a STOP marker at every tier boundary so the model can be swapped (or the wave delegated to a subagent) before continuing.

This section is the canonical reference for the convention. The work splits into two responsibilities:

- **Tagging** — assigning each executable step its honest `[xdeep]` / `[deep]` / `[exec]` / `[fast]` tier. This is owned by `personal-plan-tag-tiers`, a small shared skill. Tags reflect true complexity and are **never** rewritten for thrash reasons, so a tagged plan always shows how hard the work actually is. Run it first when you just want to see the complexity of a plan before deciding how to execute it.
- **Execution** — grouping the tagged steps into waves (the no-thrash rule), then either emitting STOP markers for a human-driven model swap or dispatching subagents. This is owned by the two driver skills, which call `personal-plan-tag-tiers` automatically when a plan is not tagged yet.

`personal-plan-model-tiers` is the passive driver (any harness that supports skills — Cursor, Claude Code — stopping at each tier boundary for a human model swap); `personal-plan-orchestrate` is the active Cursor counterpart where the `[deep]` parent delegates each wave via `Task(model=...)` subagents.

### Tiers

- `[xdeep]` — frontier reasoning, one rung above `[deep]`. For steps where a strong `[deep]` model is likely to be wrong, or already was: novel designs with nothing to copy from, security and correctness arguments (auth, crypto, concurrency, distributed consistency), migrations that can't be rolled back, and long-horizon analysis over a very large context. It runs Opus 5.5 at xhigh effort, plus ultracode in Claude Code on audit-shaped steps (see [Model picker](#model-picker)). That costs about 2× a `[deep]` step for little measured gain on code, and about 47× with ultracode (see [Expected cost](#expected-cost)), so the tag has to pass the [upgrade checklist](#xdeep-upgrade-checklist).
- `[deep]` — top-tier reasoning. Architecture decisions, ambiguous requirements, non-obvious debugging, security-sensitive review, library/stack trade-offs, anywhere the cost of getting it wrong is high.
- `[exec]` — standard implementation. Multi-file changes with cross-file reasoning, refactors with a clear target but real judgment, test writing where cases need thought, work that must read repo patterns first to extend them.
- `[fast]` — mechanical, fully-specified, single-concern work. Renames, format changes, applying a decided design line-by-line, doc updates, well-bounded ports.

**Default-up bias**: when in doubt, tag `[deep]` > `[exec]` > `[fast]`. A misclassified `[fast]` produces bad output; a misclassified `[deep]` wastes a little money. The bias stops at `[deep]`: doubt between `[deep]` and `[xdeep]` resolves to `[deep]`. A misclassified `[xdeep]` wastes real money, and a `[deep]` review beat or a failed attempt escalates the step anyway.

### `[xdeep]` upgrade checklist

A step only earns `[xdeep]` if it is clearly `[deep]` work **and** at least one of these is true:

- A `[deep]` attempt already failed it, or its review beat returned `CONCERNS` on the same design question twice.
- A mistake would be expensive and quiet: a security boundary, auth or crypto design, a data migration that can't be rolled back, concurrency or consistency correctness.
- The design is novel: nothing in the repo, the standards, or the dependencies to copy from, and it spans more than one system.
- The step needs sustained reasoning over a very large context where a `[deep]` model loses the thread: a cross-repo plan, or an **audit-shaped** step (a whole-codebase or cross-repo audit, or a broad sweep over many files). Only audit-shaped steps take ultracode.

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

**Fix-up waves.** A wave added to resolve a `CONCERNS` review of wave N is numbered `N-fix` (`--- WAVE 1-fix [exec] ---`), wherever a wave number appears: its marker, [wave title](#wave-title-format), [Cost table](#cost-table) row and [token lines](#token-line-format). A retry of a wave is not a new wave and keeps its number.

**Regex to find wave markers:** `^--- WAVE \d+(-fix)? \[(xdeep|deep|exec|fast)\] ---$`

### Model picker

One row per harness, one column per tier, effort in parentheses. "Switch harness" means the harness has nothing at that tier: run that wave in Claude Code, Codex, or Cursor.

| Harness | `[xdeep]` | `[deep]` | `[exec]` | `[fast]` |
|---|---|---|---|---|
| Claude Code | `/model opus` (xhigh), plus ultracode on audit-shaped steps (alt: `/model fable` (xhigh)) | `/model opus` (high; medium for interactive planning) | `/model sonnet` (medium; high on a large codebase or a stall) | `/model haiku` (none) (alt: `/model sonnet` (low)) |
| Cursor | `claude-opus-5-5[effort=xhigh]` (alt: `claude-fable-5-1[effort=xhigh]`) | `claude-opus-5-5[effort=high]` (`[effort=medium]` for interactive planning) | `grok-4-7[effort=high]` (alt: `claude-sonnet-5-5[effort=medium]`, `[effort=high]` on a large codebase or a stall) | `composer-2.5[fast=false]` (alt: `claude-sonnet-5-5[effort=low]`) |
| Codex | `gpt-6-astra` (xhigh) | `gpt-6.1-sol` (xhigh) | `gpt-6.1-sol` (medium) | `gpt-6-luna` (low) |
| Gemini CLI | switch harness | `gemini-3.1-pro-preview` (high) | `gemini-3.8-flash` (high) | `gemini-3.5-flash-lite` (low) |
| Muse Code | switch harness | `muse-spark-1.3` (xhigh) | `muse-spark-1.3` (medium) | `muse-spark-1.3` (low) |
| Grok Build | switch harness | `grok-4.7` (xhigh) | `grok-4.7` (high) | `grok-build-0.1` |

*As of 2026-10-01.* Refresh the rows that pin versions (everything but Claude Code) when a harness adds a model.

Notes:
- **`[xdeep]` is Opus 5.5 at xhigh.** Opus 5.5 shipped after Fable 5.1 and beats it on every benchmark Anthropic published: Terminal-Bench 4.0 66.4% vs 51.3% and CursorBench 4.0 56.0% vs 51.6%, both at xhigh (and $6.98 vs $13.01 a task), at 40% of Fable's per-token price. Anthropic says the real-world gap is narrower than those scores. So `[xdeep]` buys depth with effort rather than a pricier model; its premium is token volume, not per-token rate. A `[deep]` attempt that already failed escalates to exactly this. On code, xhigh is close to `[deep]`'s high (CursorBench 4.0 56.0% at both, FrontierCode 63.5 vs 65.2); its clear gain is on knowledge work (GDPval-AA +128 Elo), so the tag rests on the [upgrade checklist](#xdeep-upgrade-checklist), not on coding scores. Fable 5.1 at xhigh is the alt when a different model is wanted, a second opinion with different failure modes after Opus has already failed the step. Revisit when the next Fable ships.
- **Max only where a gain is measured**: a benchmark for that task type, or completed plans' actuals and Review log verdicts, showing max beating xhigh beyond noise and by enough to pay for its cost. On code it doesn't: Opus 5.5 at max scores 64.8% on Terminal-Bench 4.0 against xhigh's 66.4% (±2.6 SE), +0.1 on FrontierCode at 2.84× the cost, +3.0 on FrontierCode's hardest 100 at 2.75× (only back to medium's 54.6, from xhigh's dip to 51.4), and +1.8 points on CursorBench 4.0 at 1.92×. Claude Code's docs call max prone to overthinking. They suggest it for finding security vulnerabilities, but no benchmark measures that, so security steps run at xhigh. The measured gains are Fable 5.1 on terminal or CLI-heavy steps (Terminal-Bench 4.0 55.8% vs 51.3%, at 1.23× the cost) and Opus 5.5 on multi-app business workflows (AutomationBench 40.0 vs 34.4, at 1.59×).
- **Ultracode** is Claude Code's multi-agent orchestration mode: Claude writes and runs workflow scripts that fan the work out to many subagents in parallel, keeping intermediate results in script variables instead of its context. Turn it on for one prompt with the keyword `ultracode`, for a session with `/effort ultracode` (it keeps the session's level, so xhigh after `/effort xhigh`), or launch with `claude --effort ultracode` (xhigh with ultracode on), and off with `/effort ultracode off`. It needs Claude Code v2.1.203+; on Pro, enable it once from `/config` first. Versions before v2.1.284 force `xhigh` under ultracode, so max plus ultracode needs v2.1.284+. It opts into large runs (no 25-agent warning, no approval prompts in auto mode, up to 1,000 agents a run), so keep it off by default and use it only on audit-shaped `[xdeep]` steps ([upgrade checklist](#xdeep-upgrade-checklist)): don't leave `"ultracode": true` on in settings. Anthropic measured fan-out saving money only on work larger than one context or split into independent pieces, with workers on a cheaper model: on a 21.6M-token corpus, a Fable 5.1 lead over 25 Sonnet 5 workers cost 47-55% less than Fable solo and scored 10-12 points lower. When the work is one dependent chain, or fits in one context, the solo model at lower effort came out ahead in every case measured. Ultracode's agents run on the session's model unless the script names one, so on Opus it buys coverage and wall-clock time, not savings: about 22× a solo xhigh step ([Expected cost](#expected-cost)). So a cross-repo plan, one dependent chain, runs without it. It fans out inside one wave, so the plan's wave boundaries still hold. Cursor has no ultracode equivalent; Cursor `[xdeep]` is Opus 5.5 at xhigh alone.
- **Claude Code uses version-less aliases.** `opus`, `sonnet`, `haiku`, and `fable` (the `[xdeep]` alt) resolve to the newest model of each tier, so the row never needs a version bump. Set effort with `/effort <level>`. A level typed after `/effort`, or confirmed with `Enter` in its slider, is saved as that model's default and carries into its next chat: an Opus chat after an `[xdeep]` one starts at xhigh, and a Sonnet chat after `low` fast work starts at low. So every Next model row names its level, even a model's default; `s` in the slider (v2.1.257+) keeps a level to the session. `/effort max` is never saved and lasts only the session. Opus 5.5 and Sonnet 5.5 default to `medium` and can't turn thinking off; Fable defaults to `high` and always thinks. Haiku takes no effort level and gains nothing from thinking on bounded mechanical work. On Pro, Max, and Team plans Fable bills to usage credits and asks for consent first.
- **`[deep]` runs Opus at `high`, or `medium` for interactive planning with Gary in the loop.** On CursorBench 4.0, Opus 5.5 high scores 56.0% at $3.97 a task, level with xhigh at $6.98. Medium matches high on FrontierCode (65.3 vs 65.2, at 0.74× the cost) and returns a starting point sooner, but drops on CursorBench 4.0 (52.5%), Terminal-Bench 4.0 (57.6% vs 64.2%) and GDPval-AA (-116 Elo), so it fits only where Gary reviews each result and steers the next step. The orchestrate parent, dispatched `[deep]` subagents and review beats aren't interactive and run at high, or xhigh for the review of an `[xdeep]` wave.
- **`[exec]` runs Sonnet at `medium`, `high` on a large codebase or a stalled step, and never past `high`.** Medium is Claude Code's level for clear-scope work such as implementing a feature, at $0.21 a step against high's $0.35; its docs put fixing a bug in an existing codebase at high. Medium scores lower on every benchmark measured: FrontierCode 50.5 vs 61.5 (36.5 vs 49.4 on its hardest 100), CursorBench 4.0 39.2% vs 47.8%, and the Artificial Analysis Coding Agent Index 45.9 vs 55.0. Re-running every failure at high costs about 1.04× running high outright, so medium saves only where its misses are fixed for less than a re-run, or not caught at all; check it against the [Review log](#review-log)'s verdicts. A step that stalls at high re-tags to `[deep]`: Opus 5.5 at medium or high beats Sonnet at xhigh on FrontierCode for less (65.3 at $0.67 and 65.2 at $0.90, against 64.4 at $1.24).
- **Cursor billing has two pools, and Auto no longer protects the expensive one.** "Cursor Models" (Composer, Grok) carries much more included usage. "Other Models" (Anthropic, OpenAI, Google) bills at provider list price. Every Auto request bills the routed model's list price from that model's pool, and a subagent that names a third-party model bills Other Models even under an Auto or Grok parent. Teams and Enterprise add $0.25/Mtok on third-party models; Cursor's own models are exempt. Pin the model at every tier.
- **In Cursor, prefer the Cursor pool when it's close.** Take Grok or Composer over a third-party model when it scores within about 5 points on CursorBench 4.0 (table below). That puts `[exec]` on Grok 4.7 at high: 43.9%, 4.7 points above the Sonnet alt at medium (39.2%) and 3.9 below it at high (47.8%). It keeps `[deep]` on Opus 5.5 (Grok 4.7 at xhigh is 46.3%, against Opus 5.5 at high 56.0% and at medium 52.5%). The pool is the saving, not the per-task price: at list, Grok 4.7 high costs $4.69 a task against the Sonnet alt's $0.70 at medium (6.7×) and $1.67 at high. Grok has no step-up of its own: a stalled Grok step steps up to the Sonnet alt at high, which beats Grok at xhigh on score and list cost (46.3%, $6.01). Once included Cursor usage runs out and on-demand billing starts, move `[exec]` to the Sonnet alt, at medium with the same step-up to high as in Claude Code. This decides the model only; cost figures still use list rates ([Model price table](#model-price-table)).
- **Cursor `[fast]` is Composer 2.5 standard** ($0.50/$2.50). Fast is the product default and costs 6× on input and output (2.5× on cache reads); `[fast=false]` or empty brackets (`composer-2.5[]`) select standard. `[fast]` is the one exception to the pool rule: Composer scores 27.7% on CursorBench 4.0, 8.1 points below the Sonnet alt at low (35.8%), at a higher list price ($0.68 vs $0.50 a task), but it bills from the Cursor pool and is enough for steps that pass the [`[fast]` checklist](#fast-downgrade-checklist). Once included Cursor usage runs out, move `[fast]` to the Sonnet alt.
- **Cursor slugs** use the bracket parameters from Cursor's subagent docs (`[effort=...]`, `[fast=false]`). Cursor publishes no full ID list, so confirm with `agent --list-models`. Cursor runs Sonnet 5.5 at high by default (Claude Code: medium), and Opus 5.5 at medium and Fable 5.1 at high in both, so every slug names its effort: a bare `claude-sonnet-5-5` runs at high. Cursor's docs show only `high` and `max` as Claude effort values; `xhigh`, `medium` and `low` rest on CursorBench 4.0's runs, so confirm them too. The Fable alt in Cursor needs the data-retention opt-in under Privacy Mode, and Cursor reroutes guardrail-tripped Fable requests to Opus. Cursor doesn't offer GPT-6, and GPT-5.6 Sol scores 41.7%, so the Cursor row has no OpenAI alt.
- **Review beats are a high-ROI place to pin the top model.** A [review beat](#review-beat) reads the prior wave's diff and emits a short verdict, but its cost is mostly input, not output: every call re-sends the whole context, so cache reads and writes make up about 70% of a reviewer's API-equivalent cost (output about 30%). It still costs only about 0.6× a [medium step](#expected-cost) at the reviewer's model because it makes fewer calls, so a review is a cheap way to spend `[deep]` credit. Point it at the diff and the plan rather than the whole repo, since its cost scales with calls × context. Pin it rather than letting Auto downgrade it.
- **`[fast]` runs at `low` where the model takes an effort level.** Haiku 4.5 takes none (Claude Code's effort table doesn't list it). Fast work run on Sonnet 5.5 sets `low`, Claude Code's level for small changes like a rename: FrontierCode 43.4 at $0.17 a step, CursorBench 4.0 35.8% at $0.50 a task. A folded `[fast]` step runs at its `[exec]` wave's level, since folding exists to keep the wave in one chat or dispatch; the Sonnet-low alt is for a whole `[fast]` wave run on Sonnet.
- **Haiku vs Composer.** Haiku is Claude Code's `[fast]` model and Composer is Cursor's. They are platform-specific choices, not alternatives to each other; each harness uses its own native fast model.
- **Codex** runs the GPT-6 family. Set effort with `/model` → "More reasoning…", `model_reasoning_effort` in `config.toml`, or `-c model_reasoning_effort='"xhigh"'`. Skip `ultra`: it hands delegation to the model, and these plans do their own delegation (Claude Code's ultracode on audit-shaped `[xdeep]` steps is the one exception, and it fans out only inside one wave). Astra costs the same as Fable. `gpt-5.5` leaves Codex for ChatGPT sign-ins on 2026-10-14.
- **Gemini CLI** defaults to `auto`, which routes between Pro and Flash; pin a model with `-m` or `/model` → Manual. Thinking is set only through `modelConfigs.overrides` in `settings.json`, and the CLI sends `HIGH` to every 3.x model by default. Since 2026-06-18 Gemini CLI needs a paid API key, Vertex, or a Code Assist licence; Google AI Pro and Ultra sign-ins moved to Antigravity CLI.
- **Muse Code** runs only Meta's Muse Spark, so its tiers differ by effort (`--reasoning-effort` or `/effort`). Skip `ultra`, as in Codex. Don't use the `-contributor` models on private code: they cost a tenth as much because Meta trains on your data.
- **Grok Build** (`grok`, xAI's CLI) sets model and effort with `/model <id> [effort]`. It can call other providers' models through `[model.<id>]` config, which is the only way to reach an `[xdeep]` model there.
- **`[deep]` outside Claude Code, Codex, and Cursor.** Grok 4.7 trails Opus 5.5 by about 10 points on CursorBench 4.0, and Gemini 3.1 Pro predates the current benchmark versions. Muse Spark 1.3 reports 75.4% on DeepSWE against Opus 5's 74.0% but has no Opus 5.5 comparison. Prefer one of the three for `[deep]` waves until that changes.

**CursorBench 4.0**, the evidence behind the Cursor row (score, and list price per task, from [cursor.com/evals](https://cursor.com/evals)):

| Model (effort) | Score | Cost/task |
|---|---|---|
| Opus 5.5 (max) | 57.8% | $13.43 |
| Opus 5.5 (xhigh) | 56.0% | $6.98 |
| Opus 5.5 (high) | 56.0% | $3.97 |
| Sonnet 5.5 (xhigh) | 53.1% | $3.88 |
| Opus 5.5 (medium) | 52.5% | $2.91 |
| Fable 5.1 (max) | 51.8% | $17.28 |
| Fable 5.1 (xhigh) | 51.6% | $13.01 |
| Sonnet 5.5 (high) | 47.8% | $1.67 |
| Grok 4.7 (xhigh) | 46.3% | $6.01 |
| Grok 4.7 (high) | 43.9% | $4.69 |
| Sonnet 5.5 (medium) | 39.2% | $0.70 |
| Sonnet 5.5 (low) | 35.8% | $0.50 |
| Composer 2.5 | 27.7% | $0.68 |

### Model price table

Standard list rates in USD per million tokens for every model in the picker. Cursor charges provider list price with no markup, apart from the Teams and Enterprise surcharge above. Effort and bracket parameters don't change the rate; Fast variants do.

**Agent costs are API-equivalent.** Every agent cost a standard or skill computes (expected costs, [token lines](#token-line-format), the [Cost table](#cost-table)) prices tokens at these provider API list rates, cache tiers included, whatever the harness actually bills. Included usage, subscriptions, credits, Cursor's pools and harness surcharges don't change the figure. That keeps costs comparable across harnesses and over time, and measures what a plan consumed rather than what a billing plan absorbed. Label the figures `API-equiv`. Pools and plan limits only inform which model runs a wave (the Cursor bullets above). A model with no published API rate shows `n/a` and stays out of totals.

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

On Claude Code, price by the model the alias resolved to (read it from `message.model`).

Cache-aware cost formula, which prices every [token line](#token-line-format):

    cost_usd ≈ ( uncached_input      × in_rate
               + cache_read_input    × cached_rate
               + cache_write_5m      × in_rate × 1.25
               + cache_write_1h      × in_rate × 2.00
               + output_tokens       × out_rate ) / 1_000_000

`output_tokens` includes reasoning tokens; [source precedence](#token-accounting--source-precedence) says how to normalize each harness's counts to these terms. `cached_rate` is the table's cached-input column. The write multipliers are Anthropic's (5-minute write = 1.25×, 1-hour write = 2.00× the input rate); GPT-6 also bills writes at 1.25×. The other providers charge no write premium, so their cache writes price at 1.00× the input rate.

### Token accounting — source precedence

Take token counts from the most accurate source available, in this order. Each source yields the four counts a [token line](#token-line-format) shows: uncached input, cache read, cache write and output.

**1. Real usage the agent can read.**

| Harness | Where to read | Fields | Normalize |
|---|---|---|---|
| Claude Code | `~/.claude/projects/<slug>/<session-id>.jsonl`, where `<slug>` is the working directory with every character other than a letter or digit turned into `-` (`/Users/gary/src/github.com/x` is `-Users-gary-src-github-com-x`; a slug over 200 characters is cut there and gets a hash suffix, so match it by prefix) and the id is `$CLAUDE_CODE_SESSION_ID` (without it, the newest `.jsonl` there). Subagents and workflow agents: `<session-id>/subagents/**/agent-*.jsonl` | `message.usage` on assistant lines: `input_tokens` (uncached), `cache_read_input_tokens`, `cache_creation.ephemeral_5m_input_tokens` and `ephemeral_1h_input_tokens`, `output_tokens` (thinking included). Price by `message.model` | One call spans several lines that repeat its usage, so dedupe by `message.id`; summing lines counts about 2×. Take a call's usage from its line with `stop_reason`, which carries the final counts; main-session lines always have one. A call without one (almost every Opus call in a subagent file) logs a streaming placeholder (1-24) as `output_tokens`: keep its exact input-side counts, estimate its output at about 1,000 tokens, and label the line `(output est.)` |
| Codex | `$CODEX_HOME/sessions/**/rollout-*-<thread-id>.jsonl` (default `~/.codex`; the id is `$CODEX_THREAD_ID`) | `token_count` events, `info.total_token_usage`: `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`, `reasoning_output_tokens` | `input_tokens` includes cached tokens: input = `input_tokens` - cached - cache write. `output_tokens` already includes reasoning. Subagents write their own rollout files, linked by `session_id` and `parent_thread_id`; the parent's totals exclude them, so add them |
| Gemini CLI | The newest `~/.gemini/tmp/<project>/chats/*.jsonl` (the shell carries no session id). Subagents: `chats/<parentSessionId>/` | Per-message `tokens`: `input`, `cached`, `output`, `thoughts` | `input` is the whole prompt, cached included: input = `input` - `cached`. `thoughts` sits outside `output` but bills as output: output = `output` + `thoughts`. There is no cache-write field (implicit caching has no write charge), so cache write is 0 |
| Grok Build | `grok usage "$GROK_SESSION_ID"` | `session`: `inputTokens`, `cachedReadTokens`, `cacheCreationTokens`, `outputTokens`, and `modelUsage` per model | `inputTokens` includes cached tokens: input = `inputTokens` - cache read - cache write. `outputTokens` includes reasoning. Finished subagents are included; `grok usage <subagent_id>` shows one |
| Cursor, Muse Code | Nothing: their transcripts carry no usage | | Cursor: source 2, else 3. Muse Code: source 3 |

A wave run in its own chat is that session's total plus its subagents'. When one chat ran more than one wave, take only that wave's calls, or the difference between the cumulative totals at its start and end. The in-progress final turn isn't flushed yet: a small tail, ignore it.

- **Exact Claude Code totals after the session ends.** When the session process exits, Claude Code appends a cumulative `cost-state` record to the main transcript: `modelUsage.<model>` with `inputTokens`, `cacheReadInputTokens`, `cacheCreationInputTokens`, `outputTokens` (which already includes `thinkingTokens`) and `costUSD`, plus `totalCostUSD`, covering the main loop and its subagents. It is exact but absent while the chat is live, so [Final completion](#final-completion-all-groups-done) uses it to replace the `(output est.)` lines of sessions that have ended, found by the `session <id>` those lines carry. Headless `claude -p --output-format json` returns the same `modelUsage` and `total_cost_usd`.
- **Never price** the `Agent` tool result's `usage` or `totalTokens`, or a Workflow notification's `subagent_tokens`: each covers only an agent's final request.

Real usage is exact. An `(output est.)` line is good to about ±20% on dollars: output is about 30% of an agent's cost, and real calls average about 600-1,200 output tokens.

**2. Usage Gary pastes.** On Cursor, that is the dashboard's usage CSV export (the rows for the wave's model and time span) or the `result.usage` of `agent -p --output-format json`. In the CSV, `Input (w/o Cache Write)` is input and `Input (w/ Cache Write)` is cache write, next to `Cache Read` and `Output Tokens`; check that the four sum to `Total Tokens`. In `result.usage`, `inputTokens` is already uncached, next to `cacheReadTokens`, `cacheWriteTokens` and `outputTokens`; whether it covers `Task` subagents is unverified, so use it only for a run that dispatched none, and take subagent usage from CSV rows. Price with the formula above, not the CSV's `Cost` column. Pasted usage is exact.

**3. Accumulation heuristic.** For Cursor, Muse Code and any other harness without readable usage. Over the stretch of a chat the line covers, count the model calls `N` (about one per tool-call round, plus the final reply), the characters read (prompts, file reads, tool outputs) and the characters written (chat text, tool-call arguments, file writes):

    S            = 50_000                                          base context sent with every call
    T0           = transcript tokens before the stretch            0 for a chat's first line
    T            = (chars_read + chars_written) / 2.5 + 500 × N    transcript tokens the stretch adds
    C0           = S + T0                                          context at the stretch's first call
    billed_input = N × C0 + N × T / 2
    cache_write  = T + the whole context at each cold start
    cache_read   = max(0, billed_input - cache_write)
    output       = 500 × N + chars_written / 2.5
    input        = 0

`T0` is the same count, characters / 2.5 plus 500 per call, over the chat's earlier calls. A **cold start** is a chat's first call, or the first call after a pause longer than the 5-minute cache TTL (a gate waiting on a human, or a parent idle while its subagent works): that call writes the whole context again, which is `C0` at the stretch's first call and more after a later pause. A chat covered by a single line has `T0` = 0 and one cold start, so its cache write is `S + T` and its billed input `N × S + N × T / 2`.

Every call re-sends the whole context, so billed input grows with calls × context, almost all of it cache reads. The 500 tokens per call cover hidden thinking and tool-call framing, and Claude's tokenizer averages about 2.4 characters per token. A single count of the characters seen misses all of that and understates dollars about 7×. Label the line `(heuristic)`.

Fitted on whole Claude Code agents running Opus 5.5 at xhigh on research, review and markdown editing, the heuristic lands within ±25% of real dollars there (median real/predicted 0.94; 91% of agents within 1.25×). App-code steps that run builds and tests have bigger tool outputs and different call counts, so expect a wider spread on them. Off Claude Code its constants are uncalibrated: GPT and Gemini tokenizers run nearer 4 characters per token, and Cursor's base prompt size is unknown, so a line there can be off by 2× or more.

The Model price table covers every harness in the picker; use its row for the model the wave ran on. Every figure is API-equivalent at list rates ([Model price table](#model-price-table)), not the bill.

### Token line format

Every actual token figure a driver reports, logs or sums is a **token line**, one per row, group and model (a parallel orchestrate wave has one per working directory):

    tokens <row> <group-id> (<model>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv

For example:

    tokens wave-2 m2-s1-s3 (claude-sonnet-5-5): input ~1.2k / cache read ~2.1M / cache write ~48k / output ~22k | ~$0.76 API-equiv

- `<row>` names what spent the tokens: `wave-N` for a wave's work (its chat, or a subagent; `wave-N-fix` for a [fix-up wave](#wave-annotation-format)), `review-wave-N` for a [review beat](#review-beat) or orchestrate's `[xdeep]` review subagent, `kickoff` for the passive driver's kickoff chat, and `orchestrator-kickoff` or `orchestrator-wave-N` for orchestrate's parent. A step-up retry keeps its wave's `wave-N`.
- `<group-id>` is the wave's group identifier with hyphens (`m2-s1-s3`, orchestrate's `{task-id}`). A `kickoff` or `orchestrator-kickoff` line uses the plan's base name.
- `<model>` is the slug the tokens ran on, without Cursor's bracket parameters or a date suffix (`claude-haiku-4-5-20251001` is `claude-haiku-4-5`), plus ` Fast` for Composer's Fast variant (`composer-2.5 Fast`), so it names one [price table](#model-price-table) row. A wave that ran two models has two lines.
- `input` is uncached input. A plain `cache write` count is 5-minute writes, or the provider's only kind. Mark 1-hour writes `1h`, and show both kinds when both occur: `cache write ~40k 5m + ~8k 1h`. [Source precedence](#token-accounting--source-precedence) says how to normalize each harness's counts to these four terms.
- Round counts to two significant figures with `k` or `M`. The dollars are the [cache-aware formula](#model-price-table) over the four counts at the model's rates, so the line alone reproduces them. A model with no published rate shows `n/a API-equiv`.
- **Billed tokens** are input + cache read + cache write + output. Every token total, the [Cost table](#cost-table)'s included, is billed tokens.
- Append `(heuristic)` only when the line came from the accumulation heuristic, and `(output est.)` when only output was estimated (Claude Code calls without a `stop_reason` line). A line with neither label is real usage. An `(output est.)` line ends with `session <id>`, the Claude Code session whose transcript it came from, so a later chat can replace it from that session's `cost-state` record.
- A total sums its lines' counts. Its dollars are the sum of the lines' dollars, each at its own model's rates, never a blended rate applied to the summed tokens.

**Token log.** Both drivers append every token line to a `## Token log` section at the bottom of the plan file, below its counting header, as each row's work finishes, so the lines survive across chats. The kickoff creates the section. The [Cost table](#cost-table)'s actual columns are summed from it. A line from a better source (usage Gary pastes, or a `cost-state` record) replaces the lines it covers: the same row, group and model over the same span. Usage that can't be split by row (Cursor's CSV can't tell the Opus parent from an Opus `[deep]` subagent in the same minutes) replaces every line for that model in its span with one line, under the row that did most of the work, ending `(combined: <rows>)`.

**Counting header.** The kickoff that writes the Kickoff and the Cost table also writes a counting header directly under the `## Token log` heading, above every token line. It holds what a chat needs to write its own lines for this plan in the harness the waves are expected to run in (at kickoff, the one the Cost table's label names), so a pasted wave or review chat counts and prices from the plan alone, outside the cases the header's last line names. It is a bold label line naming that harness and a short list, about 1-2 KB:

- The line format, in backticks so no header line starts with `tokens`, with the row labels a pasted chat writes (`wave-N`, `review-wave-N`, and `wave-N-fix` and `review-wave-N-fix` for a fix-up wave), the group id with hyphens, the model as its price row names it, and the rounding rule.
- Where that harness keeps usage and how to normalize it: its row of the [source precedence](#token-accounting--source-precedence) table, which on Claude Code includes the dedupe by `message.id` and the `(output est.)` rule. On Cursor and Muse Code, the accumulation heuristic instead, in its form for a chat covered by one line (`T0` = 0), with what it counts, its constants, the cold start after each pause past the cache TTL and the `(heuristic)` label.
- One [price table](#model-price-table) row for each model this plan's waves and reviews run in that harness, alts the Next model rows name included, with any long-context surcharge.
- The cache-aware formula in one line, with the cache-write multipliers of those models.
- One line naming the cases that read this standard instead: a chat in another harness (its source-precedence row), a model the header doesn't list (the price table) and, on Cursor, usage Gary pastes (source 2).

A plan carries one counting header. Replacing the Kickoff or re-entering the plan keeps it, and refreshes it in place when the waves will now run in another harness or on other models (a re-grouping that adds a tier, a [Model picker](#model-picker) change); a plan without one gets one. Never add a second header, and leave the token lines below it as they are. For a Claude Code plan whose waves run Sonnet, Opus and Haiku:

    ## Token log

    **Counting header (Claude Code)**

    - Line, one per model a chat ran, appended below: `tokens <row> <group-id> (<model>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv`. `<row>` is `wave-N`, `review-wave-N`, or `wave-N-fix` and `review-wave-N-fix` for a fix-up wave; `<group-id>` is the wave's group id with hyphens (`m2-s1-s3`); `<model>` is `message.model` without a date suffix (`claude-haiku-4-5-20251001` is `claude-haiku-4-5`). Round counts to two significant figures with `k` or `M`.
    - Usage: `~/.claude/projects/<slug>/$CLAUDE_CODE_SESSION_ID.jsonl` (`<slug>` is the working directory with every character but a letter or digit turned into `-`, matched by prefix when long; without the id, the newest `.jsonl` there), plus its subagents' `<session-id>/subagents/**/agent-*.jsonl` in the same directory. Sum `message.usage` over assistant lines once per `message.id`, from the line with `stop_reason`: input `input_tokens`, cache read `cache_read_input_tokens`, cache write `cache_creation.ephemeral_5m_input_tokens` (with `ephemeral_1h_input_tokens` too, `cache write ~40k 5m + ~8k 1h`), output `output_tokens`. A call with no `stop_reason` line keeps its input-side counts, takes output as about 1,000, and its line ends `(output est.) session <id>`.
    - Rates by `<model>`, $ per Mtok input / cached / output: `claude-opus-5-5` 4.00 / 0.20 / 20.00; `claude-sonnet-5-5` 2.00 / 0.20 / 10.00; `claude-haiku-4-5` 1.00 / 0.10 / 5.00.
    - `$C` = (input × in + cache read × cached + 5m write × in × 1.25 + 1h write × in × 2.00 + output × out) / 1M.
    - In another harness, or on a model not listed here, count and price per plan-execution.md "Token accounting" and "Model price table" instead.

### Expected cost

The [Cost table](#cost-table) budgets each wave at kickoff from per-step anchors. The unit is one **medium plan step**: one FrontierCode v1.1 extended-set rollout, a maintainer-written issue turned into one mergeable patch with tests, median 308 lines over 6 files. Tokens are [billed tokens](#token-line-format). Dollars are API-equiv at the [Model price table](#model-price-table)'s rates. Rows marked "est." have no direct measurement and are rounded coarsely.

| Model (effort) | Used at | ~Tokens / step | ~$ / step (API-equiv) | Basis |
|---|---|---|---|---|
| Opus 5.5 (xhigh) + ultracode | Claude Code `[xdeep]`, audit-shaped steps | ~100M | ~$42 | The 9 Opus xhigh workflows of 5 or more agents in Gary's standards repo: median $37, plus $5.8 for the parent's share. Range $15-55. Assumes one workflow per step |
| Opus 5.5 (xhigh) | Claude Code `[xdeep]`, other steps; Cursor `[xdeep]`; `[xdeep]` review beats | 3.1M | $1.9 | FrontierCode ($1.86, 49k output) |
| Fable 5.1 (xhigh) | `[xdeep]` alt (Claude Code, Cursor) | 11M | $7.7 | FrontierCode ($7.70, 57k output). Tokens range 4.6-11M depending on the cache split |
| Opus 5.5 (max) + ultracode | An audit where max is measured to pay | ~170M | ~$80 | est.: the xhigh + ultracode row ×1.9 for dollars (CursorBench 4.0's max/xhigh cost ratio) and ×1.7 for tokens (its max/xhigh LLM-call ratio). FrontierCode's max/xhigh cost ratio, 2.8×, gives about $120 |
| Opus 5.5 (max) | `[xdeep]` where max is measured to pay | 8.6M | $5.3 | FrontierCode ($5.28, 144k output) |
| Fable 5.1 (max) | `[xdeep]` alt on terminal or CLI-heavy steps | 15M | $11 | FrontierCode ($10.72, 78k output). Tokens range 6-15M depending on the cache split |
| Opus 5.5 (high) | `[deep]` (Claude Code, Cursor); review beats; orchestrate parent | 1.7M | $0.90 | FrontierCode ($0.90, 21k output) |
| Opus 5.5 (medium) | `[deep]` interactive planning | 1.3M | $0.67 | FrontierCode ($0.67, 15k output) |
| Sonnet 5.5 (medium) | Claude Code `[exec]`; Cursor `[exec]` alt | 0.59M | $0.21 | FrontierCode ($0.21, 6.5k output) |
| Sonnet 5.5 (high) | `[exec]` step-up (Claude Code, Cursor alt) | 1.0M | $0.35 | FrontierCode ($0.35, 11k output) |
| Sonnet 5.5 (low) | `[fast]` work run on Sonnet | 0.48M | $0.17 | FrontierCode ($0.17, 5.4k output) |
| Haiku 4.5 | Claude Code `[fast]` | ~2M | ~$0.3 | est.: Sonnet 5.5 high's token volume ×1.8, the Haiku 4.5 / Sonnet 4.5 input ratio on SWE-bench Verified |
| Grok 4.7 (high), Cursor | Cursor `[exec]` | ~1.6M | ~$1.0 | est.: CursorBench 4.0 cost ratio of Grok to Sonnet/Opus high, applied to their FrontierCode steps |
| Composer 2.5 (standard) | Cursor `[fast]` | ~3.8M | ~$0.85 | est.: FrontierCode's $2.57, read as Fast rates and re-priced at standard |
| GPT-6 Astra (xhigh) | Codex `[xdeep]` | 1.4M | $2.9 | FrontierCode |
| GPT-6.1 Sol (xhigh) | Codex `[deep]` | 1.6M | $0.49 | FrontierCode |
| GPT-6.1 Sol (medium) | Codex `[exec]` | 1.1M | $0.31 | FrontierCode |
| GPT-6 Luna (low) | Codex `[fast]` | 1.2M | $0.018 | FrontierCode |
| Gemini 3.1 Pro (high) | Gemini CLI `[deep]` | ~5M | ~$2.2 | est.: FrontierCode v1 (older task set), run in Gemini CLI |
| Gemini 3.8 Flash (high) | Gemini CLI `[exec]` | 13M | $2.3 | FrontierCode (Cognition's own harness). The dollars double from 2027-01-01 |
| Gemini 3.5 Flash-Lite (low) | Gemini CLI `[fast]` | ~3M | ~$0.2 | est.: FrontierCode v1 Gemini 3.1 Flash-Lite low's token volume, re-priced at 3.5 Flash-Lite rates |
| Muse Spark 1.3 (xhigh) | Muse Code `[deep]` | ~8M | ~$1.6 | est.: Artificial Analysis $3.47 divided by 2.1, the median AA/FrontierCode cost ratio |
| Muse Spark 1.3 (medium) | Muse Code `[exec]` | ~5M | ~$1.1 | est.: the xhigh row ×0.68, GPT-6.1 Sol's medium/xhigh ratio on AA |
| Muse Spark 1.3 (low) | Muse Code `[fast]` | ~4M | ~$0.8 | est.: the xhigh row ×0.48, Sol's low/xhigh ratio |
| Grok 4.7 (xhigh) | Grok Build `[deep]` | 11M | $7.0 | FrontierCode (Grok Build) |
| Grok 4.7 (high), Grok Build | Grok Build `[exec]` | 9.1M | $5.6 | FrontierCode (Grok Build) |
| grok-build-0.1 | Grok Build `[fast]` | ~4M | ~$1 | est.: Grok 4.6 high's FrontierCode token volume in Grok Build, priced at grok-build-0.1 rates. Range $0.3-2.3 |

**Size factors** multiply both tokens and dollars:

| Size | Factor | Basis |
|---|---|---|
| small (about 100 lines over 4 files, fully specified) | 0.3× | Anthropic's SWE-bench Pro subset over FrontierCode for Opus 5.5: 0.30× at medium, 0.32× at high, 0.39× at xhigh. Its harness is leaner than Claude Code's, so treat 0.3× as a floor |
| medium (about 300 lines over 6 files) | 1× | FrontierCode v1.1 extended |
| large (long-horizon or ambiguous, several hundred lines or more) | 3× | CursorBench 4.0 over FrontierCode, same model and effort: median 2.96× over 15 Anthropic rows (range 0.6-4.8×). Anthropic's Terminal-Bench 4.0 over FrontierCode for Opus: median 3.95× |

**Per wave.** Price each step at the row for the model and effort that run the wave's execution tier in the harness the estimate assumes ([Model picker](#model-picker)), so a folded `[fast]` step takes the `[exec]` row, and only an audit-shaped `[xdeep]` step takes the ultracode row. Then add the wave's review:

    wave tokens  = sum over its steps of (row tokens  × size factor) + review tokens
    wave dollars = sum over its steps of (row dollars × size factor) + review dollars

- **Review beat** (passive driver): 0.6× a medium step at the reviewer's model, in tokens and dollars (range 0.4-1.2×). After a `[deep]`, `[exec]` or `[fast]` wave that is Opus 5.5 (high): about 1.0M and $0.54. After an `[xdeep]` wave it is Opus 5.5 (xhigh) without ultracode: about 1.9M and $1.1 (up to about $1.3 at 0.7×, the ratio read-only work shows at max). On another harness it is 0.6× that harness's row at the review's tier: its `[deep]` row (GPT-6.1 Sol xhigh: about $0.29), or its `[xdeep]` row after an `[xdeep]` wave (GPT-6 Astra xhigh: about $1.7). A review's cost follows calls × context, not output, so the review of a small `[fast]` wave can cost more than the wave.
- **`[xdeep]` review subagent** (orchestrate): the same 0.6× of the Opus 5.5 (xhigh) row, about 1.9M and $1.1.

**Kickoff row** (passive driver). The kickoff chat reads the skill and plan, tags, and writes the markers, the Kickoff and the Cost table, the same work as the orchestrator's kickoff part below: about 1.5M and $1.0 on Opus 5.5 (high).

**Orchestrator row** (orchestrate only). The parent runs Opus 5.5 (high) in Cursor and reviews inline:

| Part | ~Tokens | ~$ |
|---|---|---|
| Kickoff: read the skill and plan, tag, write the wave markers, Kickoff and Cost table, seed todos, git checks | 1.5M | $1.0 |
| Start-up of the orchestrating chat after the default new-chat handoff | 0.9M | $0.75 |
| Each wave: summary review, Review log line, plan bookkeeping | 1.1M, plus 0.16M per earlier wave | $0.95, plus $0.11 per earlier wave |
| Each gate that waits on a human past the 5-minute cache TTL | 0.45M | $0.8 |

The per-wave share grows with the parent's context, by about 16k tokens a wave. A wave outlasts the cache TTL while the parent makes no calls, so each wave starts by re-writing the parent's whole context at the write rate. Count the canary gate, which always waits, and each gate 2, 3, 4 or 7 the plan crosses; gates asked in one question count as one wait. These figures come from the accumulation heuristic with Claude Code's 50k base context; Cursor's base is unknown.

**Example** (Claude Code, passive driver; the [Cost table](#cost-table) shows the result):

- Wave 1 `[exec]`, 3 medium steps on Sonnet 5.5 (medium): 3 × (0.59M, $0.21) = 1.8M and $0.63, plus its review, 0.6 × (1.7M, $0.90) = 1.0M and $0.54. About 2.8M and $1.2.
- Wave 2 `[deep]`, 1 large step on Opus 5.5 (high): 3 × (1.7M, $0.90) = 5.1M and $2.70, plus its review. About 6.1M and $3.2.
- Wave 3 `[fast]`, 4 small steps on Haiku 4.5: 4 × 0.3 × (2M, $0.30) = 2.4M and $0.36, plus its review. About 3.4M and $0.90.
- Kickoff on Opus 5.5 (high): about 1.5M and $1.0.
- Total: about 14M and $6.3. The reviews are 26% of it, and wave 3's review costs more than the wave.

**Accuracy.** A single step's figure is good to about 2-3× either way, and so are a wave's and a plan total's: the largest errors (the harness's base context, how a plan step compares to a FrontierCode task) are shared by every wave, so they don't cancel. Token counts also depend on the assumed cache split, while the dollars don't, since the anchors are dollars. Harness matters: Grok 4.7 (high) costs $5.6 a step in Grok Build against the Cursor row's estimated $1.0, and Composer's FrontierCode cost is 3.8× its CursorBench cost on a longer task, for reasons unknown. The Opus and Sonnet rows below max come from Claude Code runs that carried about 23-36k tokens of context per model call on average (input backed out of FrontierCode's dollars, over its call counts), so a setup with a 50k base context (skills, MCP and tool listings) runs above them: the cache reads of the extra base alone take the Opus 5.5 rows at medium, high and xhigh to at least about 1.45×, 1.35× and 1.15×, and the Sonnet 5.5 rows at low, medium and high to about 1.45×, 1.4× and 1.3×.

*As of 2026-10-07. Sources: [FrontierCode v1.1](https://cognition.com/frontiercode) (Cognition; extended set, cost per rollout in each vendor's own harness at list prices; leaderboard of 2026-09-29; v1 for the Gemini 3.1 Pro and Flash-Lite rows), [CursorBench 4.0](https://cursor.com/evals) (2026-09-10), Anthropic's [SWE-bench Pro subset](https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence) (runs of 2026-09-19 and 20) and [Terminal-Bench 4.0 results](https://www.anthropic.com/claude-opus-5-5) (2026-09-22), the [Artificial Analysis Coding Agent Index](https://artificialanalysis.ai/agents/coding-agents) v1.5 (2026-10-05), [swebench.com](https://www.swebench.com/) bash-only trajectories (2026-02), and 97 Claude Code work agents on Opus 5.5 at xhigh (of 131 analysed) in Gary's standards repo (2026-10) for the ultracode, review and orchestrator figures.*

**Refresh** the anchors when completed plans' actuals keep landing outside 0.5×-2× of expected, and re-derive a row when the [Model picker](#model-picker) changes its model or effort.

### Wave title format

Both drivers label each wave with the same human-scannable title so a wave is identifiable wherever it surfaces:

    Wave {n} of {t} [{tier}] {group-id}

For example, `Wave 2 of 3 [exec] repo-A m2 s1-s3`. Fill it in as:

- `{n}` — the 1-based wave number the title refers to, `N-fix` for a [fix-up wave](#wave-annotation-format) (the wave a STOP marker is launching is the *next* wave; a Kickoff always refers to wave 1).
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
        Cursor:      grok-4-7[effort=high]      (or claude-sonnet-5-5[effort=medium])
        Claude Code: /model sonnet              (/effort medium)

      Prompt to paste into the next chat:
        Wave <n> of <t> [exec] <next group>
        Read <absolute path to the plan file>. Execute <next group>.
        On branch <name> (task branch): commit each finished step.
        Before you stop, update plan progress: append ` (done)` to the
        headings you finished, update the Kickoff Status line, and flip the
        matching todos. Append one line per model this chat ran to the
        plan's "## Token log", counted and priced per its counting header:
          tokens wave-<n> <group-id> (<model>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv
        Then stop at the next STOP marker and report what you changed and
        any deviations from the plan.

    ---

For an `[exec] -> [fast]` transition, the prompt should also remind the model not to generalize:

    --- STOP: tier change [exec] -> [fast] ---

      Suggested chat title: Wave <n> of <t> [fast] <next group>

      Next model
        Cursor:      composer-2.5[fast=false]
        Claude Code: /model haiku               (no effort setting)

      Prompt to paste into the next chat:
        Wave <n> of <t> [fast] <next group>
        Read <absolute path to the plan file>. Execute <next group>.
        On branch <name> (task branch): commit each finished step.
        These are mechanical edits -- apply exactly what the plan
        specifies; do not refactor, rename, or generalize. Before you
        stop, update plan progress (mark the headings you finished
        ` (done)`, update the Status line, flip the matching todos). Append
        one line per model this chat ran to the plan's "## Token log",
        counted and priced per its counting header:
          tokens wave-<n> <group-id> (<model>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv
        Then stop at the next STOP marker and report back.

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
        (see the Review beat section), so do not re-review it here.
        On branch <name> (task branch): commit each finished step.
        Before you stop, update plan progress (mark the headings you finished
        ` (done)`, update the Status line, flip the matching todos). Append
        one line per model this chat ran to the plan's "## Token log",
        counted and priced per its counting header:
          tokens wave-<n> <group-id> (<model>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv
        Stop after the design is written and report back.

    ---

For an escalation to `[xdeep]` (from any tier), use the `[deep]` escalation body above with the `[xdeep]` model row from the [Model picker](#model-picker):

      Next model
        Cursor:      claude-opus-5-5[effort=xhigh]   (Cursor has no ultracode)
        Claude Code: /model opus                (/effort xhigh, plus ultracode if audit-shaped)

For an audit-shaped wave ([upgrade checklist](#xdeep-upgrade-checklist)), start the prompt with the keyword `ultracode` so that turn runs under ultracode; for one that may take more than one turn, run `/effort ultracode` in that chat instead. Leave both out otherwise. Add one line naming the [upgrade checklist](#xdeep-upgrade-checklist) condition each step met. When Opus at xhigh has already failed the step and a different model is wanted, swap in the Fable alt (`claude-fable-5-1[effort=xhigh]` / `/model fable` + `/effort xhigh`). Name max (`[effort=max]` / `/effort max`) only for a task type where a gain is measured ([Model picker](#model-picker)).

Rules for filling in the template:

- `<absolute path to the plan file>` is the **fully-qualified absolute path** to the plan file, resolved when the plan was identified — for example: `/Users/gary/Projects/personal/public/.scratch/plan-topic-word.md`. Never emit a bare filename or a repo-relative path — the next chat may start from a different working directory. The one exception is a plan tracked in `specs/handoffs/` on a runner: give its repo-relative path, because the branch (named on the `On branch` line) is reopened on another machine where the container's absolute path means nothing.
- The `Next model` block names Cursor and Claude Code. When the plan runs in Codex, Gemini CLI, Muse Code, or Grok Build, replace the Cursor row with that harness's row from the [Model picker](#model-picker).
- Name the next group using whatever identifiers the plan uses: if headings
  carry IDs, use those (e.g. `m2 s1-s4`); if not, use exact title text
  (e.g. `the "Wire Redis client" through "Write integration tests" steps`).
- Always include the `Suggested chat title:` line in the [Wave title format](#wave-title-format). `{n}` is the **next** wave (the one this STOP launches), `{t}` the total wave count, and `{group-id}` the same identifier used to name the next group above. It is advisory — a foreground chat cannot set its own title, so emit it for the user to paste even though there is no guarantee the harness will use it.
- Always include the "Stop at the next STOP marker" hard limit so the cascade is preserved.
- `On branch <name> (task branch)` names the task branch the plan runs on. Each wave is a new chat, so a branch cut in an earlier one isn't "cut this session"; Gary pasting the prompt names the branch for the work (git.md "Task branches and shared branches"), so a chat on `<name>` commits there without asking again. A chat on another branch: on a runner, the harness-assigned branch wins; the chat works there, says in its first report that it isn't `<name>`, and puts its own branch on the remaining prompts' `On branch` lines (the earlier wave's branch stays as is). On a workstation, it proposes switching to `<name>` and waits, committing nothing until Gary answers. With no task branch yet (a workstation on a shared branch), leave the line out; the chat that cuts one adds it to the remaining prompts with its first commit. The REVIEW prompt carries it only when the plan file is tracked (in `specs/handoffs/` on a runner), as `On branch <name> (task branch): commit the plan update before you stop.`; a plan in gitignored `.scratch/` stays uncommitted (never `git add -f`).
- Always include the **progress-update reminder** spelled out inline in the prompt body (append ` (done)` to finished headings, update the Kickoff Status line, flip the matching todos). The pasted chat usually does **not** re-load the driver skill, so this inline reminder is the only way the [Progress tracking](#progress-tracking) convention reaches it — never drop it. Do not factor it out into a separate checklist block in the plan; keep it in the prompt.
- Always include the **token-line reminder** the same way, with `<n>` and `<group-id>` (the group identifier with hyphens, `m2-s1-s3`) filled in. It sends the chat to the Token log's [counting header](#token-line-format) for how to count and price the line, never to this standard, so a pasted chat reads only the plan. The [Cost table](#cost-table)'s actual columns are summed from the Token log, and the prompt is the only place a pasted chat learns to write its line.
- Use `->` ASCII arrows rather than Unicode em-dash arrows so the marker is safe in terminals and grep.
- If the next group is a `[deep]` block being delegated to a parent, the prompt should say "design only, do not implement"; if it's `[exec]` or `[fast]`, the prompt should say "implement <next group>, stop at next STOP marker."

### Review beat

A **review beat** is a dedicated, read-only `[deep]` pass over the work a wave just produced, run **after every wave** before the next one starts. It exists so cheaper-tier output (`[exec]`/`[fast]`) — and even `[deep]` output — is checked by a top-tier model against the spec before the plan builds further on it. Reviewing is `[deep]` work (catching architectural drift, broken contracts, security smells), so a review beat pins the `[deep]` model for any `[deep]`, `[exec]`, or `[fast]` wave. A wave that ran at `[xdeep]` gets an `[xdeep]` review (`--- REVIEW: wave-N [xdeep] ---`, Opus 5.5 at xhigh effort without ultracode; see the note after the template): a reviewer below the author's tier caps the review at its own level.

Cadence is recorded in the Kickoff block as a `review:` line. The default is `review: every-wave` — a beat follows every wave, including same-tier `[exec] -> [exec]` boundaries. (Contrast `personal-plan-orchestrate`, whose Opus parent reviews every returned subagent summary inline and writes the same verdict to the [Review log](#review-log) — it participates **log-only** and adds no human review gate; see [Who updates progress, and how](#who-updates-progress-and-how).)

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
        wave <n> (<group-id>) against its spec: read `git diff <from>` and
        `git status`, where <from> is the commit after `..` on the last
        Review log line (for the first review, `git merge-base HEAD
        origin/<default branch>`), and check it against the plan steps and
        any acceptance criteria. This is READ-ONLY -- do not fix anything
        yourself and do not start the next wave. Append one line to the
        "## Review log" section of the plan file (create the section if
        absent), with <to> from `git rev-parse --short HEAD`:
          review wave-<n> (<group-id>) <from>..<to>: PASS|CONCERNS - <one-line note> - <YYYY-MM-DD>
        Append one line per model this chat ran to "## Token log",
        counted and priced per its counting header:
          tokens review-wave-<n> <group-id> (<model>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv
        If the verdict is CONCERNS, also set the Kickoff Status line to
        `BLOCKED at gate review-wave-<n>`, re-post the concern, and stop.
        On PASS, update the Status line `last review:` field and report back.
        On branch <name> (task branch): commit the plan update before you
        stop.

    ---

Keep that last line only when the plan file is tracked (the [STOP fill-in rules](#stop-marker-template)); a plan in `.scratch/` isn't committed. The token-line reminder follows the same fill-in rule as in the STOP prompts.

The last wave's review also does the plan's [final completion](#final-completion-all-groups-done), since no chat runs after it. Its prompt adds, after the `On PASS` line:

        On PASS, this was the last wave, so also finish the plan: replace
        the Kickoff marker line with `--- KICKOFF: plan complete ---` and
        its Status line with `N/N groups done | completed <YYYY-MM-DD>`,
        add the `actual tokens` and `actual $` columns to the Cost table
        from "## Token log" (your own lines included), and append the
        Completion summary, per plan-execution.md "Final completion".

On a plan that runs `review:` off, the last wave's own prompt carries the same instructions instead. When the last wave's review returns `CONCERNS`, its fix-up wave's review becomes the last review and carries them; when Gary waives the concern instead, the chat that records the waiver runs final completion.

For a wave that ran at `[xdeep]`, change `[deep]` to `[xdeep]` in the marker, the chat title, and the prompt's first line, and use these rows:

      Next model
        Cursor:      claude-opus-5-5[effort=xhigh]
        Claude Code: /model opus                (/effort xhigh)

Leave ultracode off for the review, in Claude Code too: a review is one read-only verdict, and fan-out would multiply its tokens. The reviewer runs at the tier's model and effort, Opus 5.5 at xhigh, even after a wave that ran the Fable alt or max.

### Review log

The **Review log** is a durable `## Review log` section at the bottom of the plan file (parallel to the [`## Token log`](#token-line-format) the drivers maintain). It persists review verdicts across separate chats so a fresh session — or the final wave — can see the full review history. Both drivers write to it: the passive driver from each review beat, `personal-plan-orchestrate` from its parent after each wave.

One line per reviewed wave:

    review wave-<n> (<group-id>) <from>..<to>: PASS|CONCERNS - <one-line note> - <YYYY-MM-DD>

For example:

    review wave-1 (m1-s1-s5) 3f2a9c1..8d0e4b7: PASS - standards wording is internally consistent - 2026-06-07
    review wave-2 (m2-s1-s2) 8d0e4b7..c41f0a2: CONCERNS - s2 skips the orchestrate log-only note - 2026-06-07

- `<from>..<to>` is the commit range the review read (`git diff <from>` also covers uncommitted work). The next review starts from this line's `<to>`. On a shared branch, where waves stay uncommitted, both ends are the same commit.

- `PASS` verdicts let the next wave proceed; `CONCERNS` is fail-closed (see [Review beat](#review-beat) above).
- The verdict also surfaces in the Kickoff `Status:` line `last review:` field (see [Updating the Status line](#updating-the-status-line)) so re-entry sees the latest result without scanning the log.

### Kickoff template

A Kickoff block tells the next agent how to **start** executing a tagged plan: which model to run on and what prompt to paste. Same shape as a STOP marker, but emitted once at the top of the plan file rather than at each tier transition. Every plan that has been processed by `personal-plan-model-tiers` or `personal-plan-orchestrate` should carry exactly one Kickoff block at the top.

Placement and idempotence:

- The skill writes the Kickoff block at the **top of the plan file**, above the first heading, inside a fenced code block so it pastes cleanly.
- The block is idempotent: if a Kickoff block already exists at the top of the file (matching the marker line `--- KICKOFF: ... ---`), the skill **replaces** it with the appropriate variant rather than appending. A plan never carries more than one Kickoff block.
- The [Cost table](#cost-table) goes directly below the Kickoff block. Replacing the Kickoff keeps it, under the Cost table's own idempotence rule.
- The kickoff writes the [counting header](#token-line-format) at the top of `## Token log`, creating the section at the bottom of the plan. Replacing the Kickoff keeps it, under the header's own idempotence rule.
- Skills must not modify any other content in the plan when writing the Kickoff, apart from that Cost table and counting header. Tagging rules, STOP markers, and existing prose all stay where they are.

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
        Cursor:      grok-4-7[effort=high]      (or claude-sonnet-5-5[effort=medium])
        Claude Code: /model sonnet              (/effort medium)

      Prompt to paste into the next chat:
        Read <absolute path to the plan file>. Begin execution at the top
        of the plan.
        On branch <name> (task branch): commit each finished step.
        Before you stop, update plan progress: append ` (done)` to the
        headings you finished, update the Kickoff Status line, and flip the
        matching todos. Append one line per model this chat ran to the
        plan's "## Token log", counted and priced per its counting header:
          tokens wave-1 <group-id> (<model>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv
        Then stop at the next STOP marker and report what you changed and
        any deviations from the plan.

    ---

Passive variant — `[fast]` first wave (prompt body adds the "no refactor" reminder):

    --- KICKOFF: begin execution at [fast] ---

      Status: 0/N groups done | last review: — | current: <first group> [fast] | updated YYYY-MM-DD

      review: every-wave

      Suggested chat title: Wave 1 of N [fast] <first group>

      Next model
        Cursor:      composer-2.5[fast=false]
        Claude Code: /model haiku               (no effort setting)

      Prompt to paste into the next chat:
        Read <absolute path to the plan file>. Begin execution at the top
        of the plan.
        On branch <name> (task branch): commit each finished step.
        These are mechanical edits -- apply exactly what the
        plan specifies; do not refactor, rename, or generalize. Before you
        stop, update plan progress (mark the headings you finished
        ` (done)`, update the Status line, flip the matching todos). Append
        one line per model this chat ran to the plan's "## Token log",
        counted and priced per its counting header:
          tokens wave-1 <group-id> (<model>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv
        Then stop at the next STOP marker and report back.

    ---

For a `[deep]` or `[xdeep]` first wave, use the same body as the `[exec]` example with that tier's model row from the [Model picker](#model-picker) above. An `[xdeep]` first wave also takes the additions from the [STOP marker](#stop-marker-template) `[xdeep]` note: the `ultracode` opt-in for an audit-shaped wave and the checklist line.

Active variant — orchestrate (always `[deep]` / Opus):

    --- KICKOFF: begin orchestration at [deep] ---

      Status: 0/N groups done | last review: — | current: <first group> [deep] | updated YYYY-MM-DD

      review: every-wave (log-only — parent writes Review log; no human review gate)

      Next model
        Cursor:      claude-opus-5-5[effort=high]
        Claude Code: /model opus                (/effort high)

      Prompt to paste into the next chat:
        Read <absolute path to the plan file>. The plan is already tagged.
        On branch <name> (task branch): subagents commit each finished step.
        Run the personal-plan-orchestrate skill from the top: walk to
        each tier boundary, dispatch Task subagents per the skill's
        procedure, and pause only at the mandatory STOP gates. Do not
        execute plan work inline. Update plan progress after each wave
        returns per the skill's procedure. You are the kickoff destination
        chat; skip the "continue here or new chat?" question and begin
        dispatching immediately.

    ---

Rules for filling in the template:

- `<absolute path to the plan file>` is the **fully-qualified absolute path** to the plan file, resolved when the plan was identified — for example: `/Users/gary/Projects/personal/public/.scratch/plan-topic-word.md`. Never emit a bare filename or a repo-relative path — the next chat may start from a different working directory. The one exception is a plan tracked in `specs/handoffs/` on a runner: give its repo-relative path, because the branch (named on the `On branch` line) is reopened on another machine where the container's absolute path means nothing.
- For the passive variant, the `<tier>` is the **execution tier of the first wave** after the no-thrash folding pass (see [No-thrash rule](#no-thrash-rule)). This is normally the tag on the first executable heading, walking top-down — higher-level grouping headings (milestones, phases) are untagged and ignored, per [Tag placement](#tag-placement). The one exception: when a short leading `[fast]` run (< 3 steps) is folded into the following `[exec]` wave, the first wave executes at `[exec]`, so the Kickoff shows `[exec]` even though those headings keep their honest `[fast]` tags.
- The `On branch <name> (task branch)` line follows the [STOP marker](#stop-marker-template) rule: the task branch when there is one, left out until a task branch exists. In the active variant the parent passes it to every dispatch as the git instruction.
- For the active variant, the model is **always** `claude-opus-5-5[effort=high]` / `/model opus` at `/effort high`, regardless of what the first wave's tier is. The orchestrator-parent always runs at `[deep]`.
- Use `->` ASCII arrows rather than Unicode em-dash arrows so the marker is safe in terminals and grep.
- Fill in the `Status:` line with the total group count (`N`), the first group's identifier, and today's date. Update it as execution progresses (see [Progress tracking](#progress-tracking) below).
- For the passive variants, include the `Suggested chat title:` line in the [Wave title format](#wave-title-format) for the first wave (`Wave 1 of N [<tier>] <first group>`). It is advisory — a foreground chat cannot set its own title, so emit it for the user to paste even though the harness may ignore it. The active orchestrate variant has no such line: its per-wave titles are the `Task` subagent descriptions.
- For the passive variants, always keep the **progress-update reminder** spelled out inline in the prompt body (append ` (done)` to finished headings, update the Status line, flip the matching todos). A fresh chat that pastes this prompt usually does **not** re-load the driver skill, so this line is the only way the [Progress tracking](#progress-tracking) convention reaches the worker — it is the single most common reason a wave finishes without being marked done, so never drop it. Keep the token-line reminder too, filled in per the [STOP fill-in rules](#stop-marker-template). (The active orchestrate variant re-loads the skill, so its parent applies the updates per the skill procedure instead; see [Who updates progress, and how](#who-updates-progress-and-how).)
- For both variants, write the Token log's [counting header](#token-line-format) for the harness the Cost table names. The passive prompts send every pasted chat to it, and the orchestrate parent quotes it into each dispatch prompt.

### Cost table

The **Cost table** budgets the plan per wave at kickoff and records what each wave actually cost at completion. The driver writes it directly below the Kickoff fenced block, as a real markdown table outside any fence so it renders, and prints it in chat with the Kickoff. A bold label line introduces it and names the harness the estimate assumed. The label is not a heading, so the tagger never treats it as a step.

At kickoff, for the [Expected cost](#expected-cost) example:

    **Cost (API-equiv, Claude Code models)**

    | wave | expected tokens | expected $ |
    |---|---|---|
    | 1 [exec] m1 s1-s3 | ~2.8M | ~$1.2 |
    | 2 [deep] m2 s1 | ~6.1M | ~$3.2 |
    | 3 [fast] m3 s1-s4 | ~3.4M | ~$0.90 |
    | kickoff | ~1.5M | ~$1.0 |
    | **Total** | ~14M | ~$6.3 |

    Expected values are estimates, good to about 2-3× per wave.

- **Rows.** One per wave, in the order the waves run, labeled `<n> [<execution tier>] <group-id>` with the group identifier of its [wave title](#wave-title-format). A wave's row includes its review: the passive driver's review beat, or orchestrate's `[xdeep]` review subagent. Above the total, the passive driver adds a `kickoff` row for its kickoff chat, and orchestrate an `orchestrator` row for its parent: the kickoff, the start-up after the new-chat handoff, each wave's review and bookkeeping, and each gate that waits on a human ([Expected cost](#expected-cost)). The **Total** row comes last.
- **Expected values** come from [Expected cost](#expected-cost) for the harness the label names: the harness the kickoff runs in, unless Gary names another. Show them with `~`, and keep the one line under the table that says how far to trust them.
- **Waves added later.** A wave added after kickoff (a fix-up wave after `CONCERNS`, or a re-plan) gets its own row with expected `—`. A [fix-up wave](#wave-annotation-format) for wave N is `N-fix` (row `1-fix [exec] m1 s2`, token lines `wave-1-fix` and `review-wave-1-fix`). A re-plan's new waves take the next unused numbers, and a wave it drops keeps its row. The expected total sums only the planned rows and the actual total sums every row, so the gap between them shows the cost of unplanned work. A step-up retry is not a new wave: it counts in its wave's actual.
- **Idempotence.** A plan carries one Cost table. Replacing the Kickoff keeps the table and its expected values. Before any wave has run, re-grouping that changed the waves recomputes the expected columns (say so in chat); after that, a re-plan follows the rule above and no expected value changes.
- **Re-entry.** A driver re-entering a plan keeps the table as it stands and adds rows for waves added since. If the table is missing, it writes one with expected values for every planned wave.
- **Completion.** At [Final completion](#final-completion-all-groups-done), add `actual tokens` and `actual $` columns. Each row's actuals are the sum of its [Token log](#token-line-format) lines across models: billed tokens, and dollars. A wave row sums its `wave-N` and `review-wave-N` lines, the `kickoff` row its `kickoff` lines, and the `orchestrator` row the `orchestrator-*` lines. A wave that never ran shows actual `—`. Mark an actual `(heuristic)` or `(output est.)` when any line it sums carries that label, and `(combined)` when a `(combined: <rows>)` line names its row. The completed table is the plan's cost breakdown; the Token log keeps the per-model detail.

Completed, with a fix-up wave after wave 1's review:

    | wave | expected tokens | expected $ | actual tokens | actual $ |
    |---|---|---|---|---|
    | 1 [exec] m1 s1-s3 | ~2.8M | ~$1.2 | … | … |
    | 1-fix [exec] m1 s2 | — | — | … | … |
    | 2 [deep] m2 s1 | ~6.1M | ~$3.2 | … | … |
    | 3 [fast] m3 s1-s4 | ~3.4M | ~$0.90 | … | … |
    | kickoff | ~1.5M | ~$1.0 | … | … |
    | **Total** | ~14M | ~$6.3 | … | … |

## Who updates progress, and how

The two tracking surfaces — the in-harness todo list and the durable plan markdown file (both defined under [Progress tracking](#progress-tracking) below) — are kept in sync differently by each driver, because only one flow has a coordinator:

- `personal-plan-orchestrate` **has an orchestrator-parent**. After each wave's subagent returns, the parent applies the [Progress tracking](#progress-tracking) updates itself (mark ` (done)`, update the `Status:` line, flip todos). Subagents do mechanical work in their own working directory and never touch the plan file. This is handled by the skill procedure, so it does not need to ride in any prompt. The git instruction does ride in every dispatch prompt (see [Delegating execution to subagents](#delegating-execution-to-subagents)): on a task branch subagents commit each finished step, and only the parent pushes, after its review. So does the token-reporting instruction, quoted from the Token log's [counting header](#token-line-format), since subagents never read the plan. The parent also **reviews every returned summary** as part of that step and writes the verdict to the [Review log](#review-log) (`review wave-N (<group-id>) <from>..<to>: PASS|CONCERNS - … - <date>`) — this is the orchestrate **log-only** participation in the [review beat](#review-beat) convention. It adds **no human review gate** beyond orchestrate's own (the `[exec]/[fast] -> [deep]` review gate and the milestone gate), and the every-wave review beat that the passive driver runs as a separate human-driven chat is, in orchestrate, just the parent's inline review plus the log write.
- `personal-plan-model-tiers` **has no orchestrator**. Each wave runs in its own pasted chat, and that chat usually does **not** re-load the driver skill — it just reads the plan, executes, and stops. So the progress-update instruction is **baked inline into every Kickoff/STOP prompt body** (see the templates above), and so is the token-line reminder, which the REVIEW prompts carry too. The reminder sends the chat to the [counting header](#token-line-format) the kickoff wrote at the top of the plan's `## Token log`, which holds the line format, usage source, rates and formula for this plan, so a pasted chat reads the plan, not this standard. The pasted prompt is the only place the convention can reach a fresh chat, which is why the reminder is spelled out in full there rather than referenced. Do **not** add a separate checklist block to the plan file to carry this — it is noise for the human and burns context; the inline prompt reminder is the mechanism, and the counting header only holds the data it points to.

## Progress tracking

Plans span multiple chat sessions, which means native harness todos (Cursor Plan-mode checkboxes, `TodoWrite`) disappear on each handoff. The `.scratch/plan-*.md` file is the durable source of truth. The convention below keeps both surfaces in sync throughout execution. Who applies it differs by driver — see [Who updates progress, and how](#who-updates-progress-and-how) above.

### Two surfaces

- **Harness todo list** (live, in-session): one todo per *execution wave* (consecutive same-tier block after the no-thrash folding pass; a short folded `[fast]` run rides inside its neighbor's wave). The current wave is `in_progress`; it flips to `completed` the moment the wave finishes. Seeded by the driver skill that writes the Kickoff block.
- **Plan markdown file** (durable, cross-session): updated at every STOP boundary and at plan completion. Survives chat handoffs because the `.scratch/` file is on disk. On a runner the plan lives in `specs/handoffs/` instead and is committed and pushed at every STOP boundary, since the container's disk doesn't survive (core.md "Runner scratch rides the branch").

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

Final completion runs once the last group finishes and its review passes: in the passive flow, in the last wave's [review beat](#review-beat) on `PASS` (in the last wave's own chat when `review:` is off), and in orchestrate, in the parent after the last wave's review. It does:

1. Flip all remaining native todos to `completed`.
2. Ensure every executable heading carries ` (done)`.
3. Replace the Kickoff marker line with the terminal form:

       --- KICKOFF: plan complete ---

   and update the Status line to:

       Status: N/N groups done | completed YYYY-MM-DD

4. Replace each `(output est.)` line in the `## Token log` whose session has ended with that session's `cost-state` totals ([source precedence](#token-accounting--source-precedence)), per model from `modelUsage.<model>`, taking the line's dollars from its `costUSD` since the record doesn't split 5-minute from 1-hour writes; a session that is still live, or whose record also covers other rows, keeps its lines. Then add the actual columns to the [Cost table](#cost-table) from the Token log, and print the completed table in chat with the Completion summary.

5. Append a **Completion summary** at the bottom of the plan file (below all existing content):

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
- **The gate asks about the plan, not git.** On a task branch the finished wave is already committed (on a runner, pushed) when the gate asks, so the question is only the plan decision, and it names the commit range for review (`m2 s1-s3 is in 8d0e4b7..c41f0a2. Start wave 3 [deep] m3 s1?`). Never ask "approve, commit, push?" there. On a shared branch the wave stays uncommitted unless the question offers the commit as its own choice (`Commit wave 2 to main and start wave 3? yes / commit only / start only / neither`); any other reply is ambiguous: re-ask.
- **On a task branch, commit before you wait.** Update the `Status:` line and commit, then re-post the question. A runner also writes the handoff and pushes first, since the blocked-gate turn may be the container's last (core.md "Save before you wait").
- Cross-references: [Progress tracking](#progress-tracking) (the Status line) and the AGENTS.md "Wait for approval" workflow rule.

## Delegating execution to subagents

When a `[deep]` agent finishes a deep step and the next step is `[exec]` or `[fast]`, prefer delegating the next group to a subagent on a smaller model rather than burning the deep context on mechanical work.

- Use the harness's subagent/Task tool (Cursor `Task` with `subagent_type` and optional `model`; Claude Code `Agent`, called `Task` before 2.1.63 and still accepted under that name; other harnesses use the equivalent).
- Pass the cheapest model that can plausibly complete the step (see the model picker in "Model-tier stop points" above). Step up only if the subagent fails or returns low-quality output.
- Give the subagent: the spec section, the exact files to touch, acceptance criteria, and a hard scope limit. Subagents do not see the parent conversation, so be explicit.
- Check the branch and the git email first, in each working directory the subagents will touch (git.md "Task branches and shared branches", core.md "Verify git email"), since they commit there. A runner on any branch that isn't a task branch cuts one; a workstation on a shared branch asks whether to cut one before the first dispatch, and without a yes the subagents don't commit.
- Give it the git instruction too. On a task branch: commit each finished step on the current branch (`m{N}.s{K} <imperative subject>`, only the paths it changed), and don't push, branch, or switch. On a shared branch: don't commit. A subagent may not get the always-on rules (Claude Code subagents don't get SessionStart output, which is how runners load core.md), so spell it out. The parent reviews, then pushes: the one exception to a runner pushing after every commit.
- The deep parent stays responsible for reviewing the subagent's output and deciding the next stop point.
- If the harness does not support per-subagent model selection, stop at the boundary instead and let the user start a fresh session on a cheaper model using the STOP marker's handoff prompt.
