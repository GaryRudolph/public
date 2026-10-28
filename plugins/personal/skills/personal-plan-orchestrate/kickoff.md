# Kickoff and re-entry

Part of [`SKILL.md`](SKILL.md), which says when to read this file: before
a plan's kickoff, and in any session that finds a Kickoff block with a
`mode:` line. Section names in quotes refer to `SKILL.md` unless they are
in this file.

Contents: [Runner signals](#runner-signals) · [Kickoff (once per plan)](#kickoff-once-per-plan) · [The kickoff question](#the-kickoff-question) · [Reading the answer](#reading-the-answer) · [The Kickoff prompt](#the-kickoff-prompt) · [A new session on a plan already kicked off](#a-new-session-on-a-plan-already-kicked-off)

## Runner signals

Read them with one shell call (on Cursor, the Cloud MCP check below) and
write them as fixed tokens, so a later session can compare its own
environment with the record:

    env | grep -E '^(CLAUDE_CODE_REMOTE|CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE|CI|GITHUB_ACTIONS)='

| Signal | Tokens |
|---|---|
| `CLAUDE_CODE_REMOTE=true` | `runner=cloud`, or `runner=self-hosted` with `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=self_hosted` |
| `CI=true` or `GITHUB_ACTIONS=true` | `runner=ci`: nobody can reply, so the invoking words are the answer |
| Cursor: the Cursor Cloud MCP's `run-info` tool is in your tool list and answers | `harness=cursor runner=cloud` |
| none of these (Remote Control included) | `runner=none`: a workstation |

`harness` is `claude-code`, `cursor`, `codex`, `grok`, `gemini` or `muse`.
A runner proposes unattended; a workstation proposes gated. Gary's answer
decides. `CLAUDE_CODE_SESSION_ATTENDED` is undocumented; ignore it.

**A Cursor cloud agent** proposes unattended, and Gary may still answer
gated. Cursor documents its Cloud MCP, with the `run-info` tool, as
"available during Cloud Agent runs", so the tool answering is the signal
(`adapters/cursor.md` "Runner signal"). `CURSOR_AGENT` marks any Cursor
agent's terminal, local ones included, and is not a signal. A team admin
can turn the Cloud MCP off; then nothing marks the cloud agent, and it
records `runner=none` and proposes gated.

## Kickoff (once per plan)

1. **Identify the plan:** a named path, else the most recent `plan-*.md` in
   `specs/handoffs/` or `.scratch/`, else the plan in the conversation. If
   the plan already has a Kickoff block with a `mode:` line (a run under
   way, or a kickoff waiting for its answer), don't run these steps: go to
   "A new session on a plan already kicked off", which covers a pasted
   Kickoff prompt and a session started any other way.
2. **Tag, group and mark waves.** If the plan isn't tagged, run
   `personal-plan-tag-tiers`. Then the no-thrash grouping pass: consecutive
   same-tier steps form a wave, and a short `[fast]` run (fewer than 3
   steps) folds into the adjacent `[exec]` wave **without rewriting any
   tag**. Check the ≤ constraint (every step's tag ≤ its wave's tier, and
   an `[xdeep]` wave holds only `[xdeep]` steps); a violation is gate 0:
   write no markers, ask. Then write `--- WAVE N [tier] ---` before each
   wave's first heading (skip when markers exist). Fix-up waves are never
   planned; they come from the Review log.

   **Consolidation step.** Before writing markers, apply the standard's
   §"Consolidation step" criteria (two or more waves change source code;
   the Shape section's Creates lists three or more source files; a wave
   runs in worktrees of one repo). When one fires, append the step with
   its verbatim text as the last step of the last milestone, tagged
   `[deep]`, in its own wave with its own marker, never merged into the
   previous wave. The kickoff summary and the kickoff question say which
   criterion fired, or why it was skipped (docs-only, all code in one
   wave, disjoint files). Gary may add or remove it before the kickoff
   question is answered. A plan with no `## Shape` section gets one first
   (run `personal-plan-tag-tiers` step 4).

   **Fit check.** If the grouped plan is direct-sized (standard §"Driver
   fit"), ask whether to orchestrate it at all before going on, as a
   choice dialog where the harness has one, else in text: name the waves,
   step count and tiers and the conditions it met, with the options
   `Run directly (Recommended)` and `Orchestrate anyway`. Don't start the
   question with `Proposed mode:`; this isn't the kickoff question, and
   nothing launches before it. On run directly, keep the tags and markers,
   write nothing else (no Kickoff block, Cost table or handoff), and work
   the plan in this session under core.md's rules; this skill ends there.
   On orchestrate anyway, go on to step 3. Any other answer, or none,
   re-asks. Under `runner=ci` nobody can answer, so the invoking words
   stand and the run goes on. A plan that isn't direct-sized skips this,
   but one that is one-session-sized (§"Driver fit", "When orchestrate
   pays off": a single-repo feature with a written spec one engineer could
   do in a day) gets the same question with `Run directly` or the passive
   driver recommended and the reason named: orchestrate would split it
   into workers that each see one step and write more code than one
   session would.
3. **Preflight:** the branch, email and `origin/HEAD` checks in "Task branches", the
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
   will have (gated: the canary when the first unit has several groups,
   and every gate 2, 3, 4 and 7 the plan crosses, gates asked together
   counting once; unattended: one, the kickoff answer), plus a new-chat
   start-up on a workstation. Unattended needs the Total row: the guard
   reads it.
6. **Write the counting header** at the top of `## Token log` (standard
   §"Token line format"), for the harness the Cost table names.
7. **Save:** move the plan to `specs/handoffs/` (unless decision 11 keeps it
   in a plain folder's `.scratch/`), write the handoff beside it ("The
   handoff and its summary"), and on a task branch commit both in one
   commit whose subject has no step ID, then push. A workstation still
   waiting to cut commits nothing.
8. **Ask the kickoff question and wait** (below): as a choice dialog where
   the harness has one, which waits inside the turn; else in text, ending
   the turn.
9. **Record the answer** when it comes (below), then save again:
   a workstation cuts its branch first; refresh the handoff with the mode,
   commit the plan and handoff, push.
10. **Halt or dispatch.** When the answer picks this session (the dialog's
    `This session`, `here` in a typed answer, or any typed answer on a
    runner): print the kickoff summary (waves, expected total, gates, the
    Shape summary and the consolidation decision) and go
    to "Each unit"; nothing needs copying. Otherwise (`New session`, or a
    typed answer on a workstation without `here`): queue the Kickoff prompt
    as a new session where the harness can (the adapter says how), print
    the prompt on its own (standard §"Printing a prompt in chat"), the
    kickoff summary and the short handoff summary, and halt.

Seed the harness todo list (one todo per wave, first `in_progress`) when
you start dispatching, in this session or the new one.

### The kickoff question

One question, once per plan run, after the Kickoff, Cost table and
counting header are written and saved. It names the waves and their tiers,
the Cost table's expected total, the gates the plan crosses (5 at the
canary, when the first unit has more than one group; 2 or 3 before a
`[deep]` or `[xdeep]` wave after an `[exec]` or `[fast]` one; 4 at a new
milestone; 7 before each `[xdeep]` wave, with its cost), what each mode
does, the guard's dollar limit, the handoff path, the plan's Shape section
(its Creates list, for Gary to trim, and the consolidation decision), and
on a workstation the branch it will cut. It always carries the exact words
`Proposed mode: <mode>.` and, after them, a line that starts `Reply`; the
Claude Code hook looks for both, in that order, before it counts a typed
answer (a dialog's answer counts under a mode question that starts with
those words, below).
The short handoff summary follows the `Reply` line. On a runner:

    Plan plan-auth-otter: 4 waves, expected ~$26 API-equiv (Cost table above).
    Shape: creates src/auth/otp.py (no module owns one-time codes), src/auth/otp_store.py (its storage);
      modifies 5 files. Consolidation step added as m2.s4 (two waves change source code).
      Strike a file from Creates by naming it, and that step extends an existing file instead.
    Gates it crosses: 5 (canary, wave 1's two groups); 4 and 2 (before wave 3); 7 (before wave 4, [xdeep], ~$14).
    Runner detected (CLAUDE_CODE_REMOTE=true). Proposed mode: unattended.
      unattended: gates 2, 4, 5 and 7 are logged, not asked. A failed commit check or a
        CONCERNS gets an automatic fix-up, up to 2 per group. I stop to ask for information,
        at a plan error, a scope breach, a worker's disclosed breach, a failure after one
        retry (at once on the [xdeep] wave), a group's third failed check or review,
        unplanned [xdeep] or Fable work, or projected spend past 3x expected or $50,
        whichever is higher (~$78).
      gated: every gate stops, and so does every failed check or repeat CONCERNS.
    Either way, after every wave I commit and push the plan and its handoff
    (specs/handoffs/handoff-auth-otter.md), and every message that stops or asks ends
    with a short handoff summary. Opening or merging a PR, tags, remote branch deletes,
    deploys and permission prompts wait for you.
    Reply unattended or gated; name any file to strike from Creates.

On a workstation, the signal line says what was checked and names the
branch; the destination question folds in (there is no separate one):

    No runner signal (CLAUDE_CODE_REMOTE unset, no assigned branch). Proposed mode: gated.
    main is a shared branch, so the run goes on a new task branch, feature/auth-otter:
    your answer is the yes to cut it, and I push it at once.
    Reply gated or unattended; add here to orchestrate in this chat (default: new chat).

**As a choice dialog.** Where the harness has one (Claude Code's
`AskUserQuestion`; the adapter has the shape), print the question above as
text, its `Reply` line included as the typed fallback, then ask one dialog
with two questions:
- **Mode:** the question text starts with the exact words
  `Proposed mode: <mode>.`; the options are `Unattended` and `Gated`, the
  proposed one first and marked `(Recommended)`. Labels stay that plain:
  a label that negates or names the other mode reads as a re-ask. On a
  workstation the question names the branch it will cut.
- **Session:** `This session` or `New session`, marking `(Recommended)`
  on `New session` when the kickoff spent a lot of context (tagging, a
  long plan, exploration) and on `This session` otherwise. A new session
  starts with clean context; there is no "compact first" choice.
- **Shape:** when the Shape section's Creates list has any entry, a third
  question naming the new files, with `Keep as listed (Recommended)` and
  `Trim first`. On `Trim first`, the mode and session answers still
  stand: after recording the mode, ask in plain text which files to
  strike, apply it to the plan's Shape section (and to the consolidation
  decision if the count changes), save, and go on to step 10 without
  asking the kickoff question again. Typed, a strike names the file
  (`unattended; strike src/auth/otp_store.py`); a negation ("don't create
  x") re-asks by the rules below, so name the file instead.

Propose gated, and say why, where unattended can't run: no remote for the
plan's repo (decision 11), or a workstation on a harness with no hook to
check it. A runner on such a harness (a Cursor cloud agent) still proposes
unattended, saying that the mode rests on the parent there.

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

`here` anywhere in a typed answer means orchestrate in this chat.

**A dialog's answers** are read the same way, question by question: the
mode question's answer by the rules above (a pick, or words typed under
Other), the session question's pick for step 10. A declined dialog, one
dismissed, one that resolved itself while Gary was away, or one that
ended in a request for more questions answers nothing: re-ask. Record
only the mode question's answer on the mode line; the session choice goes
in the handoff.

**Record it:** replace `pending` on the mode line with the mode, and append
` | confirmed <today> session <S>: <the whole answer, whitespace
collapsed>`. Gary's words come last on the line, so they may hold any
character; `guard` and `fixups` are read only from before `confirmed`, so
his words never set them. In the same edit add `Run in <mode> mode.` as the
Kickoff prompt's mode line and clear `BLOCKED` from Status. Print the
Kickoff prompt only after this edit: a prompt without its mode line makes
the next session ask again. If the answer
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
    Run the personal-plan-orchestrate skill from the top: walk to
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
  `claude/…` branch, cut from the default branch, unless the kickoff
  started this session on the task branch (the Claude Code adapter's
  "A new session"): then the branch is the prompt's, and there is nothing
  to move. If that branch has no
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
   verbatim (as a dialog, where it was one) and wait. The paste answers nothing.
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
and this session's first launch is a canary that stops at gate 5 when
its unit has several groups): record
nothing new and go to "Each unit". An unattended record counts only in the
session that confirmed it. When its tokens match yours, confirm it instead
of re-asking: a short text (the plan, the session and date that confirmed
unattended, the spend so far against the expected total, the guard's
limit, then `Proposed mode: unattended.` and a `Reply unattended or
gated.` line), then a dialog with one question, starting `Proposed mode:
unattended.`, whose options are `Unattended (Recommended)` and `Gated`.
There is no session question: this is the new session. Record the answer
as this session's confirmation (step 9's save). When the tokens differ,
ask the full kickoff question with a fresh proposal. A `BLOCKED` Status is
re-posted first, either way.

**Re-entry with a run in flight.** If the handoff or Status shows a launch
whose result was never recorded, reconcile from git first (uncommitted and
unpushed work in each working directory), report it, and ask before
relaunching. A run that died with its session leaves no record; on Claude
Code the hook then refuses further launches in that session, so continue in
a new session from the pasted prompt.
