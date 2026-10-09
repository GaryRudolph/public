# Plan orchestration

How `personal-plan-orchestrate` runs a tagged plan: a `[deep]` parent dispatches each wave to subagents on the tier's model, checks and records the result, and pauses only where the plan's recorded mode says to stop. This spec is the design and its reasons. The procedure is in the skill, and this spec points there rather than repeating it:

- [`SKILL.md`](../plugins/personal/skills/personal-plan-orchestrate/SKILL.md): the harness-neutral loop (detection, kickoff, gates, each unit, the handoff, the worker contract).
- [`adapters/claude-code.md`](../plugins/personal/skills/personal-plan-orchestrate/adapters/claude-code.md) and [`adapters/cursor.md`](../plugins/personal/skills/personal-plan-orchestrate/adapters/cursor.md): what differs per harness.
- [`plan-execution.md`](../plugins/personal/skills/personal-standards/standards/plan-execution.md): tagging, the no-thrash rule, wave markers, the model picker, the Kickoff template, the Cost table, the Review log and token accounting, which this design builds on.

**Status.** Claude Code is native (phase 1), shipped in the `personal` plugin; `SKILL.md` marks its path "phase 1: dogfood" until real plans have run through it (gated and unattended on the Mac, unattended on a runner). Cursor is native, with the parent applying the gates by hand until phase 3. Codex, Grok Build, Gemini CLI and Muse Code run the passive driver, `personal-plan-model-tiers` (§4).

## Summary

- **One dispatch unit per launch:** a wave, the part of a wave inside one milestone, or a fix-up of one group (`N-fix`, `N-fix2`, ...).
- **The plan is the state.** `plan_state.py` derives the next unit and every gate in front of it from the plan file; the recorded mode only decides which gates stop. `check_wave.py` checks the commits around each unit.
- **On Claude Code** a saved plugin workflow, `<P>:plan-segment`, runs the unit: one worker per git working directory, each followed by one read-only reviewer. A `PreToolUse` hook denies any launch whose state, approvals, mode, branch or handoff isn't true on disk and in the transcript.
- **One kickoff question sets the mode.** Gated stops at every gate. Unattended logs the routine gates as checkpoints and fixes failed checks and repeat concerns automatically, up to a cap, and still stops for information, plan errors, scope breaches, unplanned premium work and the cost guard.
- **Every run lives on a task branch.** The plan and a session handoff are committed and pushed at kickoff (on a workstation, once the answer has cut the branch) and after every wave, so a new session continues the run from the branch when Gary pastes the plan's Kickoff prompt.

## 1. Harness-neutral core

### 1.1 What it keeps

From the standard and the passive driver, unchanged:
- **Plan structure:** tagging by `personal-plan-tag-tiers`, the no-thrash grouping and its ≤ constraint, `--- WAVE N [tier] ---` markers.
- **Plan bookkeeping:** the Kickoff block, Cost table, Status line, `(done)` markers, Review log, and the Token log with its counting header.
- **Gate rules:** fail closed (a non-answer is never approval), approval per gate, `BLOCKED at gate N` in Status, save before you wait, and unattended work only on Gary's explicit word, which here is his answer to the kickoff question (§1.4).
- **Execution rules:** one subagent per git working directory (separate repos or `git worktree`s run in parallel; one directory runs serially), the eight-item context contract (`SKILL.md` "Subagent context contract"), and the commit policy: subagents commit each step and never push; the parent pushes.
- **The parent never does plan work.** It tags, dispatches, checks, records and asks; committing the plan and handoff and pushing are bookkeeping. It always runs at `[deep]` (Opus high), also through `[xdeep]` waves, which go to xhigh subagents and an xhigh reviewer.

### 1.2 What the plan derives

`plan_state.py <plan>` reads only the plan and prints one JSON object (version 3): the next unit (`kind` `wave` or `fixup`, `wave`, `label`, `fix`, `tier`, `milestone`, its open `steps`, `start`, and a fix-up's `groups`), `gates`, `stops`, `checkpoints`, `mode` (with `via`: `answer` or `prompt`), `prompt_mode` and `prompt_plan` (the Kickoff prompt's mode line and plan line), `cost`, `concerns`, `waivers` and `errors`. Every orchestrate parent runs it before every dispatch. Gate names are `gate-<N>` there and `BLOCKED at gate <N>` in Status.

| Gate | Derived from |
|---|---|
| mode | No Kickoff `mode:` line with a confirmed answer |
| 0 | `errors`: markers not numbered 1..N in file order or outside the grammar (`N`, `N-fix`, `N-fix<k>` for k ≥ 2), a step before any marker, a ≤ violation (or a lower-tier step inside an `[xdeep]` wave, which holds only `[xdeep]` steps), a step ID used twice (an `s{K}` heading under `m{N}` has the ID `m{N}.s{K}`, so only a true repeat counts), `(done)` out of order, a Review log line outside the grammar, a fix-up streak on a wave with no steps, a `fixups` cap under 1, no tagged steps; unattended with no Cost table Total; an unattended record whose proposal signal isn't tokens (§1.4); a Kickoff prompt whose mode line doesn't name the confirmed mode or comes before the answer, or that has no line naming the repo and plan |
| 1 | `BLOCKED at gate 1`; a fix-up whose group's latest Review log line is a failed check; a fix-up whose group has two or more CONCERNS in a row |
| 2 / 3 | A unit starts in `[deep]` or `[xdeep]` right after an `[exec]` / `[fast]` unit |
| 4 | A unit starts in another milestone (`m{N}` from the step ID or the enclosing heading) |
| 5 | `BLOCKED at gate 5`, which the parent writes after a gated canary |
| 7 | The first unit of an `[xdeep]` wave (a canary's continuation isn't asked twice), and every fix-up of an `[xdeep]` wave |
| guard | Projected spend passes the cost guard (§1.5) |

The workflow adds gate 6 (and 7 into `[xdeep]` or Fable) when a launch carries a step-up, and the canary's gate 5 (§2.1). A `BLOCKED at gate N` line is always a stop.

- **Fix-ups come from the Review log, never from open steps.** The k-th CONCERNS line in a row for a group makes the next unit its fix-up, labeled `N-fix` for k = 1 and `N-fix<k>` after (never `N-fix1`); its review is logged as `review wave-N-fix<k> (<group-id>) ...` and counts toward wave N's group. A PASS ends the streak, and so does a WAIVED line (§1.5). A failed check is logged as a CONCERNS line too, so it starts or extends the same streak. Fix-ups run before any open step; when several groups of the earliest wave have streaks, the longest goes first, and groups tied on it share the unit. A group's id is `<workdir basename> <steps>` (`repo-b m1 s4-s5`); the Review log carries it exactly, since a fix-up's groups must match it.
- **A wave that spans milestones** (in a plan the passive driver grouped) splits into one unit per milestone, without renumbering markers.
- **A fix-up marker** (`--- WAVE 2-fix [exec] ---`, which the passive driver may write) doesn't count toward the wave total or the numbering check.
- **Cost** comes from the plan: the Cost table's Total and rows (expected) and the Token log's dollars (actual).

