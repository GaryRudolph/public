# Run sheet: phase 1 dogfood of personal-plan-orchestrate (m2.s9)

Plan `specs/handoffs/plan-orchestrate-native-kestrel.md`, step m2.s9; design `specs/plan-orchestration.md`. Gary runs three real plans through the shipped skill, each in its own session, on one target: bringing `lolay/ghx` to the shape of `lolay/triage` (macOS, Linux and Windows; CI; releases to the lolay Homebrew tap and Scoop bucket). A later fresh subagent reads what the runs leave behind, applies the fixes and flips the gate. Nobody relays during the runs. Wave 8 deletes this file and `specs/handoffs/dogfood-ghx/`.

| Run | Plan | Where | Mode | Answer at the kickoff question | New session from the pasted prompt |
|---|---|---|---|---|---|
| A | `plan-ghx-baseline-heron` | Mac CLI, `~/Projects/lolay/ghx` | gated | `gated here` | at its second gate stop (re-entry with a `BLOCKED` question) |
| B | `plan-ghx-platforms-lynx` | Mac CLI, `~/Projects/lolay/ghx` | unattended | `unattended` (no `here`) | right after the kickoff (the paste confirms unattended) |
| C | `plan-ghx-release-finch` | Claude Code on the web, `lolay/ghx` | unattended, switched to gated in wave 2 | `yes` (decision 9) | no |

## 1. The three ghx plans

The plans are in this repo at `specs/handoffs/dogfood-ghx/`, tagged, with acceptance criteria per step and no Kickoff block, wave markers or Cost table (the kickoff writes those). Each run's plan goes into ghx as described in §3. Step headings are the standard `#### s{K} - [tier] Title` under their `## m{N}` milestone, numbered from `s1` in each; `plan_state.py` qualifies each as `m{N}.s{K}`, the ID that dispatches and commit subjects carry.

| Plan | What it does | Waves after grouping | Gates it crosses | Expected |
|---|---|---|---|---|
| A `plan-ghx-baseline-heron` | Module `github.com/lolay/ghx` and binary `ghx` (from `ghx-go`); `.gitignore`, `.gitattributes`, `.go-version`; a standard Makefile + `Makefile.md`, `.golangci.yml`, `triage.yaml` for `make doctor`; test seams and the first unit tests (`config`, filter, `manifest`, `ui`) with `specs/testing.md`; README, CHANGELOG, CONTRIBUTING, SECURITY, CODEOWNERS, AGENTS.md | 1 `[exec]` m1 s1-s3 (s2 `[fast]` folded), 2 `[deep]` m1 s4, 3 `[exec]` m2 s1-s2 | 5 (canary, wave 1); 2 (wave 2); 4 (wave 3) | about $9-12 |
| B `plan-ghx-platforms-lynx` | Hermetic tests for the cloner (local bare repos), a GitHub API seam with `httptest`, end-to-end run-flow tests; a Windows audit and fixes (reserved names, rename and delete of git dirs, `git.exe`, console colour, long paths); `ci.yml` on macOS, Linux and Windows; then reading that branch's CI run and fixing what fails | 1 `[exec]` m1 s1-s3, 2 `[deep]` m1 s4, 3 `[exec]` m2 s1-s2, 4 `[deep]` m2 s3 | 5; 2 (wave 2); 4 (wave 3); 2 (wave 4) | about $11-14 |
| C `plan-ghx-release-finch` | `version.txt`, `internal/buildinfo` and `ghx --version` per `versioning.md`; `.goreleaser.yaml` and a local snapshot; formula and Scoop publishers (dry run only); Danger targets; `release.yml` (personal-release template) and a tag-triggered `publish.yml` (goreleaser, then tap, then bucket); release docs. Ends before any tag, secret or publish | 1 `[deep]` m1 s1, 2 `[exec]` m1 s2-s4, 3 `[deep]` m2 s1, 4 `[exec]` m2 s2 | 5; 4 and 2 (wave 3) | about $11-13 |

Expected figures are mine from the standard's anchors; each kickoff's Cost table is the one of record. None of the steps pushes a tag, publishes, opens a PR or writes to `lolay/homebrew-tap` or `lolay/scoop-bucket`.

**Order: they don't stack; merge each before the next starts.** B builds on A's Makefile and module path, and C adds a job to B's `ci.yml`. Each kickoff starts from ghx `main` (A and B cut their task branch from it; C's cloud session gets its `claude/…` branch from it), so A's PR merges before B's kickoff, and B's before C's. B's PR is also where the Windows and macOS jobs run for real: merge it only when all three are green.

