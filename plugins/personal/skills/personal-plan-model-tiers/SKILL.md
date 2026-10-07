---
name: personal-plan-model-tiers
description: >-
  Evaluate each step in a plan and tag it as [xdeep], [deep], [exec], or [fast] so the
  user can swap to the right model (or delegate to a subagent) at every tier
  boundary. Each STOP marker emits the next model for both Cursor and Claude
  Code plus a copy-pasteable handoff prompt. Use when the user asks to
  "evaluate each step", "tag xdeep / deep / exec / fast", "split a plan by model
  tier", "stop when the model should change", or wants to know which steps
  need a stronger vs. cheaper model.
---

# personal-plan-model-tiers

Passive execution driver. This skill owns the **execution** layer — grouping
tagged steps into waves (the no-thrash rule), inserting STOP markers, writing
the passive Kickoff block, and handing each model swap off to you. It does
**not** own tagging: the honest `[xdeep]` / `[deep]` / `[exec]` / `[fast]` tags come from
the shared [`personal-plan-tag-tiers`](../personal-plan-tag-tiers/SKILL.md)
skill, which this skill invokes automatically when a plan is not tagged yet.

The canonical reference for tier definitions, the `[fast]` downgrade checklist,
tag placement, the no-thrash rule, the model picker (Cursor + Claude Code +
thinking levels), the STOP marker template, token lines, expected cost, and
the Cost table lives in:

> `../personal-standards/standards/plan-execution.md` §"Model-tier stop
> points"

Read that section first when in doubt. This file does not duplicate it.

## Procedure

### 1. Identify the plan

In priority order:

1. File path the user names explicitly.
2. The most recent `plan-*.md` in `.scratch/` or `specs/handoffs/` (a
   runner session leaves it in the latter).
3. The plan visible in the current conversation.

Read it fully before tagging anything. Remember the resolved plan path as
its **fully-qualified absolute path** — every STOP handoff prompt must
reference it by absolute path, never a bare filename or repo-relative path.
The one exception is a plan tracked in `specs/handoffs/` on a runner: use
its repo-relative path, since the branch (the prompt's `On branch` line) is
reopened on another machine (plan-execution.md, template fill-in rules).

If the plan file already has a Kickoff block with a `Status:` line and
` (done)` markers on some headings, this is a re-entry into a partially-
executed plan. Re-derive the native todo list from those markers (one todo
per group; groups that have all steps marked done → `completed`; the
current group → `in_progress`; remaining groups → `pending`). Do not
assume native todos from a prior session still exist. Keep the plan's Cost
table as it stands, per the re-entry rule in standards §"Cost table".

### 2. Ensure the plan is tagged

Check whether the plan's executable headings already carry tiers (regex
`^#+\s+.*\[(xdeep|deep|exec|fast)\]`).

- **Not tagged** → run [`personal-plan-tag-tiers`](../personal-plan-tag-tiers/SKILL.md)
  (the shared tagging skill) to tag every executable step, then return here.
- **Already tagged** → keep the existing tags. Do a light sanity pass against
  the `[fast]` downgrade checklist, the `[xdeep]` upgrade checklist, and
  default-up bias, but do not churn tags.

Tags reflect honest complexity and stay as-is from here on. This skill never
rewrites a tag for thrash reasons — that happens only at the wave-grouping
step below, and it changes the *execution wave*, not the tag.

### 3. Group tagged steps into execution waves (no-thrash) and write wave markers

Walk the tagged steps and collect consecutive same-tier steps into execution
waves. Always STOP at any boundary involving `[xdeep]` or `[deep]`. STOP at `[exec]` ↔
`[fast]` boundaries only when the `[fast]` block has ≥ 3 contiguous fast
steps; otherwise **fold those `[fast]` steps into the adjacent `[exec]` wave**
so they execute on the `[exec]` model with no model swap — but leave their
`[fast]` tags in the plan untouched. Re-merge adjacent waves of the same
**execution tier** after any fold.

**Validate the ≤ constraint before writing wave markers.** For each wave,
check that every step's tag is ≤ the wave's execution tier
(`[xdeep]` > `[deep]` > `[exec]` > `[fast]`). If any step's tag is *greater* than its
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
(1-based, through the total wave count) gets a [review beat](../personal-standards/standards/plan-execution.md)
when that wave finishes and before wave N+1 starts (including after the
final wave, before plan completion). Record the `(wave-N, <group-id>)`
pair for each wave — `<group-id>` is the same identifier used in the
Wave title format (e.g. `m1-s1-s5`). Default cadence is `review:
every-wave` (see step 5).

