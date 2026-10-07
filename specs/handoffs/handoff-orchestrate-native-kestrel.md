# Handoff: harness-native plan orchestration (kestrel)

**Branch:** `feature/orchestrate-native` (task branch, cut from `main` at bf5da80 on Gary's instruction).
**Plan:** `specs/handoffs/plan-orchestrate-native-kestrel.md`, tagged and driven by `personal-plan-model-tiers` (passive). 8 waves, expected ~73M tokens, ~$38 API-equiv.
**Status:** kickoff written; no wave has run. Waiting on Gary's answer to the kickoff question below.

## Done

- Read `specs/handoffs/orchestrate-native/` (brief, proposal v6, README).
- Ran the kit's offline suite with the README recipe on a fresh copy: 152 pass (plan_state 44, check_wave 15, hook 37, token_tally 6, workflow 50) plus the consistency check, on Python 3.14.8, node 26.10.0, Claude Code 2.1.291.
- Wrote the plan: m1 = phase 0, the ten exit criteria as steps (Mac first, then the cloud runner); m2 = phase 1, proposal §4's phase-1 rows plus the PR's five items. Kickoff, Cost table and Token log counting header written.

## Key decisions

- Gary's decisions 2-12 are recorded in the plan's "Decisions" section.
- **Plan shape (mine):** m1.s1 does the kit's file move into the plugin (PR item 1), since installing from the branch through the local marketplace needs it there. m1's step order is Mac first, so step numbers differ from criterion numbers; each title names its criterion.
- **The spike plugin (mine):** a renamed copy (suggested `orch-spike`) on this branch outside `plugins/`, published through a marketplace entry pinned to this branch. m1.s6 checks the docs and asks Gary. A private scratch repo for the cloud fixture is proposed there too.
- **Wave 3 runs from the Mac:** the chat coordinates, and Gary starts and answers the cloud sessions with prompts it writes.
- **Final completion moves into wave 8:** wave 8 deletes the plan, so its chat finishes the plan, prints the Cost table and Completion summary for the PR description, then deletes. Wave 8 gets no review beat.
- **"Flip the gate" (my reading):** m2.s3 ships the Claude Code path marked "phase 1: dogfood", and m2.s9 removes the mark after the dogfood runs pass.

## Gotchas

- Once m1.s1 installs the branch's plugin locally, every Workflow launch in Gary's local sessions passes through `orchestrate_gate.py`.
- Merging waits until criterion 6 holds (org sync and Cowork accept the new manifest fields).
- Merge with a squash, passing the PR title and description explicitly.

## Pending question (verbatim)

> Continue execution in this chat, or hand off to a new chat for clean context? (default: new chat)

## How to resume

Paste the Kickoff prompt from the top of the plan into a new Claude Code chat on `/model opus` with `/effort high`.
