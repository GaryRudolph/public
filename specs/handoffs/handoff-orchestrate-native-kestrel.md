# Handoff: harness-native plan orchestration (kestrel)

**Branch:** `feature/orchestrate-native` (task branch, cut from `main` at bf5da80 on Gary's instruction).
**Plan:** `specs/handoffs/plan-orchestrate-native-kestrel.md`, tagged and driven by `personal-plan-model-tiers` (passive). 8 waves, expected ~73M tokens, ~$38 API-equiv.
**Status:** orchestrate driver, Agent-tool path (Gary's option 2), expected ~$54. Wave 1 (m1 s1-s3) done and reviewed PASS; spend so far ~$19. Wave 2: s4 and s5 done, s6 built (`94c710f`, reviewed); blocked at gate 1 on Gary's publish. Spend ~$23.

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

## Wave 2 (m1 s4-s6)

Commit `94c710f` (m1.s6, reviewed): `specs/handoffs/orchestrate-native/spike-plugin/build-spike-plugin.sh` regenerates `spike-plugin/orch-spike/` (62 files: the 5 agents, workflow and hooks fields; skills `orch-spike-plan-orchestrate`, `-plan-model-tiers`, `-plan-tag-tiers`, `-standards`; a SessionStart that prints one marker line, not the core) and `spike-plugin/.claude-plugin/marketplace.json` (marketplace `orch-spike-lab`, one `git-subdir` entry for GaryRudolph/public, `path` the spike plugin, `ref: feature/orchestrate-native`). 152 pass on it, `claude plugin validate` passes on plugin and marketplace, `make -C agents validate test` passes. `~/.claude-lolay/settings.json` unchanged this wave (diffed against `.scratch/spike/lolay-settings-before-wave2.json`).

- **Criterion 5, held for Edit/Write, not for Bash.** `plan-reviewer` and `-xdeep` (Opus) report no Edit or Write tool, and declined `touch` and `git commit` by instruction, even when told the owner authorized it. A control agent with the same allowlist ran both under throwaway allow rules: Bash writes are possible, so the reviewer is read-only by instruction only.
- **Criterion 3, held.** Fresh 1-wave fixture in auto mode (Sonnet parent, Haiku workers, real Opus reviewers), allow rules only `Workflow(personal:plan-segment)`, `Bash(git add/commit/push:*)`, `Bash(grep:*)` from a throwaway `--settings` file: no permission prompt; workers committed `befc062` (repo-a) and `0b5c23d` (repo-b); `check_wave.py` `ok:true` on the first run; the parent's pushes went through.
- **Publish route** (docs checked: code.claude.com/docs/en/plugins/marketplace-reference, host-marketplace, create-marketplace; claude.com/docs/plugins/org-sync.md, overview.md, platform-support.md, admin.md): a marketplace file must sit at the root of a repo's default branch; org sync reads only the default branch and on github.com needs a private repo; `ref`/`sha` pin a plugin source, so the branch pin goes in the entry; the Add marketplace dialog documents no branch ref. Hence the private scratch repo `GaryRudolph/orchestrate-spike`. UNVERIFIED: whether claude.ai sync honors `ref` on `git-subdir`; fallback is a copy of orch-spike in the scratch repo with a `./plugins/orch-spike` relative source.
- **m2.s2 kit changes, adding to wave 1's:** block reviewer Bash writes (a reviewer-scoped `PreToolUse` Bash deny, after checking the hook input carries the subagent type, or drop Bash and pass the diff in the prompt); `check_wave.py` reports the parent's own bookkeeping commit as `others` (`problems: []` but `ok:false`) on a second check, so skip the plan repo's bookkeeping commits there, or have SKILL.md commit the handoff before the snapshot. `Grep`, `Glob` in reviewer `tools:` are no-ops on this CLI build (no change needed).
- **m2.s3 SKILL.md notes:** state the order (refresh and commit plan and handoff, snapshot, launch; hook rule 6 otherwise denies a relaunch); say a canary launch runs only the first group (the Sonnet parent read it as a failure) and that `(done)` goes at the end of the heading.
- Parent's change to the subagent's question: keep the account install of `orch-spike` until wave 3 is done (its cloud checks need it); only the org source can go after criterion 6.

## Criterion 6, org route (Gary, 2026-10-06 22:08)

Org sync of `GaryRudolph/orchestrate-spike` (commit `409b3ff`): "Synced with warnings. Every plugin synced, but these items were left out." One warning, on `orch-spike`: "Plugin 'orch-spike' has unrecognized key in plugin.json: 'workflows' (stripped — the SDK ignores unknown top-level fields)". So the manifest is accepted (no rejection) and `agents` and `hooks` are kept, but `workflows` is dropped on org-synced surfaces. Docs (https://code.claude.com/docs/en/plugins/manifest-reference, checked by the parent): `workflows` is a documented top-level key ("Workflow `.js` files or directories. Replaces the default `workflows/` scan"), and the Standard layout's default for workflows is `workflows/` at the plugin root ("Workflow `.js` files"); an unrecognized top-level key "is stripped, and the plugin loads". So org sync's validator lags the CLI on this key. **Planned fix (parent's proposal, for wave 3 to apply first and m2 to keep):** move `plan-segment.js` from `skills/<org>-plan-orchestrate/claude-workflows/` to `<plugin>/workflows/`, drop the `workflows` key, update the tests and the spike builder, rebuild `orch-spike`, and have Gary re-sync to confirm the warning is gone; criterion 7 then checks the workflow arrives in a cloud session. **Update 2026-10-07:** Gary reports neither the account install nor the org sync shows a warning any more, with no plugin change pushed (commits after `94c710f` touch only the plan and handoff). This desktop session (account install) now lists the 5 `orch-spike:plan-*` agents and `orch-spike:plan-segment` (the workflow, listed among the skills), so the `workflows` key registered there. The warning looks transient or was cleared by a newer validator; the `workflows/` move is held as the fix only if criterion 7 shows the workflow missing in a cloud session. Still pending from Gary: Cowork.

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

> Wave 2 needs you for m1.s6 (criterion 6): publish the `orch-spike` spike plugin and tell me whether claude.ai accepts its new manifest fields. It's a renamed copy of `personal` plus the `agents`, `workflows` and `hooks` fields, on `feature/orchestrate-native` (pushed), so `personal` itself isn't touched.
>
> 1. Create the private scratch repo with the marketplace file (wave 3 also uses it as the cloud fixture):
>
>    cd ~/Projects && gh repo create GaryRudolph/orchestrate-spike --private --clone --description "Phase 0 spike: orch-spike marketplace and cloud fixture"
>    cd orchestrate-spike && mkdir .claude-plugin
>    cp ~/Projects/personal/public/specs/handoffs/orchestrate-native/spike-plugin/.claude-plugin/marketplace.json .claude-plugin/
>    printf '# orchestrate-spike\n\nPhase 0 scratch repo: the orch-spike marketplace and the cloud fixture.\n' > README.md
>    git add -A && git commit -m "add the orch-spike marketplace" && git push -u origin HEAD
>
> 2. Account route (account sync, cloud sessions, Cowork). In claude.ai or the desktop app: Customize > Plugins > Add > Add marketplace, enter `GaryRudolph/orchestrate-spike` (connect GitHub / install the Claude GitHub App on that repo if asked), then under `orch-spike-lab` pick `orch-spike` > Add. Accepted means: no error; `orch-spike` listed with 5 agents and 4 skills; `personal` still present and enabled. Then start a new Cowork task and ask it to list `orch-spike`'s agents and skills: it should start cleanly and see them.
>
> 3. Org route. Organization settings > Plugins & skills > Add > Sync from GitHub, pick `GaryRudolph/orchestrate-spike`, Sync automatically off, Default access Not available, Create. Open Marketplaces > `orch-spike-lab` and read Last synced. Accepted means: no error, `orch-spike` on the Inventory tab, `personal` still there. On an error, copy the date and reason verbatim and change nothing else ("path not found" would mean the branch `ref` was ignored; I'd switch to a copy inside the scratch repo).
>
> 4. Reply with one line per route: accepted, or the verbatim error. Afterwards you can delete the `orch-spike-lab` source from the org, but keep the account install and the repo until wave 3 is done: its cloud checks need `orch-spike` synced into cloud sessions.

## How to resume

Paste the Kickoff prompt from the top of the plan into a new Claude Code chat on `/model opus` with `/effort high`; it re-posts the pending question above.
