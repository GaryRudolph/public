---
name: orch-spike-plan-orchestrate
description: >-
  Actively orchestrate a tiered plan: the `[deep]` Opus parent dispatches
  each wave to subagents on the tier's model and keeps control, pausing
  only where the plan's recorded mode stops (gated: every STOP gate;
  unattended: only questions, failures, premium work and the cost guard).
  Same `[xdeep]` / `[deep]` / `[exec]` / `[fast]` tagging and no-thrash rule
  as `orch-spike-plan-model-tiers`. Runs on a task branch and commits and
  pushes the plan and a handoff after every wave. On Claude Code it calls
  the Workflow tool to launch the plugin's plan-segment workflow (phase 1:
  dogfood); on Cursor it dispatches `Task` subagents; elsewhere it points
  to the passive driver. Use when the user asks to "orchestrate this
  plan", "delegate exec groups", "run the plan unattended", "run plan in
  parallel where possible across repos / worktrees", or wants the cascade
  run automatically rather than stopping at each handoff.
---

# orch-spike-plan-orchestrate

Active counterpart to [`orch-spike-plan-model-tiers`](../orch-spike-plan-model-tiers/SKILL.md).
Both drivers tag via the shared
[`orch-spike-plan-tag-tiers`](../orch-spike-plan-tag-tiers/SKILL.md) skill and
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

> `../orch-spike-standards/standards/plan-execution.md` §"Model-tier stop
> points", §"Progress tracking", §"STOP gate semantics (fail closed)"

Read it when in doubt. Where this file and the standard disagree on how an
orchestrate run works (the kickoff question, unattended mode, the per-wave
handoff, fix-up numbering), this file is newer and wins until the standard
catches up.

## Anti-pattern: read this before you start

If you find yourself emitting STOP markers, printing copy-pasteable handoff
prompts at a tier change, or asking the user to swap models, **you are
running the wrong skill**. The artifact for each tier transition here is a
tool call (a workflow launch or a subagent dispatch), not a marker. The
phrase "STOP marker" belongs to `orch-spike-plan-model-tiers`.

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
`orch-spike-plan-model-tiers` and drive the swaps yourself.

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
     opt-in), use the **Agent path** (`adapters/claude-code.md`).
   - Otherwise use the **workflow path**: you will **call the Workflow
     tool** to launch the `<P>:plan-segment` workflow, one launch per
     dispatch unit. Confirm the workflow exists from the skills list (it is
     listed there as `<P>:plan-segment`), not from the Workflow tool's
     schema, which on the web lists no plugin workflows. If it isn't
     listed, launch it by name anyway; an unknown-workflow error is gate 0,
     and then use the Agent path.
   - **Phase 1: dogfood.** The Claude Code path is new and is being proven
     on real plans. Say so in the kickoff question, and report anything the
     procedure below doesn't cover as a deviation.
3. **Cursor: `Task` with a `model` parameter, and no `Agent`** →
   `adapters/cursor.md`. Cursor imports Claude plugins and may list the
   `<P>:plan-*` agents with `model: inherit`; never dispatch them there.
4. **Codex (`spawn_agent`), Grok Build (`spawn_subagent`), Gemini CLI
   (`invoke_agent`), Muse Code (`subagent_spawn`)**, or nothing that
   matches: this skill doesn't drive them yet. Recommend
   `orch-spike-plan-model-tiers`, and stop until Gary answers.

`K` below is the absolute path of this skill's `scripts/` folder (Claude
Code prints the skill's base directory when it loads it). Shell state
doesn't carry over between tool calls, so write `$K`, `$C` and the like out
as absolute paths in each command. Other files this skill cites:
`core.md` is `../orch-spike-standards/core.md`, and `git.md` is
`../orch-spike-standards/standards/git.md`. "Decision N" names one of Gary's
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
| `[xdeep]` | `<P>:plan-worker-xdeep`, Opus xhigh | `<P>:plan-reviewer-xdeep`, Opus xhigh |
| `[deep]` | `<P>:plan-worker`, Opus high | `<P>:plan-reviewer`, Opus high |
| `[exec]` | `<P>:plan-worker`, Sonnet high | `<P>:plan-reviewer`, Opus high |
| `[fast]` | `<P>:plan-worker`, Haiku (no effort setting) | `<P>:plan-reviewer`, Opus high |
| Fable step-up (gates 6 and 7) | `<P>:plan-worker-xdeep`, Fable xhigh | `<P>:plan-reviewer-xdeep`, Opus xhigh |

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
- **One read-only reviewer per working directory per wave**, at the
  author's tier: Opus high, or Opus xhigh after an `[xdeep]` wave.
