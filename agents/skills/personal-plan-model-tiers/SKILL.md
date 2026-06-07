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

Passive execution driver. This skill owns the **execution** layer — grouping
tagged steps into waves (the no-thrash rule), inserting STOP markers, writing
the passive Kickoff block, and handing each model swap off to you. It does
**not** own tagging: the honest `[deep]` / `[exec]` / `[fast]` tags come from
the shared [`personal-plan-tag-tiers`](../personal-plan-tag-tiers/SKILL.md)
skill, which this skill invokes automatically when a plan is not tagged yet.

The canonical reference for tier definitions, the `[fast]` downgrade checklist,
tag placement, the no-thrash rule, the model picker (Cursor + Claude Code +
thinking levels), and the STOP marker template lives in:

> `~/Projects/personal/public/standards/plan-execution.md` §"Model-tier stop
> points"

Read that section first when in doubt. This file does not duplicate it.

## Procedure

### 1. Identify the plan

In priority order:

1. File path the user names explicitly.
2. The most recent `.scratch/plan-*.md` in the workspace.
3. The plan visible in the current conversation.

Read it fully before tagging anything. Remember the resolved plan path as
its **fully-qualified absolute path** — every STOP handoff prompt must
reference it by absolute path, never a bare filename or repo-relative path.

If the plan file already has a Kickoff block with a `Status:` line and
` (done)` markers on some headings, this is a re-entry into a partially-
executed plan. Re-derive the native todo list from those markers (one todo
per group; groups that have all steps marked done → `completed`; the
current group → `in_progress`; remaining groups → `pending`). Do not
assume native todos from a prior session still exist.

### 2. Ensure the plan is tagged

Check whether the plan's executable headings already carry tiers (regex
`^#+\s+.*\[(deep|exec|fast)\]`).

- **Not tagged** → run [`personal-plan-tag-tiers`](../personal-plan-tag-tiers/SKILL.md)
  (the shared tagging skill) to tag every executable step, then return here.
- **Already tagged** → keep the existing tags. Do a light sanity pass against
  the `[fast]` downgrade checklist and default-up bias, but do not churn tags.

Tags reflect honest complexity and stay as-is from here on. This skill never
rewrites a tag for thrash reasons — that happens only at the wave-grouping
step below, and it changes the *execution wave*, not the tag.

### 3. Group tagged steps into execution waves (no-thrash) and write wave markers

Walk the tagged steps and collect consecutive same-tier steps into execution
waves. Always STOP at any boundary involving `[deep]`. STOP at `[exec]` ↔
`[fast]` boundaries only when the `[fast]` block has ≥ 3 contiguous fast
steps; otherwise **fold those `[fast]` steps into the adjacent `[exec]` wave**
so they execute on the `[exec]` model with no model swap — but leave their
`[fast]` tags in the plan untouched. Re-merge adjacent waves of the same
**execution tier** after any fold.

**Validate the ≤ constraint before writing wave markers.** For each wave,
check that every step's tag is ≤ the wave's execution tier
(`[deep]` > `[exec]` > `[fast]`). If any step's tag is *greater* than its
wave's execution tier, that is a tagging error — do not write wave markers.
Surface the violation (e.g. "`[deep]` step s3 is inside an `[exec]` wave"),
halt, and ask the user to re-tag the step or widen the wave before continuing.

**Write wave markers into the plan file.** Once the ≤ constraint is satisfied,
insert `--- WAVE N [execution-tier] ---` immediately before the first
executable heading of each wave (1-based, using the wave's execution tier, not
the step tag). Format and placement rules live in the standards section
§"Wave annotation format". Skip this write if wave markers already exist
(re-entry into a partially-executed plan).

This is an execution-grouping decision only: a folded wave's execution tier
(the model it runs on) can differ from a step's tag (its honest complexity).
STOP markers and the Kickoff key off the execution tier. See the standards
section §"Wave annotation format" and §"No-thrash rule" for the full rules.

**Compute a review point for every wave.** After grouping, each wave N
(1-based, through the total wave count) gets a [review beat](~/Projects/personal/public/standards/plan-execution.md)
when that wave finishes and before wave N+1 starts (including after the
final wave, before plan completion). Record the `(wave-N, <group-id>)`
pair for each wave — `<group-id>` is the same identifier used in the
Wave title format (e.g. `m1-s1-s5`). Default cadence is `review:
every-wave` (see step 5).