`check_wave.py` runs around every unit:
- **`snapshot`, before the launch:** each working directory's HEAD and dirty paths. A `.scratch/` that isn't gitignored fails it, which blocks the kickoff's preflight; it also reports the repo's `attribution` setting (a `Co-authored-by` attribution would fail every commit).
- **`check`, after the run,** per group: `from` is an ancestor of HEAD; every commit's first line is `<step-id> <subject>` for one of the group's steps, then a blank line; no `Co-authored-by` or `Signed-off-by` line; the required trailers in the last paragraph; every step has a commit; no new dirty paths; and every snapshotted directory without a group is unchanged. It prints each group's `to`, so Review log ranges come from git, never from a reviewer.
- **The parent's bookkeeping commits** may sit inside a group's range (a fix-up's `from` is the wave's start; a relaunch spans a save-before-you-wait commit). Given the plan path, a commit that touches only the plan and its session handoff under a subject with no step ID is listed as `bookkeeping` and skipped, in a group's range and in a directory with no group (the plan's repo, when no group runs there). Any other commit that touches either file fails: workers never edit the plan.
- **For a fix-up,** `--baseline` takes the snapshot from before the wave it fixes, so a path that wave left behind is checked again. The parent keeps that snapshot until the group's streak ends.
- **Scope breaches are sorted out** for the parent: `scope` lists a `from` no longer an ancestor of HEAD and every changed directory with no group; `uncommitted` lists each group's new uncommitted paths (§1.5).

Two more rules every adapter keeps:
- **Trailers are spelled out.** The parent passes the exact trailer lines from its own attribution (`Assisted-by: Claude Code`, plus any line the harness adds, such as `Claude-Session:` on the web), and the worker ends each commit with exactly those. The parent's own commits carry `Assisted-by` and never `Co-authored-by`, whatever the harness's default attribution says.
- **Gate questions are plain text and end the turn.** None of these is ever an answer to anything: a completion notification, a workflow approval prompt, a hook's continuation prompt (a runner's Stop hook), a timer, or a pasted Kickoff prompt.

### 1.3 Review

Each working directory gets one read-only reviewer per unit, at the author's tier: Opus high, or Opus xhigh after an `[xdeep]` unit. It gets the spec, the acceptance criteria, the standards, the worker's summary and the commit range, backs every finding with evidence, and reports only defects the plan must fix. A missing review is gate 1. A first CONCERNS gets its `N-fix` without a gate in both modes; a second in a row is gate 1 (§1.5). On Cursor, until phase 3, the parent reviews below `[xdeep]` inline (§3).

### 1.4 Mode and the kickoff

**The kickoff** (`SKILL.md` "Kickoff", once per plan) tags and groups the plan, runs the preflight, writes the Kickoff block, the Cost table and the Token log's counting header, saves, asks one question, records the answer, saves again, then halts for a new chat or dispatches. Before the answer the Kickoff block carries

    mode: pending | proposed <gated|unattended> (harness=<h> runner=<r>; <note>) | guard 3x min $50 | fixups 2

and Status reads `BLOCKED at gate mode`; the Kickoff prompt has no mode line yet.

**Runner signals become fixed tokens**, so a later session can compare its own environment with the record. `harness` is `claude-code`, `cursor`, `codex`, `grok`, `gemini` or `muse`. `runner` is `cloud` (`CLAUDE_CODE_REMOTE=true`, or a Cursor cloud agent), `self-hosted` (with `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=self_hosted`), `ci` (`CI=true` or `GITHUB_ACTIONS=true`) or `none`, a workstation, Remote Control included. The note after `;` is free text for Gary. An unattended record whose signal doesn't parse is gate 0. `CLAUDE_CODE_SESSION_ATTENDED` is undocumented and not used.

**The question** names the waves and their tiers, the expected total, the gates the plan crosses, what each mode does, the guard's dollar limit, the handoff path and, on a workstation, the branch it will cut. It always carries the words `Proposed mode: <mode>.` and, after them, a line that starts `Reply`, both in the parent's last message before the answer (the Claude Code hook looks for both there), followed by the short handoff summary. A runner proposes unattended; a workstation proposes gated, and so does a plan whose repo has no remote or a harness with no hook to check the answer, saying why. On a workstation the question also asks where to orchestrate (`here`, or the default, a new chat), which replaces the standard's separate destination question; a runner orchestrates in its own chat. An invoking message that names a mode only sets the proposal; the question still runs, so Gary sees the waves, the total and the gates before he opts in. Only under `runner=ci`, where nobody can reply, do the invoking words count as the answer.

**The answer** is Gary's next message after the question, whole, and only that:
- **Unattended** when it names `unattended` and not `gated`, asks nothing back (no `?`) and negates nothing (no, not, never, without, `n't`); or when it is a plain yes and the question carried `Proposed mode: unattended.` (decision 9; core.md "Wait for approval" names it as the explicit instruction).
- **Gated** when it names `gated`, or is a yes to a gated proposal, which never records unattended.
- **Re-ask** on anything else: a question back, a negation, silence, words that are the Kickoff prompt or hold its mode line, or a declined branch cut (`gated, but stay on main`), which re-asks once and names the two ways on (cut the branch, or run `personal-plan-model-tiers` on the current branch with the plan back in `.scratch/`).

The parent records it as `mode: <mode> | proposed ... | guard 3x min $50 | fixups 2 | confirmed <date> session <id>: <the whole answer, whitespace collapsed>`. Gary's words come last, so they may hold any character, and `guard` and `fixups` are read only from before `confirmed`, so his words never set them. In the same edit the Kickoff prompt gets its mode line and `BLOCKED` clears. If the answer picked the other mode, the Cost table's orchestrator row is recomputed before any wave runs.

**The Kickoff prompt** (`SKILL.md` "The Kickoff prompt") is how a new session continues the run. It names the repo as `<owner>/<repo>` and the plan's repo-relative path (`In GaryRudolph/public, read specs/handoffs/plan-auth-otter.md.`; `Read <absolute path>.` only for a plan in no git repo, which then works only on that machine), always an `On branch` line (one entry per repo when names differ), and after the answer a mode line, exactly `Run in unattended mode.` or `Run in gated mode.`. After the answer only two things rewrite it: a mode switch (its mode line) and a cloud session keeping its own branch (its `On branch` line). So the handoff's resume step is always "paste the plan's Kickoff prompt".