### 4. Insert STOP and REVIEW markers with handoff blocks

**REVIEW markers first, then STOP markers** at each inter-wave boundary.
For each wave N, insert an inline-complete `--- REVIEW: wave-N [deep] ---`
block (`--- REVIEW: wave-N [xdeep] ---` after an `[xdeep]` wave, so Opus at
xhigh reviews it) immediately after that wave's last executable
heading and **before**
the next `--- STOP …` or `--- WAVE …` marker (for the final wave, after
its last heading and before end-of-file or the Completion section). Use
the REVIEW template from standards §"Review beat" — fill in wave number,
total wave count, `<group-id>`, and the resolved plan path from step 1, so
the prompt is self-contained. Add its `On branch` line only on a task
branch with the plan file tracked (`specs/handoffs/` on a runner): a plan
in gitignored `.scratch/` isn't committed, and never `git add -f` it.
After an `[xdeep]` wave, also apply the `[xdeep]` note under that
template: `[xdeep]` in the marker, title, and prompt, its Opus xhigh
rows, and no ultracode. The final wave's REVIEW prompt also carries the
standards' final-completion paragraph, so that review finishes the plan
on `PASS`; with `review:` off, the STOP or Kickoff prompt that launches the
last wave carries it. **Idempotent:** skip a REVIEW write when
`--- REVIEW: wave-N` already exists for that wave (re-entry).

Then insert STOP markers at tier transitions.

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
   (look up from the model picker in standards). Name the level on every
   row, even a model's default: Claude Code saves a typed `/effort` level
   as that model's default for later chats. When the plan runs in
   Codex, Gemini CLI, Muse Code, or Grok Build, use that harness's row in
   place of Cursor's.
4. A copy-pasteable prompt that names the next group using whatever
   identifiers the plan uses (IDs like `m2 s1-s4` if present, or exact
   title text if not), references the resolved plan path from step 1, carries
   the **progress-update reminder spelled out inline** (before stopping:
   append ` (done)` to finished headings, update the Status line, flip
   todos), carries `On branch <name> (task branch): commit each finished
   step.` on a task branch (Gary pasting it names the branch for that chat;
   leave it out until a task branch exists; a chat on another branch
   follows the standards' fill-in rule: a runner keeps its assigned branch
   and says so, a workstation proposes switching and waits), carries the
   **token-line reminder** inline (append one line per model to `## Token
   log`, labeled `wave-<n> <group-id>`, with the format quoted, counted
   and priced per the log's counting header from step 5), and ends
   with "Stop at the next STOP marker and report back" so the cascade is
   preserved. There is no orchestrator in this flow, and the pasted chat
   usually does not re-load this skill, so those inline reminders are the
   only thing that tells the wave to update plan state and log its tokens —
   never omit them, and do not move them into a separate checklist block in
   the plan.
5. For a STOP into an `[xdeep]` wave, the extras from the standards'
   `[xdeep]` escalation note: for an audit-shaped wave (a whole-codebase or
   cross-repo audit, or a broad sweep over many files), start the prompt
   with the keyword `ultracode` so that turn runs under ultracode (for a
   wave that may take more than one turn, run `/effort ultracode` in that
   chat instead), and leave it out otherwise. Add one line naming the
   `[xdeep]` upgrade checklist condition each step met. Cursor has no
   ultracode equivalent; its `[xdeep]` row is Opus at xhigh alone.
   Name the Fable alt only when Opus at xhigh has already failed the step,
   and max only for a task type where a gain is measured.

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
- The prompt body references the resolved plan path from step 1 and
  uses the matching body for the tier (the `[fast]` body adds the
  "mechanical edits, do not refactor" reminder; `[deep]` and `[exec]`
  use the standard body; an `[xdeep]` first wave uses the standard body
  plus the step 4 `[xdeep]` extras: the `ultracode` opt-in for an
  audit-shaped wave and the checklist line).
- On a task branch, the prompt body carries the same `On branch <name>
  (task branch)` line as the STOP prompts (step 4).
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
Kickoff block. Apart from the Cost table and the counting header below,
do not modify any other content in the plan. Do **not** write any
separate progress checklist block into the plan — the progress-update
and token-line reminders live inline in the Kickoff/STOP prompt bodies
(see step 4), which is the only surface a fresh pasted chat reliably
reads.

**Write the Cost table directly below the Kickoff block** (standards
§"Cost table"). Estimate each wave per standards §"Expected cost": each
step at the row for the model and effort that run the wave's execution
tier in this harness (or the harness the user names), with only an
audit-shaped `[xdeep]` step on the ultracode row, times the step's size
factor, plus the wave's review beat. Label the table with that harness (e.g.
`**Cost (API-equiv, Claude Code models)**`), give it one row per wave, a
`kickoff` row for this chat (standards §"Expected cost", "Kickoff row")
and a **Total** row, and keep the one-line accuracy note under it. Print
the Kickoff block and the table in chat. When you replace an existing
Kickoff, keep the table; recompute its expected columns only when
re-grouping changed the waves before any wave has run, and say so. After
a wave has run, a re-plan adds rows with expected `—` instead.