### 4. Insert STOP and REVIEW markers with handoff blocks

**REVIEW markers first, then STOP markers** at each inter-wave boundary.
For each wave N, insert an inline-complete `--- REVIEW: wave-N [deep] ---`
block immediately after that wave's last executable heading and **before**
the next `--- STOP …` or `--- WAVE …` marker (for the final wave, after
its last heading and before end-of-file or the Completion section). Use
the REVIEW template from standards §"Review beat" — fill in wave number,
total wave count, `<group-id>`, and the resolved absolute plan path so
the prompt is self-contained. **Idempotent:** skip a REVIEW write when
`--- REVIEW: wave-N` already exists for that wave (re-entry).

Then insert STOP markers at tier transitions as before.

Use the STOP-marker template from the standards section. Each STOP must
include:

1. The tier transition direction.
2. A `Suggested chat title:` line in the canonical Wave title format
   (`Wave {n} of {t} [{tier}] {group-id}`, e.g. `Wave 2 of 3 [exec] m2 s1-s3`)
   — the same title `personal-plan-orchestrate` uses for its `Task`
   subagents. `{n}` is the wave this STOP launches (the next wave), `{t}`
   the total wave count from the Status line. This is advisory: a foreground
   chat cannot set its own title, so the user pastes it as the new chat's
   name if their harness supports it. Emit it even though there is no
   guarantee it will be used. See the standards §"Wave title format".
3. The next model + thinking level for **both** Cursor and Claude Code
   (look up from the model picker in standards).
4. A copy-pasteable prompt that names the next group using whatever
   identifiers the plan uses (IDs like `m2 s1-s4` if present, or exact
   title text if not), references the resolved absolute plan path, carries
   the **progress-update reminder spelled out inline** (before stopping:
   append ` (done)` to finished headings, update the Status line, flip
   todos), and ends with "Stop at the next STOP marker and report back" so
   the cascade is preserved. There is no orchestrator in this flow, and the
   pasted chat usually does not re-load this skill, so that inline reminder
   is the only thing that tells the wave to update plan state — never omit
   it, and do not move it into a separate checklist block in the plan.

Use `->` ASCII arrows in the marker so it stays safe in terminals and grep.

### 5. Write the Kickoff block to the top of the plan file

Use the **passive** variant of the Kickoff template from the standards
section (`§"Model-tier stop points" → "Kickoff template"`). Fill in the
`Status:` line with `0/N groups done | last review: — | current: <first
group> <tier> | updated <today>` where `N` is the total number of waves
after the no-thrash folding pass. Add a `review: every-wave` line
(default cadence; see standards §"Review beat"). Then fill in the rest:

- `<tier>` is the **execution tier of the first wave** after the no-thrash
  folding pass — normally the tag on the first executable heading walking
  top-down, except when a short leading `[fast]` run is folded into the
  following `[exec]` wave, in which case the first wave executes at `[exec]`
  even though those headings keep their `[fast]` tags. Higher-level grouping
  headings (milestones, phases) are untagged and ignored.
- The "Next model" rows come from the model picker in the same standards
  section. Include both Cursor and Claude Code rows.
- The prompt body references the resolved absolute plan path from step 1 and
  uses the matching body for the tier (the `[fast]` body adds the
  "mechanical edits, do not refactor" reminder; `[deep]` and `[exec]`
  use the standard body).
- Include a `Suggested chat title:` line in the Wave title format for the
  first wave (`Wave 1 of N [<tier>] <first group>`) — the same advisory
  title as the STOP markers (step 4). Emit it even though a foreground chat
  cannot set its own title; the user pastes it as the new chat's name if
  their harness supports it.

Write the resulting block at the top of the plan file, above the first
heading, inside a fenced code block. The Kickoff block is **idempotent**:
if a Kickoff block already exists at the top of the file (any line
matching `--- KICKOFF: ... ---`), replace it with the appropriate
variant rather than appending. A plan never carries more than one
Kickoff block. Do not modify any other content in the plan. Do **not**
write any separate progress checklist block into the plan — the
progress-update reminder lives inline in the Kickoff/STOP prompt bodies
(see step 4), which is the only surface a fresh pasted chat reliably reads.

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
this chat. See `standards/plan-execution.md` §"STOP gate semantics (fail
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