**A new session on a plan already kicked off** (`SKILL.md` has the order):
- **A paste counts** only when a human message, whitespace collapsed, is the plan's whole Kickoff prompt as committed, with its mode line; only its `On branch` lines may differ. "run unattended", the mode line alone, or the prompt plus extra words is not a paste. A paste never answers a gate, a `needs_info` question, a waiver or the kickoff question, so a plan `BLOCKED` at a gate gets that question re-posted.
- **When the paste counts and the record's `harness=` and `runner=` tokens equal the session's,** it records `confirmed <date> session <new id> by Kickoff prompt: Run in <mode> mode.`, commits and pushes, prints the kickoff summary with the spend so far, and dispatches without asking. It asks the kickoff question again when the environment differs (another runner token or harness; another harness also recomputes the Cost table and refreshes the counting header), when no mode was confirmed yet, or on another machine (path c).
- **(a) Same machine:** the clone is on the task branch already.
- **(b) A cloud session** gets its own `claude/…` branch from the default branch. With no commits of its own, it fast-forwards that branch to the prompt's branch, pushes it, works there, and rewrites the prompt's `On branch` line and the handoff's branch in its confirmation commit. A branch with commits of its own that doesn't hold the plan is gate 0: start a session from the prompt's branch.
- **(c) Another machine** (usually a clone on `main`) fetches, reads the plan from `origin/<branch>` without switching, and asks the kickoff question with the switch folded in; the answer is the yes to both, then `git switch <branch>` makes a tracking branch and the answer is recorded there.
- **Not started from a paste:** a gated record carries over while its tokens match (it relaxes nothing, and the session's first launch is a canary); an unattended record counts only in the session that confirmed it, so the kickoff question runs again, quoting the spend so far. A `BLOCKED` Status is re-posted first either way.
- **A run in flight** whose result was never recorded: reconcile from git (uncommitted and unpushed work), report, and ask before relaunching.

**Switching.** A short human message (10 words or fewer) that names `gated` and not `unattended` takes unattended back; on Claude Code the hook enforces it, and a longer message that only mentions the word doesn't count. A switch to unattended takes Gary's explicit words naming it, and also answers a pending gate that unattended would pass as a checkpoint, with those words as the approval, never one that stops in both modes. The parent records the new words, date and session on the mode line and rewrites the prompt's mode line. A message holding a prompt mode line is a paste and switches nothing. A run in flight finishes as launched; the switch is recorded first thing in the turn its completion starts. Nothing moves: plan and handoff stay in `specs/handoffs/` in both modes.

**The Cost table follows the proposed mode.** Each wave row includes its review subagent (about 0.6× a medium step at Opus high, about twice that at xhigh). The orchestrator row counts the kickoff, each wave's checks and bookkeeping (about $0.1 a wave for the handoff refresh, commit and push), and the gate waits the mode will have: gated counts the canary and every gate 2, 3, 4 and 7 the plan crosses (gates asked together count once), unattended counts one, the kickoff answer; a workstation adds a new-chat start-up. Fix-ups get rows with expected `—`, labeled with their number (`2-fix2 [exec] repo-b m1 s4`).

### 1.5 Gates by mode

| Gate | Gated | Unattended |
|---|---|---|
| mode | Stops | Stops |
| 0, a plan or launch error | Stops | Stops |
| 1, a failed, crashed or unreviewed group | Stops | One automatic retry inside the run, then stops |
| 1, a worker's `needs_info` (a fix-up worker's too) | Stops | Stops at once |
| 1, a `check_wave.py` failure that isn't a scope breach | Stops | Automatic fix-up `N-fix` |
| 1, a scope breach | Stops | Stops (decision 10) |
| 1, a second or later CONCERNS or failed check in a row on a group | Stops | Automatic fix-up `N-fix2` and on, up to the `fixups` cap (2 per group, decision 3); the next failure stops |
| 2 / 3, into `[deep]` or `[xdeep]` | Stops | Checkpoint |
| 4, milestone | Stops | Checkpoint; on a project with `specs/`, the milestone handoff is written first |
| 5, canary | Stops | Checkpoint once the canary group passes `check_wave.py` and its review, fix-ups included; then the rest of the wave launches (decision 4) |
| 6, step-up | Stops | Checkpoint for the in-run retry into `[exec]` or `[deep]`; stops for `[xdeep]` or Fable |
| 7, `[xdeep]` | Stops | Checkpoint on a wave the Cost table planned, whose cost the kickoff quoted (decision 2); stops for unplanned `[xdeep]` work (a fix-up, a re-plan row, a step-up), and drafts and `max` need a gate-7 approval |
| guard | Stops | Stops |
| `BLOCKED at gate N` in Status | Stops | Stops |
| Opening or merging a PR, pushing a tag, deleting a remote branch, deploying, posting outside the branch and chat, a permission prompt | Waits | Waits |

The canary: the first launch of a session runs only its first group, in both modes (decision 4), and that is not a failure. A planned `[xdeep]` gate 7 is a checkpoint only when the wave's Cost table row has an expected dollar figure; a `—` row is unplanned.

**Checkpoints are logged, not asked:** at the end of the unit's Review log note (`; passed unattended: gate 4, gate 2`; an automatic fix-up's `; passed unattended: gate 1 (fix-up 2 of 2)`), the latest on the Status line, and every checkpoint, retry and fix-up with its reason under **Deviations from plan** in the handoff and the Completion summary.

**Automatic retries (unattended, inside the run).** A worker with no result or a review that died reruns once on the same tier (a dead review reruns only the review). `failed` or `low_quality` reruns once a tier up, into `[exec]` or `[deep]` only, logged as a gate-6 checkpoint, so a stalled `[exec]` group re-tags to `[deep]` and never runs Sonnet past high. Never on an `[xdeep]` or Fable unit, never on a step-up Gary approved, never for `needs_info`. The retry keeps its wave's number and token row; its prompt names the earlier attempt. A second failure is gate 1. Retrying inside the run means neither the hook nor `plan_state.py` needs a run history.

