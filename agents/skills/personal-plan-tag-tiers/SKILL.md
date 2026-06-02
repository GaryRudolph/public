---
name: personal-plan-tag-tiers
description: >-
  Tag every executable step in a plan as [deep], [exec], or [fast] so you can
  see how complex the work actually is before deciding how to run it. This is
  the shared tagging layer: it only tags — it does not group steps into waves,
  apply the no-thrash rule, insert STOP markers, write Kickoff blocks, or
  execute anything. Tags reflect honest complexity and are never rewritten for
  thrash reasons. Use when the user asks to "tag the tiers", "tag deep / exec /
  fast", "show how complex this plan is", or wants the complexity readout before
  choosing personal-plan-model-tiers (STOP-and-swap) or personal-plan-orchestrate
  (auto-dispatch). The two driver skills call this one automatically when a plan
  is not tagged yet, so you never have to invoke it by hand first.
---

# personal-plan-tag-tiers

Shared tagging layer for tiered plans. The canonical reference for tier
definitions, the `[fast]` downgrade checklist, default-up bias, and tag
placement lives in:

> `~/Projects/personal/public/standards/plan-execution.md` §"Model-tier stop
> points"

Read that section's "Tiers", "`[fast]` downgrade checklist", and "Tag
placement" subsections first when in doubt. This file does not duplicate them.

## What this skill does — and does not do

**Does:** identify the plan, then tag every executable step `[deep]`,
`[exec]`, or `[fast]` to reveal the true shape of the work, and print a short
complexity readout.

**Does not:** group steps into execution waves, apply the no-thrash rule,
insert STOP markers, write a Kickoff block, seed todos, ask where to execute,
or run any step. All of that belongs to the execution drivers:
[`personal-plan-model-tiers`](../personal-plan-model-tiers/SKILL.md) (passive,
STOP-and-swap) and [`personal-plan-orchestrate`](../personal-plan-orchestrate/SKILL.md)
(active, auto-dispatch).

Keeping tagging separate is the whole point: the **tags stay honest**. The
no-thrash logic in the drivers may run a short `[fast]` run on the `[exec]`
model to avoid a model swap, but it never rewrites the `[fast]` tag. So a
tagged plan always shows how complex the task actually was, independent of how
it ends up being executed.

## Procedure

### 1. Identify the plan

In priority order:

1. File path the user names explicitly.
2. The most recent `.scratch/plan-*.md` in the workspace.
3. The plan visible in the current conversation.

Read it fully before tagging anything.

### 2. Tag every executable step

Following the tag placement rule in the standards section above, add
`[deep]`, `[exec]`, or `[fast]` to each heading at the executable level
(typically the deepest heading level). Leave higher-level grouping headings
(milestones, phases, sections) untagged. Apply the `[fast]` downgrade
checklist before assigning `[fast]`. Default-up bias: when in doubt,
`[deep]` > `[exec]` > `[fast]`. Do not rename, renumber, or otherwise change
any other content.

Tagging is **idempotent**: if a step is already tagged, leave its tag as-is
unless it is clearly miscategorized. Do not introduce thrash-driven tag
changes here — that is not this skill's job, and there is no thrash concept at
the tagging layer.

### 3. Report the complexity readout

After tagging, print a short summary so the user can size the work before
picking a driver:

- Tag counts: `N deep / M exec / K fast`.
- The top-down tier sequence (e.g. `deep, exec, exec, fast, fast, deep`).
- A one-line recommendation:
  - Mostly `[exec]` / `[fast]` with little `[deep]` → good fit for
    [`personal-plan-orchestrate`](../personal-plan-orchestrate/SKILL.md)
    (auto-dispatch, hands-off, Opus parent).
  - Heavy `[deep]`, or you want to drive each model swap yourself → use
    [`personal-plan-model-tiers`](../personal-plan-model-tiers/SKILL.md)
    (STOP-and-swap).

Then **stop**. Do not group waves, insert STOP markers, write a Kickoff block,
or execute anything. The user decides which driver to invoke next — or invokes
one directly, in which case that driver re-runs this skill only if the plan is
not already tagged.

## See also

- [`personal-plan-model-tiers`](../personal-plan-model-tiers/SKILL.md) —
  passive driver. Groups the tagged steps into execution waves (no-thrash),
  inserts STOP markers + a passive Kickoff block, and hands each model swap
  off to you.
- [`personal-plan-orchestrate`](../personal-plan-orchestrate/SKILL.md) —
  active Cursor driver. Same wave grouping, but the `[deep]` parent dispatches
  each wave via `Task(model=...)` subagents and pauses only at mandatory STOP
  gates.
- `~/Projects/personal/public/standards/plan-execution.md` §"Model-tier stop
  points" — canonical reference for tiers, the downgrade checklist, and tag
  placement.
