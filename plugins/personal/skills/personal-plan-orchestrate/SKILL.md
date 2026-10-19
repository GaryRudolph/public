---
name: personal-plan-orchestrate
description: >-
  Actively orchestrate a tiered plan: the `[deep]` Opus parent dispatches
  each wave to subagents on the tier's model and keeps control, pausing
  only where the plan's recorded mode stops (gated: every STOP gate;
  unattended: only questions, failures, premium work and the cost guard).
  Same `[xdeep]` / `[deep]` / `[exec]` / `[fast]` tagging and no-thrash
  rule as `personal-plan-model-tiers`. Runs on a task branch and commits
  and pushes the plan and a handoff after every wave. On Claude Code it
  calls the Workflow tool to launch the plugin's plan-segment workflow,
  with hooks that check each launch, keep reviewers read-only and keep
  workers from outward commands; on
  Cursor it dispatches `Task` subagents; elsewhere it points to the
  passive driver. Use when the user asks to "orchestrate this plan",
  "delegate exec groups", "run the plan unattended", "run plan in parallel
  where possible across repos / worktrees", or wants the cascade run
  automatically rather than stopping at each handoff.
---

# personal-plan-orchestrate

Active counterpart to [`personal-plan-model-tiers`](../personal-plan-model-tiers/SKILL.md).
Both drivers tag via the shared
[`personal-plan-tag-tiers`](../personal-plan-tag-tiers/SKILL.md) skill and
group the tagged steps into waves with the same no-thrash rule. The passive
skill inserts STOP markers and waits for a human to swap models at every
tier boundary. This skill dispatches the next wave to subagents on the
right model and continues, pausing only where the plan's recorded mode
says to stop.

This file is the harness-neutral core: what a run is, the kickoff and its
mode, the gates, the loop, the handoff, and how to tell which harness you
are on. The steps that differ by harness (the dispatch call, its arguments,
the hooks that check it, the run's result, the token tally) are in
[`adapters/claude-code.md`](adapters/claude-code.md) and
[`adapters/cursor.md`](adapters/cursor.md). Once detection picks the
harness, read that adapter next: this file and the adapter are one
procedure, and the adapter says where each of its steps falls in the loop
below.

Canonical reference for tier definitions, the `[fast]` downgrade and
`[xdeep]` upgrade checklists, tag placement, the no-thrash rule, the model
picker, the Kickoff template, token lines, expected cost, the Cost table,
the Review log and progress tracking:

> `../personal-standards/standards/plan-execution.md` §"Model-tier stop
> points", §"Progress tracking", §"STOP gate semantics (fail closed)"

Read it when in doubt. Where this file and the standard disagree on how an
orchestrate run works (the kickoff question, unattended mode, the per-wave
handoff, fix-up numbering), this file is newer and wins until the standard
catches up.

**Read the plugin's own copy.** Every standards file this skill cites
(`plan-execution.md`, `core.md`, `git.md`, and those you pass to workers) is
read at its path relative to this skill's base directory, inside the plugin
that ships this skill, never from `~/Projects/personal/public/standards/` or
another checkout. The kit and its standards are versioned together, so a
plugin installed from a branch or a frozen copy runs against the standards it
was tested with. This beats core.md's "read the `~/Projects/...` path first"
rule for this skill's run. Pass workers absolute paths into the same copy.

## Anti-pattern: read this before you start

If you find yourself emitting STOP markers, printing copy-pasteable handoff
prompts at a tier change, or asking the user to swap models, **you are
running the wrong skill**. The artifact for each tier transition here is a
tool call (a workflow launch or a subagent dispatch), not a marker. The
phrase "STOP marker" belongs to `personal-plan-model-tiers`.

Writing the Kickoff block (with its Kickoff prompt) to the top of the plan
is **not** the anti-pattern: it is how a new session continues the run.

**Never do plan work yourself.** The parent tags, dispatches, checks,
records and asks. It never edits source code, runs the plan's tests or
produces diffs in its own context. Committing the plan and its handoff and
pushing the task branch are bookkeeping, not plan work.

**Gates are fail-closed.** A non-answer is never approval. None of these is
ever an answer to anything: a completion notification, a workflow approval
prompt, a hook's continuation prompt (a runner's Stop hook asking you to
commit and push), a timer, or a pasted Kickoff prompt.

