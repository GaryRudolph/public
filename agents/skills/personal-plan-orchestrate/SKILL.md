---
name: personal-plan-orchestrate
description: >-
  Actively orchestrate a tiered plan by delegating each `[exec]` or `[fast]`
  group to a Cursor `Task` subagent on the right model, while the `[deep]`
  parent retains overall control. Same `[deep]` / `[exec]` / `[fast]` tagging
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
The passive skill inserts STOP markers and waits for the human to swap
models or paste handoff prompts at every tier boundary. This skill does the
same tagging but, where the passive skill would emit a STOP, **delegates
the next group to a Cursor `Task` subagent on the right model and
continues** — pausing only at the mandatory STOP gates listed below.

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

Canonical reference for tier definitions, the `[fast]` downgrade checklist,
tag placement, the no-thrash rule, the model picker (Cursor + Claude Code
+ thinking levels), and the Kickoff template lives in:

> `~/Projects/personal/public/standards/documentation.md` §"Model-tier stop
> points"

Read that section first when in doubt. This file does not duplicate it.

## Orchestrator-parent invariant

The orchestrator-parent **always runs at `[deep]` /
`claude-opus-4-7-thinking-xhigh`**. Tagging decisions, subagent-summary
review, re-tagging on failure, and the gate-2/3 architectural review of
cheaper-tier output are all `[deep]` work; weakening the orchestrator caps
review quality at the level of the work being reviewed. The Kickoff block
written in step 4 hardcodes Opus xhigh for the same reason.

- Want a cheaper supervisor on a mostly-mechanical plan? Use
  [`personal-plan-model-tiers`](../personal-plan-model-tiers/SKILL.md)
  instead and let the human drive the model swaps. Same tagging, no opus
  parent.

## Harness gate — verify before proceeding

This skill assumes **Cursor's `Task` tool with a per-invocation `model`
parameter** and the documented Cursor model slugs:

- `claude-opus-4-7-thinking-xhigh`
- `claude-4.6-sonnet-medium-thinking`
- `composer-2.5-fast`

**Default for Cursor: proceed.** Inspect your tool list. If you see a
`Task` tool whose `model` parameter accepts the slugs above — a quick
check is that the schema enumerates `claude-opus-4-7-thinking-xhigh`,
`claude-4.6-sonnet-medium-thinking`, and `composer-2.5-fast` — assume it
works and continue. The schema is sufficient evidence; you do not need
explicit user confirmation, and you do not need to verify the parameter
"actually takes effect" beyond the schema.

Only STOP and ask the user when one of these is true:

- `Task` is absent from your tool list entirely.
- `Task` is present but has no `model` parameter, or the slugs above are
  not in its accepted enum.
