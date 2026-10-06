---
name: personal-plan-orchestrate
description: >-
  Actively orchestrate a tiered plan by delegating each wave to a Cursor
  `Task` subagent on the right model, while the `[deep]` parent retains
  overall control. Same `[xdeep]` / `[deep]` / `[exec]` / `[fast]` tagging
  and no-thrash rule as `personal-plan-model-tiers`, but instead of stopping
  at every tier boundary for a human-driven model swap, the orchestrator
  dispatches subagents automatically and pauses only at a small set of
  mandatory STOP gates. Cursor-only today. Use when the user asks to
  "orchestrate this plan", "delegate exec groups", "run plan in parallel
  where possible across repos / worktrees", or wants the cascade run
  automatically rather than stopping at each handoff.
---

# personal-plan-orchestrate

Active counterpart to [`personal-plan-model-tiers`](../personal-plan-model-tiers/SKILL.md).
Both drivers tag via the shared
[`personal-plan-tag-tiers`](../personal-plan-tag-tiers/SKILL.md) skill and
group the tagged steps into waves with the same no-thrash rule. The passive
skill inserts STOP markers and waits for the human to swap models or paste
handoff prompts at every tier boundary. This skill, where the passive skill
would emit a STOP, **delegates the next wave to a Cursor `Task` subagent on
the right model and continues** — pausing only at the mandatory STOP gates
listed below.

