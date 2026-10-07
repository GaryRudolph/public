# Harness-native plan orchestration (draft)

Design proposal and prototype kit for running `personal-plan-orchestrate` natively in Claude Code (a saved plugin workflow, gate scripts and a `PreToolUse` hook), with Codex and Cursor adapters to follow. It rides this branch only so it survives the container; it is removed before PR #12 merges and comes back in its own PR.

- `brief.md`: the decision brief for Gary, one page.
- `proposal.md`: the design, v6, revised after an adversarial review. §5 lists the decisions and the review fixes.
- The kit now lives in the plugin (plan m1.s1). Under `plugins/personal/skills/personal-plan-orchestrate/`: `scripts/` (`plan_state.py`, `check_wave.py`, `orchestrate_gate.py`, `token_tally.py`), `claude-workflows/plan-segment.js` and five `claude-agents/`; the hook is `plugins/personal/hooks/claude-hooks.json`, and the manifest's `agents`, `workflows` and `hooks` fields are in `plugins/personal/.claude-plugin/plugin.json`. Where the proposal says `kit/`, read those paths.
- The 152 offline tests are in that skill's `tests/` and run in place, from the repo root:

      bash plugins/personal/skills/personal-plan-orchestrate/tests/test-orchestrate.sh plugins/personal

## State

Settled by Gary: API list rates for every cost; a cost guard at 3× the expected total or $50, whichever is higher; one kickoff question that proposes unattended on a runner and gated on a workstation; unattended runs continue with automatic fix-ups; a committed handoff after every wave and a handoff summary in every message that stops or asks, in both modes; the plan keeps a Kickoff prompt for starting the run in a new session; orchestrate always runs on a task branch, workstation included; the effort rules (`[exec]` Sonnet high, never past high; `[deep]` Opus high; `[xdeep]` Opus xhigh, with max only where a gain is measured and ultracode only for audit-shaped steps).

In v6: the Kickoff prompt names the repo, the plan's path, the branch and the confirmed mode, and pasting it confirms the mode in a new session (hook rule 7); the kickoff commits and pushes the plan before it halts or dispatches; the shared-branch paths are gone; a bare yes re-asks. The review fixes (`proposal.md` §5): a paste never answers a gate, a waiver or the kickoff question; a mode answer counts only right after the kickoff question; the hook denies with exit 2 when it fails; the runner signal is tokens with the harness; a cloud session keeps its assigned branch and another machine switches after the question; rule 9 fails closed on an unknown default branch and on git errors.

Open for Gary: decisions 2, 3, 4, 5, 7, 8, 9 and 10 in `proposal.md` §5, plus my 11 (nowhere to push) and 12 (unreviewed commits pushed at a stop on a workstation).

Nothing in the kit has run live since v2 (Haiku stand-ins, $0.86). Phase 0 is a spike that tests plugin sync of agents, workflows and hooks in a cloud session first.