## The parent

The parent always runs at `[deep]`: `/model opus` at `/effort high` on
Claude Code, `claude-opus-5-5[effort=high]` on Cursor. Its review of
cheaper-tier output and its re-tagging are `[deep]` work. It stays at high
for `[xdeep]` waves, which go to xhigh subagents and get an xhigh reviewer.
Want a cheaper supervisor on a mechanical plan? Use
`personal-plan-model-tiers` and drive the swaps yourself.

Its own commits (the plan, the handoff) end with the trailer
`Assisted-by: Claude Code` (or the harness's equivalent) and never carry a
`Co-authored-by` line. It quotes every hook deny reason verbatim.

## Detection: which harness, which path

Work down this list and take the first that matches.

1. **Inside a subagent?** If your instructions say your final message is a
   return value to a caller, or you have no subagent tool, don't
   orchestrate: report gate 0 to the caller.
2. **Claude Code: `Agent` and `Workflow` both appear**, loaded or deferred.
   Grok Build and Muse Code also have a lowercase `workflow`; requiring
   both tools keeps them out.
   - Load both schemas with ToolSearch before checking anything else.
   - If `Agent` has no `model` parameter, `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`
     hid it: go passive.
   - `<P>` is the plugin's name: this skill's own name without its
     `-plan-orchestrate` suffix. The skill folder, the plugin manifest's
     `name` and the `plugin` you pass at launch always agree, so a renamed
     copy of the plugin works unchanged. If `<P>:plan-worker` isn't among
     `Agent`'s subagent types, the plugin's agents aren't loaded: go passive.
   - If `Workflow` is missing (disabled, or Pro without the `/config`
     opt-in), use the **Agent path** (`adapters/claude-code.md`). It sets
     each tier's effort per call, so if `Agent` has no `effort` parameter
     (Claude Code before v2.1.292), go passive.
   - Otherwise use the **workflow path**: you will **call the Workflow
     tool** to launch the `<P>:plan-segment` workflow, one launch per
     dispatch unit. Confirm the workflow exists from the skills list (it is
     listed there as `<P>:plan-segment`), not from the Workflow tool's
     schema, which on the web lists no plugin workflows. If it isn't
     listed, launch it by name anyway; an unknown-workflow error is gate 0,
     and then use the Agent path.
3. **Cursor: `Task` with a `model` parameter, and no `Agent`** →
   `adapters/cursor.md`. Cursor imports Claude plugins and may list the
   `<P>:plan-*` agents with `model: inherit`; never dispatch them there.
4. **Codex (`spawn_agent`), Grok Build (`spawn_subagent`), Gemini CLI
   (`invoke_agent`), Muse Code (`subagent_spawn`)**, or nothing that
   matches: this skill doesn't drive them yet. Recommend
   `personal-plan-model-tiers`, and stop until Gary answers.

`K` below is the absolute path of this skill's `scripts/` folder (Claude
Code prints the skill's base directory when it loads it). Shell state
doesn't carry over between tool calls, so write `$K`, `$C` and the like out
as absolute paths in each command. Other files this skill cites:
`core.md` is `../personal-standards/core.md`, and `git.md` is
`../personal-standards/standards/git.md`. "Decision N" names one of Gary's
recorded design decisions; the rule it labels is stated where it is cited.
The scripts are harness-neutral Python 3:
- `plan_state.py <plan>`: the next dispatch unit and every gate in front of
  it, split into `stops` and `checkpoints` by the recorded mode, plus the
  mode record, the cost guard and `errors` (gate 0). It reads only the plan.
- `check_wave.py snapshot <dir>...` before a launch and `check_wave.py check`
  after it: commit shape, trailers, step coverage, scope.
- `token_tally.py` (Claude Code): token lines from the session's transcripts.

## Tiers and models

| Tier | Claude Code worker | Claude Code reviewer |
|---|---|---|
| `[xdeep]` | `<P>:plan-worker`, Opus xhigh | `<P>:plan-reviewer`, Opus xhigh |
| `[deep]` | `<P>:plan-worker`, Opus high | `<P>:plan-reviewer`, Opus high |
| `[exec]` | `<P>:plan-worker`, Sonnet high | `<P>:plan-reviewer`, Opus high |
| `[fast]` | `<P>:plan-worker`, Haiku low | `<P>:plan-reviewer`, Opus high |
| Fable step-up (gates 6 and 7) | `<P>:plan-worker`, Fable xhigh | `<P>:plan-reviewer`, Opus xhigh |

The workflow sets these itself. `[exec]` never runs past high: a stalled
`[exec]` group re-tags to `[deep]`. `max` runs an `[xdeep]` or Fable worker
at max, only on a task type with a measured gain, and needs a gate-7
approval in every mode; on any other tier it is gate 0. No ultracode in orchestrate: an audit-shaped
`[xdeep]` wave that needs its fan-out runs on the passive driver. Cursor's
slugs are in `adapters/cursor.md`. If the standard's model picker and this table
disagree, the picker wins and the kit's consistency check fails.

## Rules every run keeps

- **One dispatch unit per launch.** A unit is a wave, or the part of a wave
  inside one milestone, or a fix-up (`N-fix`, `N-fix2`, ...). `plan_state.py`
  names it. Never batch two waves.
- **One subagent per git working directory.** Groups in distinct working
  directories (separate repos, or `git worktree`s of one repo) run in
  parallel; within one directory, serially. Gary opts into in-repo
  parallelism by creating worktrees before he invokes the skill.
- **One read-only reviewer per working directory per unit**, at the
  author's tier: Opus high, or Opus xhigh after an `[xdeep]` unit. On
  Cursor, until its phase 3, the parent reviews below `[xdeep]` inline
  (`adapters/cursor.md`).
- **Task branches only** (below). Subagents commit each finished step and
  never push; the parent pushes.
- **The plan and its handoff are committed and pushed** at kickoff and
  after every wave, before any halt, question or launch.
- **While a run works, write nothing to the tree**, commit nothing and push
  nothing. The plan is tracked, so an edit shows up as a new dirty path to
  `check_wave.py`. Reply to anything that arrives with one line.
- **Outward actions wait for Gary in every mode:** opening or merging a PR,
  pushing a tag, deleting a remote branch, deploying, publishing a release
  or a package, posting anywhere outside the branch and the chat, and
  permission prompts. Workers never take one (`contract.md` item 8).
- **A compaction changes nothing.** The plan, the handoff, the snapshot
  files and the run record are the state, not the chat. After a `/compact`
  (Gary's or automatic), re-read the plan's Status and the handoff before
  acting, and find a run in flight by its notification. A compaction never
  answers, confirms or takes back anything.
- **What this procedure doesn't cover:** take the conservative choice, and
  list it under **Deviations from plan** in the handoff.

## Files a run keeps

- **The plan:** `specs/handoffs/plan-{topic}-{word}.md` in the repo that
  holds it, tracked on the task branch. A plan written in `.scratch/` moves
  there at kickoff.
- **The handoff:** `handoff-{topic}-{word}.md` beside it, same
  `{topic}-{word}`. Both are removed or promoted to durable docs before the
  PR merges (core.md "Runner scratch rides the branch").
- **Where nothing can be pushed** (decision 11, a workstation only, gated
  only): a plan in no git repo, such as a cross-repo plan in a plain folder
  of sibling repos, stays with its handoff in that folder's `.scratch/`,
  refreshed after every wave and never committed (the folder may sit inside
  another repo's ignored path); a plan in a repo with no remote is
  committed in `specs/handoffs/` and not pushed, and so is a working
  directory with no remote. Unattended needs the plan in a repo with a
  remote, so there the kickoff question proposes gated and says why.
- **Worker artifacts:** `<workdir>/.scratch/orchestrate-{plan-name}-{wave-n}-{task-id}.md`,
  gitignored. `{wave-n}` is the unit's label: `2`, `2-fix`, `2-fix2`;
  `{task-id}` is the group id with every run of other characters than
  letters, digits, `.`, `_` and `-` turned into `-` (`repo-b-m1-s4-s5`). An
  automatic retry writes the same path.
- **Snapshots:** `<plan repo>/.scratch/orchestrate-{plan-name}-{wave-n}-snapshot.json`
  (in a plain folder, its `.scratch/`), so a session that compacted finds
  them.

## Task branches

Orchestrate runs only on a task branch, on every machine, in both modes:
never `main`, `master`, `release/*`, the remote's default branch, a
detached HEAD, or Gary's own branch. Check each working directory and the
repo that holds the plan, each on its own (git.md "Task branches and shared
branches"), and the git email in each (core.md "Verify git email").

- **Find or cut one per repo.** Where the checked-out branch isn't a task
  branch, cut one per core.md "Cut a task branch": `feature/<topic>-<word>`
  from the plan's name, `git switch -c <branch> --no-track`, then
  `git push -u origin <branch>` at once. Each repo that needs one gets the
  same name unless it is taken there.
- **A runner** (cloud or self-hosted) works on the branch its system prompt
  assigns. It switches to it (`git switch <it>`, or `git switch -c <it>
  --no-track` when it doesn't exist) and pushes it before saving anything,
  without asking, and says which branch it started on and which it works on.
- **A workstation** names the branch in the kickoff question and commits
  nothing before the answer: the answer to the kickoff question is Gary's
  yes to cut it. Then it cuts and pushes; uncommitted plan and handoff
  edits ride along.
- **A declined cut** (`gated, but stay on main`) dispatches nothing. Re-ask
  once, naming the two ways on: cut the branch, or run
  `personal-plan-model-tiers` on the current branch under core.md's
  shared-branch rules, with the plan back in `.scratch/`.
- In every repo with a remote and no `refs/remotes/origin/HEAD` (a cloud
  checkout has none), run `git remote set-head origin --auto`, so the
  default branch is known. The Claude Code hook denies without it.

## Kickoff and re-entry

[`kickoff.md`](kickoff.md) has the runner signals, the kickoff steps, the
kickoff question and how to read and record its answer, the Kickoff
prompt, and what a session does on a plan that already has a Kickoff
block with a `mode:` line. Read it before a kickoff, and in any session
that finds such a block, before acting. Gary's whole next message is the
answer, a paste or a non-answer confirms nothing, and nothing dispatches
while Status reads `BLOCKED`.

## Gates

`plan_state.py` derives every gate from the plan in every mode; the mode
only decides which ones stop. Gate names are `gate-<N>` in its output and
`BLOCKED at gate <N>` in Status.

| Gate | Fires when | Gated | Unattended |
|---|---|---|---|
| mode | No confirmed kickoff answer | Stops | Stops |
| 0 | A plan or launch error: tagging, markers, the Kickoff prompt, the mode record's signal, a missing Cost table Total (unattended) | Stops | Stops |
| 1 | A failed, crashed or unreviewed group | Stops | One automatic retry inside the run, then stops |
| 1 | A worker's `needs_info` (a fix-up worker's too) | Stops | Stops at once |
| 1 | A `check_wave.py` failure that isn't a scope breach | Stops | Automatic fix-up `N-fix` |
| 1 | A scope breach (`gates.md`) | Stops | Stops (decision 10) |
| 1 | A worker's disclosed breach, blocked or ran (`gates.md`) | Stops | Stops, and so does its fix-up |
| 1 | A second or later CONCERNS or failed check in a row on a group | Stops | Automatic fix-up `N-fix2` ..., up to the cap (2 per group, decision 3); the next failure stops |
| 2 / 3 | A `[deep]` or `[xdeep]` unit right after an `[exec]` / `[fast]` one | Stops | Checkpoint |
| 4 | A unit in another milestone | Stops | Checkpoint; on a project with `specs/`, write the milestone handoff first (core.md) |
| 5 | The canary: the first launch of a session runs only its first group, when its unit has more than one | Stops | Checkpoint once that group passes `check_wave.py` and its review, fix-ups included; the rest of the wave then launches |
| 6 | A step-up to a stronger model or effort | Stops | Checkpoint for the in-run retry into `[exec]` or `[deep]`; stops for `[xdeep]` or Fable |
| 7 | The first unit of an `[xdeep]` wave, and every fix-up of one | Stops | Checkpoint on a wave the Cost table planned (decision 2); stops for unplanned `[xdeep]` work (a fix-up, a re-plan row, a step-up), drafts and `max` |
| guard | Projected spend passes the guard | Stops | Stops |
| any | Status reads `BLOCKED at gate N` | Stops | Stops |

The rest of the gate rules (no canary on a one-group unit, how
checkpoints are logged, automatic retries, fix-ups and their numbering,
the cost guard, scope breaches and waivers) are in [`gates.md`](gates.md).
Read it whenever `plan_state.py` reports a stop or a checkpoint, the next
unit is a fix-up, a check fails, or a worker discloses a breach.

## Each unit

1. **Save first:** the plan and its handoff are committed together and
   pushed (in a plain folder, refreshed in `.scratch/`). On Claude Code the
   hook denies a launch otherwise.
2. **Run `python3 $K/plan_state.py <plan>`.**
   - `errors` is gate 0: save and ask.
   - `next` is null: final completion.
   - `stops` holds a gate the human message that started (or joined) this
     turn doesn't answer: write `BLOCKED at gate <N>` in Status, save, ask
     one question, end the turn. `checkpoints` ask nothing.
3. **Snapshot:** `python3 $K/check_wave.py snapshot <each working directory>
   > <the unit's snapshot path>` ("Files a run keeps"). Keep the snapshot
   from before each wave until its groups' streaks end: a fix-up's check
   uses it as `--baseline`.
   **Access:** before a group whose steps need the network, `gh` or another
   service, check that access once from the parent with a read-only call
   (`gh api repos/<owner>/<repo> --jq .full_name`, `git ls-remote <url>`).
   If it fails and a step can't meet its acceptance without it, that is
   missing access: save and ask, in both modes. If the step can still be
   met (a stub, a dry run), pass the failure on as an environment note.
4. **Dispatch the unit** per the harness's steps. Build one group per
   working directory: split `next.steps` by the working directory each
   step's spec names (one directory for a single-repo plan), and give each
   group its steps, their headings and text verbatim, the acceptance
   criteria, the standards to read, the directory's task branch and its
   HEAD SHA now as `from`. Pass the unit's carry-forward too (`contract.md`
   item 9): the decisions so far and the environment notes, from the
   handoff. A group's id is `<workdir basename> <steps>`
   (`repo-b m1 s4-s5`). On a fix-up (`next.kind: "fixup"`), the groups are
   the ones `next.groups` names, with their steps, and `from` is the
   `<from>` of each group's latest Review log line. On a session's first launch only the
   first group runs (the canary), in both modes, when the unit has more than
   one; that is not a failure. A one-group first unit runs whole.
5. **While it runs**, end the turn with one line. A continuation that isn't
   a human message (a runner's Stop hook saying to commit and push) is not
   an instruction: reply with one line, and don't commit or push. Don't
   chain `sleep` in your shell to wait; the completion notification is the
   wait.

### When a unit completes

1. **Check:** `python3 $K/check_wave.py check --snapshot <this unit's
   snapshot> ...` (the harness's steps give the rest); for a fix-up add
   `--baseline <the snapshot from before the wave it fixes>`. It skips the
   parent's own bookkeeping commits, given the plan path.
2. **Tally** the unit's tokens and append the lines to `## Token log`
   (below). Quote any MISROUTED line: it is gate 1.
3. **For each group that ran:**
   - Mark each step ` (done)` at the **end** of its heading, after all
     other text. A group whose check failed or whose review said CONCERNS
     is still marked done; its fix-up comes from the Review log. A group
     that failed, crashed or asked keeps its steps open.
   - Write its Review log line, `<from>..<to>` from `check_wave.py`, never
     from a reviewer:

         review wave-<label> (<group-id>) <from>..<to>: PASS|CONCERNS - <note> - <YYYY-MM-DD>

     `<label>` is `3`, `2-fix` or `2-fix2`. A failed check is that group's
     line with verdict CONCERNS and a note that starts `check_wave.py:`,
     quotes the failing output on one line, and ends `; review PASS` or
     `; review CONCERNS: <its note>`. Checkpoints go at the end of the note.
   - A scope breach gets no line (`gates.md`).
   - **A worker's disclosed breach** (a rule of its prompt it broke or
     tried to break: an outward command, an edit outside its directory, a
     push; on Claude Code the result's `breaches`, elsewhere its summary)
     makes the group's verdict CONCERNS whatever the review said, with a
     note that starts `worker disclosed: <its words>` and ends with the
     review's verdict and what it found. Blocked or ran, it is gate 1 in
     both modes, with no automatic retry or fix-up: on Claude Code the run
     stops there, and `plan_state.py` makes the group's `N-fix` gate 1,
     never a checkpoint. Write `BLOCKED at gate 1`, save, and ask, saying
     whether it ran and what, if anything, left the machine or the
     directory. Gary answers with the fix-up, a waiver, or a re-plan.
   - **Carry forward:** add a decision the group made that changes a later
     step's text (its review passed) to the handoff's "Decisions so far",
     quoted from its Review log line or the worker's `decided`; and every
     `env:` line in a worker's surprises to the handoff's "Environment
     notes".
4. **Update Status:** `<done>/<total> groups done | last review: wave-<label>
   PASS|CONCERNS | current: <next group> | updated <today>`, plus
   `| passed unattended: <gates>` when any, `BLOCKED at gate <N>` at a stop,
   and `UNREVIEWED <sha>...` when worker commits weren't reviewed. Update
   the todo list.
5. **Refresh the handoff, commit and push:** the plan and the handoff in one
   commit whose subject has no step ID; push every working directory with a
   remote (with a lease after a reword fix-up). This happens in both modes,
   before anything below.
6. **Go on:**
   - The unit passed, or failed in a way that isn't a stop for this mode:
     back to step 1 of "Each unit" in this same turn, with no approvals.
     Unattended, a failed check that isn't a scope breach doesn't stop:
     `plan_state.py` makes the fix-up the next unit, a checkpoint until the
     cap is spent.
   - The unit stopped at a gate, or a check or scope breach stops here:
     save with `BLOCKED at gate <N>` and any worker questions (step 5 above
     already did), then ask one question that names each repo's commit
     range and the next unit, with the short handoff summary, and wait: a
     choice dialog where the harness has one (its options name the next
     unit, `Stop here`, and any step-up or waiver the gate allows), else
     text, ending the turn.
   - `plan_state.py` has no `next`: final completion.

### After an answer

In the turn Gary's answer starts (a typed reply) or joins (a dialog's
answer): clear `BLOCKED`, then go through "Each unit" from step 1 (refresh
the handoff, commit, push, `plan_state.py`, a fresh snapshot) and launch the
unit with his message, or the label he picked, as the approval, verbatim, and each gate approved for the launched unit's wave: every gate
the last run stopped at (gate 5 after a gated canary, though Status no
longer shows it) and every gate in `plan_state.py`'s `stops`. Never approve
`gate-0` or `gate-mode`: they clear only from the plan (fix the plan, or
record the kickoff answer), and nothing accepts an approval for them. A
`needs_info` group also carries `answer: {question, answer}`, the answer
being the same words. A gate answer counts only in the turn his message
starts or joins; never reuse it in a later turn. Gated, an answer at gate 1
may also be a step-up (gate 6, plus gate 7 into `[xdeep]` or Fable), a
re-plan (new waves take the next unused numbers, with their markers after
the last marker in the file, since gate 0 checks the numbering in file
order, and get Cost table rows with expected `—`), or a waiver.

## Mode switch

A short human message (10 words or fewer) that names `gated` and not
`unattended` switches to gated. Rewrite the mode line's ` | confirmed ...`
part with today, this session and his words, and the prompt's mode line to
`Run in gated mode.`; commit and push. A switch to unattended takes his
explicit words naming it, recorded the same way; it also answers a pending
gate that unattended would pass as a checkpoint (relaunch with his words as
the approval), never one that stops in both modes. A message that holds a prompt mode line is a paste and switches
nothing. If a run is in flight, reply with one line and record the switch
first thing in the turn its completion starts; the run finishes as
launched, and from then on the new mode applies. Nothing moves: the plan
and handoff stay in `specs/handoffs/` in both modes.

## Questions, and saving before them

Unattended, the parent asks only for what is Gary's:
- an ambiguous spec (a worker's `needs_info`, or a choice the plan leaves
  open); missing access or credentials (a `needs_info`, a push refused by a
  ruleset, a git email mismatch);
- a choice with materially different outcomes: a re-plan, dropping a wave,
  a step-up past the automatic one, the guard;
- a third failure on a group, a scope breach, a worker's disclosed breach,
  gate 0, and gate 1 after the automatic retry or at once;
- outward actions, including the PR at completion.

Gated mode asks all of these, plus every gate, every failed check and every
repeat CONCERNS.

**Save, then ask** (core.md "Save before you wait"), in this order:
1. Update the plan: `(done)` markers, the Review log, the Token log
   (including the parent's own open stretch, "Token tally"), and Status's
   `BLOCKED at gate N`. This holds for every save that ends a turn to wait
   or ends the session: a gate, a question, the kickoff question, the halt
   for a new chat, and final completion.
2. Refresh the handoff with the question verbatim.
3. Commit the plan and the handoff. On a runner, commit everything in the
   tree, a partial step under an honest subject; a workstation stages only
   its own paths.
4. Push every working directory that has a remote, in both modes. Worker
   commits not yet reviewed are pushed too, labeled `UNREVIEWED` in Status,
   the handoff and the question (decision 12).
5. Ask one question, with the short handoff summary: a choice dialog
   where the harness has one and the answers are a fixed set, else plain
   text, ending the turn.

A usage limit is the one stop where this can't run: the run fails, its
commits stay unreviewed and unpushed, and the pushed handoff is one wave
behind. The next human turn reconciles from git before relaunching. A
scheduled relaunch after the limit resets may run checkpoints, but never
answers a gate.

## The handoff and its summary

**The handoff** (`handoff-{topic}-{word}.md` beside the plan) is refreshed
before every commit of the plan, in both modes. It holds: the branch (every
repo's, when they differ), the mode, what's done with each group's commit
range, the Review log verdicts, the fix-ups, retries and checkpoints with
their reasons, the Token log total against the Cost table's expected total,
the next unit, how to resume ("paste the plan's Kickoff prompt"), and any
pending question verbatim. Two carry-forward sections ride along, quoted
into each later launch (`contract.md` item 9): **Decisions so far** (decisions a
passed unit made that change later steps' text) and **Environment notes**
(workarounds the run's agents found, such as a tool version or a missing
binary). At a stop and at completion it is final: the
same fields plus the question or the PR ask, and at completion the
Completion summary.

**The short handoff summary**, about six lines, ends every message that
stops, asks, or ends the run, in both modes: the branch and the handoff
path; the waves and fix-ups done with their ranges; spend against expected;
the next unit or the question. It goes in the chat, and the handoff on the
branch; posting either anywhere else is an outward action.

## Token tally

Every token figure is a token line (standard §"Token line format"),
appended to `## Token log` below its counting header as soon as it exists:
- **Workers and reviewers:** `wave-<label> <group-id>` and
  `review-wave-<label> <group-id>`, per model; a fix-up's lines use its
  label (`wave-2-fix2`); a retry keeps its wave's.
- **The parent:** `orchestrator-kickoff <plan name>` for the session that
  kicked off, up to its first launch; `orchestrator-resume <plan name>` for
  any later session (a pasted Kickoff prompt, a re-entry), up to its first
  launch; then `orchestrator-wave-<N> <group-id>` for each stretch after a
  launch, where wave N is the unit that launch carried. Windows don't
  overlap, so the guard never counts the parent twice.
- **The open stretch.** Every save that ends a turn to wait or ends the
  session ("Questions, and saving before them") first appends the parent's
  stretch since its last line, up to now, under that stretch's row. If the
  same session goes on (Gary answers here), the next line for the same row
  covers the longer span and replaces the one written at the stop (the
  standard's replace rule). So a session that ends at a gate, at the
  kickoff's halt for a new chat, or at completion leaves no parent spend
  unlogged.

Price each line at its own model's list rates (API-equivalent, whatever the
harness bills), never a blended rate. At a stop, print the lines so far and
their total. At completion, add the Cost table's actual columns from the
Token log.

## Final completion

When `plan_state.py` has no `next` and the last review passed:
1. Mark every step done and flip the todos; replace the Kickoff marker with
   `--- KICKOFF: plan complete ---` and Status with `<n>/<n> groups done |
   completed <date>`.
2. Replace the `(output est.)` lines of sessions that have ended with their
   `cost-state` totals (standard §"Final completion"), then add the Cost
   table's actual columns. A `cost-state` that covers several rows (the
   parent's own session, with every wave it launched) never replaces their
   lines; when one is found, at completion or by any later turn while the
   plan still exists, add one line under the Cost table, `Exact
   (cost-state, session <id>): ~$<costUSD>, covering <rows>.`, and leave
   the lines and the actual columns as they are.
3. Append the Completion summary (standard §"Final completion"), with every
   checkpoint, retry and fix-up under **Deviations from plan**.
4. Write the final handoff; commit; push.
5. Print the completed Cost table and the Completion summary, then ask
   (a choice dialog where the harness has one: `Open the PR`, `Not yet`)
   whether to open a PR, naming the cleanup commit (remove the plan and the
   handoff, or promote what's durable to `specs/`), with the short handoff
   summary. Wait.

## Subagent context contract

On the Claude Code workflow path, `plan-segment.js` writes every worker
and reviewer prompt from the group and `args`. On Cursor and the Agent
path you write them: follow [`contract.md`](contract.md), items 1-9.

## Harness steps

- **Claude Code:** [`adapters/claude-code.md`](adapters/claude-code.md), the
  workflow launch and its arguments, the three hooks, the run's result, the
  Agent path, runners and limits, permissions and the token tally.
- **Cursor:** [`adapters/cursor.md`](adapters/cursor.md), the harness gate,
  the `Task` dispatch, the boundary rows and the heuristic tally.

## Out of scope

- Plan work in the parent's own context (above).
- Ultracode in the parent: it orchestrates every task in the session.
- Codex, Grok Build, Gemini CLI and Muse Code: the passive driver, until
  their adapters ship.
- Merging with `personal-plan-model-tiers`. The passive-vs-active split is
  intentional; Gary picks oversight by picking the skill.