**Where to start:** run A first. It's the smallest (three waves), Mac only, gated so every gate stops in front of you, and the others need it merged. Its wave 1 (rename, hygiene, Makefile) ends at the canary stop, about $2-3 in: that's the cheap point to judge the kit before spending more. A single step can't stand in for a run, because the checks need a canary, a gate 2, a gate 4 and a re-entry in one plan.

**Left for afterwards** (not in any plan, §6): the first real release (secrets, tag, tap and bucket rows), GitHub's merge settings for ghx, and the token in ghx's HTTPS clone URLs (git stores it in every clone's `.git/config`; B's wave 2 notes it as a follow-up).

## 2. One-time setup

1. **Push this branch.** The orchestrating parent pushes `feature/orchestrate-native` after this wave; that carries the rebuilt spike plugin (`49573fb`, with the step-ID fix) and the three plans.

   **Gary's ghx decisions (2026-10-08):** rename the binary `ghx-go` to `ghx` (plan A); `version.txt` starts at `0.1.0` (plan C), and the first release is `0.2.0` (a minor bump, done by Gary by hand after the dogfood).
2. **Re-sync `orch-spike`.** In claude.ai's organization plugin settings, sync the `orch-spike-lab` source (`GaryRudolph/orchestrate-spike`), as for criterion 6. Its marketplace pins `ref: feature/orchestrate-native`, so it now serves the wave-6 kit; the scratch repo itself needs no push. The Mac's synced copy (`~/.claude-lolay/plugins/synced/…/orch-spike/`, synced 2026-10-07 10:39) is pre-wave-5: no `reviewer_guard.py`, and a gate hook without the compaction, queued-message and `<pasted_content>` fixes, so it would deny run B's pasted confirmation. Check the Mac copy after the sync (start any `CLAUDE_CONFIG_DIR=~/.claude-lolay claude` session once, quit, then):

       cd ~/Projects/personal/public
       diff -r --exclude=__pycache__ ~/.claude-lolay/plugins/synced/*/orch-spike/skills/orch-spike-plan-orchestrate/scripts \
         specs/handoffs/orchestrate-native/spike-plugin/orch-spike/skills/orch-spike-plan-orchestrate/scripts && echo current

   Both gate hooks then run on every Mac launch with the same rules, so they agree. If it isn't `current`, don't start A or B.
3. **Freeze the kit for the Mac runs** (so a branch switch or a later fix doesn't change the hooks mid-run). The plans are read from here too:

       git -C ~/Projects/personal/public fetch origin
       git -C ~/Projects/personal/public worktree add --detach ~/Projects/personal/orchestrate-kit origin/feature/orchestrate-native

   The session settings for A and B are in `.scratch/dogfood/mac-gated/settings.json` and `.scratch/dogfood/mac-unattended/settings.json` (gitignored): the allow rules from spec §2.5 (`Workflow(personal:plan-segment)`, `git add`/`commit`/`push` and read-only git, the three scripts under the frozen kit), ghx's commands (`make`, `go build`/`test`/`vet`/`mod`/`tool`, `go run ./cmd/ghx`, `gofmt`, `golangci-lint run`, the three `GOOS=… go vet` forms, `git mv`, `git check-ignore`, `actionlint`, and `gh run list`/`view`/`watch` for B's last wave), and a capture hook that appends every `Bash` and `Workflow` hook input to `hook-input.jsonl` beside it. `--settings` is per session, so nothing in `~/.claude-lolay` changes. Run A will still prompt for a few commands (a `curl` to go.dev for the Go version, installing govulncheck); approve them, it's gated.
4. **Prepare ghx's `main`** (once, before A). The snapshot fails without `.scratch/` ignored, and without the attribution setting worker commits get a `Co-authored-by` line that `check_wave.py` rejects:

       cd ~/Projects/lolay/ghx
       git switch main && git pull --ff-only
       printf '\n# Agent scratch: plans in progress and worker artifacts\n/.scratch/\n' >> .gitignore
       mkdir -p .claude
       cp ~/Projects/personal/public/plugins/personal/skills/personal-repo-baseline/templates/claude-settings.json .claude/settings.json
       git add .gitignore .claude/settings.json
       git commit -m "ignore .scratch and add the agent baseline settings"
       git push origin main
       git check-ignore -q .scratch/x && echo ignored

   Optional: run `personal-repo-baseline` on ghx too, for squash-only merges with the PR's title and body (ghx allows merge commits today).
5. **Run C's access and allow rules** (before C, after B merged):
   - **Repo access:** the Claude GitHub App is installed on the `lolay` org with access to all repositories (checked 2026-10-07: installation `claude`, `repository_selection: all`), so a cloud session can clone and push `lolay/ghx`, provided your claude.ai account is connected to GitHub with access to `lolay`. If the session can't see the repo, grant the app access in the org's GitHub App settings.
   - **Public repo:** ghx is public, so the run's plan, handoff and closing report sit on a public branch until the cleanup commit. The closing prompt (§3 C step 9) keeps the report to record fields. If that's not acceptable, run C on a private mirror instead (`gh repo create lolay/ghx-dogfood --private`, push `main` there, and use that repo in step 1).
   - **Allow rules:** a cloud session can't take `--settings`. Replace ghx's `.claude/settings.json` on `main` with this (it keeps the baseline) and push; §6 removes the `orch-spike` line afterwards. Otherwise accept each prompt with "don't ask again" as it comes; a prompt mid-run waits for you, which is the design.

         {
           "$schema": "https://json.schemastore.org/claude-code-settings.json",
           "permissions": {
             "allow": [
               "Workflow(orch-spike:plan-segment)",
               "Bash(git add:*)",
               "Bash(git commit:*)",
               "Bash(git push:*)",
               "Bash(make:*)",
               "Bash(go build:*)",
               "Bash(go test:*)",
               "Bash(go vet:*)",
               "Bash(go mod:*)",
               "Bash(go run:*)",
               "Bash(gofmt:*)",
               "Bash(python3 scripts/bump_version.py:*)"
             ]
           },
           "attribution": {
             "commit": "Assisted-by: Claude Code",
             "pr": "Assisted-by: Claude Code"
           }
         }

   - **Toolchain:** C needs Go at ghx's `go.mod` version, plus network to `proxy.golang.org` (and `github.com` for the triage clone and `go run` of goreleaser and actionlint). The cloud image's Go may be older; Go's `GOTOOLCHAIN=auto` fetches the right one through the module proxy. If the environment's network access is set below the package-registry level, raise it, or add a setup script that installs Go, before C.
6. **The Mac launch command** (run from `~/Projects/lolay/ghx`):

       CLAUDE_CONFIG_DIR=~/.claude-lolay claude \
         --plugin-dir ~/Projects/personal/orchestrate-kit/plugins/personal \
         --settings ~/Projects/personal/public/.scratch/dogfood/<mac-gated|mac-unattended>/settings.json

   then `/model opus` and `/effort high`. `--plugin-dir` outranks the synced `personal` (wave 1: "shadowed by local copy personal@inline"). The desktop app can't take `--plugin-dir` and loads main's `personal`, so A and B run in the CLI. Run B adds `--permission-mode auto` (worker commits pass in auto mode, criterion 3).

## 3. The runs

### A: Mac, gated (`plan-ghx-baseline-heron`)

1. **Put the plan in ghx, untracked, on `main`:**

       cd ~/Projects/lolay/ghx
       git switch main && git pull --ff-only
       mkdir -p specs/handoffs
       cp ~/Projects/personal/orchestrate-kit/specs/handoffs/dogfood-ghx/plan-ghx-baseline-heron.md specs/handoffs/
       git status --short        # only: ?? specs/

2. **Launch** (§2 step 6, `mac-gated`), then `/model opus` and `/effort high`.
3. **Start:**

       Orchestrate the plan at specs/handoffs/plan-ghx-baseline-heron.md with the personal-plan-orchestrate skill.

4. **Kickoff question.** Expect: 3 waves (1 `[exec]` m1 s1-s3, 2 `[deep]` m1 s4, 3 `[exec]` m2 s1-s2), the expected total, `Gates it crosses: 5 (canary, wave 1); 2 (before wave 2); 4 (before wave 3).`, `Claude Code path: phase 1 dogfood.`, `No runner signal … Proposed mode: gated.`, `main is a shared branch, so the run goes on a new task branch, feature/ghx-baseline-heron`, a line starting `Reply`, and the short handoff summary. Nothing committed yet (`git status` still shows the plan untracked). Answer:

       gated here

   Expect: it records `gated` with your words, cuts and pushes `feature/ghx-baseline-heron`, commits the plan and handoff in one commit with no step ID, pushes, prints the kickoff summary and launches wave 1. Wave 1 has one group, so the canary is the whole wave.
5. **First stop, after wave 1** (gates 5 and 2 in one question): wave 1's commit range (`m1.s1`-`m1.s3` commits), a Review log line, the next unit (wave 2 `[deep]` m1 s4) and the short handoff summary. Answer:

       yes, continue wave 2

6. **Second stop, before wave 3** (`BLOCKED at gate 4`). **Don't answer.** Quit (`/exit`), relaunch the same command (same folder, now on `feature/ghx-baseline-heron`), `/model opus`, `/effort high`, and paste the plan's Kickoff prompt: the indented lines after `Prompt to paste into the next chat:` in the plan's Kickoff block (`sed -n '/Prompt to paste into the next chat:/,/^---$/p' specs/handoffs/plan-ghx-baseline-heron.md`). Expect: it re-posts the `BLOCKED at gate 4` question verbatim and asks nothing else; no new mode record (gated carries over). Answer:

       yes, continue wave 3

   Expect: wave 3 runs as this session's canary (one group, so the whole wave), then the Completion summary and the PR question. If it stops at gate 5 after wave 3 instead of completing, that's a finding: note it and answer `yes, continue`.
7. **PR question:** the plan and handoffs have to leave the branch before the merge, and B needs this merged. Answer:

       yes: make the cleanup commit, push, and open the PR

   Then merge the PR yourself (squash) once you've read it.

### B: Mac, unattended (`plan-ghx-platforms-lynx`)

1. **After A's PR merged, put the plan in ghx on `main`:**

       cd ~/Projects/lolay/ghx
       git switch main && git pull --ff-only
       mkdir -p specs/handoffs
       cp ~/Projects/personal/orchestrate-kit/specs/handoffs/dogfood-ghx/plan-ghx-platforms-lynx.md specs/handoffs/
       git status --short        # only: ?? specs/handoffs/plan-ghx-platforms-lynx.md

2. **Launch** (§2 step 6, `mac-unattended`, plus `--permission-mode auto`), then `/model opus` and `/effort high`.
3. **Start:**

       Orchestrate the plan at specs/handoffs/plan-ghx-platforms-lynx.md with the personal-plan-orchestrate skill.

4. **Kickoff question.** Expect: 4 waves (1 `[exec]` m1 s1-s3, 2 `[deep]` m1 s4, 3 `[exec]` m2 s1-s2, 4 `[deep]` m2 s3), `Gates it crosses: 5 (canary, wave 1); 2 (before wave 2); 4 (before wave 3); 2 (before wave 4).`, `Proposed mode: gated.` (no runner signal) and the branch `feature/ghx-platforms-lynx`. Answer:

       unattended

   Expect: it records `unattended` with your word, cuts and pushes the branch, commits the plan and handoff, pushes, prints the Kickoff prompt, the kickoff summary and the short handoff summary, and **halts for a new chat**.
5. **New session:** copy the printed Kickoff prompt (all of it, from `In lolay/ghx, read …` to `… begin dispatching.`). Quit, relaunch the same command (with `--permission-mode auto`), `/model opus`, `/effort high`, and paste it. Expect: no question; the mode line now ends `confirmed <today> session <new id> by Kickoff prompt: Run in unattended mode.`; it commits, pushes, prints the kickoff summary with the spend so far, and launches wave 1. (The first live check of the CLI's `<pasted_content>` unwrap.)
6. **While wave 2 runs** (after the parent's one-line "wave 2 running" reply; wave 2 is the `[deep]` Windows audit, several minutes), type:

       /compact

   Expect: wave 3 launches when wave 2 ends (no "a later human turn names gated" deny).
7. **Let it run.** Gates 5, 2, 4 and 2 pass as checkpoints (`passed unattended: …` in the Review log and Status). Wave 4 waits on the branch's CI run (`gh run watch`), so expect it to take as long as the slowest of the macOS, Linux and Windows jobs. It should stop only for a design reason (a `needs_info`, a scope breach, a third failure, the guard) or at the PR question. Answer:

       yes: make the cleanup commit, push, and open the PR

   Merge the PR yourself once its CI is green on all three operating systems.

### C: runner, unattended, switched to gated (`plan-ghx-release-finch`)

1. **After B's PR merged** and §2 step 5 is done: on claude.ai/code, start a session on `lolay/ghx` (or the private mirror), branch `main`, model Opus, high effort.
2. **Copy the plan:** `pbcopy < ~/Projects/personal/orchestrate-kit/specs/handoffs/dogfood-ghx/plan-ghx-release-finch.md`.
3. **Start** with this, then a blank line, then paste the plan:

       Orchestrate the plan below with the orch-spike-plan-orchestrate skill. Its plugin is orch-spike:
       the agents are orch-spike:plan-*, the workflow is orch-spike:plan-segment, and args.plugin is
       "orch-spike". Don't use the personal-plan-orchestrate skill (main's older copy, also loaded).
       Save the plan as specs/handoffs/plan-ghx-release-finch.md.

   (The spike copy's `adapters/claude-code.md` still says `<P>` is `personal`; SKILL.md's rule, the skill's own name, wins. Watch for a parent that passes `personal`.)
4. **Kickoff question.** Expect: the branch it started on and its assigned `claude/…` branch (switched to and pushed before saving), 4 waves (1 `[deep]` m1 s1, 2 `[exec]` m1 s2-s4, 3 `[deep]` m2 s1, 4 `[exec]` m2 s2), `Gates it crosses: 5 (canary, wave 1); 4 and 2 (before wave 3).`, `Runner detected (CLAUDE_CODE_REMOTE=true). Proposed mode: unattended.` Answer:

       yes

   Expect: it records `unattended` with your `yes` (decision 9), commits, pushes, and launches wave 1 with no further question.
5. **While wave 1 runs**, type:

       /compact

   Expect wave 2 to launch when wave 1 ends (the runner's false deny in phase 0).
6. **The `gated` switch:** right after the parent's one-line "wave 2 running" reply, type:

       gated

   Wave 2 (goreleaser, the publishers, the Danger targets) takes minutes, so there's no race. Expect a one-line reply now; at wave 2's completion it records the switch (the mode line's `confirmed` part and the prompt's `Run in gated mode.`), commits, pushes, and **stops before wave 3** with `BLOCKED at gate 4` (gates 4 and 2), the question and the short summary. If wave 2 had already ended, type it anyway: the take-back still stops the next launch.
7. **Approve wave 3**, the first approval launch on a runner, gated:

       yes, continue wave 3

   Expect wave 3 (`[deep]` workflows) to launch, then wave 4 (`[exec]` docs) with no stop (no gate between them), then the Completion summary and the PR question.
8. The runner's Stop hook may say "commit and push" while workers run; the parent should reply one line and not commit. At the PR question answer:

       not yet

9. **Closing prompt**, so the fix-up subagent can work without the cloud transcript:

       Write specs/handoffs/dogfood-runner-report.md and commit and push it on this branch. From your own
       transcript and run records: the session id, Claude Code version, and the branch you started on and
       worked on; every Workflow launch (runId, unit, approved, result stop and gates) and every hook deny
       verbatim; the transcript records for my `/compact`, my `gated` message and my `yes` (type,
       promptSource, turnOrigin, origin.kind, isCompactSummary, and queued_command attachments), quoted as
       JSON; each Stop hook firing and your reply; whether a reviewer's Bash call was ever denied; token use
       per model from the transcripts; and anything the skill's procedure didn't cover. This repo is public:
       quote only those record fields, never environment values, tokens or file contents.

## 4. Checks the dogfood must cover

| Check | Where | How it shows |
|---|---|---|
| A typed `gated` switch stops the next launch | C step 6 | The mode line's `confirmed` part holds `gated` and its session; `BLOCKED at gate 4` before wave 3; the report's record shapes |
| Gated mode on a runner: a gate stop, `BLOCKED`, an approval launch | C step 7 | Plan and handoff on the `claude/…` branch; the report's launches |
| `/compact` doesn't void unattended (m2.s2 item 1) | B step 6, C step 5 | The next launch has no deny |
| Decision 9's plain yes | C step 4 | The mode line reads `confirmed … : yes`; the launch passed |
| A pasted Kickoff prompt confirms unattended on the CLI (`<pasted_content>` unwrap) | B step 5 | `by Kickoff prompt` on the mode line; no deny |
| A workstation names and cuts the task branch only after the answer | A step 4, B step 4 | Nothing committed on `main`; the branch's first commit is the kickoff's |
| Re-entry re-posts a `BLOCKED` question; gated carries over | A step 6 | The new session's first message; no new `confirmed` record |
| The reviewer's `agent_type` reaches the Bash hook as `personal:plan-reviewer` | A, B | `.scratch/dogfood/<run>/hook-input.jsonl`: Bash inputs from reviewer agents and their `agent_type`. The subagent then replays one with a write (`jq '.tool_input.command="touch x"' … \| python3 reviewer_guard.py`) to show the deny on a real input |
| Worker commits in auto mode; `check_wave.py` on real commits | B | The Review log, no fix-up for commit shape |
| A milestone handoff at gate 4 (core.md, a project with `specs/`) | B, C (checkpoints) | `specs/handoffs/handoff-m2-….md` on the branch before wave 3's commits; note whether gated A wrote one too |
| Cost: actual against expected | A, B, C | Each plan's Cost table actual columns at completion; the subagent notes the ratio in the session handoff |
| Cursor `[exec]` slug | only if you run one on Cursor | Whether `Task`'s `model` accepts `grok-4-7[effort=high,fast=false]`; note what the enum offers |

## 5. What to paste back, and where the subagent finds it

After each run, paste to the orchestrating chat (or fill the table below): the branch, the PR number, the outcome in a line (completed / stopped at gate N for <reason>), and anything that surprised you; for C also the session URL.

Where the evidence is:
- **Plans and handoffs:** on each task branch before its cleanup commit. A merged PR's commits stay fetchable after the branch is deleted (`git fetch origin pull/<N>/head`), and the Mac clone keeps its local branches; don't delete them until the subagent is done.
- **Mac transcripts:** `~/.claude-lolay/projects/-Users-gary-Projects-lolay-ghx/<session-id>.jsonl`; each run's records under `<session-id>/workflows/<runId>.json` and workers under `<session-id>/subagents/workflows/<runId>/`. Session ids: the plan's mode line names the confirming session; `ls -t ~/.claude-lolay/projects/-Users-gary-Projects-lolay-ghx/*.jsonl` lists the rest (A has two sessions, B two).
- **Hook captures:** `~/Projects/personal/public/.scratch/dogfood/mac-gated/hook-input.jsonl` and `mac-unattended/hook-input.jsonl`.
- **C's transcript:** `specs/handoffs/dogfood-runner-report.md` on its `claude/…` branch. If the desktop app's session tools can export the cloud session by its URL, that's the raw source.

| Run | Repo | Branch | Plan | PR | Sessions | Outcome |
|---|---|---|---|---|---|---|
| A | `lolay/ghx` | `feature/ghx-baseline-heron` | `specs/handoffs/plan-ghx-baseline-heron.md` | | | |
| B | `lolay/ghx` | `feature/ghx-platforms-lynx` | `specs/handoffs/plan-ghx-platforms-lynx.md` | | | |
| C | `lolay/ghx` | `claude/…` | `specs/handoffs/plan-ghx-release-finch.md` | | | |

## 6. Afterwards

- **C's PR:** once the subagent has the report, ask C's session (or do it by hand) for the cleanup commit that removes `specs/handoffs/`, then open the PR. Its CI adds the `goreleaser check` job.
- **ghx's settings:** remove the `Workflow(orch-spike:plan-segment)` line from ghx's `.claude/settings.json` (keep the rest, or cut back to the baseline).
- **The first release, by hand, when you want it** (C's `specs/releasing.md` is the guide): create the three repo secrets on `lolay/ghx` (`RELEASE_TOKEN`: contents write on `lolay/ghx`; `HOMEBREW_TAP_TOKEN`: contents write on `lolay/homebrew-tap`; `SCOOP_BUCKET_TOKEN`: contents write on `lolay/scoop-bucket`; fine-grained PATs, or reuse the scoped ones triage has), then Actions → Release → Run workflow with a level. Its tag starts `publish.yml`: GitHub Release, then `Formula/ghx.rb`, then `bucket/ghx.json`. Add the `ghx` rows to the tap's and the bucket's README tables, and try `brew install lolay/tap/ghx` and `scoop install lolay/ghx`.
- **Follow-up plan:** keep the token out of clone URLs (a credential helper or `http.extraHeader`), and scrub it from failure messages.
- **Remove the frozen kit:** `git -C ~/Projects/personal/public worktree remove ~/Projects/personal/orchestrate-kit`.
- The fix-up subagent applies fixes, flips the gate (removes "phase 1: dogfood" from `SKILL.md`, the adapter and the spec's Status line), rebuilds `orch-spike` only if a later run needs it, and records each run's outcome and cost ratio in the session handoff.
- After m2.s9, decide whether to remove the org's `orch-spike-lab` source and the scratch repo's branches (m2.s10 asks). Wave 8 deletes `specs/handoffs/orchestrate-native/`, which the org source points at, and this file with `specs/handoffs/dogfood-ghx/`.
