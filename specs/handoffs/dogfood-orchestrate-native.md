# Run sheet: phase 1 dogfood of personal-plan-orchestrate (m2.s9)

Plan `specs/handoffs/plan-orchestrate-native-kestrel.md`, step m2.s9; design `specs/plan-orchestration.md`. Gary runs three real plans through the shipped skill, each in its own session; a later fresh subagent reads what they leave behind, applies the fixes and flips the gate. Nobody relays during the runs. Wave 8 deletes this file.

| Run | Where | Mode | Answer at the kickoff question | New session from the pasted prompt |
|---|---|---|---|---|
| A | Mac CLI, a local repo | gated | `gated here` | at its second gate stop (re-entry with a `BLOCKED` question) |
| B | Mac CLI, a repo with a remote | unattended | `unattended` (no `here`) | right after the kickoff (the paste confirms unattended) |
| C | Claude Code on the web | unattended | `yes` (decision 9) | no |

## 1. Pick three plans

Every plan needs:
- **Real work you want done**, written as a plan in the standard's shape: `## m{N} - …` milestone sections and `#### s{K} - …` steps, with acceptance criteria. Plan mode plus `personal-handoff` ("save the plan") makes one; it doesn't need tags, since the kickoff runs `personal-plan-tag-tiers`.
- **3-5 waves after tagging** (roughly 6-15 steps), with **at least one tier change into `[deep]` after `[exec]` or `[fast]`** (gate 2) and **at least one milestone boundary** (gate 4). `[xdeep]` is allowed but not needed (it costs more; a planned one is a checkpoint unattended).
- **A repo with a GitHub remote, `origin/HEAD` known, and `.scratch/` in `.gitignore`.** The snapshot fails without the ignore line, and the kickoff stops there. A repo whose `.claude/settings.json` has the `personal-repo-baseline` attribution (`Assisted-by: Claude Code`) avoids a kickoff warning.
- **No outward actions inside the steps** (deploys, PRs, tags, posting): a worker that needs one stops with `needs_info`, which is the design's stop, not a test.
- **A moderate expected cost**, about $5-25 in the Cost table, so the guard (3x or $50) never trips by accident.

Per run:
- **A, Mac gated:** any repo on this Mac, ideally starting on `main` so the kickoff names a new task branch and cuts it after your answer. A second repo in the same plan is a bonus (a two-group canary; start the session with `--add-dir`). Mac-only tooling is fine.
- **B, Mac unattended:** a repo with a remote (decision 11: unattended needs one). Its test commands should be in the allow list (§2 step 3), or the run waits at a permission prompt, which is a design stop.
- **C, runner unattended:** a GitHub repo the cloud environment can clone and push (the Claude GitHub App has access), with no Mac-only tools or secrets. A **private** repo is better: its report may carry transcript excerpts. **Wave 3 must cross a gate** (2, 3, 4 or 7) right after wave 2, since the typed `gated` switch during wave 2 is tested by wave 3 stopping. Example shape: wave 1 `[exec]` m1, wave 2 `[exec]` m1, wave 3 `[deep]` m2.

Candidates I can see from here, only if they're on your list: applying a saved Makefile audit to one repo of `nowline` or `triage` with `personal-makefile` (Mac, `[exec]`-heavy; pick one repo, not the whole workspace), or a self-contained piece of a follow-up such as Codex's role files for phase 2 (runner, offline tests). Avoid plain folders of sibling repos: they keep the plan in `.scratch/`, and m2.s9 asks for `specs/handoffs/`.

## 2. One-time setup