**Write the counting header at the top of `## Token log`** (standards
§"Token line format", "Counting header"), creating the section at the
bottom of the plan. For the harness the Cost table names, it carries the
token line format and row labels, that harness's usage source and how to
normalize it (the accumulation heuristic on Cursor and Muse Code), the
price rows of the models this plan's waves and reviews run (alts the Next
model rows name included), and the one-line formula: everything a pasted
wave or review chat needs to write its lines without reading the
standard. When you replace an existing Kickoff or re-enter the plan, keep
the header, refreshing it in place when the waves will now run in another
harness or on other models; never write a second one.

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

- **New chat (default).** Append this chat's `kickoff` token line to
  `## Token log` (see "Token tally on report-back" below). Print the full
  modified plan (with STOP markers, and the Kickoff block and Cost table
  at the top) so the user can see the result. Halt. Do **not** begin
  executing any step — the user will start a fresh chat by copying the
  Kickoff prompt from the top of the plan file.
- **Current chat.** Append this chat's `kickoff` token line, print the
  full modified plan, then begin executing the first group. Stop at the
  first STOP marker and report back, with a `wave-1` token line for the
  work since the kickoff line.

In whichever chat executes a group, **before halting at the STOP marker**:

1. Append ` (done)` to every executable heading in the just-finished
   group.
2. Flip that group's native todo to `completed`; mark the next group
   `in_progress`.
3. Update the `Status:` line in the Kickoff block: increment the done
   count, set `current:` to the next group's identifier, and refresh
   the date.
4. Append this chat's token lines to `## Token log`, as the prompt's
   token-line reminder says (see "Token tally on report-back").
