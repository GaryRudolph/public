# Handoff: harness-native plan orchestration (kestrel)

**Branch:** `feature/orchestrate-native` (task branch, cut from `main` at bf5da80 on Gary's instruction).
**Plan:** `specs/handoffs/plan-orchestrate-native-kestrel.md`, tagged and driven by `personal-plan-model-tiers` (passive). 8 waves, expected ~73M tokens, ~$38 API-equiv.
**Status:** driver switched to `personal-plan-orchestrate` on the Agent-tool path (Gary's option 2); expected ~$54. Wave 1 ran once and stopped at `needs_info`: the standalone `claude` CLI is signed out, so no live spike run happened. Blocked at gate 1 and the gate-5 canary.

## Done

- Read `specs/handoffs/orchestrate-native/` (brief, proposal v6, README).
- Ran the kit's offline suite with the README recipe on a fresh copy: 152 pass (plan_state 44, check_wave 15, hook 37, token_tally 6, workflow 50) plus the consistency check, on Python 3.14.8, node 26.10.0, Claude Code 2.1.291.
- Wrote the plan: m1 = phase 0, the ten exit criteria as steps (Mac first, then the cloud runner); m2 = phase 1, proposal §4's phase-1 rows plus the PR's five items. Kickoff, Cost table and Token log counting header written.

## Wave 1, first attempt (m1 s1-s3)

Commit `f356a2f` (m1.s1 staging, reviewed by the parent): the kit's scripts, agents, workflow and tests are in `plugins/personal/skills/personal-plan-orchestrate/`, `claude-hooks.json` in `plugins/personal/hooks/`, the manifest fields in `plugin.json`; the README runs the tests in place. 152 pass there, `claude plugin validate` passes (no-version warning), `make -C agents validate test` passes (it doesn't run the kit tests until m2.s1).

- `claude --plugin-dir plugins/personal` loads the hooks file, 5 agents, 1 workflow and 10 skills for one session, with no persistent install; the CLI has no synced `personal`, so no name clash.
- Fixture: `.scratch/spike/fixture/` (two repos, bare origins, `origin/HEAD`, branch `feature/smoke-wren`, a 2-wave smoke plan `plan_state.py` reads cleanly). Offline against it, the hook allows an honest launch, denies an edited `state`, and ignores other workflows.
- Criterion 1: not run (CLI signed out). Criterion 10: not run; a logging proxy (`.scratch/spike/wire/proxy.py`) is ready, and whether Claude Code keeps its credentials behind `ANTHROPIC_BASE_URL` is unverified.
- Criterion 4, partial, from a probe and existing desktop-app transcripts: a typed CLI prompt is `promptSource: "typed"` (not in the proposal; the hook already accepts it); notifications classify correctly. The hook wrongly treats compaction summaries (`turnOrigin: "human"`), the `[Request interrupted by user]` marker and a `turnOrigin: "sdk"` record as human, and never reads `queued_command` attachments. Bracketed paste on the CLI not yet seen.
- **Kit changes for m2.s2 so far:** skip `isCompactSummary` / `isVisibleInTranscriptOnly`; count a record human only when `origin.kind` or `turnOrigin` is `human` and `promptSource` isn't `system`, and skip text starting `[Request interrupted by user`; read `queued_command` attachments (`commandMode: prompt`, `origin.kind: human`) as human text of the absorbing turn; test fixtures for each shape plus `typed`; the paste shape and any effort fix after the live runs.
- The CLI logged "applying 2 old allow rules to user settings" at launch; `settings.json` was not modified.
- Rerun kit: `.scratch/spike/run-spike.sh s1|s3`, `parent-brief.md`, `wire/proxy.py`, `s2/*.py`; full detail in `.scratch/orchestrate-plan-orchestrate-native-kestrel-1-m1-s1-s3.md`.

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

> Wave 1 is blocked: the standalone `claude` CLI on the Mac is signed out, so the spike sessions can't run. Please run `claude auth login` in a terminal and sign in with the account the spike should bill (a Console API key is the sure route for criterion 10's proxy capture; a claude.ai sign-in behind the proxy is untested), then reply `continue wave 1` and I'll re-dispatch m1 s1-s3 against the ready fixture. This also clears the canary: `f356a2f` (staging only) is the wave's commit so far.

Gary replied `continue wave 1` (approves gate 5 and the re-dispatch), but `claude auth status` still reported `loggedIn: false`, in and out of the sandbox, so nothing was dispatched. Re-dispatch once the CLI is signed in.

## How to resume

Paste the Kickoff prompt from the top of the plan into a new Claude Code chat on `/model opus` with `/effort high`; it re-posts the pending question above.
