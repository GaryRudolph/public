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

Canonical reference for tier definitions, the `[fast]` downgrade checklist,
tag placement, the no-thrash rule, and the model picker (Cursor + Claude
Code + thinking levels) lives in:

> `~/Projects/personal/public/standards/documentation.md` §"Model-tier stop
> points"

Read that section first when in doubt. This file does not duplicate it.

## Harness gate — verify before proceeding

This skill assumes **Cursor's `Task` tool with a per-invocation `model`
parameter** and the documented Cursor model slugs:

- `claude-opus-4-7-thinking-xhigh`
- `claude-4.6-sonnet-medium-thinking`
- `composer-2.5-fast`

Before doing anything else, self-check your available tool list. If `Task`
with a per-invocation `model` parameter is missing — or you cannot tell —
**STOP and ask the user** whether to proceed anyway (with the relevant
caveat) or fall back to `personal-plan-model-tiers`. Surface the specific
concern:

- **Claude Code** — `Task` accepts a `model` parameter on paper, but
  [anthropics/claude-code#43869](https://github.com/anthropics/claude-code/issues/43869)
  reports it is silently ignored; subagents inherit the parent model. The
  orchestrator pattern is unreliable until that bug closes. Use
  `personal-plan-model-tiers` with `/model` swaps instead.
- **Codex CLI / Gemini CLI** — no subagent tool with per-invocation model
  selection. Use `personal-plan-model-tiers`.
- **Unknown harness** — you cannot verify the `Task` affordances. Default
  to the safer `personal-plan-model-tiers` unless the user overrides.

Wait for explicit user confirmation before proceeding when the gate is not
clean. Do not auto-detect; ask.

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
take it inline (see STOP gates below).

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
so they can run in parallel. Emit a single message with two `Task`
invocations:

```
Task(
  description="repo-A m2 s1-s3",
  subagent_type="generalPurpose",
  model="claude-4.6-sonnet-medium-thinking",
  prompt=<<<see "Subagent context contract" below — repo-A-scoped>>>,
)

Task(
  description="repo-B m2 s4-s6",
  subagent_type="generalPurpose",
  model="claude-4.6-sonnet-medium-thinking",
  prompt=<<<see "Subagent context contract" below — repo-B-scoped>>>,
)
```

After both return, collect their summaries, drop full outputs (already on
disk per the compaction policy), and advance to the next boundary.

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
2. **`[exec] -> [deep]` boundary** — the parent is already on the deep
   model; it takes over the next group inline rather than delegating. STOP
   first so the user can review the just-finished `[exec]` output.
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
these:

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

## Procedure

1. **Identify the plan** using the same priority order as the sibling
   skill (named path → most recent `.scratch/plan-*.md` → in-conversation
   plan). Remember the resolved path.
2. **Run the harness gate** above. STOP and ask if not Cursor.
3. **Tag the plan** per `personal-plan-model-tiers` if it is not already
   tagged. Apply the `[fast]` downgrade checklist and the no-thrash rule.
4. **Walk to the next tier boundary** from the current cursor position
   (start: top of the plan).
5. **Decide what to do at the boundary**:
   - `[deep] -> [exec]`, single working dir → one `Task(model="claude-4.6-sonnet-medium-thinking", ...)`.
   - `[deep] -> [exec]`, multiple working dirs → batched `Task(...)`, one
     invocation per working dir, all on sonnet-medium.
   - `[deep] -> [fast]`, no-thrash satisfied → `Task(model="composer-2.5-fast", ...)`,
     one per working dir.
   - `[deep] -> [fast]`, no-thrash failed → already promoted to `[exec]`;
     treat as the `[deep] -> [exec]` row.
   - `[exec] -> [fast]` → same no-thrash logic.
   - `[exec] -> [deep]` or `[fast] -> [deep]` → STOP (gate 2/3); parent
     takes the next group inline.
   - `[deep] -> [deep]` focused subagent (optional) — dispatch
     `Task(model="claude-opus-4-7-thinking-xhigh", ...)` only when
     isolation from the parent's context is worth the round trip;
     otherwise inline.
   - **Milestone boundary** crossed mid-walk → STOP (gate 4) before the
     next dispatch.
6. **Build each subagent prompt** per the "Subagent context contract"
   above.
7. **Dispatch**. For parallel-eligible groups, batch all the `Task` calls
   into a single message.
8. **First-subagent canary** — STOP after the first subagent of the run
   regardless of outcome (gate 5).
9. **Collect summaries**. Update "state so far". Re-read artifacts only
   when needed.
10. **Handle errors / low-quality output** — STOP (gate 1) and offer
    retry / step-up / re-plan. Stepping up triggers gate 6.
11. **Advance** to the next boundary. Repeat from step 4 until the plan
    is complete, stopping at every gate.

## Out of scope

- Auto-executing `Task` calls without user approval at the gates above.
- Re-enabling this skill on Claude Code. Flip the harness gate once
  [anthropics/claude-code#43869](https://github.com/anthropics/claude-code/issues/43869)
  closes.
- Merging with `personal-plan-model-tiers`. The passive-vs-active split is
  intentional; users pick oversight level by picking which skill they
  invoke.
