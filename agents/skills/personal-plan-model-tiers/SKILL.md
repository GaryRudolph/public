---
name: personal-plan-model-tiers
description: >-
  Evaluate each step in a plan and tag it as [deep] or [exec] so the user can
  switch to a deeper or cheaper model at tier boundaries, or delegate exec work
  to a subagent. Use when the user asks to "evaluate each step", "tag deep or
  exec", "split a plan by model tier", "stop when the model should change", or
  wants to know which steps need a stronger vs. simpler model.
---

# personal-plan-model-tiers

Evaluates a plan and inserts STOP markers at every model-tier boundary so you
can swap to the right model (or delegate to a subagent) at each transition.

## What the tiers mean

See `~/Projects/personal/public/standards/documentation.md` §"Model-tier stop
points" for the full reference. Short version:

- `[deep]` — top-tier reasoning model needed: architecture decisions, ambiguous
  requirements, non-obvious debugging, security-sensitive review, library/stack
  trade-offs, or anywhere the cost of getting it wrong is high.
- `[exec]` — mechanical, well-specified work: applying a decided design across
  files, refactors with a clear target, renames, test scaffolding for
  already-designed behavior, formatting, doc updates, well-bounded ports.

When in doubt, tag `[deep]`. A misclassified `[deep]` wastes a little money; a
misclassified `[exec]` produces bad output.

## Procedure

### 1. Identify the plan

In priority order:
1. File path the user names explicitly.
2. The most recent `.scratch/plan-*.md` in the workspace.
3. The plan visible in the current conversation.

Read it fully before tagging anything.

### 2. Tag every milestone and step

Add `[deep]` or `[exec]` after the title on every milestone and step heading.
Do not change any other content.

```
### m1 - Design the caching layer [deep]
#### s1 - Choose eviction strategy [deep]
#### s2 - Spec the cache key format [deep]

### m2 - Implement the cache [exec]
#### s1 - Wire Redis client [exec]
#### s2 - Add cache middleware [exec]
#### s3 - Write integration tests [exec]
```

### 3. Group and insert STOP markers

Walk the tagged steps in order. Collect consecutive same-tier steps into a
group. At every boundary where the tier changes, insert a STOP marker between
the groups:

```
--- STOP: tier change [deep] → [exec] — switch to a cheaper/faster model, or
    delegate the next group to a subagent before continuing ---
```

or

```
--- STOP: tier change [exec] → [deep] — switch back to a stronger model before
    continuing ---
```

### 4. Output and halt

Print the full re-tagged plan with STOP markers in place. Do not begin
executing any step. Stop at the first STOP marker and wait for the user to:

- Continue on the current model, or
- Swap to a different model, or
- Delegate the next group to a subagent (provide the group's steps, relevant
  spec sections, files to touch, and acceptance criteria — subagents don't see
  the parent conversation).

## Delegating exec groups to subagents

When handing an `[exec]` group to a subagent, include in the prompt:

1. The relevant spec section or plan excerpt (exact steps, acceptance criteria).
2. The exact files to touch and what change is expected.
3. A hard scope limit: "only implement steps s1–s3; stop and report back."
4. The cheapest model that can plausibly complete the work; step up only if the
   subagent fails or returns low-quality output.

The deep parent is responsible for reviewing subagent output before moving to
the next STOP marker.
