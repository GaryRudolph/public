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

If the plan file already has a Kickoff block with a `Status:` line and
` (done)` markers on some headings, this is a re-entry into a partially-
executed plan. Re-derive the native todo list from those markers (one todo
per group; groups that have all steps marked done → `completed`; the
current group → `in_progress`; remaining groups → `pending`). Do not
assume native todos from a prior session still exist.

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

### 5. Write the Kickoff block to the top of the plan file

Use the **passive** variant of the Kickoff template from the standards
section (`§"Model-tier stop points" → "Kickoff template"`). Fill in the
`Status:` line with `0/N groups done | current: <first group> <tier> |
updated <today>` where `N` is the total number of groups after the
no-thrash promotion pass. Then fill in the rest:

- `<tier>` is the **first executable tier** in the plan after the
  no-thrash promotion pass — i.e. the tier on the first tagged heading,
  walking top-down. Higher-level grouping headings (milestones, phases)
  are untagged and ignored.
- The "Next model" rows come from the model picker in the same standards
  section. Include both Cursor and Claude Code rows.
- The prompt body references the resolved plan filename from step 1 and
  uses the matching body for the tier (the `[fast]` body adds the
  "mechanical edits, do not refactor" reminder; `[deep]` and `[exec]`
  use the standard body).

Write the resulting block at the top of the plan file, above the first
heading, inside a fenced code block. The Kickoff block is **idempotent**:
if a Kickoff block already exists at the top of the file (any line
matching `--- KICKOFF: ... ---`), replace it with the appropriate
variant rather than appending. A plan never carries more than one
Kickoff block. Do not modify any other content in the plan.

After writing the Kickoff block, **seed the native todo list**: create
one todo per group (in order), with the first group as `in_progress` and
all others as `pending`. Use the group identifier (e.g. `m1 s1-s3 [exec]`)
as the todo content. See `§"Model-tier stop points" → "Progress tracking"`
in the standards for the full convention.

### 6. Ask the user where to execute

After writing the Kickoff block and seeding todos, ask the user:

> Continue execution in this chat, or hand off to a new chat for clean
> context? (default: new chat)

Wait for the user's answer. Treat any non-affirmative reply (silence,
dismissal, ambiguous answer, or failure to respond) as **new chat**.

This question is fail-closed: a missed or ambiguous answer defaults to
new chat (the safer path) and never authorizes continuing execution in
this chat. See `standards/documentation.md` §"STOP gate semantics (fail
closed)" for the canonical rules — approval is per-gate, a prior
one-time "continue" in another context is not a standing waiver here,
and the only way to authorize multiple unattended steps is an explicit
"run unattended" / "auto-approve the next N steps" instruction.

### 7. Branch on the answer

- **New chat (default).** Print the full modified plan (with STOP
  markers and the Kickoff block at the top) so the user can see the
  result. Halt. Do **not** begin executing any step — the user will
  start a fresh chat by copying the Kickoff prompt from the top of the
  plan file.
- **Current chat.** Print the full modified plan. Then begin executing
  the first group. Stop at the first STOP marker and report back, just
  as the prior version of this skill did.

In whichever chat executes a group, **before halting at the STOP marker**:

1. Append ` (done)` to every executable heading in the just-finished
   group.
2. Flip that group's native todo to `completed`; mark the next group
   `in_progress`.
3. Update the `Status:` line in the Kickoff block: increment the done
   count, set `current:` to the next group's identifier, and refresh
   the date.

**At every STOP marker, these gates are fail-closed.** A missed,
timed-out, dismissed, or ambiguous response to a STOP-marker question
never authorizes continuing past that marker. If no explicit
affirmative answer is received, record `BLOCKED at gate <identifier>`
in the Kickoff `Status:` line (e.g.
`Status: 2/5 groups done | BLOCKED at gate [exec]->[deep] | updated 2026-05-28`),
re-post the STOP-marker question, and end the turn. The next session
re-derives state from the `Status:` line and ` (done)` markers —
a `BLOCKED at gate` status means re-post and wait, never assume approval.

When the **last group finishes**, perform the final-completion steps from
`§"Model-tier stop points" → "Progress tracking" → "Final completion"`
in the standards: flip all todos to `completed`, replace the Kickoff
marker with `--- KICKOFF: plan complete ---`, and append the Completion
summary at the bottom of the plan file.

## Token tally on report-back

Before halting (new-chat branch of step 7) or after stopping at the first
STOP marker (current-chat branch of step 7), append one line to your
report-back:

```
tokens: input ~X / output ~Y / total ~Z / model <slug> (heuristic)
```

Use `~tokens ≈ chars / 4`. Count input chars as everything you read (user
prompts, file reads, tool outputs); count output chars as everything you
wrote (chat text, tool call arguments, file writes). Numbers are approximate
(~±15%). This tally is per-chat — it covers only the work done in this
session.

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