**Automatic fix-ups (unattended)** are their own units and runs, scheduled from the Review log (§1.2). A failed check is logged as its group's CONCERNS line whose note starts `check_wave.py:`, quotes the failing output on one line, and ends `; review PASS` or `; review CONCERNS: <its note>`. The fix-up's worker gets the failure verbatim with the streak's earlier ones, and its `from` is the group's Review log `<from>` (the wave's start):
- a review concern is fixed with new commits under the step IDs they fix;
- a failed check is fixed at its cause: a missing step commit is made (an empty one when the step changes no file), a by-product path is deleted or the group's own path committed, and a rejected message is reworded on just the commits the check names, by `git commit --amend` when HEAD is one of them, otherwise a non-interactive rebase onto `<from>` that keeps every other commit's message and content, the parent's bookkeeping commits included; the replay gives later commits new SHAs, so the parent pushes with `--force-with-lease --force-if-includes`;
- a note carrying both a failed check and a review concern gets both instructions, and the fix-up's reviewer checks the quoted failure itself too.

The cost guard runs before every fix-up; any fix-up of an `[xdeep]` wave is gate 7 and stops. Raising the cap (`fixups N`) needs Gary's approval of gate 1.

**A waiver.** At a gate 1 that a streak raised, in either mode, Gary may waive the concern instead of approving the next fix-up. The parent logs `review wave-N (<group-id>) <from>..<to>: WAIVED - <his answer, whitespace collapsed> - <date>`, which ends the streak as a PASS does. A paste never waives.

**Scope breaches stop at gate 1 in both modes** (decision 10), since no fix-up can repair them: edits in a directory with no group, a `from` that is no longer an ancestor of HEAD, and, on a workstation only, a group's new uncommitted path, which may be Gary's own edit. The parent writes `BLOCKED at gate 1`, logs no Review log line for the group, leaves its steps open, saves and asks. On a runner an `uncommitted` path is an ordinary failed check that gets `N-fix`.

**The cost guard**, before every unit, in both modes, once the Cost table has a Total (decision 1; unattended without one is gate 0, gated without one has no guard):

    projected = the Token log's dollars so far
              + the next unit's expected $ (its Cost table row; 0 once any step of its wave is done,
                which covers a canary's continuation and a split wave's later units; 0 for an unplanned row)
    stop at gate-guard when projected > max(guard × the Cost table's Total, floor)

With `guard 3x min $50`, a plan expected at $78 stops past $234, and one expected at $10 past $50. A yes at the guard raises the multiple to the next whole one above the projection, or to what Gary names, and needs his approval of `gate-guard`. Unplanned premium work stops whatever the spend. The guard counts only the Token log lines the parent appends after each run, and checks between runs, so an overrun is bounded by one unit. Its inputs are approximate (Claude Code subagent lines are mostly `(output est.)`, Cursor's heuristic), which is close enough for a 3× trip. On the Claude Code Agent path the parent's own spend reaches the Token log only at completion (§2.3), so the guard leaves it out.

### 1.6 Questions, saving and the handoff

Unattended, the parent asks only for what is Gary's: an ambiguous spec (a worker's `needs_info`, or a choice the plan leaves open), missing access or credentials (a `needs_info`, a push a ruleset refuses, a git email mismatch), a choice with materially different outcomes (a re-plan, dropping a wave, a step-up past the automatic one, the guard), a group's third failure, a scope breach, gate 0, gate 1 after the retry or at once, and outward actions, including the PR at completion. A worker whose step needs an outward action returns `needs_info` naming it. Gated mode also asks every gate, every failed check and every repeat CONCERNS. A re-plan Gary approves adds waves with the next unused numbers, after the last marker (gate 0 checks the numbering in file order), and Cost table rows of expected `—`.

**Save, then ask** (core.md "Save before you wait"): update the plan (`(done)`, Review log, Token log, `BLOCKED at gate N`); refresh the handoff with the question verbatim; commit the plan and handoff (on a runner, everything in the tree, a partial step under an honest subject; a workstation stages only its own paths); push every working directory with a remote, in both modes, including worker commits not yet reviewed, labeled `UNREVIEWED` in Status, the handoff and the question (decision 12); ask one plain-text question with the short handoff summary and end the turn. A usage limit is the one stop where this can't run: the pushed handoff is then one wave behind, and the next human turn reconciles from git before relaunching.

**Files a run keeps** (`SKILL.md` "Files a run keeps"): the plan at `specs/handoffs/plan-{topic}-{word}.md` in the repo that holds it, tracked on the task branch (a `.scratch/` plan moves there at kickoff), and the handoff `handoff-{topic}-{word}.md` beside it, on every machine and in both modes. Both are removed or promoted to durable docs before the PR merges (core.md "Runner scratch rides the branch"). Worker artifacts go to `<workdir>/.scratch/orchestrate-{plan-name}-{wave-n}-{task-id}.md`, where `{wave-n}` is the unit's label.

**The handoff after every wave, in both modes.** After each unit's review the parent's bookkeeping commit updates the plan and refreshes the handoff, then pushes every working directory. The handoff holds the branch (each repo's when they differ), the mode, what's done with each group's commit range, the Review log verdicts, the fix-ups, retries and checkpoints with reasons, the Token log total against the expected total, the next unit, how to resume (paste the Kickoff prompt), and any pending question verbatim; at a stop or completion it is final. Every message that stops, asks or ends the run carries a short handoff summary of about six lines: branch and handoff path, waves and fix-ups done with their ranges, spend against expected, and the next unit or the question. It goes in the chat and the handoff on the branch; posting either anywhere else is an outward action. While a run works the parent writes nothing to the tree, commits nothing and pushes nothing, since a tracked plan edit would show up as a new dirty path.

**Where nothing can be pushed** (decision 11, a workstation, gated only): a plan in no git repo, such as a cross-repo plan in a plain folder of sibling repos, stays with its handoff in that folder's `.scratch/`, refreshed after every wave and never committed; a plan in a repo with no remote is committed in `specs/handoffs/` and not pushed, and so is a working directory with no remote. Unattended needs the plan in a repo with a remote.

### 1.7 Task branches

Orchestrate runs only on a task branch, on every machine, in both modes (decision 6): never `main`, `master`, `release/*`, the remote's default branch, a detached HEAD, or Gary's own branch. Each working directory and the repo that holds the plan are checked on their own, with the git email in each. Where the branch isn't a task branch the kickoff cuts one per core.md "Cut a task branch" (`feature/<topic>-<word>`, `git switch -c <branch> --no-track`, `git push -u origin <branch>` at once), the same name in each repo unless it is taken there. A runner works on the branch its system prompt assigns, without asking. A workstation names the branch in the kickoff question and commits nothing before the answer, which is Gary's yes to cut it; uncommitted plan and handoff edits ride along. Every repo with a remote must know `origin/HEAD` (`git remote set-head origin --auto` on a cloud checkout, which has none), so the default branch can be named. core.md carries the carve-out from "Stay on the current branch", including the cut from Gary's own branch.

### 1.8 The passive driver

`personal-plan-model-tiers` has no unattended mode: each STOP is a model swap, and only a human can make one. On a runner it saves (plan, handoff, commit, push) and stops at each STOP marker; its plan file and STOP prompts are the handoff. When the runner is Claude Code with the plugin loaded, its kickoff points to orchestrate, which sets the model per subagent. It keeps core.md's branch rules as they are; always-a-task-branch is orchestrate's rule only.

## 2. Claude Code adapter

### 2.1 The pieces

| Piece | Job |
|---|---|
| `<P>:plan-segment` (`claude-workflows/plan-segment.js`) | Runs one unit. It checks `args` against `plan_state.py`'s unit (the groups cover exactly its steps, or a fix-up's groups exactly the Review log's; one group per working directory; every group names its `branch`, absolute `workdir` and `from` SHA; the trailers carry no `Co-authored-by`; a `stepUp` is above the unit's tier; a non-empty `approved` has a non-empty `approval`) and returns gate 0 otherwise. It refuses any stopping gate not approved for the launched unit's wave, and never accepts an approval of `gate-0` or `gate-mode`. While `canaryDone` is false it runs only the first group. It runs `pipeline(groups, worker, reviewer)`, so each directory's review starts when its worker finishes. Unattended, it retries each broken group once (§1.5) and returns the checkpoints it passed. A fix-up quotes its failure verbatim into the worker's and reviewer's prompts. Every prompt forbids outward actions. It returns a result object only (`stop` `done`, `gate` or `end`; `gates`, `checkpoints`, `retries`, `questions`, and per group `work`, `review`, `from`, `branch`, `tier`); the parent decides everything after. |
| Five plugin agents (`claude-agents/`) | `plan-worker` (`model: inherit`; the call sets model and effort), `plan-worker-exec` (Sonnet, high), `plan-worker-xdeep` (Opus, xhigh), `plan-reviewer` (Opus, high) and `plan-reviewer-xdeep` (Opus, xhigh); reviewers have tools Read, Grep, Glob, Bash. |
| `orchestrate_gate.py` | A `PreToolUse` hook on `Workflow`, in the Claude-only `hooks/claude-hooks.json`, which the manifest loads beside `hooks/hooks.json`. It denies a launch unless every rule below holds, and never allows one outright, so the session's permission rules still apply. |
| `reviewer_guard.py` | A `PreToolUse` hook on `Bash` in the same file. It denies a write (git subcommands that write, file writers, `gh`, in-place edits, redirection to a file) when the hook input's `agent_type` is `<P>:plan-reviewer` or `<P>:plan-reviewer-xdeep`. An agent's `tools` list can drop Edit and Write but can't narrow Bash, so without it a reviewer is read-only by instruction only. It sees every Bash call of every session, so unlike the gate hook it fails open, and the instruction stays. |
| `plan_state.py`, `check_wave.py`, `token_tally.py` | §1.2, §2.6 |

`<P>` is the plugin's name, read from the skill's own name without `-plan-orchestrate`. The skill folder, the manifest's `name` and `args.plugin` always agree, so a renamed copy of the plugin (the phase 0 spike's `orch-spike`, or another org's) works unchanged.

**The gate hook's rules** for a launch of any `*:plan-segment` (numbered as in `orchestrate_gate.py`; `adapters/claude-code.md` has the deny-to-fix table):
1. `args.state` equals `plan_state.py` run now from disk.
2. Approvals ride only on a launch in a turn a human message started or joined mid-turn, and `approval` is that human's latest message verbatim. An approval, a group's `answer`, a waiver or a mode answer that is the Kickoff prompt or holds its mode line is denied: a paste answers nothing.
3. `canaryDone` is true only after an earlier canary launch in this session.
4. No earlier run of this session is unfinished.
5. Every gate the last run stopped at is approved (`gate-0` and `gate-mode` clear only from the plan).
6. The launch is by name, never by `script` or `scriptPath`; an inline script mentioning plan-segment is denied.
7. An unattended mode is confirmed in this session, for this harness and runner (below), and not taken back.
8. A cost guard raised since this session's last launch carries an approval of `gate-guard`, and a raised fix-up cap one of `gate-1`.
9. Task branch and per-wave handoff. Every group's directory has the group's `branch` checked out, and neither it nor the plan repo's branch is `main`, `master`, `release/*` or origin's default branch. The plan and its handoff sit in `specs/handoffs/`, have no uncommitted changes, the handoff's last commit is the plan's or later, and it is on the branch's upstream; every working directory of this session's last finished run has its HEAD on its upstream. Gated without `CLAUDE_CODE_REMOTE` (a workstation, and also a CI job, which the hook doesn't tell apart here), a plan in no git repo skips the plan check, a plan in a repo with no remote skips its push check, and a working directory with no remote isn't checked; a plan git ignores, in a repo where no group runs, is in no repo (a plain folder nested in another repo's work tree). Unattended needs the plan in a repo with a remote. A repo with a remote must have one named `origin` and record `origin/HEAD`, and any git error other than "not a git repository" denies.
10. A WAIVED line added since this session's last launch is a human message of this session, verbatim; in any session a WAIVED line holding the Kickoff prompt or its mode line denies.

It fails closed on its own failures: bad input, a missing or older `plan_state.py`, any exception, or no decision within its own 20 s deadline deny with exit 2, which blocks even when the JSON is lost; the hooks file reports "could not run" and exits 2 when `python3` itself fails (any status but 0 or 2). Two limits remain: Claude Code cancels a hook at its 30 s timeout and then doesn't block, and a hooks file that isn't loaded checks nothing. A plain deny reaches the model as `PreToolUse:Workflow hook error: …` even at exit 0; it is a deny all the same.

**Which transcript records are human.** The hook reads the transcript's own fields rather than a `UserPromptSubmit` recorder, which also fires for background subagents reporting back. A user record is human only when `origin.kind` or `turnOrigin` is `human` and `promptSource` isn't `system`: `typed` and `queued` on the CLI, `sdk` on the desktop app and the web. Never human: notifications (`promptSource: "system"`, `turnOrigin: "task_notification"`), compaction summaries (`isCompactSummary`, `isVisibleInTranscriptOnly`), `isMeta` records (a runner's Stop hook feedback), the `[Request interrupted by user` marker, slash-command records, and `turnOrigin: "sdk"` records. A message typed while the parent works is a `queued_command` attachment (`commandMode: "prompt"`, origin human) and counts as human text of the turn that absorbed it; one with `commandMode: "task-notification"` doesn't. A record replayed after a compaction counts once (by `uuid`). The Mac CLI wraps a bracketed paste in `<pasted_content id="…">` tags; the web doesn't; the hook removes them before every comparison.

**How rule 7 proves an unattended record:**
- the mode line's `session` is the hook input's `session_id`, and its signal names `harness=claude-code` and the hook's own runner token (from `CLAUDE_CODE_REMOTE`, its environment type, and `CI`/`GITHUB_ACTIONS`), on both paths below;
- **by an answer:** a human turn here is the recorded words, whitespace collapsed, right after an assistant message that asked the kickoff question (`Proposed mode:` then `Reply`), unless `CI=true`; the words name `unattended` and not `gated` and ask and negate nothing, or are a plain yes to a question that carried `Proposed mode: unattended.`; they are never the Kickoff prompt or its mode line. It may be an earlier turn, since later launches start from notification turns;
- **by the Kickoff prompt:** the words are `Run in unattended mode.`, the plan's prompt on disk carries that line, and a human turn here is that whole prompt with its `On branch` lines set aside;
- **not taken back:** no later human message of 10 words or fewer names `gated` and not `unattended`. A false trip errs toward stopping.

A gated record needs no proof: it relaxes nothing, and its session's first launch is a canary. Gates still derive from the plan in unattended mode: rule 1 makes the launch carry exactly `plan_state.py`'s split, rule 7 makes the mode behind it real, and the script requires an approval for every stop.

**Why the Workflow tool rather than plain Agent calls:** only there can code refuse to spawn; effort is set per call (the Agent tool has no effort field); returns are checked against a schema; reviews follow their workers without a parent turn between; diffs never enter the parent's context. Rejected: ultracode in the parent (it orchestrates every task in the session and lifts the agent-count warning and auto mode's first-launch prompt); agent teams (no per-teammate gates); a script the model writes each run (no "don't ask again", gate logic new each time); retries across runs (the hook would need a retry chain and `plan_state.py` a run history); fix-ups inside the run (`check_wave.py` runs in the parent, and each fix-up's Review log line and handoff commit must land between runs, where the streak is visible).

**What enforces what:**

| Risk | Stopped by |
|---|---|
| The parent forgets a gate | The script, from `plan_state.py`'s stops |
| The parent passes a unit, milestone or gate split other than the plan's, or claims a canary | The hook (state from disk; transcript history) |
| A stale or reused approval | The script (approvals of `stops` keyed by wave) and the hook (human turn, verbatim, owed gates by name) |
| An unattended mode Gary never confirmed, or took back, mid-turn included | The hook (rule 7) |
| An invoking message, casual mention or question back recorded as the answer | The hook (rule 7) |
| A pasted prompt that isn't the plan's, or from another harness, runner or session | The hook (rule 7) |
| A paste used as a gate answer, `needs_info` answer, waiver or mode answer | The hook (rules 2, 7, 10) |
| A hook that crashes, can't import `plan_state.py`, or stalls | Exit 2 and the 20 s deadline |
| Dispatch before a kickoff answer | `plan_state.py` (`gate-mode`) and the script |
| A guard or fix-up cap raised without asking, or a waiver Gary never gave, within a session | The hook (rules 8, 10) |
| Fix-ups past the cap | `plan_state.py` (gate 1 stops) |
| A wave's results or handoff left uncommitted or unpushed; a launch off a task branch or in a repo git refuses to read | The hook (rule 9) |
| A Kickoff prompt that disagrees with the record or names no plan; an unparseable signal | `plan_state.py` (gate 0) |
| Unplanned premium spend unattended | The script (no automatic retry at or into `[xdeep]` or Fable; drafts and `max` need gate 7) and `plan_state.py` (gate 7 on unplanned `[xdeep]` work) |
| Spend past the estimate | `plan_state.py`'s guard, between runs |
| Two runs at once in one session | The hook (rule 4) |
| Commit, trailer or scope slips | `check_wave.py` (gate 1) |
| A reviewer that writes | `reviewer_guard.py`, and its instructions |
| An `availableModels` substitution or wrong alias | `token_tally.py --check-routing` (gate 1) |

**What still rests on trust:** whether Gary's words mean yes (the hook checks where they came from and that they name unattended without a question or negation); whether the kickoff question was honest about cost and gates; a gated record's words; a guard, cap or waiver raised before a session's first launch, and the other working directories at that launch (rules 8-10 compare with this session's previous launch only; re-entry reconciles from git); `(done)` markers and Review log lines in the plan (the hook checks that `args.state` matches the plan, not that the plan is true; nothing checks that a PASS came from a reviewer or that a breach was held back); the Kickoff prompt's plan line naming this plan (`plan_state.py` checks only that one exists); Token log lines; the handoff's content; which branch is a task branch beyond its name (an open PR's base passes; the kickoff's git.md checks catch it); the prompt on disk (rule 7 compares with the prompt as it is now; a rewrite would be in the pushed history); the runner tokens against an assigned branch; a worker's outward commands; a failure recorded in an earlier session (the `BLOCKED` line is the record); and the whole Agent path.

### 2.2 Tiers, models and effort

`SKILL.md` "Tiers and models" has the table: `[xdeep]` on `plan-worker-xdeep` and `plan-reviewer-xdeep` (Opus xhigh); `[deep]` on `plan-worker` (Opus high) with `plan-reviewer` (Opus high); `[exec]` on `plan-worker` (Sonnet high); `[fast]` on `plan-worker` (Haiku, no effort setting, though it still thinks with the session's setting); a Fable step-up on `plan-worker-xdeep` (Fable xhigh). Reviews below `[xdeep]` and the parent run at Opus high: none is interactive planning, the one case the standard drops `[deep]` to medium. The standard's model picker wins over this table, and the kit's consistency check fails when they disagree.

- **`[exec]` never runs past high.** A stalled `[exec]` group re-tags to `[deep]`, by a step-up Gary approves at gate 6, or unattended by the in-run retry.
- **`max`** runs an `[xdeep]` or Fable worker at max, per launch, only on a task type with a measured gain; its review, drafts and judge stay at xhigh. It needs Gary's gate-7 approval in every mode (the script refuses it unattended without one) and is gate 0 on any other tier.
- **Drafts** (`xdeepDrafts` 2-4) fan an `[xdeep]` or Fable worker out into independent drafts from fixed angles and a judge, on the `-xdeep` reviewer; opt-in, with the same gate-7 rule as `max`.
- **No ultracode in orchestrate.** Workers don't spawn subagents; the fan-out is one worker per working directory plus the opt-in drafts. An `[xdeep]` audit that needs ultracode's fan-out runs on the passive driver.
- **Why five agents:** the Agent path can't pass effort, so the `[xdeep]` worker and reviewer need definitions that say xhigh, the Agent path's `[exec]` worker one that says high (Sonnet defaults to medium), and reviewers one that carries the tool allowlist. The `-xdeep` and `-exec` names carry the tier, not an effort.

### 2.3 The loop on Claude Code

`SKILL.md` "Each unit" and "When a unit completes" are the loop; `adapters/claude-code.md` gives the commands. In outline: commit and push the plan and handoff; run `plan_state.py`; take a `check_wave.py snapshot`; **call the Workflow tool** with `name: "<P>:plan-segment"` and `args` as a JSON object (the skill says those words because that sentence is the opt-in); end the turn with one line. A launch result with `error` set (the script failed its own check) or `remote_launched` (the run went to a cloud session whose commits land elsewhere) is gate 0. On the completion notification: `check_wave.py check --run <run record>` (the record supplies the plan path and trailers), `token_tally.py` for the unit and the parent window before it, the `(done)` markers, Review log line, Token log lines and Status, a refreshed handoff in one bookkeeping commit, a push, and then the next unit in the same turn, or a stop. After Gary's answer the next launch carries `approved: [{gate, wave}]` for every gate the last run stopped at and every gate in `stops`, with `wave` the launched unit's, and `approval`, a top-level string, his message verbatim; a `needs_info` group also carries `answer: {question, answer}` with the same words. A gate answer counts only in the turn his message starts or joins.

**Detection** (`SKILL.md` "Detection"): Claude Code is the harness where `Agent` and `Workflow` both appear, loaded or deferred (Grok and Muse have a lowercase `workflow`, so requiring both keeps them out). If `Agent` has no `model` parameter (`CLAUDE_CODE_SUBAGENT_MODEL_FORCE` hid it), or `<P>:plan-worker` isn't among its subagent types, go passive. If `Workflow` is missing (disabled, or Pro without the opt-in), use the Agent path. The workflow's presence is read from the skills list, where it appears as `<P>:plan-segment`, because the web's Workflow schema lists no plugin workflows; an unknown-workflow error at launch is gate 0, then the Agent path. Inside a subagent nothing orchestrates: report gate 0 to the caller.

**The Agent path** reuses the agents, the prompt text and the checks, with no hook and no script, so its gates and its unattended mode rest on the parent, as on Cursor. One `Agent` call per working directory in one message, with `run_in_background: false` (without it Claude Code backgrounds the call), then each directory's reviewer the same way. `[exec]` uses `plan-worker-exec` and `[xdeep]` `plan-worker-xdeep`; `max` doesn't exist there. The parent applies `plan_state.py`'s stops, the retries, the fix-ups and the per-wave handoff by hand, checks with `check_wave.py --group`, and tallies from the session's `subagents/` transcripts, labeled by each call's wave title, once per wave; with no run ids to bound the parent's windows, it writes one `orchestrator` line at final completion. Foreground calls keep the turn open, which also avoids the runner's Stop hook.

### 2.4 Runners, recovery and limits

- **Cloud sessions get the plugin through claude.ai sync.** Phase 0 showed sync registers the manifest's `agents`, `workflows` and `hooks` in a fresh cloud session and on the Mac CLI, and org sync and Cowork accept them. The workflow launches by name even though the web's Workflow schema doesn't list it, and the hook process sees `CLAUDE_CODE_REMOTE`.
- **The runner's Stop hook** is a git check: it fires at a turn's end only while the tree is dirty or unpushed, as it is while workers run. Its continuation is not an instruction: the parent replies in one line and doesn't commit or push, and the next stop goes through. The completion notification is the wait; the web harness blocks `sleep N; cmd` chains anyway. The container stays up while a run works.
- **No resume.** Claude Code reruns a failed agent and every agent that started after it, so the parent starts a new run from `plan_state.py` instead; the worker prompt skips steps that already have commits, and the review covers the whole range. A run that dies with its session leaves no record, so the hook refuses further launches in that session: continue in a new session from the pasted Kickoff prompt. The branch holds the plan and a handoff as of the last reviewed wave, so a lost session costs at most the wave in flight.
- **Two installed copies of the plugin** under different names (the phase 0 spike's `orch-spike` beside `personal`) both run their gate hooks on every `*:plan-segment` launch, and an older copy applies its older rules.
- **Unreviewed worker commits at a stop** are pushed, labeled `UNREVIEWED` (decision 12); in the plan's repo the handoff commit sits on top of them, and rule 9 checks every working directory.
- **Usage limits.** A run pauses at a limit only in an interactive claude.ai session; background and Remote Control runs fail, and a spend limit on the web let the run complete with agents returning null. The workflow's retry then fails at once too (a crash and a limit both return null). Relaunch once the limit resets, after the next human turn reconciles from git; a scheduled relaunch may run checkpoints and never answers a gate.

### 2.5 Permissions

- Workers use the session's rules: allow `git add`, `git commit` and each repo's test commands, and the parent's `git push`, `--force-with-lease --force-if-includes` included. Leave `gh pr`, tags and deploys out, so a worker that tries one meets a prompt.
- In `-p` or the SDK, allow `Workflow(<P>:plan-segment)`; without it the launch is denied with "Review dynamic workflow before running". Interactive sessions get "don't ask again" for a plugin workflow.
- Other repos come in with `--add-dir`.
- In auto mode, the prompt the script passes to `agent()` doesn't count as a request from Gary; worker commits pass in auto mode with the allow rules above.
- Unattended answers no permission prompt: one mid-run still waits. On a runner, commit and push before a call likely to trip one.
- A repo whose `.claude/settings.json` attribution adds `Co-authored-by` is reported at kickoff: `check_wave.py` would fail every commit, and `personal-repo-baseline` fixes the setting.

### 2.6 Token tally and routing

`token_tally.py` reads a run's `subagents/workflows/<runId>/agent-*.jsonl` and their `.meta.json` labels and follows the standard's source precedence: one call per `message.id`, its usage from the line that carries `stop_reason`; a call with no such line (almost every Opus subagent call) keeps its input-side counts, gets 1,000 output tokens, and its line ends `(output est.) session <id>`. Rows are `wave-<label> <group-id>` and `review-wave-<label> <group-id>` per model (a fix-up's carry its label; a retry keeps its wave's row and is routed by its own tier). The parent's lines come from `--parent-window <prev>:<runId>`: `orchestrator-kickoff <plan>` up to the first launch, then `orchestrator-wave-<N> <group-id>` per stretch between launches; windows don't overlap, so the guard never counts the parent twice, and parent lines are exact. `<model>` drops a trailing `-YYYYMMDD`; pricing (the standard's Model price table) and `--check-routing` use the raw id, and `--check-routing` exits 2 when an agent ran on another model than its tier's, which is gate 1. Workflow workers get no token instruction; the parent writes every token line. At completion, `(output est.)` lines of ended sessions are replaced from their `cost-state` totals; in a live session they stay, since its `cost-state` covers the parent and every wave.

## 3. Cursor

Cursor dispatches with `Task` and a per-call `model` slug, and `adapters/cursor.md` is its procedure: the harness check on the `model` enum, the slugs from the standard's picker (`[xdeep]` `claude-opus-5-5[effort=xhigh]`, `[deep]` and the parent `claude-opus-5-5[effort=high]`, `[exec]` `grok-4-7[effort=high,fast=false]` or Sonnet high, `[fast]` `composer-2.5[fast=false]`), one `Task` per working directory in one message titled by the standard's wave title, the boundary rows, the step-up chain, `check_wave.py check --group`, and the heuristic token lines (contract item 7, which applies only to Cursor `Task` subagents, quoting the counting header into each prompt; pasted usage replaces them). It runs the same core: the kickoff question, task branches, the per-wave handoff, the Kickoff prompt.

What Cursor lacks today: nothing checks the gates or the mode in code, so both rest on the parent; the parent reviews `[deep]`, `[exec]` and `[fast]` work inline and only `[xdeep]` with a read-only xhigh subagent. A Cursor cloud agent shows itself through the Cloud MCP's `run-info` tool or its own pushed branch (`CURSOR_AGENT` is set in every Cursor shell and isn't a signal); which mode it proposes is open (§6). Cursor imports Claude plugins and may list the `<P>:plan-*` agents with `model: inherit`, so the Cursor path never dispatches them; the Claude hooks file's gate hook matches only `Workflow`, which Cursor lacks, and its reviewer guard passes every caller but a `<P>:plan-reviewer`.

## 4. Later phases

- **Cursor, phase 3:** `plan_state.py`'s gates checked in code, an Opus review subagent per working directory in place of the inline review, and an optional fail-closed `subagentStart` hook that denies a dispatch while `stops` is non-empty (a cloud agent reads only the repo's `.cursor/hooks.json`, so it would live there).
- **Codex, phase 2:** native, with `spawn_agent` per working directory, role files that lock each tier's model (copied into `~/.codex/agents/`, read-only by instruction only), the parent running the scripts and asking every stop in plain text, no documented cloud signal (gated proposed; unattended a local opt-in), and the rollout's `token_count` events for the tally. Until then the skill points to the passive driver.
- **Grok Build, phase 4 (optional):** passive until a signed-in test of `spawn_subagent` with per-agent models. Gemini CLI (its parent model isn't trusted with `[deep]`; its hooks fail open) and Muse Code (no model or effort per child) stay on the passive driver. Grok and Muse load the Claude hooks file; it does nothing for calls that aren't a plan-segment launch or a reviewer's Bash.
- **The Agerpoint bok** ports the kit after phase 1 runs live (decision 8): it is namespace-safe through `<P>` and `args.plugin`.

## 5. Decisions

Gary's, and the refinements he accepted:
1. **Cost guard:** 3× the expected total or $50, whichever is higher, in both modes (`guard 3x min $50`).
2. **A planned `[xdeep]` wave** is a logged checkpoint unattended; unplanned `[xdeep]` work stops.
3. **Fix-up cap:** 2 automatic fix-ups per group (`fixups 2`); the third failure in a row stops.
4. **The canary** stays in both modes: one group per session's first launch; unattended passes it on a clean check and review.
5. **One unit per run.** The gates, the git checks and the pushes need the plan updated between waves; the parent's wake-up costs about $0.5-1 a wave.
6. **Task branches only**, on every machine; the kickoff cuts one where needed, a runner without asking, a workstation on the mode answer.
7. **One Opus reviewer per working directory per unit**, about 0.6× a medium step, in place of the parent's inline review (Claude Code now, Cursor in phase 3).
8. **The Agerpoint bok port** follows phase 1's live runs.
9. **A plain yes** to a kickoff question that proposes unattended confirms it; a yes to a gated proposal records gated.
10. **Scope breaches** stop at gate 1 in both modes.
11. **No git remote** means gated only, with the plan in `.scratch/` (no repo) or committed and unpushed (no remote).
12. **Unreviewed worker commits** are pushed at a stop, labeled `UNREVIEWED`, on a workstation too; `plan-execution.md` carries the exception.

Also settled: API list rates for every cost; automatic fix-ups unattended; a committed handoff after every wave and a handoff summary in every message that stops or asks, in both modes; the plan keeps a Kickoff prompt that continues the run in a new session through the branch; the effort rules (`[exec]` Sonnet high, never past high; `[deep]`, the parent and reviews below `[xdeep]` Opus high; `[xdeep]` and its review Opus xhigh; `[fast]` Haiku; `max` only where a gain is measured; no ultracode in orchestrate); the committed `(output est.)` rule. The refinements that came with the design and stand: cutting from Gary's own branch; unattended not implying `here`; the paste rule, the `by Kickoff prompt` record and the signal tokens; gate 0 for a prompt that disagrees with the record; path (b)'s fast-forward and branch rewrite, and path (c)'s folded switch; the hook's branch-name check, its `origin/HEAD` requirement, and its answer checks; the re-ask after a declined cut; the agent names; `max` per launch with gate 7.

## 6. Open questions

- **A workflow reviewer's `agent_type`.** That a reviewer launched by the workflow's `agent()` reaches `reviewer_guard.py` as `<P>:plan-reviewer` is unverified; phase 1's dogfood checks it.
- **Live only partly:** the third failure in a row stopping at gate 1 (shown offline by `plan_state.py`), a typed `gated` switch stopping the next launch, and gated mode on a runner; phase 1's dogfood covers the last two.
- **Runner signals:** whether Remote Control sets `CLAUDE_CODE_REMOTE`; any Codex cloud signal; whether `CURSOR_CODE_REMOTE` reaches Cursor cloud agents' hooks.
- **Effort:** which effort an Agent-path subagent takes on a model other than the session's.
- **Fable:** its usage-credit consent prompt during a run.
- **Cursor:** the bracket efforts other than `high` and `max` (`xhigh`, `medium`, `low`), and whether the `Task` enum takes `grok-4-7[effort=high,fast=false]`.
- **Grok:** how it resolves `inherit` and `opus` in Claude agent files (phase 4).
- **A Cursor cloud agent's proposal.** `SKILL.md` proposes gated on a harness with no hook to check the answer, while `adapters/cursor.md` proposes unattended on a Cursor cloud agent, resting on the parent. Phase 3, which adds the gates in code, settles it.

## Where it lives

| Path | What |
|---|---|
| `plugins/personal/skills/personal-plan-orchestrate/SKILL.md`, `adapters/` | The procedure |
| `…/scripts/` | `plan_state.py`, `check_wave.py`, `orchestrate_gate.py`, `reviewer_guard.py`, `token_tally.py` (Python 3, standard library) |
| `…/claude-workflows/plan-segment.js`, `…/claude-agents/` | The workflow and the five agents |
| `…/tests/` | Suites for each script and the workflow (a stub harness), and `orchestrate_check.py`, which checks the routing against the standard's picker and the agents' frontmatter; `test-orchestrate.sh` runs them, and `make -C agents test` runs that |
| `plugins/personal/hooks/claude-hooks.json`, `.claude-plugin/plugin.json` | The two `PreToolUse` hooks; the manifest's `agents`, `workflows` and `hooks` fields |
| `plugins/personal/skills/personal-standards/standards/plan-execution.md`, `core.md` | The standard's side: STOP gate semantics with the mode, fix-up numbering, the Review log's failed-check and WAIVED lines, the Kickoff's mode line and prompt, orchestrate's handoff, the task-branch cut, decision 9's line |