- You can tell you are running on **Claude Code**. `Task` there accepts
  `model` on paper, but
  [anthropics/claude-code#43869](https://github.com/anthropics/claude-code/issues/43869)
  reports it is silently ignored; subagents inherit the parent model.
  Recommend `personal-plan-model-tiers` with `/model` swaps instead.
- You can tell you are running on **Codex CLI** or **Gemini CLI**. No
  subagent tool with per-invocation model selection exists there.
  Recommend `personal-plan-model-tiers`.

When you do STOP, surface the specific concern, recommend the fallback,
and wait for explicit confirmation before proceeding. Otherwise, continue
to the Procedure section.

## Tier vocabulary and model picker — by reference

The `[deep]` / `[exec]` / `[fast]` definitions, default-up bias, `[fast]`
downgrade checklist, tag placement rule, no-thrash rule, and the Cursor /
Claude Code model picker live in the standards section above. Cursor picks
for orchestrator subagents, repeated here for reading clarity only:

- `[deep]` subagent or parent: `claude-opus-4-7-thinking-xhigh`
- `[exec]` subagent (default for delegated work): `claude-4.6-sonnet-medium-thinking`
- `[fast]` subagent (only when no-thrash criterion met): `composer-2.5-fast`

If the standards section and this list disagree, the standards section
wins.

**Step-up on subagent failure**: composer → sonnet → opus. Stepping up to
opus usually means the step was mistagged; STOP, re-tag as `[deep]`, and
dispatch an opus subagent for the re-attempt — the orchestrator-parent
never executes plan work inline (see STOP gates below).

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

- `description` — short title (e.g. `"repo-A m2 s1-s3"`).
- `subagent_type` — `"generalPurpose"` for these waves.
- `model` — the slug from the model picker
  (`"claude-4.6-sonnet-medium-thinking"` for `[exec]`).
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
invocations of `Task`, both with `model="claude-opus-4-7-thinking-xhigh"`,
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
- `{wave-n}` — monotonic counter of orchestrator waves starting at `1`.
- `{task-id}` — the heading ID(s) from the plan, e.g. `m2-s1-s3`, or a
  short kebab-case slug derived from the title if there are no IDs.

The orchestrator's own context holds only: subagent summaries, the active
plan section (current group + next), and a rolling "state so far" updated
at every STOP gate. Re-read artifacts only when needed. Artifacts under
`.scratch/` are gitignored and ephemeral.

## Mandatory STOP gates

Pause and hand control to the user at exactly these points. At every STOP
gate, summarize "state so far", surface the relevant decision, and wait for
explicit confirmation before continuing.

1. **Subagent error or self-reported low-quality output** — surface to the
   user; decide retry on same model, step up one tier, or re-plan.
2. **`[exec] -> [deep]` boundary** — review gate. STOP so the user can
   review the just-finished `[exec]` output before any opus tokens are
   spent on the next group. After review, the orchestrator-parent
   dispatches an opus subagent for the next `[deep]` group; it does
   **not** execute that group inline.
3. **`[fast] -> [deep]` boundary** — same as above.
4. **Milestone boundary** (`m{N}` → `m{N+1}`) — universal review per the
   standards section. Fires even on `[exec] -> [exec]` across a milestone
   boundary.
5. **First-subagent canary** — STOP after the **first** subagent of any
   orchestration run, regardless of outcome. Catches "orchestrator
   misunderstood the plan" or a bad subagent prompt before cascading the
   mistake.
6. **Model step-up on retry** — when retrying a failed subagent on a
   stronger model (composer → sonnet, or sonnet → opus), STOP first so the
   user confirms the budget impact and the diagnosis.

Deliberately **not** STOP gates: per-wave success on the same tier,
large-diff thresholds, scope drift (already enforced at the git layer by
the one-subagent-per-working-dir rule).

## Subagent context contract

Every `Task` prompt the orchestrator dispatches **must** include all six of
these. The contract applies equally to `[deep]` subagents — opus subagents
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
7. **Token reporting** — end your returned summary with one line:
   `tokens: input ~X / output ~Y / total ~Z / model <slug> (heuristic)`,
   where X and Y use `~tokens ≈ chars / 4`. Count input chars as
   everything you read (prompts, file reads, tool outputs); count output
   chars as everything you wrote (chat text, tool call arguments, file
   writes). Flag the numbers as estimates.

## Token tally

The orchestrator-parent maintains a running token tally across the run using
the same `~tokens ≈ chars / 4` heuristic. At every STOP gate, print a
one-line running total:

```
tokens so far: input ~X / output ~Y / total ~Z (heuristic)
```

At plan completion, print a per-wave breakdown table:

| wave | model | ~input | ~output | ~total |
|------|-------|--------|---------|--------|
| orchestrator | claude-opus-4-7-thinking-xhigh | … | … | … |
| wave-1 (task-id) | <slug> | … | … | … |
| … | | | | |
| **GRAND TOTAL** | | | | |

All numbers are heuristic estimates (~±15%). They are not authoritative
usage data.

## Procedure

1. **Identify the plan** using the same priority order as the sibling
   skill (named path → most recent `.scratch/plan-*.md` → in-conversation
   plan). Remember the resolved path.
2. **Run the harness gate** above. STOP and ask if not Cursor.
3. **Tag the plan** by running **only steps 1–3** of
   `personal-plan-model-tiers` if it is not already tagged: identify the
   plan, tag every executable step, apply the `[fast]` downgrade checklist
   and the no-thrash rule. **Do not** run that skill's steps 4–7 (insert
   STOP markers, write the passive Kickoff, ask user, branch) — this
   skill replaces all of those.
4. **Write the Kickoff block to the top of the plan file** using the
   **active** variant of the Kickoff template from
   `~/Projects/personal/public/standards/documentation.md` §"Kickoff
   template". The model row is **always** `claude-opus-4-7-thinking-xhigh`
   / `/model opus` xhigh because the orchestrator-parent always runs at
   `[deep]` (see "Orchestrator-parent invariant" above). The prompt body
   references the resolved plan filename from step 1 and names this
   skill (`personal-plan-orchestrate`). The Kickoff block is
   **idempotent**: if a Kickoff block already exists at the top of the
   file (any line matching `--- KICKOFF: ... ---`), replace it;
   otherwise insert above the first heading inside a fenced code block.
   A plan never carries more than one Kickoff block. Do not modify any
   other content. **Record whether step 4 replaced an existing matching
   Kickoff block (`--- KICKOFF: begin orchestration at [deep] ---`) or
   inserted a new one — this "kickoff-replaced" signal is used in
   step 5.**
