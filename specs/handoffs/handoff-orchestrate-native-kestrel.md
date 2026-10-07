# Handoff: harness-native plan orchestration (kestrel)

**Branch:** `feature/orchestrate-native` (task branch, cut from `main` at bf5da80 on Gary's instruction).
**Plan:** `specs/handoffs/plan-orchestrate-native-kestrel.md`, tagged and driven by `personal-plan-model-tiers` (passive). 8 waves, expected ~73M tokens, ~$38 API-equiv.
**Status:** orchestrate driver, Agent-tool path (Gary's option 2), expected ~$54. Wave 1 (m1 s1-s3) done and reviewed PASS; spend so far ~$19. Blocked at gate 1: wave 1's spike sessions changed Gary's `~/.claude-lolay/settings.json`, outside its scope.

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

## Wave 1 result (second attempt, the evidence of record)

No new repo commits; the wave's only commit is `f356a2f`. Evidence in `.scratch/spike/` (gitignored, Mac only) and `.scratch/orchestrate-plan-orchestrate-native-kestrel-1-m1-s1-s3.md`.

- **Setup:** `.scratch/spike/env-clean.sh` exports `CLAUDE_CONFIG_DIR=/Users/gary/.claude-lolay`. That config has an account-synced `personal`; `--plugin-dir` outranks it (debug log: `Synced plugin "personal" shadowed by local copy personal@inline`), loading the branch's hooks file, 5 agents, 1 workflow and 10 skills with no double hooks.
- **Criterion 1, held.** Transcript `~/.claude-lolay/projects/-Users-gary-Projects-personal-public--scratch-spike-fixture-repo-a/d26c40ed-19d2-4195-b00c-42fa13c0281b.jsonl`. Parent Opus high in auto mode. Kickoff question asked (`Proposed mode: gated.` … `Reply gated or unattended.`), `unattended` typed and recorded with the session id. Four `personal:plan-segment` runs: canary, an automatic `1-fix` after a real Haiku CONCERNS (missing trailing newline), the repo-b continuation, wave 2 `[deep]`; each `async_launched`, each relaunch from a `task_notification` turn; `check_wave.py` passed all four; the hook allowed every honest launch and denied an edited `state` (`args.state differs from plan_state.py …`). Parent checked: 5 Workflow calls, 1 denial, 4 notification turns in the transcript.
- **Criterion 4, partial.** CLI 2.1.291: typed prompts `promptSource: "typed"`, prompts queued after a turn `"queued"`, both `turnOrigin`/`origin.kind` `human` (fine). A bracketed paste records as `"typed"` with its text wrapped in `<pasted_content id="…">…</pasted_content id="…">`, so `is_paste` fails (criterion 8's Mac side too); unwrapped, it equals the plan's prompt exactly. A message typed between tool calls is a `queued_command` attachment the hook never reads. The interrupt marker, `/compact` and other slash-command records, and the compaction summary (no `turnOrigin` on the CLI) all read as human.
- **Criterion 10, held.** The logging proxy works with the Team OAuth sign-in. Workflow `agent()` with `effort: 'xhigh'` → `claude-opus-5-5`, `output_config.effort: "xhigh"`; `plan-worker-xdeep` and `plan-reviewer-xdeep` frontmatter → opus `"xhigh"`; `plan-worker-exec` frontmatter and the workflow's `[exec]` `plan-worker` call → sonnet `"high"`, even with the session at `low`. Captures in `.scratch/spike/wire/`.
- **Fallback:** none applies.
- **m2.s2 hook changes (`orchestrate_gate.py` and its suite):** (1) skip `isCompactSummary` / `isVisibleInTranscriptOnly`; (2) human only when `origin.kind` or `turnOrigin` is `human` and `promptSource` isn't `system` (drops the interrupt marker, slash-command records, `turnOrigin: "sdk"`); (3) read `queued_command` attachments as human text of the absorbing turn; (4) unwrap `<pasted_content>` before every paste, approval, answer and waiver comparison; (5) suite records for each shape, including CLI `typed` and `queued`.
- **For m2.s3/s4:** the Agent path must pass `run_in_background: false`; the Agent tool ran probe agents in the background even when asked for foreground.
- **Surprises:** `ANTHROPIC_DEFAULT_OPUS_MODEL` didn't remap `opus` (reviews and the `[deep]` worker ran real Opus); one of four mid-turn messages never reached the transcript (likely a tmux keystroke loss); a plain hook deny shows the model `PreToolUse:Workflow hook error: …` though the hook exited 0.
- **Out-of-scope changes to Gary's lolay config, not reverted:** `/effort high` in a spike session saved `modelSettings."claude-opus-5-5".effortLevel: "high"` to `~/.claude-lolay/settings.json` (the subagent says Opus ran at xhigh before; `/effort xhigh` or removing the key restores it); approving the probe workflow's dialog added `"skipWorkflowUsageWarning": true`; workspace trust accepted for `.scratch/spike/fixture/repo-a` and `.scratch/spike/wire`. The settings file also has `claude-sonnet-5-5` `effortLevel: "medium"`, origin unknown.

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

> Gate 1 (scope): wave 1's spike sessions changed your `~/.claude-lolay/settings.json` — Opus `effortLevel` saved as `high` (the subagent says it was xhigh before) and `skipWorkflowUsageWarning: true` — and accepted workspace trust for two `.scratch/spike/` folders. Shall I restore Opus to `xhigh` and remove `skipWorkflowUsageWarning`, and continue to wave 2 (m1 s4-s6 on Sonnet), whose spike sessions will pass effort on the command line and use a throwaway settings file so they can't write your config again?

## How to resume

Paste the Kickoff prompt from the top of the plan into a new Claude Code chat on `/model opus` with `/effort high`; it re-posts the pending question above.