- **Task branches only** (below). Subagents commit each finished step and
  never push; the parent pushes.
- **The plan and its handoff are committed and pushed** at kickoff and
  after every wave, before any halt, question or launch.
- **While a run works, write nothing to the tree**, commit nothing and push
  nothing. The plan is tracked, so an edit shows up as a new dirty path to
  `check_wave.py`. Reply to anything that arrives with one line.
- **Outward actions wait for Gary in every mode:** opening or merging a PR,
  pushing a tag, deleting a remote branch, deploying, posting anywhere
  outside the branch and the chat, and permission prompts.

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
  gitignored. `{wave-n}` is the unit's label: `2`, `2-fix`, `2-fix2`.

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
  `orch-spike-plan-model-tiers` on the current branch under core.md's
  shared-branch rules, with the plan back in `.scratch/`.
- In every repo with a remote and no `refs/remotes/origin/HEAD` (a cloud
  checkout has none), run `git remote set-head origin --auto`, so the
  default branch is known. The Claude Code hook denies without it.

## Runner signals

Read them with one shell call and write them as fixed tokens, so a later
session can compare its own environment with the record:

    env | grep -E '^(CLAUDE_CODE_REMOTE|CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE|CI|GITHUB_ACTIONS)='

| Signal | Tokens |
|---|---|
| `CLAUDE_CODE_REMOTE=true` | `runner=cloud`, or `runner=self-hosted` with `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=self_hosted` |
| `CI=true` or `GITHUB_ACTIONS=true` | `runner=ci`: nobody can reply, so the invoking words are the answer |
| A Cursor cloud agent (the Cloud MCP's `run-info` tool, or its own pushed branch) | `harness=cursor runner=cloud` |
| none of these (Remote Control included) | `runner=none`: a workstation |

`harness` is `claude-code`, `cursor`, `codex`, `grok`, `gemini` or `muse`.
A runner proposes unattended; a workstation proposes gated. Gary's answer
decides. `CLAUDE_CODE_SESSION_ATTENDED` is undocumented; ignore it.

## Kickoff (once per plan)

1. **Identify the plan:** a named path, else the most recent `plan-*.md` in
   `specs/handoffs/` or `.scratch/`, else the plan in the conversation. If
   the plan already has a Kickoff block with a `mode:` line (a run under
   way, or a kickoff waiting for its answer), don't run these steps: go to
   "A new session on a plan already kicked off", which covers a pasted
   Kickoff prompt and a session started any other way.
2. **Tag, group and mark waves.** If the plan isn't tagged, run
   `orch-spike-plan-tag-tiers`. Then the no-thrash grouping pass: consecutive
   same-tier steps form a wave, and a short `[fast]` run (fewer than 3
   steps) folds into the adjacent `[exec]` wave **without rewriting any
   tag**. Check the ≤ constraint (every step's tag ≤ its wave's tier, and
   an `[xdeep]` wave holds only `[xdeep]` steps); a violation is gate 0:
   write no markers, ask. Then write `--- WAVE N [tier] ---` before each
   wave's first heading (skip when markers exist). Fix-up waves are never
   planned; they come from the Review log.
3. **Preflight:** the branch, email and `origin/HEAD` checks above, the
   runner signals, and `python3 $K/check_wave.py snapshot <each working
   directory>`, which must pass (it flags a `.scratch/` that isn't
   gitignored and reports each repo's attribution setting).
4. **Write the Kickoff block** at the top of the plan (the standard's
   active variant; replace an existing one, never add a second). Its model
   row is always the `[deep]` Opus row. Its `Status:` line starts
   `0/N groups done | last review: — | current: <first group> [<tier>] |
   updated <today>`. Add `review: every-wave (log-only)`. Then the mode
   line, right under `Status:`:

       mode: pending | proposed <gated|unattended> (harness=<h> runner=<r>; <short note>) | guard 3x min $50 | fixups 2

   and set Status to `BLOCKED at gate mode | updated <today>`. The prompt
   gets no mode line yet (see "The Kickoff prompt").
5. **Write the Cost table** below the Kickoff block (standard §"Cost
   table"), labeled for the harness. Each wave row includes its review
   subagent: about 0.6× a medium step at Opus high, about 2× that at xhigh
   after an `[xdeep]` wave. The `orchestrator` row counts the parent: the
   kickoff, each wave's checks and bookkeeping (about $0.1 a wave for the
   handoff refresh, commit and push), and the gate waits the proposed mode
   will have (gated: the canary and every gate 2, 3, 4 and 7 the plan
   crosses, gates asked together counting once; unattended: one, the
   kickoff answer), plus a new-chat start-up on a workstation. Unattended
   needs the Total row: the guard reads it.
6. **Write the counting header** at the top of `## Token log` (standard
   §"Token line format"), for the harness the Cost table names.
7. **Save:** move the plan to `specs/handoffs/` (unless decision 11 keeps it
   in a plain folder's `.scratch/`), write the handoff beside it ("The
   handoff and its summary"), and on a task branch commit both in one
   commit whose subject has no step ID, then push. A workstation still
   waiting to cut commits nothing.
8. **Ask the kickoff question and end the turn** (below).
9. **Record the answer** in the next human turn (below), then save again:
   a workstation cuts its branch first; refresh the handoff with the mode,
   commit the plan and handoff, push.
10. **Halt or dispatch.** On a runner, or when the answer adds `here`: print
    the kickoff summary (waves, expected total, gates) and go to "Each
    unit". Otherwise print the Kickoff prompt, the kickoff summary and the
    short handoff summary, and halt for a new chat (the default on a
    workstation).

Seed the harness todo list (one todo per wave, first `in_progress`) when
you start dispatching, in this session or the new one.

### The kickoff question

One question, once per plan run, after the Kickoff, Cost table and
counting header are written and saved. It names the waves and their tiers,
the Cost table's expected total, the gates the plan crosses (5 at the
canary; 2 or 3 before a `[deep]` or `[xdeep]` wave after an `[exec]` or
`[fast]` one; 4 at a new milestone; 7 before each `[xdeep]` wave, with its
cost), what each mode does, the guard's dollar limit, the handoff path,
and on a workstation the branch it will cut. It always carries the exact
words `Proposed mode: <mode>.` and ends with a line that starts `Reply`;
the Claude Code hook looks for both before it counts an answer. It ends
with the short handoff summary. On a runner:

    Plan plan-auth-otter: 4 waves, expected ~$26 API-equiv (Cost table above).
    Gates it crosses: 5 (canary, wave 1); 4 and 2 (before wave 3); 7 (before wave 4, [xdeep], ~$14).
    Runner detected (CLAUDE_CODE_REMOTE=true). Proposed mode: unattended.
      unattended: gates 2, 4, 5 and 7 are logged, not asked. A failed commit check or a
        CONCERNS gets an automatic fix-up, up to 2 per group. I stop to ask for information,
        at a plan error, a scope breach, a failure after one retry (at once on the [xdeep]
        wave), a group's third failed check or review, unplanned [xdeep] or Fable work, or
        projected spend past 3x expected or $50, whichever is higher (~$78).
      gated: every gate stops, and so does every failed check or repeat CONCERNS.
    Either way, after every wave I commit and push the plan and its handoff
    (specs/handoffs/handoff-auth-otter.md), and every message that stops or asks ends
    with a short handoff summary. Opening or merging a PR, tags, remote branch deletes,
    deploys and permission prompts wait for you.
    Reply unattended or gated.

On a workstation, the signal line says what was checked and names the
branch; the destination question folds in (there is no separate one):

    No runner signal (CLAUDE_CODE_REMOTE unset, no assigned branch). Proposed mode: gated.
    main is a shared branch, so the run goes on a new task branch, feature/auth-otter:
    your answer is the yes to cut it, and I push it at once.
    Reply gated or unattended; add here to orchestrate in this chat (default: new chat).

Propose gated, and say why, where unattended can't run: no remote for the
plan's repo (decision 11), or a harness with no hook to check it. On the
Claude Code path, add one line: `Claude Code path: phase 1 dogfood.`

An invoking message that names a mode ("orchestrate this unattended") only
sets the proposed mode; the question still runs, so Gary sees the waves,
the total and the gates before he opts in. Only under `runner=ci` do the
invoking words count as the answer: record them, print the kickoff summary
and start.

### Reading the answer

The answer is Gary's next message after the question, whole, and only
that. Read it like this:

- **Unattended** when it names `unattended` and not `gated`, asks nothing
  back (no `?`) and negates nothing (no, not, never, without, `n't`); or
  when it is a plain yes ("yes", "ok", "sure, go ahead") and the question
  carried `Proposed mode: unattended.` (decision 9).
- **Gated** when it names `gated`, or is a yes to a gated proposal. A yes to
  a gated proposal records gated, never unattended.
- **Re-ask** on anything else: a question back, a negation, "hmm", silence,
  a message that is the plan's Kickoff prompt or holds its mode line, or a
  declined branch cut (above).

`here` anywhere in the answer means orchestrate in this chat.

**Record it:** replace `pending` on the mode line with the mode, and append
` | confirmed <today> session <S>: <the whole answer, whitespace
collapsed>`. Gary's words come last on the line, so they may hold any
character; `guard` and `fixups` are read only from before `confirmed`, so
his words never set them. In the same edit add `Run in <mode> mode.` as the
Kickoff prompt's mode line and clear `BLOCKED` from Status. If the answer
picked the other mode, recompute the Cost table's orchestrator row before
any wave runs, and say so. `<S>` is this session's id (Claude Code:
`$CLAUDE_CODE_SESSION_ID`; without it, the basename of the newest
transcript in this project's `projects/<slug>/`, which is wrong when two
sessions share the folder, so check it is the transcript holding this
conversation). The Claude Code hook compares it with its own session id.

### The Kickoff prompt

The Kickoff block's `Prompt to paste into the next chat:` is how a new
session continues the run. After the answer it reads:

    In GaryRudolph/public, read specs/handoffs/plan-auth-otter.md. The plan is already tagged.
    On branch feature/auth-otter (task branch): subagents commit each finished step.
    Run in unattended mode.
    Run the orch-spike-plan-orchestrate skill from the top: walk to
    each tier boundary, dispatch subagents per the skill's procedure,
    and pause only where the recorded mode stops. Do not execute plan
    work inline. Update plan progress after each wave returns per the
    skill's procedure. The mode line above is the kickoff answer. If the
    Status line shows BLOCKED, re-post that question and wait; otherwise
    record the mode, print the kickoff summary and begin dispatching.

- **The plan line** names the repo as `<owner>/<repo>` from its origin URL
  (its folder name when it has no remote) and the plan's repo-relative
  path. A plan in no git repo uses `Read <absolute path>.`, and its prompt
  works only on that machine. `plan_state.py` reports gate 0 when no line
  names a repo and a plan.
- **The `On branch` line** names the plan repo's branch. When a repo's
  branch differs (the name was taken there), it lists each:
  `On branches public feature/auth-otter, api feature/auth-otter-quill (task branches): subagents commit each finished step.`
- **The mode line** is exactly `Run in unattended mode.` or `Run in gated
  mode.` on its own line, written with the answer and never before it.
  `plan_state.py` reports gate 0 when it doesn't match the confirmed mode.
- **What rewrites it:** after the answer, only a mode switch (its mode
  line) and a cloud session keeping its own branch (its `On branch` line).
  So the handoff's resume step is always "paste the plan's Kickoff prompt".

## A new session on a plan already kicked off

This section covers every session that finds the plan's Kickoff block
with a `mode:` line, whether Gary pasted the Kickoff prompt or not. Keep the plan's tagging, markers, Cost table and
counting header as they stand (re-entry adds rows for waves added since).

The paste counts only when a human message, whitespace collapsed, is the
plan's whole Kickoff prompt as committed, with its mode line; only its `On
branch` lines may differ. "run unattended", the mode line alone, or the
prompt plus "and skip the canary" is not a paste: ask the kickoff question.
A paste never answers a gate, a `needs_info` question, a waiver or the
kickoff question.

Three ways in:
- **(a) A new local session on the same machine**, usually right after the
  kickoff halted for a new chat. The clone is on the task branch already.
- **(b) A cloud session.** Claude Code on the web gives each session its own
  `claude/…` branch, cut from the default branch. If that branch has no
  commits of its own, fast-forward it to the prompt's branch
  (`git fetch origin && git merge --ff-only origin/<prompt branch>`), push
  it, and work there; in the confirmation commit rewrite the prompt's `On
  branch` line and the handoff's branch to yours. If it has commits of its
  own and doesn't hold the plan, stop at gate 0 and say to start a session
  from the prompt's branch.
- **(c) Another machine** (usually a workstation clone on `main`, where the
  plan doesn't exist): `git fetch origin`, read the plan with
  `git show origin/<b>:<path>` without switching, and ask the kickoff
  question with the switch folded in ("I'll switch to `<b>`; your answer is
  the yes to both"). After the answer, `git switch <b>` (a local branch
  tracking `origin/<b>`), then record the answer there.

Then, in this order:
1. **The plan's Status shows `BLOCKED at gate N`:** re-post that question
   verbatim and wait. The paste answers nothing.
2. **The prompt has a mode line, the plan's mode line is confirmed, and its
   `harness=` and `runner=` tokens equal yours:** replace the mode line's
   ` | confirmed ...` part with ` | confirmed <today> session <S> by Kickoff
   prompt: Run in <mode> mode.`, commit and push it (with the path (b)
   rewrite), print the kickoff summary with the spend so far, and dispatch
   without asking.
3. **Otherwise ask the kickoff question again** with a fresh proposal: the
   environment differs (another runner token, or another harness, which
   also recomputes the Cost table and refreshes the counting header for
   that harness), no mode was confirmed yet (a prompt copied before the
   answer), or path (c).

A session **not** started from a paste: a gated record carries over when
its `harness=` and `runner=` tokens still match yours (it relaxes nothing,
and this session's first launch is a canary that stops at gate 5): record
nothing new and go to "Each unit". An unattended record counts only in the
session that confirmed it, so ask the kickoff question again, quoting the
spend so far against the expected total. A `BLOCKED` Status is re-posted
first, either way.

**Re-entry with a run in flight.** If the handoff or Status shows a launch
whose result was never recorded, reconcile from git first (uncommitted and
unpushed work in each working directory), report it, and ask before
relaunching. A run that died with its session leaves no record; on Claude
Code the hook then refuses further launches in that session, so continue in
a new session from the pasted prompt.

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
| 1 | A scope breach (below) | Stops | Stops (decision 10) |
| 1 | A second or later CONCERNS or failed check in a row on a group | Stops | Automatic fix-up `N-fix2` ..., up to the cap (2 per group, decision 3); the next failure stops |
| 2 / 3 | A `[deep]` or `[xdeep]` unit right after an `[exec]` / `[fast]` one | Stops | Checkpoint |
| 4 | A unit in another milestone | Stops | Checkpoint; on a project with `specs/`, write the milestone handoff first (core.md) |
| 5 | The canary: the first launch of a session runs only its first group | Stops | Checkpoint once that group passes `check_wave.py` and its review, fix-ups included; the rest of the wave then launches |
| 6 | A step-up to a stronger model or effort | Stops | Checkpoint for the in-run retry into `[exec]` or `[deep]`; stops for `[xdeep]` or Fable |
| 7 | The first unit of an `[xdeep]` wave, and every fix-up of one | Stops | Checkpoint on a wave the Cost table planned (decision 2); stops for unplanned `[xdeep]` work (a fix-up, a re-plan row, a step-up), drafts and `max` |
| guard | Projected spend passes the guard | Stops | Stops |
| any | Status reads `BLOCKED at gate N` | Stops | Stops |

A first review CONCERNS (not a failed check) gets its `N-fix` without a
gate in both modes. Opening a PR, tags, remote branch deletes, deploys and
permission prompts wait in both modes; on a runner, commit and push before a
call likely to trip a permission prompt.

**Checkpoints are logged, not asked.** End the unit's Review log note with
them (`; passed unattended: gate 4, gate 2`; an automatic fix-up's
`; passed unattended: gate 1 (fix-up 2 of 2)`), keep the latest on the Status
line (`| passed unattended: gate 4, gate 2 before wave 3`), and list every
checkpoint, automatic retry and fix-up with its reason under **Deviations
from plan** in the handoff and the Completion summary.

**Automatic retries (unattended only, inside the run).** A worker with no
result, or a review that died, reruns once on the same tier (a dead review
reruns only the review). `failed` or `low_quality` reruns once a tier up,
into `[exec]` or `[deep]` only, logged as a gate-6 checkpoint. Never on an
`[xdeep]` or Fable unit, never on a step-up Gary approved, never for
`needs_info`. The retry keeps its wave's number and token row. A second
failure is gate 1. On Claude Code the workflow does this; elsewhere the
parent does.

**Fix-ups** come from the Review log, never from open steps. The k-th
CONCERNS line in a row for a group makes the next unit its fix-up, labeled
`N-fix` for the first and `N-fix<k>` after (`N-fix2`, `N-fix3`; never
`N-fix1`). A failed check is logged as a CONCERNS line, so it starts or
extends the same streak. A PASS ends the streak, and so does a WAIVED line.
When several groups of one wave have streaks, the longest goes first. A
fix-up's worker gets the failure verbatim, with the streak's earlier ones,
and its `from` is the `<from>` of the group's Review log line (the wave's
start), not HEAD:
- a review concern is fixed with new commits whose subjects start with the
  step ID they fix; earlier commits stay as they are;
- a failed check is fixed at its cause: a missing step commit is made (an
  empty one when the step changes no file), a by-product path is deleted or
  a path the group made is committed, and a rejected message (first line,
  `Co-authored-by`, missing trailer) is reworded on just the commits the
  check names by SHA: `git commit --amend` when HEAD is one of them,
  otherwise a non-interactive `git rebase` onto `<from>` (`GIT_SEQUENCE_EDITOR`
  and `GIT_EDITOR` set to commands) that keeps every other commit's message
  and content, the parent's bookkeeping commits included;
- a failed-check note that also carries `; review CONCERNS:` gets both
  instructions;
- the fix-up's reviewer checks the quoted failure itself too, not only the
  change.

A reword replays the commits after it with new SHAs, so after a fix-up that
rewrote pushed commits, push with `--force-with-lease --force-if-includes`.
Raising the cap (`fixups N` on the mode line) needs Gary's approval of
gate 1. Each fix-up gets a Cost table row with expected `—`, labeled with
its number (`2-fix2 [exec] repo-b m1 s4`), so it adds nothing to the guard's
projection until it has run.

**The cost guard**, before every unit, in both modes:

    projected = the Token log's dollars so far
              + the next unit's expected $ (its Cost table row; 0 once any step of
                that wave is done, which covers a canary's continuation and a split
                wave's later units; 0 for an unplanned row)
    stop at gate-guard when projected > max(guard × the Cost table's Total, floor)

With `guard 3x min $50`, a plan expected at $78 stops past $234, and one
expected at $10 past $50. A yes at the guard raises the multiple to the
next whole one above the projection, or to what Gary names; the raise needs
his approval of `gate-guard`. Unplanned premium work stops whatever the
spend.

**Scope breaches stop at gate 1 in both modes** (decision 10), since no
fix-up can repair them: edits in a directory with no group, a `from` that
is no longer an ancestor of HEAD (both in `check_wave.py`'s `scope`), and,
on a workstation only, a group's new uncommitted path (its `uncommitted`,
which may be Gary's own edit). Write `BLOCKED at gate 1`, no Review log line
for the group, leave its steps open, save, ask. On a runner, `uncommitted`
paths are an ordinary failed check that gets `N-fix`.

**A waiver.** At a gate 1 a streak raised, Gary may waive the concern
instead of approving the next fix-up. Log `review wave-N (<group-id>)
<from>..<to>: WAIVED - <Gary's answer, whitespace collapsed> - <date>`,
which ends the streak as a PASS does. The words must be his message
verbatim (the Claude Code hook checks); a paste never waives.

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
   > <a temp file named for the unit>`. Keep the snapshot from before each
   wave until its groups' streaks end: a fix-up's check uses it as
   `--baseline`.
4. **Dispatch the unit** per the harness's steps. Build one group per
   working directory: split `next.steps` by the working directory each
   step's spec names (one directory for a single-repo plan), and give each
   group its steps, their headings and text verbatim, the acceptance
   criteria, the standards to read, the directory's task branch and its
   HEAD SHA now as `from`. A group's id is `<workdir basename> <steps>`
   (`repo-b m1 s4-s5`). On a fix-up (`next.kind: "fixup"`), the groups are
   the ones `next.groups` names, with their steps, and `from` is the
   `<from>` of each group's latest Review log line. On a session's first launch only the
   first group runs (the canary), in both modes; that is not a failure.
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
   - A scope breach gets no line (above).
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
     range and the next unit, with the short handoff summary, and end the
     turn.
   - `plan_state.py` has no `next`: final completion.

### After an answer

In the turn Gary's answer starts: clear `BLOCKED`, then go through "Each
unit" from step 1 (refresh the handoff, commit, push, `plan_state.py`, a
fresh snapshot) and launch the unit with his message as the approval,
verbatim, and each gate approved for the launched unit's wave: every gate
the last run stopped at (gate 5 after a gated canary, though Status no
longer shows it) and every gate in `plan_state.py`'s `stops`. Never approve
`gate-0` or `gate-mode`: they clear only from the plan (fix the plan, or
record the kickoff answer), and nothing accepts an approval for them. A
`needs_info` group also carries `answer: {question, answer}`, the answer
being the same words. A gate answer counts only in the turn his message
starts or joins; never reuse it in a later turn. Gated, an answer at gate 1
may also be a step-up (gate 6, plus gate 7 into `[xdeep]` or Fable), a
re-plan (new waves take the next unused numbers and get Cost table rows
with expected `—`), or a waiver.

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
- a third failure on a group, a scope breach, gate 0, and gate 1 after the
  automatic retry or at once;
- outward actions, including the PR at completion.

Gated mode asks all of these, plus every gate, every failed check and every
repeat CONCERNS.

**Save, then ask** (core.md "Save before you wait"), in this order:
1. Update the plan: `(done)` markers, the Review log, the Token log, and
   Status's `BLOCKED at gate N`.
2. Refresh the handoff with the question verbatim.
3. Commit the plan and the handoff. On a runner, commit everything in the
   tree, a partial step under an honest subject; a workstation stages only
   its own paths.
4. Push every working directory that has a remote, in both modes. Worker
   commits not yet reviewed are pushed too, labeled `UNREVIEWED` in Status,
   the handoff and the question (decision 12).
5. Ask one plain-text question and end the turn, with the short handoff
   summary.

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
pending question verbatim. At a stop and at completion it is final: the
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
- **The parent:** `orchestrator-kickoff <plan name>` for the stretch up to
  the first launch, then `orchestrator-wave-<N> <group-id>` for each stretch
  between two launches, where wave N is the unit the earlier launch carried.
  Windows don't overlap, so the guard never counts the parent twice.

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
   table's actual columns.
3. Append the Completion summary (standard §"Final completion"), with every
   checkpoint, retry and fix-up under **Deviations from plan**.
4. Write the final handoff; commit; push.
5. Print the completed Cost table and the Completion summary, then ask
   whether to open a PR, naming the cleanup commit (remove the plan and the
   handoff, or promote what's durable to `specs/`), with the short handoff
   summary. Wait.

## Subagent context contract

Every worker prompt carries all eight. On Claude Code the workflow writes
the prompt from the group you pass; on Cursor you write it.

1. **Spec excerpt:** the plan section, verbatim. Quote, don't paraphrase.
2. **Working-directory scope:** the absolute path of the one git working
   directory it may edit, as a hard limit ("All edits must be inside
   `<path>`. Do not edit anything outside this directory.").
3. **Acceptance criteria:** the plan's, quoted, or derived from the step
   titles.
4. **Hard scope limit:** the exact step IDs as `plan_state.py` reports
   them (a heading's `s1` under `m2` is `m2.s1`, since step numbers
   restart in each milestone), and "stop at the end of this group; do not
   start the next group or any work not listed here."
5. **Standards pointers:** the specific standards files the work needs.
   Don't skimp for `[deep]` and `[xdeep]` work.
6. **Output contract:** "Write your full output (diffs, decisions,
   surprises, follow-ups) to
   `.scratch/orchestrate-{plan-name}-{wave-n}-{task-id}.md`. Return only a
   structured 1-paragraph summary covering: what changed, what was decided,
   any surprises, and the artifact path." `{wave-n}` is the unit's label
   (`2`, `2-fix`, `2-fix2`); a retry adds `-retry{k}`; `{task-id}` is the
   step IDs (`m2-s1-s3`). The result's status is `done`, `failed`,
   `low_quality` or `needs_info` (with one question); never report partial
   work as `done`.
7. **Token reporting (Cursor `Task` subagents only):** see `adapters/cursor.md`.
   Claude Code workflow workers get no token instruction; the parent tallies
   their transcripts.
8. **Git instruction:** "Commit each finished step on the current branch
   (`<branch>`) as its own commit, staging only the paths you changed. A
   step that changes no file gets an empty commit (`git commit
   --allow-empty`). The first line is the step ID as the scope lists it,
   a space, and an imperative subject (`m2.s3 Wire the results view`);
   then a blank line; then, as the last paragraph, exactly these trailer
   lines: <the harness's trailers>. Never add `Co-authored-by` or
   `Signed-off-by` lines. Do not
   push, create, or switch branches." Plus: "If the spec reads two ways
   with materially different results, or you lack an access the step
   needs, return `needs_info` with one question. Don't open or merge a PR,
   push a tag, delete a remote branch or deploy; if a step needs one,
   return `needs_info` naming it." Plus the resume rule: "Run `git -C
   <workdir> log --format=%s <from>..HEAD` first. A step that already has a
   commit whose subject starts with its ID was done by an earlier attempt:
   check it against the acceptance criteria and skip it if it holds. If a
   file you need already has uncommitted changes, don't touch it: return
   `failed` and name it." A retry's prompt also names the earlier attempt
   and how it ended.

Reviewers are read-only and get the spec, the acceptance criteria, the
standards, the worker's summary and the commit range; they back every
finding with evidence and report only defects the plan must fix.

## Harness steps

- **Claude Code:** [`adapters/claude-code.md`](adapters/claude-code.md), the
  workflow launch and its arguments, the two hooks, the run's result, the
  Agent path, runners and limits, permissions and the token tally.
- **Cursor:** [`adapters/cursor.md`](adapters/cursor.md), the harness gate,
  the `Task` dispatch, the boundary rows and the heuristic tally.

## Out of scope

- Plan work in the parent's own context (above).
- Ultracode in the parent: it orchestrates every task in the session.
- Codex, Grok Build, Gemini CLI and Muse Code: the passive driver, until
  their adapters ship.
- Merging with `orch-spike-plan-model-tiers`. The passive-vs-active split is
  intentional; Gary picks oversight by picking the skill.
