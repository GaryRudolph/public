# Harness-native plan orchestration (draft)

Design proposal and prototype kit for running `personal-plan-orchestrate` natively in Claude Code (a saved plugin workflow, gate scripts and a `PreToolUse` hook), with Codex and Cursor adapters to follow. It rides this branch only so it survives the container; it is removed before PR #12 merges and comes back in its own PR.

- `proposal.md`: the design, v5. §5 lists the decisions.
- `kit/`: the prototype. `scripts/` (`plan_state.py`, `check_wave.py`, `orchestrate_gate.py`, `token_tally.py`), `claude-workflows/plan-segment.js`, four `claude-agents/`, `hooks/claude-hooks.json`, and `plugin-manifest.json` (the manifest fields the kit adds).
- `tests/`: 137 offline tests. They expect the plugin layout, so copy the plugin and the kit into a scratch tree first:

      k=specs/handoffs/orchestrate-native; root=/tmp/kit-check/personal
      mkdir -p /tmp/kit-check && cp -r plugins/personal "$root"
      cp -r $k/kit/scripts $k/kit/claude-agents $k/kit/claude-workflows $k/tests \
            "$root/skills/personal-plan-orchestrate/"
      cp $k/kit/plugin-manifest.json "$root/.claude-plugin/plugin.json"
      cp $k/kit/hooks/claude-hooks.json "$root/hooks/"
      bash "$root/skills/personal-plan-orchestrate/tests/test-orchestrate.sh" "$root"

## State

Settled by Gary: API list rates for every cost; a cost guard at 3× the expected total or $50, whichever is higher; one kickoff question that proposes unattended on a runner and gated on a workstation; unattended runs continue with automatic fix-ups; a committed handoff after every wave and a handoff summary in every message that stops or asks, in both modes; the plan keeps a Kickoff prompt for starting the run in a new session; orchestrate always runs on a task branch, workstation included.

Pending in v6: carry the confirmed mode in the Kickoff prompt so pasting it confirms the mode in the new session; commit and push the plan at kickoff so the prompt works on any machine (branch plus repo-relative path); strip the shared-branch paths (decision 11's parts and decision 12 that only exist for shared branches).

Open for Gary: decisions 2, 3, 4, 5, 7, 8, 9 and 10 in `proposal.md` §5.

Nothing in the kit has run live since v2 (Haiku stand-ins, $0.86). Phase 0 is a spike that tests plugin sync of agents, workflows and hooks in a cloud session first.
