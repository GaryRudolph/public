---
name: personal-plan-tag-tiers
description: >-
  Tag every executable step in a plan as [xdeep], [deep], [exec], or [fast] so you can
  see how complex the work actually is before deciding how to run it. This is
  the shared tagging layer: it only tags — it does not group steps into waves,
  apply the no-thrash rule, insert STOP markers, write Kickoff blocks, or
  execute anything. Tags reflect honest complexity and are never rewritten for
  thrash reasons. Use when the user asks to "tag the tiers", "tag xdeep / deep /
  exec / fast", "show how complex this plan is", or wants the complexity readout before
  choosing personal-plan-model-tiers (STOP-and-swap) or personal-plan-orchestrate
  (auto-dispatch). The two driver skills call this one automatically when a plan
  is not tagged yet, so you never have to invoke it by hand first.
---

# personal-plan-tag-tiers

Shared tagging layer for tiered plans. The canonical reference for tier
definitions, the `[fast]` downgrade checklist, the `[xdeep]` upgrade
checklist, tag placement and the Shape section lives in:

> `../personal-standards/standards/plan-execution.md` §"Model-tier stop
> points"

Read that section's "Tiers", "`[fast]` downgrade checklist", "`[xdeep]`
upgrade checklist", "Tag placement" and "Shape" subsections first when in doubt. This file does not duplicate them.

## What this skill does — and does not do

**Does:** identify the plan, tag every executable step `[xdeep]`,
`[deep]`, `[exec]`, or `[fast]` to reveal the true shape of the work, propose
splitting a build step whose only deep part is one design choice, write the
plan's Shape section (the files it will create and modify), and print a short
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
2. The most recent `plan-*.md` in `.scratch/` or `specs/handoffs/` (a
   runner session leaves it in the latter).
3. The plan visible in the current conversation.

Read it fully before tagging anything.

### 2. Tag every executable step

Following the tag placement rule in the standards section above, add
`[xdeep]`, `[deep]`, `[exec]`, or `[fast]` to each heading at the executable level
(typically the deepest heading level). Leave higher-level grouping headings
(milestones, phases, sections) untagged. Apply the `[fast]` downgrade
checklist before assigning `[fast]` and the `[xdeep]` upgrade checklist
before assigning `[xdeep]`. There is no default-up bias: doubt between
`[exec]` and `[deep]` resolves to `[exec]` (the unit's review and the
escalation path catch a step that needed more); doubt between `[deep]` and
`[xdeep]` resolves to `[deep]`. Every `[deep]` tag needs a one-line reason
(what in the step needs top-tier reasoning), which goes in the readout, not
the heading. A step that is Gary's own decision gets no tag: it is a gate,
not work. Do not rename, renumber, or otherwise change any other content.

A step ID must be one token (standard §"Tag placement"): a heading whose
prefix has whitespace (`#### Phase 1: Auth`) can never match a commit
subject and is gate 0 under orchestrate. Say so in the readout and propose
the fix (`#### phase-1 - Auth`, or the `s{N}` shape); don't rewrite the
heading yourself.

Tagging is **idempotent**: if a step is already tagged, leave its tag as-is
unless it is clearly miscategorized. Do not introduce thrash-driven tag
changes here — that is not this skill's job, and there is no thrash concept at
the tagging layer.

### 3. Propose splits

A build step tagged `[deep]` only because one design choice sits inside it
(an implementation step with a "choose the strategy" or "decide the
layout" clause) is two steps: a short `[deep]` step whose output is a
design note (the options, the choice, why), and an `[exec]` step that
applies it. List each such step in the readout as a proposed split:

    s3 [deep] "Wire the cache" -> s3 [deep] decide the invalidation strategy
    (design note); s4 [exec] wire the cache per s3; s4..s6 become s5..s7

Apply a split only on Gary's yes, and only while the plan has no wave
marker (after that, the drivers own the numbering): split the heading and
its text, renumber the later steps of that milestone, and update every
cross-reference in the plan to the renumbered steps. Without a yes, the
tags stand as they are.

### 4. Write the Shape section

Write the `## Shape` section the standard describes (§"Shape"): every file
the plan will create, one per line with one line on why a new file is
needed, and every file it will modify, bare. Read the repo to tell new from
existing; a step that names no files gets your best guess, marked
`(guess)`. Put it before the first milestone heading (below a Kickoff
block and Cost table when those exist). If the plan already has one, keep
it and add a line per step added since; never remove a line Gary trimmed.

### 5. Report the complexity readout

After tagging, print a short summary so the user can size the work before
picking a driver:

- Tag counts: `X xdeep / N deep / M exec / K fast`.
- The top-down tier sequence (e.g. `xdeep, deep, exec, exec, fast, fast, deep`).
- For each `[deep]` step, its one-line reason.
- For each `[xdeep]` step, the checklist condition it met and whether it is
  audit-shaped (a whole-codebase or cross-repo audit, or a broad sweep over
  many files: the one case that takes ultracode in Claude Code, and only under
  the passive driver), so the
  `[xdeep]` spend is easy to second-guess.
- The proposed splits (step 3), if any, and any step ID that isn't one
  token.
- The Shape summary: `N new files, M modified`, naming the new ones, so the
  plan's decomposition is visible before a line is written.
- A one-line recommendation:
  - Direct-sized (plan-execution.md §"Driver fit": one working directory,
    one wave or three steps or fewer, no `[xdeep]`, fits one context) →
    neither driver: run it in this session. Say which conditions it met,
    and name the step, if any, that might still earn a driver's reviews.
  - One-session-sized (§"Driver fit", "When orchestrate pays off"): a
    single-repo feature with a written spec one engineer could do in a
    day → one Opus session, direct or under
    [`personal-plan-model-tiers`](../personal-plan-model-tiers/SKILL.md);
    say why orchestrate would split it too far.
  - Mostly `[exec]` / `[fast]` with little `[deep]`, spanning repos,
    needing unattended hours, or with independent chains → good fit for
    [`personal-plan-orchestrate`](../personal-plan-orchestrate/SKILL.md)
    (auto-dispatch, hands-off, Opus parent).
  - Heavy `[deep]` / `[xdeep]`, or you want to drive each model swap yourself → use
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
  active driver, on Claude Code and Cursor. Same wave grouping, but the
  `[deep]` parent dispatches each wave to subagents on the tier's model and
  pauses only where its recorded mode stops.
- `../personal-standards/standards/plan-execution.md` §"Model-tier stop
  points" — canonical reference for tiers, the downgrade checklist, tag
  placement and the Shape section.