1. **Push this branch.** The orchestrating parent pushes `feature/orchestrate-native` after this wave; that carries the rebuilt spike plugin (`b75c58c`).
2. **Re-sync `orch-spike`.** In claude.ai's organization plugin settings, sync the `orch-spike-lab` source (`GaryRudolph/orchestrate-spike`), as for criterion 6. Its marketplace pins `ref: feature/orchestrate-native`, so it now serves the wave-6 kit; the scratch repo itself needs no push. The Mac's synced copy (`~/.claude-lolay/plugins/synced/…/orch-spike/`, synced 2026-10-07 10:39) is pre-wave-5: no `reviewer_guard.py`, and a gate hook without the compaction, queued-message and `<pasted_content>` fixes, so it would deny run B's pasted confirmation. Check the Mac copy after the sync (start any `CLAUDE_CONFIG_DIR=~/.claude-lolay claude` session once, quit, then):

       cd ~/Projects/personal/public
       diff -r --exclude=__pycache__ ~/.claude-lolay/plugins/synced/*/orch-spike/skills/orch-spike-plan-orchestrate/scripts \
         specs/handoffs/orchestrate-native/spike-plugin/orch-spike/skills/orch-spike-plan-orchestrate/scripts && echo current

   Both gate hooks then run on every Mac launch with the same rules, so they agree. If it isn't `current`, don't start A or B.
3. **Freeze the kit for the Mac runs** (so a branch switch or a later fix doesn't change the hooks mid-run):

       git -C ~/Projects/personal/public fetch origin
       git -C ~/Projects/personal/public worktree add --detach ~/Projects/personal/orchestrate-kit origin/feature/orchestrate-native

   The session settings for A and B are already in `.scratch/dogfood/mac-gated/settings.json` and `.scratch/dogfood/mac-unattended/settings.json` (gitignored): the allow rules from spec §2.5 (`Workflow(personal:plan-segment)`, `git add`/`commit`/`push` and read-only git, the three scripts under the frozen kit) and a capture hook that appends every `Bash` and `Workflow` hook input to `hook-input.jsonl` beside it. Add each repo's test command to `permissions.allow` (for example `"Bash(make test:*)"`). `--settings` is per session, so nothing in `~/.claude-lolay` changes.
4. **Run C's allow rules:** a cloud session can't take `--settings`. Either accept the first Workflow permission prompt with "don't ask again", or commit to the repo's default branch beforehand a `.claude/settings.json` with `"permissions": {"allow": ["Workflow(orch-spike:plan-segment)", "Bash(git add:*)", "Bash(git commit:*)", "Bash(git push:*)", "<the repo's test command>"]}`. A prompt mid-run waits for you; that's the design.
5. **The Mac launch command** (run from the plan's repo; add `--add-dir <repo>` per extra repo):

       CLAUDE_CONFIG_DIR=~/.claude-lolay claude \
         --plugin-dir ~/Projects/personal/orchestrate-kit/plugins/personal \
         --settings ~/Projects/personal/public/.scratch/dogfood/<mac-gated|mac-unattended>/settings.json

   then `/model opus` and `/effort high`. `--plugin-dir` outranks the synced `personal` (wave 1: "shadowed by local copy personal@inline"). The desktop app can't take `--plugin-dir` and loads main's `personal`, so A and B run in the CLI. Run B may add `--permission-mode auto` (worker commits pass in auto mode, criterion 3).

## 3. The runs

### A: Mac, gated

1. Launch (§2 step 5, `mac-gated`) in the repo, on `main` if you can.
2. Start: `Orchestrate the plan at <path to plan.md> with the personal-plan-orchestrate skill.` (An untagged plan is tagged first; a `.scratch/` plan moves to `specs/handoffs/` at kickoff.)
3. **Kickoff question:** expect the waves and tiers, the expected total, the gates it crosses, `Claude Code path: phase 1 dogfood.`, `Proposed mode: gated.`, the branch it will cut, and a `Reply …` line. Answer `gated here`. Expect: it cuts and pushes the branch, commits plan and handoff, launches the canary (first group only).
4. **Gate 5 (canary):** a stop with commit ranges and a short handoff summary. Answer `yes, continue wave 1`.
5. **Each later gate (2, 4):** a stop with `BLOCKED at gate N`. At the **second** gate stop, don't answer: quit, relaunch the same command, and paste the plan's Kickoff prompt (from the plan's Kickoff block). Expect: it re-posts the `BLOCKED` question verbatim and asks nothing else; answer it in that session. The gated record carries over, and the new session's first launch is a canary again.
6. To the end: the Completion summary, the final handoff, and a PR question. Answer `not yet` (the PR is your call later).

### B: Mac, unattended

1. Launch (§2 step 5, `mac-unattended`) in the repo.
2. Start: `Orchestrate the plan at <path to plan.md> with the personal-plan-orchestrate skill.`
3. **Kickoff question:** proposes gated (no runner signal). Answer `unattended` alone. Expect: it records your words, cuts or keeps the task branch, commits and pushes, prints the Kickoff prompt with the kickoff summary, and **halts for a new chat**.
4. **New session:** quit, relaunch the same command, paste the whole Kickoff prompt. Expect: no question; it records `confirmed … session <new id> by Kickoff prompt: Run in unattended mode.`, commits, pushes, prints the summary and launches. (This is the first live check of the CLI's `<pasted_content>` unwrap.)
5. **While wave 2 runs**, type `/compact`. Expect the next launch to go through (no "a later human turn names gated" deny).
6. Let it run. Gates 2, 4, 5 should pass as checkpoints (`passed unattended: …` in the Review log and Status). It should stop only for a design reason (a `needs_info`, a scope breach, a third failure, the guard) or at the PR question. Answer `not yet`.

### C: runner, unattended

1. On claude.ai/code, start a session on the repo, default branch, model Opus, high effort.
2. Start with this, then paste the plan's text below it (the kickoff saves it to `specs/handoffs/`):

       Orchestrate the plan below with the orch-spike-plan-orchestrate skill. Its plugin is orch-spike:
       the agents are orch-spike:plan-*, the workflow is orch-spike:plan-segment, and args.plugin is
       "orch-spike". Don't use the personal-plan-orchestrate skill (main's older copy, also loaded).

   (The spike copy's `adapters/claude-code.md` still says `<P>` is `personal`; SKILL.md's rule, the skill's own name, wins. Watch for a parent that passes `personal`.)
3. **Kickoff question:** expect `Runner detected (CLAUDE_CODE_REMOTE=true). Proposed mode: unattended.` and the assigned `claude/…` branch. Answer `yes` (decision 9). Expect it to record `unattended` with your `yes`, commit, push, and launch with no further question.
4. **While wave 1 runs**, type `/compact` (the runner's false deny in phase 0). Expect wave 2 to launch.
5. **The `gated` switch, with a window:** right after the parent's one-line "wave 2 running" reply, type `gated`. Wave 2 takes minutes (workers plus an Opus review), so there is no race. Expect a one-line reply now; at wave 2's completion it records the switch (mode line and the prompt's mode line), commits, pushes, and **stops at wave 3's gate** with `BLOCKED at gate N`, the question and the short summary. If wave 2 had already ended, type it anyway: the take-back still stops the next launch.
6. Answer the gate (`yes, continue wave 3`): the first approval launch on a runner, gated. Optionally type `unattended` later to switch back; it should also pass a pending checkpoint gate.
7. The runner's Stop hook may say "commit and push" while workers run; the parent should reply one line and not commit. At the PR question answer `not yet`.
8. **Closing prompt** (after the PR question), so the fix-up subagent can work without the cloud transcript:

       Write specs/handoffs/dogfood-runner-report.md and commit and push it on this branch. From your own
       transcript and run records: the session id, Claude Code version, and the branch you started on and
       worked on; every Workflow launch (runId, unit, approved, result stop and gates) and every hook deny
       verbatim; the transcript records for my `/compact`, my `gated` message and my `yes` (type,
       promptSource, turnOrigin, origin.kind, isCompactSummary, and queued_command attachments), quoted as
       JSON; each Stop hook firing and your reply; whether a reviewer's Bash call was ever denied; token use
       per model from the transcripts; and anything the skill's procedure didn't cover.

## 4. Checks the dogfood must cover

| Check | Where | How it shows |
|---|---|---|
| A typed `gated` switch stops the next launch | C step 5 | The mode line's `confirmed` part holds `gated` and its session; `BLOCKED at gate N` before wave 3; the report's record shapes |
| Gated mode on a runner: a gate stop, `BLOCKED`, an approval launch | C step 6 | Plan and handoff on the `claude/…` branch; the report's launches |
| `/compact` doesn't void unattended (m2.s2 item 1) | B step 5, C step 4 | The next launch has no deny |
| Decision 9's plain yes | C step 3 | The mode line reads `confirmed … : yes`; the launch passed |
| A pasted Kickoff prompt confirms unattended on the CLI (`<pasted_content>` unwrap) | B step 4 | `by Kickoff prompt` on the mode line; no deny |
| Re-entry re-posts a `BLOCKED` question; gated carries over | A step 5 | The new session's first message |
| The reviewer's `agent_type` reaches the Bash hook as `personal:plan-reviewer` | A, B | `.scratch/dogfood/<run>/hook-input.jsonl`: Bash inputs from reviewer agents and their `agent_type`. The subagent then replays one with a write (`jq '.tool_input.command="touch x"' … \| python3 reviewer_guard.py`) to show the deny on a real input |
| Worker commits in auto mode; `check_wave.py` on real repos | B | The Review log, no fix-up for commit shape |
| Cost: actual against expected | A, B, C | Each plan's Cost table actual columns at completion; the subagent notes the ratio in the session handoff |
| Cursor `[exec]` slug | only if you run one on Cursor | Whether `Task`'s `model` accepts `grok-4-7[effort=high,fast=false]`; note what the enum offers |

## 5. What to paste back, and where the subagent finds it

After each run, paste to the orchestrating chat (or fill the table below):
- **A, B:** the repo path on this Mac, the task branch, the plan path, the outcome in a line (completed / stopped at gate N for <reason>), and anything that surprised you.
- **C:** the GitHub repo, the `claude/…` branch, the session URL, and the outcome in a line.

Where the evidence is:
- **Plans and handoffs:** `specs/handoffs/plan-*.md` and `handoff-*.md` on each task branch, pushed (C's on GitHub; the subagent fetches it).
- **Mac transcripts:** `~/.claude-lolay/projects/<slug>/<session-id>.jsonl`, where `<slug>` is the repo path with every non-alphanumeric character turned into `-`; each run's records under `<session-id>/workflows/<runId>.json` and workers under `<session-id>/subagents/workflows/<runId>/`. Session ids: the plan's mode line names the confirming session; `ls -t ~/.claude-lolay/projects/<slug>/*.jsonl` lists the rest (A has two sessions, B two).
- **Hook captures:** `~/Projects/personal/public/.scratch/dogfood/mac-gated/hook-input.jsonl` and `mac-unattended/hook-input.jsonl`.
- **C's transcript:** `specs/handoffs/dogfood-runner-report.md` on its branch. If the desktop app's session tools can export the cloud session by its URL, that's the raw source.

| Run | Repo | Branch | Plan | Sessions | Outcome |
|---|---|---|---|---|---|
| A | | | | | |
| B | | | | | |
| C | | | | | |

## 6. Afterwards

- Remove the frozen kit: `git -C ~/Projects/personal/public worktree remove ~/Projects/personal/orchestrate-kit`.
- The fix-up subagent applies fixes, flips the gate (removes "phase 1: dogfood" from `SKILL.md`, the adapter and the spec's Status line), rebuilds `orch-spike` only if a later run needs it, and records each run's outcome and cost ratio in the session handoff.
- After m2.s9, decide whether to remove the org's `orch-spike-lab` source and the scratch repo's branches (m2.s10 asks). Wave 8 deletes `specs/handoffs/orchestrate-native/`, which the org source points at.