If you want STOP-and-paste handoffs (e.g. you prefer to drive each tier
change yourself, or you're not on Cursor), invoke `personal-plan-model-tiers`
instead. The two skills are deliberately separate; do not merge them.

## Anti-pattern — read this before you start

If you find yourself emitting STOP markers, printing copy-pasteable handoff
prompts, or asking the user to swap models manually, **you are running the
wrong skill**. Stop, re-read the "Procedure" section below, and dispatch
`Task` subagents at the boundaries instead. The correct artifact for each
tier transition in this skill is a tool call, not a marker. The phrase
"STOP marker" should not appear in any output you produce — it belongs to
`personal-plan-model-tiers`, not here.

Writing the Kickoff block to the top of the plan file in step 4 of the
Procedure is **not** the anti-pattern; that block is a durable reference
the user can reuse to launch a fresh Opus chat. The anti-pattern is (a)
printing STOP markers in chat output asking the user to swap models, or
(b) executing plan work inline in this chat instead of dispatching a
`Task` subagent at the boundary.

The orchestrator's mandate is to keep moving and pause only at mandatory
STOP gates — **and those gates are fail-closed.** Never rationalize
proceeding on a missed answer, a dismissed prompt, or a prior one-time
"continue". A background-subagent completion notification is not an
answer; it does not advance a pending gate. See "Mandatory STOP gates"
below and the standards §"STOP gate semantics (fail closed)" for the
canonical rules.

Tagging is owned by the shared
[`personal-plan-tag-tiers`](../personal-plan-tag-tiers/SKILL.md) skill. If a
plan is not yet tagged, run that skill to tag every executable step, then come
back. This skill owns everything downstream of tagging: it applies the
no-thrash **wave-grouping** pass itself (grouping consecutive same-tier steps
into waves and folding short `[fast]` runs into adjacent `[exec]` waves
**without rewriting any tags**), writes the **active** Kickoff variant in its
own step 4 below, runs its own ask-and-branch in steps 5–6, and dispatches
`Task` subagents at wave boundaries instead of emitting STOP markers. The
orchestrator never halts on a tier transition and never re-tags a step to
avoid a model swap — folding changes the wave's execution tier, not the tag.

(The passive [`personal-plan-model-tiers`](../personal-plan-model-tiers/SKILL.md)
sibling does the same wave grouping but emits STOP markers for a human-driven
model swap; use it instead when you're not on Cursor or want to drive each
swap yourself.)

Canonical reference for tier definitions, the `[fast]` downgrade checklist,
tag placement, the no-thrash rule, the model picker (Cursor + Claude Code
+ thinking levels), the Kickoff template, token lines, expected cost, and
the Cost table lives in:

> `../personal-standards/standards/plan-execution.md` §"Model-tier stop
> points"

Read that section first when in doubt. This file does not duplicate it.

## Orchestrator-parent invariant

The orchestrator-parent **always runs at `[deep]` /
`claude-opus-5-5[effort=high]`**. Tagging decisions, subagent-summary
review, re-tagging on failure, and the gate-2/3 architectural review of
cheaper-tier output are all `[deep]` work; weakening the orchestrator caps
review quality at the level of the work being reviewed. The Kickoff block
written in step 4 hardcodes Opus for the same reason.

- `[xdeep]` waves go to a max-effort Opus subagent; the parent stays on
  Opus high. The parent's job (dispatch, gates, summary review) is
  `[deep]` work, and max effort on every summary it reads is waste.
  Reviews of `[xdeep]` waves are the exception; see step 12.
- Cursor has no ultracode equivalent, so an orchestrated `[xdeep]` wave
  gets max effort without ultracode's multi-agent fan-out. When a wave
  needs that, run it through `personal-plan-model-tiers` in Claude Code
  instead.
- Want a cheaper supervisor on a mostly-mechanical plan? Use
  [`personal-plan-model-tiers`](../personal-plan-model-tiers/SKILL.md)
  instead and let the human drive the model swaps. Same tagging, no opus
  parent.

## Harness gate — verify before proceeding

This skill assumes **Cursor's `Task` tool with a per-invocation `model`
parameter** and the Cursor slugs from the standards model picker:

- `[xdeep]`: `claude-opus-5-5[effort=max]` (alt: `claude-fable-5-1[effort=max]`)
- `[deep]` and the parent: `claude-opus-5-5[effort=high]`
- `[exec]`: `grok-4-7[effort=high]` (alt: `claude-sonnet-5-5[effort=high]`)
- `[fast]`: `composer-2.5[fast=false]`

**Default for Cursor: proceed.** Inspect your tool list. If you see a
`Task` tool whose `model` parameter accepts these slugs, or takes a
free-form model string, assume it works and continue. The schema is
sufficient evidence; you do not need explicit user confirmation, and you
do not need to verify the parameter "actually takes effect" beyond the
schema.

**Bracket parameters.** The `[effort=...]` and `[fast=false]` forms come
from Cursor's subagent docs, which don't list the `Task` enum. If the enum
offers plain or suffixed IDs instead, dispatch the entry for the same model
at the same (or nearest) effort, and tell the user to refresh the standards
model picker. If the only Composer entry is Fast, use it, name its token
lines' model `composer-2.5 Fast`, and price them at the Fast row of the
Model price table (6× standard on input and output, 2.5× on cache reads).

**Use the newest version of each family.** Cursor has no version-less
alias, so the slugs above go stale. If the enum offers a newer entry of the
same family at the same effort, dispatch that one instead, and tell the
user to refresh the standards model picker. Missing the exact listed slug
is not a reason to STOP when a newer entry of the same family is present.

Only STOP and ask the user when one of these is true:

- `Task` is absent from your tool list entirely.
- `Task` is present but has no `model` parameter, or its enum is missing
  Opus, Composer, or both Grok and Sonnet. (A missing Fable entry only
  removes the `[xdeep]` alt; a missing max-effort Opus entry is handled in
  step 8.)
- You can tell you are running on **Claude Code**. Its subagent tool is
  `Agent` (renamed from `Task` in 2.1.63; `Task` still works as an alias).
  It accepts `model` on paper, but
  [anthropics/claude-code#43869](https://github.com/anthropics/claude-code/issues/43869)
  reports it is silently ignored; subagents inherit the parent model.
  Recommend `personal-plan-model-tiers` with `/model` swaps instead. (Once
  that is fixed, dispatch with the version-less aliases `opus`, `sonnet`,
  and `haiku`, which always resolve to the newest model of the tier, rather
  than pinned slugs.)
- You can tell you are running on **Codex CLI**, **Gemini CLI**, **Muse
  Code**, or **Grok Build**. Codex custom agents (`.codex/agents/*.toml`),
  Gemini CLI agents (`.gemini/agents/*.md`), and Grok Build's
  `[subagents.models]` can each pin a model per subagent definition, but
  this skill is written against Cursor's `Task` and doesn't drive them.
  Recommend `personal-plan-model-tiers`.

When you do STOP, surface the specific concern, recommend the fallback,
and wait for explicit confirmation before proceeding. Otherwise, continue
to the Procedure section.

## Tier vocabulary and model picker — by reference

The `[xdeep]` / `[deep]` / `[exec]` / `[fast]` definitions, default-up bias,
`[fast]` downgrade checklist, `[xdeep]` upgrade checklist, tag placement rule, no-thrash rule, and the Cursor /
Claude Code model picker live in the standards section above. Cursor picks
for orchestrator subagents, repeated here for reading clarity only:

- `[xdeep]` subagent (after gate 7): `claude-opus-5-5[effort=max]`; alt
  `claude-fable-5-1[effort=max]` only as a different-model second opinion
  after Opus max has already failed the step
- `[deep]` subagent or parent: `claude-opus-5-5[effort=high]`
- `[exec]` subagent (default for delegated work): `grok-4-7[effort=high]`,
  or `claude-sonnet-5-5[effort=high]` once included Cursor-pool usage runs
  out (see the standards model picker notes)
- `[fast]` subagent (only when no-thrash criterion met): `composer-2.5[fast=false]`

`[xdeep]` maps to Opus max because Opus 5.5 beats Fable 5.1 on every
benchmark Anthropic published, at 40% of the per-token price. Revisit when
the next Fable ships. If the standards section and this list disagree, the
standards section wins.

**Step-up on subagent failure**: composer → the `[exec]` model (grok, or
sonnet) → opus high → opus max as `[xdeep]`; fable is the different-model
alt after that. Stepping up to opus usually means the step was
mistagged; STOP, re-tag as `[deep]`, and
dispatch an opus subagent for the re-attempt — the orchestrator-parent
never executes plan work inline (see STOP gates below). Stepping up from
opus high to opus max is the first condition of the `[xdeep]` upgrade
checklist (a `[deep]` attempt already failed): re-tag as `[xdeep]` and pass
gates 6 and 7 before dispatching. If opus max fails too, a fable
re-attempt (the different-model alt) also goes through gates 6 and 7.

## Parallel-eligibility rule — one subagent per git working directory

Tasks are parallel-eligible **if and only if** they target distinct git
working directories. Distinct working directory = separate repository, or a
`git worktree` of the same repo. Within one working directory: serial. No
file-set prediction, no forbid-list, no DAG dependency classification —
git's worktree isolation does the work.

Users opt into within-repo parallelism by creating worktrees explicitly
(Cursor's `/worktree` slash command, or `git worktree add`) **before**
invoking this skill. If the current group spans only one working directory,
dispatch one subagent and continue.

### Worked Cursor example — 2-repo `[exec]` wave

A plan spans two repos. The next `[exec]` group has steps `m2 s1-s3` in
repo A and `m2 s4-s6` in repo B. Both target distinct working directories,
so they can run in parallel.

**Issue these as real `Task` tool calls, not text in chat.** Send a single
assistant message that invokes the `Task` tool twice (one invocation per
working directory). Do not paste the calls into the chat as a code block
for the user to run; do not ask the user to dispatch them. Each call
takes:

- `description` — the subagent's **title** in the Cursor agents list. Use
  the canonical [Wave title format](../personal-standards/standards/plan-execution.md#wave-title-format)
  `Wave {n} of {t} [{tier}] {group-id}` (e.g.
  `Wave 2 of 3 [exec] repo-A m2 s1-s3`) so each wave is scannable at a glance.
  `{n}` is the 1-based wave number (the same `{wave-n}` used in the
  compaction policy above), `{t}` is the total wave count (the `N` from the
  Kickoff `Status:` line), `{tier}` is the wave's execution tier, and
  `{group-id}` is the working-directory-scoped group identifier (repo or
  worktree name + step IDs, e.g. `repo-B m2 s4-s6` for the sibling
  parallel call). This title is fixed at spawn — Cursor exposes no
  supported way to update a subagent's title after dispatch.
- `subagent_type` — `"generalPurpose"` for these waves.
- `model` — the slug from the model picker
  (`"grok-4-7[effort=high]"` for `[exec]`).
- `prompt` — the full subagent prompt assembled per the
  "Subagent context contract" below, scoped to that working directory.

The `Task(...)` shapes shown elsewhere in this file are illustrative
pseudocode for humans reading the doc — they describe what the actual
tool calls must contain, not text to print.

After both return, collect their summaries, drop full outputs (already on
disk per the compaction policy), and advance to the next boundary.

### Worked Cursor example — 2-repo `[deep]` wave

A plan spans two repos. The next group is a `[deep]` wave: an architectural
decision in repo A and a sibling decision in repo B. The orchestrator-parent
**does not** take either inline; both go out as opus subagents in parallel.

Issue these as real `Task` tool calls in a single assistant message — two
invocations of `Task`, both with `model="claude-opus-5-5[effort=high]"`,
one scoped to each working directory. The subagent context contract still
applies: quote the spec excerpt verbatim, pass the full standards-pointer
set (architecture work, do not skimp), and include the disk-backed output
contract.

After both return, the orchestrator reviews their summaries, re-reading
artifacts only when needed, and advances. The parent's context never
holds the diffs or full reasoning of either deep wave — just the
structured summaries — even though both ran on the same opus model the
parent does. This is the always-dispatch invariant in action: the
orchestrator-parent is a supervisor, not an executor, regardless of tier.

## Context-compaction policy — per-subagent disk-backed artifacts

Every subagent prompt **must** end with:

> Write your full output (diffs, decisions, surprises, follow-ups) to
> `.scratch/orchestrate-{plan-name}-{wave-n}-{task-id}.md`. Return only a
> structured 1-paragraph summary covering: what changed, what was decided,
> any surprises, and the artifact path.

Substitute:

- `{plan-name}` — the base name of the plan file (no `.md`, no path).
- `{wave-n}` — the wave's number from its `--- WAVE` marker, starting at
  `1`: `N-fix` for a fix-up wave for wave N (standards §"Wave annotation
  format"). A retry reuses its wave's number in token lines, but its
  artifact adds `-retry{k}` (`…-2-retry1-m2-s1-s3.md`) so the failed
  attempt's output survives for gates 1 and 6.
- `{task-id}` — the heading ID(s) from the plan, e.g. `m2-s1-s3`, or a
  short kebab-case slug derived from the title if there are no IDs.

The orchestrator's own context holds only: subagent summaries, the active
plan section (current group + next), and a rolling "state so far" updated
at every STOP gate. Re-read artifacts only when needed. Artifacts under
`.scratch/` are gitignored and ephemeral, on a runner too: there only the
plan and the handoff survive, in `specs/handoffs/`, per core.md "Runner
scratch rides the branch".

## Mandatory STOP gates

Pause and hand control to the user at exactly these points. At every STOP
gate, summarize "state so far", surface the relevant decision, and wait for
explicit confirmation before continuing.

**These gates are fail-closed** — a non-answer is never approval. See
`../personal-standards/standards/plan-execution.md` §"STOP gate
semantics (fail closed)" for the canonical rules. Key points: a
background-subagent completion notification does NOT advance a pending
gate; approval is per-gate (a prior one-time "continue" is not a standing
waiver); if no explicit affirmative answer is received, re-post the exact
gate question, write `BLOCKED at gate <N>` into the Kickoff `Status:`
line, and end the turn. Never dispatch subagents while blocked.

**Gate questions are about the plan.** On a task branch, every wave is
committed by its subagents (and on a runner pushed by the parent) before
any gate asks, so a gate never asks for commit or push permission; it
names the wave's commit range so the user can review it. On a shared
branch, nothing is committed: a gate that wants the wave committed offers
that as its own choice in the same question. See standards §"STOP gate
semantics (fail closed)".

1. **Subagent error or self-reported low-quality output** — surface to the
   user; decide retry on same model, step up one tier, or re-plan.
2. **`[exec] -> [deep]` or `[exec] -> [xdeep]` boundary** — review gate. STOP so the user can
   review the just-finished `[exec]` output before any opus tokens are
   spent on the next group. After review, the orchestrator-parent
   dispatches an opus subagent for the next group (high effort for
   `[deep]`, max for `[xdeep]`); it does **not** execute that group inline.
3. **`[fast] -> [deep]` or `[fast] -> [xdeep]` boundary** — same as above.
4. **Milestone boundary** (`m{N}` → `m{N+1}`) — universal review per the
   standards section. Fires even on `[exec] -> [exec]` across a milestone
   boundary.
5. **First-subagent canary** — STOP after the **first** subagent of any
   orchestration run, regardless of outcome. Catches "orchestrator
   misunderstood the plan" or a bad subagent prompt before cascading the
   mistake.
6. **Model step-up on retry** — when retrying a failed subagent on a
   stronger model or effort, or on the Fable alt as a different-model
   second opinion (composer → the `[exec]` model, the `[exec]` model →
   opus high, opus high → opus max, or opus max → the fable alt),
   STOP first so the user confirms the budget impact and the diagnosis.
   Quote the re-attempt's expected tokens and dollars from standards
   §"Expected cost" at the target model's row, plus its review subagent
   when the re-attempt runs at `[xdeep]`; the wave's Cost table row prices
   the original model.
7. **`[xdeep]` budget gate** — STOP before every `[xdeep]` dispatch,
   including `[deep] -> [xdeep]` and `[xdeep] -> [xdeep]` across waves.
   Name the steps, the checklist condition each one met, and the wave's
   expected tokens and dollars, so the user approves `[xdeep]` spend wave
   by wave. A wave planned at `[xdeep]` quotes its Cost table row (it
   includes the wave's review subagent). A row with expected `—` (a wave
   added after kickoff) and every step-up re-attempt (opus high → opus
   max, or the Fable alt) get theirs from standards §"Expected cost" at
   the gate: the target model's row plus the review subagent, as gate 6
   quotes it. The read-only review subagent after an `[xdeep]` wave
   (step 12) is covered by that wave's gate-7 approval and does not STOP
   again. When gate 2 or 3 also fires, ask both in one question.

Deliberately **not** STOP gates: per-wave success on the same tier,
large-diff thresholds, scope drift (already enforced at the git layer by
the one-subagent-per-working-dir rule).

## Subagent context contract

Every `Task` prompt the orchestrator dispatches **must** include all eight of
these. The contract applies equally to `[deep]` and `[xdeep]` subagents — opus subagents
dispatched at `[deep] -> [deep]`, `[exec] -> [deep]`, or `[fast] -> [deep]`
boundaries are doing architecture work, so quote the spec excerpt verbatim
and pass the full set of standards pointers relevant to the work. Don't
skimp on standards just because the subagent is on the same model the
parent is.

1. **Spec excerpt** — verbatim copy of the relevant plan section. Quote,
   do not paraphrase.
2. **Working-directory scope** — the absolute path of the single git
   working directory the subagent is allowed to touch. Phrased as a hard
   limit: "All edits must be inside `<path>`. Do not edit anything
   outside this directory."
3. **Acceptance criteria** — what "done" looks like for these steps. If
   the plan section has explicit ACs, quote them; otherwise derive from
   the step titles.
4. **Hard scope limit** — the exact step IDs or titles the subagent is
   allowed to execute, plus "stop at the end of this group; do not start
   the next group or any work not listed here."
5. **Standards pointers** — the specific standards files relevant to the
   work, picked from the personal AGENTS.md "Standards Reference". Do not
   dump everything.
6. **Output contract** — the disk-backed compaction sentence above plus
   the requirement that the returned summary cover: what changed, what was
   decided, surprises, and the artifact path.
7. **Token reporting** — end your returned summary with one token line
   per model you ran on, in the format of
   `../personal-standards/standards/plan-execution.md` §"Token line
   format":
   `tokens wave-N <task-id> (<slug>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv (heuristic)`
   (`review-wave-N` for the `[xdeep]` review subagent).
   A Cursor `Task` subagent can't read its own usage, so it uses the
   accumulation heuristic from §"Token accounting — source precedence"
   (source 3): it counts its model calls, the characters it read and the
   characters it wrote, and applies the formula there. Quote that formula
   in the prompt, since the subagent may not read the standard. Compute
   `C` with the cache-aware formula and the model's rates from
   §"Model price table". Keep the `(heuristic)` label: off Claude Code
   its constants are uncalibrated, and the line can be off by 2× or more.
8. **Git instruction** — on a task branch: "Commit each finished step on
   the current branch as `m{N}.s{K} <imperative subject>`, staging only
   the paths you changed. Do not push, create, or switch branches." On a
   shared branch: "Do not commit, push, or switch branches." Spell it out
   every time. This skill runs only on Cursor today, and a `Task`
   subagent may not receive the always-on rules, so it can't be assumed
   to know them.

## Token tally

The orchestrator-parent keeps every token figure as token lines in the
format of `../personal-standards/standards/plan-execution.md` §"Token line
format", one per row, group and model, and appends each line to the plan's
`## Token log` as soon as it has it, so the tally survives a chat that ends
at a gate:

- **Subagent lines** (contract item 7), labeled `wave-N <task-id>`: one per
  working directory in a parallel wave. A step-up retry keeps its wave's
  label, so it counts in that wave's actual. The max-effort Opus review
  subagent after an `[xdeep]` wave reports its own `review-wave-N` line.
- **Orchestrator lines** for this parent: `orchestrator-kickoff` once the
  kickoff is written (step 6), then `orchestrator-wave-N` after each wave's
  review and bookkeeping (step 12). Each covers the parent's tokens since
  its previous line in this chat, gates included. Inline review work counts
  here, not as `review-wave-N` lines (contrast the passive driver's
  separate review-beat chats in `personal-plan-model-tiers`). On the
  heuristic, each uses the standards' form for part of a chat: `T0` is the
  tokens of this chat's earlier lines, and the first call after a
  subagent run or a gate wait that outlasted the 5-minute cache TTL is a
  cold start.

Cursor exposes no usage to an agent, so both kinds normally come from the
accumulation heuristic (standards §"Token accounting — source precedence",
source 3) and carry `(heuristic)`. When the user pastes Cursor usage
(source 2), it replaces the lines it covers, per standards §"Token line
format" ("Token log"): CSV rows that can't tell this parent from an Opus
subagent become one combined line. Because the orchestrator and its
subagents run on different models with different rates, **never blend
their token counts into a single cost line**: each line is priced at its
own model's list rates from the Model price table, API-equivalent,
whatever the harness bills (standards §"Model price table", "Agent costs
are API-equivalent"). The parent can recompute any line's dollars from its
four counts when a subagent omits or miscomputes them.

At every STOP gate, print the running block: the Token log lines so far,
then a total.

```
tokens so far:
  tokens orchestrator-kickoff <plan-name> (claude-opus-5-5): input ~… / cache read ~… / cache write ~… / output ~… | ~$… API-equiv (heuristic)
  tokens wave-1 m1-s1-s3 (grok-4-7): input ~… / cache read ~… / cache write ~… / output ~… | ~$… API-equiv (heuristic)
  …
  RUNNING TOTAL: input ~… / cache read ~… / cache write ~… / output ~… | ~$… API-equiv (heuristic)
```

The RUNNING TOTAL's dollars are the **sum of the lines' dollars**, not a
blended rate applied to the summed tokens. It carries `(heuristic)` when
any line does.

At plan completion, add the actual tokens and actual $ columns to the
plan's Cost table from the `## Token log`, per standards §"Cost table":
each wave row sums its `wave-N` and `review-wave-N` lines, and the
`orchestrator` row sums the `orchestrator-*` lines. Print the completed
table; the Token log keeps the per-model detail.

## Procedure

1. **Identify the plan** using the same priority order as the sibling
   skill (named path → most recent `plan-*.md` in `.scratch/` or
   `specs/handoffs/` → in-conversation plan). Remember the resolved path.
   On re-entry into a partially-executed plan, keep its Cost table as it
   stands, per the re-entry rule in standards §"Cost table".
2. **Run the harness gate** above. STOP and ask if not Cursor. Then
   **check the branch and the git email in each working directory** the
   plan touches (standards `git.md` §"Task branches and shared branches",
   core.md "Verify git email"). A runner on any branch that isn't a task
   branch cuts one without asking; a workstation on a shared branch asks
   whether to cut one before the first dispatch, since subagents commit
   (core.md "Cut a task branch off a shared branch"). Without a yes,
   orchestrate on the shared branch and tell subagents not to commit. On a
   workstation, a branch that's neither shared nor a task branch gets the
   one-time ask, also before the first dispatch. If a pasted Kickoff names
   another branch on its `On branch` line, a runner keeps its assigned
   branch and says so in its first report; a workstation proposes
   switching and waits, committing nothing until Gary answers.
3. **Tag the plan, group into waves, and write wave markers.** If the plan
   is not already tagged, run
   [`personal-plan-tag-tiers`](../personal-plan-tag-tiers/SKILL.md) to tag
   every executable step (it applies the `[fast]` downgrade checklist and
   default-up bias). Then apply the no-thrash **wave-grouping** pass: collect
   consecutive same-tier steps into execution waves and fold short `[fast]`
   runs (< 3 steps) into adjacent `[exec]` waves so they run on the `[exec]`
   model — **without rewriting any tags**. The folded steps keep their
   `[fast]` tags; only the wave's execution tier changes.

   **Validate the ≤ constraint before writing wave markers.** For each wave,
   verify that every step's tag is ≤ the wave's execution tier
   (`[xdeep]` > `[deep]` > `[exec]` > `[fast]`). If any step's tag is *greater* than its
   wave's execution tier, that is a tagging error — do not write wave markers.
   Surface the violation, halt (STOP gate 0, a pre-dispatch error), and ask
   the user to re-tag the step or widen the wave.

   Once the ≤ constraint is satisfied, **write wave markers into the plan
   file**: insert `--- WAVE N [execution-tier] ---` immediately before the
   first executable heading of each wave. Format and idempotence rules live in
   `../personal-standards/standards/plan-execution.md` §"Wave annotation
   format". Skip if wave markers already exist (re-entry).

   Do not emit STOP markers or a passive Kickoff — this skill replaces those
   with `Task` dispatch and the active Kickoff below.
4. **Write the Kickoff block to the top of the plan file** using the
   **active** variant of the Kickoff template from
   `../personal-standards/standards/plan-execution.md` §"Kickoff
   template". The model row is **always** `claude-opus-5-5[effort=high]`
   / `/model opus` + `/effort high` because the orchestrator-parent always
   runs at `[deep]` (see "Orchestrator-parent invariant" above). The prompt body
   references the resolved plan path from step 1, carries the `On branch
   <name> (task branch)` line when step 2 left a task branch, and names
   this skill (`personal-plan-orchestrate`). The Kickoff block is
   **idempotent**: if a Kickoff block already exists at the top of the
   file (any line matching `--- KICKOFF: ... ---`), replace it;
   otherwise insert above the first heading inside a fenced code block.
   A plan never carries more than one Kickoff block. Fill in the
   `Status:` line with `0/N groups done | last review: — | current:
   <first group> [deep] | updated <today>` where `N` is the total group
   count. Add `review: every-wave (log-only — parent writes Review log; no
   human review gate)`. Apart from the Cost table below, do not modify any
   other content. **Record whether you replaced an existing matching
   Kickoff block (`--- KICKOFF: begin orchestration at [deep] ---`) or
   inserted a new one — this "kickoff-replaced" signal is used in
   step 5.** Do not write any
   separate progress checklist block into the plan; the
   orchestrator-parent applies the progress updates itself in step 12, so
   no in-plan reminder is needed.

   **Write the Cost table directly below the Kickoff block** (standards
   §"Cost table"), labeled `**Cost (API-equiv, Cursor models)**`. Estimate
   each wave per standards §"Expected cost" at the Cursor slug for its
   execution tier, each `[xdeep]` row including its review subagent. Add
   an `orchestrator` row for this parent: the kickoff, the start-up after
   the default new-chat handoff, each wave, and each gate expected to wait
   on a human (the canary, plus every gate 2, 3, 4 and 7 the plan
   crosses, counting gates asked in one question once). Print the Kickoff
   block and the table in chat. On a replace, keep the table; recompute
   its expected columns only when re-grouping changed the waves before any
   wave has run, and say so. After a wave has run, a re-plan adds rows
   with expected `—` instead.

   After writing the Kickoff block, **seed the native todo list**: one
   todo per group (in order), first group `in_progress`, rest `pending`.
   Use the group identifier (e.g. `m1 s1-s3 [exec]`) as the todo content.
   See `§"Model-tier stop points" → "Progress tracking"` in the standards
   for the full convention.
5. **Ask the user where to orchestrate from** — but only when needed.

   If step 4 **replaced** an existing matching Kickoff block
   (`--- KICKOFF: begin orchestration at [deep] ---`), or the user
   message that invoked this skill explicitly identifies this chat as the
   kickoff destination, **skip this step and proceed directly to step 7.**
   The user already chose "new chat" in a prior invocation; this chat is
   that destination. The first-subagent canary STOP (gate 5) still
   applies as a safety net.

   Otherwise, ask:

   > Continue orchestrating in this chat, or hand off to a new Opus
   > chat for clean context? (default: new chat)

   Wait for the answer. Treat any non-affirmative reply (silence,
   dismissal, ambiguous answer, no response) as **new chat**. This
   question is itself a gate: if no explicit answer is received, write
   `BLOCKED at gate (kickoff-destination)` to the `Status:` line and end
   the turn. Do not dispatch subagents while blocked.
6. **Branch on the answer.** In both branches, first append this chat's
   `orchestrator-kickoff` token line to `## Token log` (see "Token
   tally").
   - **New chat (default).** Print the modified plan (with the Kickoff
     block and Cost table at the top) so the user can see it. Halt. Do
     **not** dispatch any `Task` subagents from this chat. The fresh Opus
     chat will re-invoke this skill from the top, see the existing tagging
     and Kickoff block, and begin dispatching.
   - **Current chat.** Print the modified plan, then continue to step 7.
     The first-subagent canary STOP (gate 5) still applies.
7. **Walk to the next tier boundary** from the current cursor position
   (start: top of the plan).
8. **Decide what to do at the boundary**. Note the orchestrator-parent
   **never** takes plan work inline — every row below ends in a `Task`
   dispatch (after a STOP gate where applicable):
   - `[deep] -> [exec]`, single working dir → one
     `Task(model="grok-4-7[effort=high]", ...)`.
   - `[deep] -> [exec]`, multiple working dirs → batched `Task(...)`,
     one invocation per working dir, all on the `[exec]` model.
   - `[deep] -> [fast]`, no-thrash satisfied (≥ 3 contiguous fast) →
     `Task(model="composer-2.5[fast=false]", ...)`, one per working dir.
   - `[deep] -> [fast]`, no-thrash failed (< 3 fast) → the fast run was
     folded into the adjacent `[exec]` wave (its `[fast]` tags stay in the
     plan); treat as the `[deep] -> [exec]` row.
   - `[exec] -> [fast]` → same no-thrash logic: ≥ 3 fast dispatches a
     `composer-2.5[fast=false]` wave; < 3 folds into the `[exec]` wave, tags
     unchanged.
   - `[exec] -> [deep]` or `[fast] -> [deep]` → STOP (gate 2/3) for the
     user to review the just-finished cheaper-tier output. Fail-closed:
     if no explicit answer is received, re-post the review question,
     write `BLOCKED at gate 2` (or `3`) to the `Status:` line, and end
     the turn. **Then dispatch** `Task(model="claude-opus-5-5[effort=high]", ...)`, one
     per working directory. The parent does not execute the next group
     itself.
   - **Any boundary into `[xdeep]`** → STOP (gate 7, plus gate 2/3 when
     coming from `[exec]`/`[fast]`). Fail-closed: if no explicit answer is
     received, write `BLOCKED at gate 7` to the `Status:` line and end the
     turn. Then dispatch `Task(model=<[xdeep] Cursor slug>, ...)`
     (`claude-opus-5-5[effort=max]` today), one per working directory. If
     the `Task` enum has no max-effort Opus entry, dispatch the
     highest-effort Opus entry and tell the user. Dispatch the Fable alt
     only on a gate-6 step-up after Opus max has already failed the step.
   - **Leaving `[xdeep]`** → same rows as leaving `[deep]`.
   - `[deep] -> [deep]` → dispatch
     `Task(model="claude-opus-5-5[effort=high]", ...)`, one per working
     directory. Always dispatch, even on a single working dir; the
     parent's context never holds the diffs or full reasoning of a deep
     wave.
   - **Milestone boundary** crossed mid-walk → STOP (gate 4) before the
     next dispatch. Fail-closed: if no explicit answer is received,
     re-post the milestone review question, write `BLOCKED at gate 4` to
     the `Status:` line, and end the turn.
9. **Build each subagent prompt** per the "Subagent context contract"
   above.
10. **Dispatch**. Issue actual `Task` tool calls — do not print them in
    chat as text or pseudocode for the user to run. For parallel-eligible
    groups, batch all the `Task` calls into a single assistant message
    (one tool invocation per working directory).
11. **First-subagent canary** — STOP after the first subagent of the run
    regardless of outcome (gate 5). Fail-closed: if no explicit answer
    is received, re-post the canary review question, write
    `BLOCKED at gate 5` to the `Status:` line, and end the turn. Do not
    dispatch the next subagent while blocked. A background-subagent
    completion notification does NOT count as an answer to the canary
    question.
12. **Collect summaries**. Update "state so far". Re-read artifacts only
    when needed. Append each subagent's token lines (contract item 7) to
    `## Token log`; include the running block (see "Token tally") in the
    "state so far" update.

    After each successful wave, **update plan state**:
    - Append ` (done)` to every executable heading in the just-finished
      group in the plan file.
    - Flip that group's native todo to `completed`; mark the next group
      `in_progress`.
    - Update the `Status:` line in the Kickoff block: increment the done
      count, set `current:` to the next group's identifier, refresh
      `last review: wave-N PASS|CONCERNS` from the review below, and
      refresh the date.
    - **Review log (log-only).** As part of the same step, review each
      returned subagent summary against the plan spec (read artifacts when
      needed). Append one line to `## Review log` in the plan file (create
      the section if absent) using the grammar from standards §"Review log":
      `review wave-N (<group-id>) <from>..<to>: PASS|CONCERNS - <one-line
      note> - <YYYY-MM-DD>`. This is orchestrate's **log-only** participation in
      the [review beat](../personal-standards/standards/plan-execution.md) —
      it adds **no human STOP gate** beyond gates 1–7. Review
      tokens count in this parent's `orchestrator-wave-N` token line, not
      a separate `review-wave-N` line. **Exception: an `[xdeep]` wave** is
      reviewed by a read-only max-effort Opus subagent
      (`Task(model=<[xdeep] Cursor slug>, ...)`), not inline, because the
      high-effort parent would cap the review at `[deep]`. The parent
      writes that subagent's verdict to the Review log and appends its
      `review-wave-N` token line to `## Token log`.
    - **Commit and push (task branch).** After the review, whatever the
      verdict, commit the plan file if it's tracked (on a runner, in
      `specs/handoffs/`). A runner then pushes each working directory's
      branch; a workstation pushes at will. A `CONCERNS` verdict adds a
      fix-up wave on top; it never rewrites the wave's commits. The
      fix-up wave is numbered `N-fix` and gets its own Cost table row with
      expected `—` (standards §"Cost table").
    - **Token log.** Append this parent's `orchestrator-wave-N` token
      line for the wave (see "Token tally").
13. **Handle errors / low-quality output** — STOP (gate 1) and offer
    retry / step-up / re-plan. Fail-closed: if no explicit answer is
    received, re-post the error gate question, write `BLOCKED at gate 1`
    to the `Status:` line, and end the turn. Stepping up tiers triggers
    gate 6, and the re-attempt itself is **dispatched** as a subagent on
    the next model in the step-up chain — composer → `[exec]` model → opus
    high → opus max, then the fable alt — never executed inline. The
    re-attempt's token lines keep the wave's `wave-N` label. A re-plan's
    new waves get Cost table rows with expected `—`, and a wave it drops
    keeps its row.
14. **Advance** to the next boundary. Repeat from step 7 until the plan
    is complete, stopping at every gate. When the plan is complete, add
    the actual columns to the Cost table and print it, as the "Token
    tally" section above says.

    When the **last group finishes** and its review passes, perform the
    final-completion steps from `§"Model-tier stop points" → "Progress
    tracking" → "Final completion"` in the standards: flip all remaining
    todos to `completed`, replace the Kickoff marker with
    `--- KICKOFF: plan complete ---`, update the Status line to
    `N/N groups done | completed <date>`, add the Cost table's actual
    columns, and append the Completion summary at the bottom of the plan
    file. Print this summary alongside the completed Cost table.

## Out of scope

- The orchestrator-parent never edits source code, runs tests, or
  produces diffs in its own context. If you find yourself doing plan
  work directly, dispatch a `Task` subagent for the current group
  instead. The orchestrator's job is tagging, dispatching, reviewing
  summaries, and advancing — nothing else. Committing the plan file and
  pushing the task branch are bookkeeping, not plan work.
- Auto-executing `Task` calls without user approval at the gates above.
- Running this skill on Claude Code. Flip the harness gate once
  [anthropics/claude-code#43869](https://github.com/anthropics/claude-code/issues/43869)
  closes, and use the version-less `opus` / `sonnet` / `haiku` aliases for
  the `model` parameter there.
- Merging with `personal-plan-model-tiers`. The passive-vs-active split is
  intentional; users pick oversight level by picking which skill they
  invoke.