**Review beat (separate chat).** After a wave finishes, the human runs
the REVIEW marker for that wave before starting the next wave. When
executing a review beat, follow the REVIEW prompt in the plan: read-only,
append one line to `## Review log` per standards §"Review log", update
`last review:` on the Kickoff `Status:` line (`wave-N PASS` or
`wave-N CONCERNS`), and report back. Do **not** fix or start the next
wave.

**Review gate (fail-closed).** Before starting wave N+1 (via a STOP or
Kickoff prompt), verify wave N's review verdict is `PASS` — either
`last review: wave-N PASS` on the Status line or a matching `PASS` line
in `## Review log`. If the verdict is `CONCERNS` or missing when
required, set `Status:` to
`BLOCKED at gate review-wave-N` (with `last review: wave-N CONCERNS` when
applicable), re-post the concern, and end the turn. The next wave does
not start until a human resolves the block.

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
STOP marker (current-chat branch of step 7), append a wave summary line to
your report-back. After a **review beat** chat, use the same shape with
`review-wave-N` instead of `wave-N`:

```
tokens wave-N <group-id> (model-slug): input ~X / output ~Y | cost ~$C (heuristic)
tokens review-wave-N <group-id> (model-slug): input ~X / output ~Y | cost ~$C (heuristic)
```

Where `wave-N` is the 1-based wave number (1 for the first group executed, 2
for the second, etc.), `<group-id>` is the group identifier from the plan
(e.g. `m1-s1-s3`), and `model-slug` is the model this chat ran on.

Derive `X` and `Y` using the **source precedence** in
`~/Projects/personal/public/standards/plan-execution.md` §"Token accounting —
source precedence": prefer real harness usage when available (on Claude Code,
read `message.usage` — incl. cache tiers and reasoning tokens — from the
session JSONL), and fall back to `~tokens ≈ chars / 4` only when it isn't
(e.g. Cursor). Tag the line `(heuristic)` and treat it as ±40% when using the
fallback; ±15% when using real usage.

Compute `C` with the cache-aware formula and the input/output rates for the
model slug from the same standards section (§"Model price table").

**Also write the wave line to the plan file.** Append it to a `## Token log`
section at the bottom of the plan file (create the section if it doesn't
exist). This persists cross-wave data across separate chats so the final
wave can assemble the full table.

When the **last group finishes**, read all wave and review lines from the
`## Token log` section and print the full per-wave breakdown table alongside
the Completion summary (include `review-wave-N` rows interleaved after their
wave):

| wave | group | model | ~input | ~output | ~cost |
|------|-------|-------|--------|---------|-------|
| wave-1 | m1-s1-s3 | claude-opus-4-8-thinking-xhigh | … | … | … |
| review-wave-1 | m1-s1-s3 | claude-opus-4-8-thinking-xhigh | … | … | … |
| wave-2 | m2-s4-s6 | claude-4.6-sonnet-medium-thinking | … | … | … |
| **GRAND TOTAL** | | | | | … |

The GRAND TOTAL cost is the **sum of per-wave costs** (each priced at its own
model's rates), not a blended rate applied to the total token count. Accuracy
follows the source each wave used (±15% from real harness usage, ±40% from
the `chars / 4` heuristic). These are rough estimates, not authoritative
billing data.

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

- [`personal-plan-tag-tiers`](../personal-plan-tag-tiers/SKILL.md) — the
  shared tagging skill this one invokes when a plan isn't tagged. Run it
  directly first when you only want to see a plan's complexity before
  choosing a driver.
- [`personal-plan-orchestrate`](../personal-plan-orchestrate/SKILL.md) —
  active counterpart for Cursor. Same tagging and model picks, but the
  parent delegates each `[exec]` or `[fast]` wave via `Task(model=...)`
  subagents and continues automatically, pausing only at a small set of
  mandatory STOP gates. Use it when you want the cascade run for you
  instead of stopping at every tier boundary.
