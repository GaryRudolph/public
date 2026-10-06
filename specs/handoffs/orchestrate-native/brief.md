# Orchestrate natively: decision brief

Gary, this page is the short form of `proposal.md` (v6, revised after review). Section numbers point there.

## What it does

`personal-plan-orchestrate` runs each wave of a tagged plan on subagents at the tier's model, with the `[deep]` parent in control. On Claude Code a saved plugin workflow runs one wave per launch. `plan_state.py` derives the next unit and its gates from the plan file, `check_wave.py` checks the commits, and a `PreToolUse` hook denies any launch whose state, approvals, mode, branch or handoff isn't true on disk and in the transcript. Every run lives on a task branch, and the plan and its handoff are committed and pushed after every wave.

## How a run looks

**Gated, on the Mac, from `main`.**
- One kickoff question: the waves, the expected cost, the gates, `Proposed mode: gated`, and the task branch it will cut (`feature/auth-otter`). Your answer is the yes to cut it.
- The kickoff cuts and pushes the branch, commits the plan and handoff, prints the Kickoff prompt, and halts for a new chat (or dispatches here, if you add `here`).
- The canary group runs alone and stops at gate 5. Every gate stops with one question and a short handoff summary.
- After each wave: commit check, one Opus review per repo, a bookkeeping commit, a push. At the end: the Completion summary, the final handoff, and the PR question.

**Unattended, on a cloud runner.**
- The kickoff cuts a task branch without asking and proposes unattended, quoting the guard (3x expected or $50).
- You reply `unattended`. Gates 2, 3, 4, 5 and a planned 7 become logged checkpoints, and a failed check or a repeat CONCERNS gets an automatic fix-up (`N-fix`, `N-fix2`).
- It stops for a question it needs answered, a plan error, a scope breach, a worker failure after its one retry, a group's third failure, unplanned `[xdeep]` or Fable work, and the guard. PRs, tags, deploys and permission prompts wait for you.

**A new session.** You paste the plan's Kickoff prompt. It names the repo, the plan path, the branch and the confirmed mode.
- Same harness and runner as the record: the session records the paste as your confirmation and starts, or re-posts a `BLOCKED` question.
- A cloud session on its own `claude/...` branch keeps that branch, rewrites the prompt's `On branch` line, and still starts.
- Another runner or harness, no mode yet, or a Mac clone on another branch: it asks the kickoff question again (on the Mac, with the switch folded in).
- A paste never answers a gate, a waiver or the kickoff question.

## Settled

- Cost guard: "if it's under $50 don't worry about the cost guards going above 3x" and "If the original expectation was $78 that would be fine to continue until it was at most 3x that".
- Fix-ups: "If unattended, it can also continue with automatic fix-ups."
- Handoff: "If unattended it should also commit the result to the branch in a handoff update or post handoff summary in the event the work is lost." Then: "Actually, for each work, let's keep the handoff and also keep the handoff summaries whether it's attended or unattended".
- Kickoff prompt: "Continue keeping the idea that a plan has a prompt to kick off the workflow in a new session if desired." The branch carries the plan to the new session.
- Task branches: "What's the easy path? If it's to just use a task branch each time, I'm fine with that. Even on a workstation."
- Also settled, not quoted here: API list rates for every cost; one kickoff question that proposes unattended on a runner and gated on a workstation.

## Open decisions (§5), with my recommendation

2. Planned `[xdeep]` wave, unattended: checkpoint or stop? Checkpoint; the kickoff quoted its cost, and unplanned `[xdeep]` still stops.
3. Fix-up cap per group: 1, 2 or 3? Keep 2.
4. Canary when unattended: keep or skip? Keep; it catches a broken setup before the whole wave runs.
5. One wave per run, about $0.5-1 of parent cost a wave: keep? Keep; the gates and git checks need the plan updated between waves.
7. One Opus reviewer per repo per wave, about 0.6x a medium step: keep? Keep; it replaces the parent's inline review.
8. Port the kit to the Agerpoint bok? Yes, after phase 1 runs live; it is namespace-safe.
9. Does a bare "yes" confirm unattended? Yes, when it answers a kickoff question that says `Proposed mode: unattended`; you asked for "at least asks the user to confirm". It needs a one-line core.md "Wait for approval" change naming the kickoff answer as an explicit instruction. Until you decide, the kit re-asks.
10. Scope breach, unattended: stop or fix up? Stop at gate 1; no fix-up can repair it.
11. Nowhere to push (no repo, or no remote): allow gated only? Yes; unattended needs a remote.
12. Unreviewed commits at a stop on a workstation: push them labeled `UNREVIEWED`? Yes, as on a runner, so a resume elsewhere sees them; `plan-execution.md` gains the exception.

Also mine, for your veto: cutting a task branch off your own branch; the answer checks (right after the question, no question back or negation); the paste rule and the runner tokens; the cloud branch rewrite and the folded switch; the re-ask after a declined branch cut.

## What phase 0 must prove

1. The launch, notification and relaunch loop works on the Mac, and typed and pasted prompts look human to the hook.
2. The runner Stop-hook rule holds, and worker commits pass in auto mode.
3. Reviewers can't edit (the `tools` allowlist holds).
4. Org sync and Cowork accept the new manifest fields, before the kit merges to main.
5. A fresh cloud session gets the synced skills, the 4 agents, the workflow and the gate hook.
6. Unattended on a runner runs from the kickoff answer to the PR question with no other stop, and a short `gated` stops the next launch.
7. Which branch a cloud session started on a task branch gets, and that a paste there starts without a question.
8. In both modes every wave is committed and pushed before the next launch; a planted check failure gets `N-fix`, and a third failure stops.
9. Gated on `main` cuts the branch only after the answer; a runner plan pasted into a Mac clone on `main` switches after the question; a hook exit 2 blocks the launch.
