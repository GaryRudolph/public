---
name: personal-plan-model-tiers
description: >-
  Evaluate each step in a plan and tag it as [deep], [exec], or [fast] so the
  user can swap to the right model (or delegate to a subagent) at every tier
  boundary. Each STOP marker emits the next model for both Cursor and Claude
  Code plus a copy-pasteable handoff prompt. Use when the user asks to
  "evaluate each step", "tag deep / exec / fast", "split a plan by model
  tier", "stop when the model should change", or wants to know which steps
  need a stronger vs. cheaper model.
---

# personal-plan-model-tiers

Operational skill that runs the procedure. The canonical reference for tier
definitions, the `[fast]` downgrade checklist, tag placement, the no-thrash
rule, the model picker (Cursor + Claude Code + thinking levels), and the
STOP marker template lives in:

> `~/Projects/personal/public/standards/documentation.md` §"Model-tier stop
> points"

Read that section first when in doubt. This file does not duplicate it.

## Procedure

### 1. Identify the plan

In priority order:

1. File path the user names explicitly.
2. The most recent `.scratch/plan-*.md` in the workspace.
3. The plan visible in the current conversation.

Read it fully before tagging anything. Remember the resolved plan path —
every STOP handoff prompt has to reference it.

### 2. Tag every executable step

Following the tag placement rule in the standards section above, add
`[deep]`, `[exec]`, or `[fast]` to each heading at the executable level
(typically the deepest heading level). Leave higher-level grouping headings
(milestones, phases, sections) untagged. Apply the `[fast]` downgrade
checklist before assigning `[fast]`. Default-up bias: when in doubt,
`[deep]` > `[exec]` > `[fast]`. Do not rename, renumber, or otherwise
change any other content.

### 3. Apply the no-thrash rule

Walk the tagged steps and collect consecutive same-tier steps into groups.
Always STOP at any boundary involving `[deep]`. STOP at `[exec]` ↔ `[fast]`
boundaries only when the `[fast]` block has ≥ 3 contiguous fast steps;
otherwise promote those `[fast]` steps to `[exec]` to avoid model-swap
thrash. Re-merge adjacent same-tier groups after any promotion.

See the standards section for the full rule.

### 4. Insert STOP markers with a handoff block

Use the STOP-marker template from the standards section. Each STOP must
include:

1. The tier transition direction.
2. The next model + thinking level for **both** Cursor and Claude Code
   (look up from the model picker in standards).
3. A copy-pasteable prompt that names the next group using whatever
   identifiers the plan uses (IDs like `m2 s1-s4` if present, or exact
   title text if not), references the resolved plan filename, and ends with
   "Stop at the next STOP marker and report back" so the cascade is
   preserved.

Use `->` ASCII arrows in the marker so it stays safe in terminals and grep.

### 5. Output and halt

Print the full re-tagged plan with STOP markers in place. Do not begin
executing any step. Stop at the first STOP marker and wait for the user.

## Delegating to subagents

When a `[deep]` parent reaches an `[exec]` or `[fast]` group, prefer
delegating to a subagent on the cheaper model from the picker rather than
burning the deep context on mechanical work. Pass: the spec section, the
exact files to touch, acceptance criteria, and a hard scope limit naming
the exact steps to implement and instructing the subagent to stop and report
back after completing them. The deep parent reviews the
subagent output before moving to the next STOP marker. See the standards
section "Delegating execution to subagents" for the full guidance.

## See also

- [`personal-plan-orchestrate`](../personal-plan-orchestrate/SKILL.md) —
  active counterpart for Cursor. Same tagging and model picks, but the
  parent delegates each `[exec]` or `[fast]` group via `Task(model=...)`
  subagents and continues automatically, pausing only at a small set of
  mandatory STOP gates. Use it when you want the cascade run for you
  instead of stopping at every tier boundary.