5. **Ask the user where to orchestrate from** — but only when needed.

   If step 4 **replaced** an existing matching Kickoff block
   (`--- KICKOFF: begin orchestration at [deep] ---`), or the user
   message that invoked this skill explicitly identifies this chat as the
   kickoff destination, **skip this step and proceed directly to step 7.**
   The user already chose "new chat" in a prior invocation; this chat is
   that destination. The first-subagent canary STOP (gate 5) still
   applies as a safety net.

   Otherwise, ask:

   > Continue orchestrating in this chat, or hand off to a new Opus xhigh
   > chat for clean context? (default: new chat)

   Wait for the answer. Treat any non-affirmative reply (silence,
   dismissal, ambiguous answer, no response) as **new chat**.
6. **Branch on the answer.**
   - **New chat (default).** Print the modified plan (with the Kickoff
     block at the top) so the user can see it. Halt. Do **not** dispatch
     any `Task` subagents from this chat. The fresh Opus chat will
     re-invoke this skill from the top, see the existing tagging and
     Kickoff block, and begin dispatching.
   - **Current chat.** Print the modified plan, then continue to step 7.
     The first-subagent canary STOP (gate 5) still applies.
7. **Walk to the next tier boundary** from the current cursor position
   (start: top of the plan).
8. **Decide what to do at the boundary**. Note the orchestrator-parent
   **never** takes plan work inline — every row below ends in a `Task`
   dispatch (after a STOP gate where applicable):
   - `[deep] -> [exec]`, single working dir → one
     `Task(model="claude-4.6-sonnet-medium-thinking", ...)`.
   - `[deep] -> [exec]`, multiple working dirs → batched `Task(...)`,
     one invocation per working dir, all on sonnet-medium.
   - `[deep] -> [fast]`, no-thrash satisfied →
     `Task(model="composer-2.5-fast", ...)`, one per working dir.
   - `[deep] -> [fast]`, no-thrash failed → already promoted to `[exec]`;
     treat as the `[deep] -> [exec]` row.
   - `[exec] -> [fast]` → same no-thrash logic.
   - `[exec] -> [deep]` or `[fast] -> [deep]` → STOP (gate 2/3) for the
     user to review the just-finished cheaper-tier output. **Then
     dispatch** `Task(model="claude-opus-4-7-thinking-xhigh", ...)`, one
     per working directory. The parent does not execute the next group
     itself.
   - `[deep] -> [deep]` → dispatch
     `Task(model="claude-opus-4-7-thinking-xhigh", ...)`, one per working
     directory. Always dispatch, even on a single working dir; the
     parent's context never holds the diffs or full reasoning of a deep
     wave.
   - **Milestone boundary** crossed mid-walk → STOP (gate 4) before the
     next dispatch.
9. **Build each subagent prompt** per the "Subagent context contract"
   above.
10. **Dispatch**. Issue actual `Task` tool calls — do not print them in
    chat as text or pseudocode for the user to run. For parallel-eligible
    groups, batch all the `Task` calls into a single assistant message
    (one tool invocation per working directory).
11. **First-subagent canary** — STOP after the first subagent of the run
    regardless of outcome (gate 5).
12. **Collect summaries**. Update "state so far". Re-read artifacts only
    when needed. Parse the `tokens:` line from each subagent summary
    into the rolling tally; include the running tally in the "state so
    far" update.
13. **Handle errors / low-quality output** — STOP (gate 1) and offer
    retry / step-up / re-plan. Stepping up tiers triggers gate 6, and
    the re-attempt itself is **dispatched** as a subagent on the higher
    tier's model — composer → sonnet, sonnet → opus — never executed
    inline.
14. **Advance** to the next boundary. Repeat from step 7 until the plan
    is complete, stopping at every gate. When the plan is complete,
    print the final per-wave + orchestrator + grand-total token table
    from the "Token tally" section above.

## Out of scope

- The orchestrator-parent never edits source code, runs tests, or
  produces diffs in its own context. If you find yourself doing plan
  work directly, dispatch a `Task` subagent for the current group
  instead. The orchestrator's job is tagging, dispatching, reviewing
  summaries, and advancing — nothing else.
- Auto-executing `Task` calls without user approval at the gates above.
- Re-enabling this skill on Claude Code. Flip the harness gate once
  [anthropics/claude-code#43869](https://github.com/anthropics/claude-code/issues/43869)
  closes.
- Merging with `personal-plan-model-tiers`. The passive-vs-active split is
  intentional; users pick oversight level by picking which skill they
  invoke.