5. On a task branch, commit; a runner also pushes (core.md "Save before
   you wait"). The STOP question is then only about the next wave and
   names the commit range. On a shared branch, offer the commit as its
   own choice (standards §"STOP gate semantics"); a workstation asks once,
   at its first pause (end of the first step), before anything is
   committed, whether to cut a task branch (core.md "Cut a task branch off
   a shared branch"). A chat that cuts one adds its `On branch` line to the
   remaining STOP prompts (and REVIEW prompts, when the plan is tracked)
   with its first commit.

**Review beat (separate chat).** After a wave finishes, the human runs
the REVIEW marker for that wave before starting the next wave. When
executing a review beat, follow the REVIEW prompt in the plan: read-only,
append one line to `## Review log` per standards §"Review log" and its
`review-wave-N` token lines to `## Token log`, update `last review:` on
the Kickoff `Status:` line (`wave-N PASS` or `wave-N CONCERNS`), and
report back. Do **not** fix or start the next wave.

**Review gate (fail-closed).** Before starting wave N+1 (via a STOP or
Kickoff prompt), verify wave N's review verdict is `PASS` — either
`last review: wave-N PASS` on the Status line or a matching `PASS` line
in `## Review log`. If the verdict is `CONCERNS` or missing when
required, set `Status:` to
`BLOCKED at gate review-wave-N` (with `last review: wave-N CONCERNS` when
applicable), re-post the concern, and end the turn. The next wave does
not start until a human resolves the block. A fix-up wave added to resolve
it is numbered `N-fix` and gets its own Cost table row with expected `—`
(standards §"Cost table").

**At every STOP marker, these gates are fail-closed.** A missed,
timed-out, dismissed, or ambiguous response to a STOP-marker question
never authorizes continuing past that marker. If no explicit
affirmative answer is received, record `BLOCKED at gate <identifier>`
in the Kickoff `Status:` line (e.g.
`Status: 2/5 groups done | BLOCKED at gate [exec]->[deep] | updated 2026-05-28`),
re-post the STOP-marker question, and end the turn. The next session
re-derives state from the `Status:` line and ` (done)` markers —
a `BLOCKED at gate` status means re-post and wait, never assume approval.

When the **last group finishes**, its chat updates progress and logs its
tokens like any other wave and stops. The final-completion steps from
`§"Model-tier stop points" → "Progress tracking" → "Final completion"`
in the standards run in the last wave's review beat, on `PASS`, as its
REVIEW prompt says (in the last wave's own chat when `review:` is off):
replace the Kickoff marker with `--- KICKOFF: plan complete ---`, add the
actual columns to the Cost table (see "Token tally on report-back"
below), and append the Completion summary at the bottom of the plan
file.

## Token tally on report-back

This chat ends its report-back with one token line per model it ran, in
the canonical format of `../personal-standards/standards/plan-execution.md`
§"Token line format":

- **Kickoff** (both branches of step 7): `kickoff <plan-name>`, for the
  work through writing the Kickoff block, the Cost table and the counting
  header.
- **Wave 1** (current-chat branch only): `wave-1 <group-id>`, for the work
  since the kickoff line: only those calls when the harness has real
  usage, or the heuristic's form for part of a chat (`T0` is the kickoff's
  tokens).

`<group-id>` is the group identifier from the plan with hyphens (e.g.
`m1-s1-s3`). Later wave chats and review-beat chats write their own
`wave-N` and `review-wave-N` lines, from the token-line reminder in the
prompts they paste (step 4), counted and priced per the counting header
step 5 writes, so they read the plan, not the standard.

Take the counts from the **source precedence** in the same standards file
(§"Token accounting — source precedence"):

- **Claude Code**: this chat's session transcript, deduped by `message.id`
  (exact). A subagent this chat delegated to adds the exact input-side
  counts from its own transcript, with output estimated for the calls the
  standards table names, so that model's line carries `(output est.)` and
  ends with `session <id>`.
- **Codex, Gemini CLI, Grok Build**: that harness's usage, normalized per
  the standards table.
- **Cursor**: usage the user pastes, else the accumulation heuristic,
  labeled `(heuristic)`.
- **Muse Code**: the accumulation heuristic, labeled `(heuristic)`.

Accuracy follows the source, as the standards section states. Price each
line with the cache-aware formula and its model's list rates (§"Model price
table"): API-equivalent, whatever the harness bills. The counting header
(step 5) carries these rules cut to the harness the Cost table names, with
the rates of the models the plan's waves and reviews run.

**Also write the lines to the plan file.** Append them to the `## Token log`
section at the bottom of the plan file, below its counting header (step 5
creates both). This persists the lines across separate chats, and the Cost
table's actual columns come from it.

At final completion (the last wave's review beat, step 7), the actual
tokens and actual $ columns come from the `## Token log` (standards §"Cost
table": each wave row sums its `wave-N` and `review-wave-N` lines across
models, and the `kickoff` row its `kickoff` lines), and the completed table
prints alongside the Completion summary. The Token log keeps the per-model
detail.

## Delegating to subagents

When a `[deep]` parent reaches an `[exec]` or `[fast]` group, prefer
delegating to a subagent on the cheaper model from the picker rather than
burning the deep context on mechanical work. Pass: the spec section, the
exact files to touch, acceptance criteria, and a hard scope limit naming
the exact steps to implement and instructing the subagent to stop and report
back after completing them. Spell out the git instruction too: on a task
branch, commit each finished step and don't push or switch branches; on a
shared branch, don't commit. The deep parent reviews the subagent output
before moving to the next STOP marker, and only the parent pushes. Count
the subagent's tokens in the wave's token lines, one line per model. See the
standards section "Delegating execution to subagents" for the full
guidance.

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
