# Proposal: running personal-plan-orchestrate natively in each harness (v6)

*As of 2026-10-07. Versions: Claude Code 2.1.292, Codex 0.160.1, Cursor CLI 2026.10.01, Gemini CLI 0.62.0, Grok Build 1.0.46, Muse Code 1.4.3. Builds on `plan-execution.md` as committed at 9e22488 (source precedence, the token line format, the Token log's counting header, Expected cost and the Cost table), with its model picker set to Gary's effort rules of 2026-10-07 (§5). v6 revises v5 (a5285ee) with Gary's decisions on task branches and the Kickoff prompt; this revision applies an adversarial review of v6 (§5 "Review fixes"). Only `specs/handoffs/orchestrate-native/` changes: the kit is in `kit/`, its tests in `tests/`, and `brief.md` is the decision brief.*

## Summary

**Claude Code: move the skill onto a saved plugin workflow now.** Issue #43869 ("Subagent model routing is broken — all mechanisms resolve to parent model (Opus)", https://github.com/anthropics/claude-code/issues/43869) is still open as of today. On 2.1.291, though, v1's wire captures show the per-call `model` and `effort`, and plugin-agent frontmatter, reaching the API.

**What the design does.** `personal-plan-orchestrate` dispatches each wave of a tagged plan to subagents on the tier's model while the `[deep]` parent keeps control. On Claude Code a saved plugin workflow, `personal:plan-segment`, runs one wave per launch. `plan_state.py` derives the next unit and its gates from the plan file, `check_wave.py` checks the commits, and a `PreToolUse` hook, `orchestrate_gate.py`, denies any launch whose state, approvals, mode confirmation, branch or handoff isn't true on disk and in the transcript. One kickoff question sets the mode. Gated stops at every gate. Unattended logs the routine gates as checkpoints, fixes failed checks and repeat concerns automatically up to a cap, and still stops for information, plan errors, unplanned premium work and the cost guard. Every run lives on a task branch, and the plan and a session handoff are committed and pushed after every wave, so a new session continues from the branch when Gary pastes the plan's Kickoff prompt (§1.5).

Gary's settled decisions, in his words, and the refinements that are mine are listed once, in §5.

**Tested:**
- **Offline, this kit:** 154 tests pass on a fresh plugin copy (README recipe): 52 for the workflow against a stub harness (among them each tier's agent, model and effort, `execHigh`, `max` and its unattended gate 7, and an `[exec]` group's retry at Sonnet high before `[deep]`), 44 for `plan_state.py`, 15 for `check_wave.py`, 37 for the hook, 6 for `token_tally.py`, plus the consistency check, which reads the efforts from plan-execution.md's picker row. `claude plugin validate` (2.1.292) passes with one warning (no version). The review's fixes add 7 hook cases (an answer only after the kickoff question, a paste recorded as an answer, a runner on its assigned branch, a paste never answering a gate, exit 2 when the hook can't decide, an unknown default branch, a git error in the plan repo) and 2 `plan_state.py` cases (the signal tokens, the prompt's plan line), and change 4 (an invoking message denied outside CI, another harness or runner token, exit 2 on a hook error, and the bare-yes case's question text).
- **The new suites on the previous v6 kit:** the hook suite passes 26 of 37, failing the 7 new cases, 3 changed ones and 1 whose fixture now uses the signal tokens, and the `plan_state.py` suite stops at the signal-token case.
- **Not yet in the kit**, from the v5 final review: the hook's turn reading (compaction summaries, the interrupt marker, messages typed mid-turn), rule 7's take-back (10 words or fewer; the kit still voids on any later human turn that names gated, which errs toward stopping), marker numbering, the guard on split waves, and the model's date suffix. Phase 1 adds each with a stub test.
- **Live, v2 kit only:** 4 `claude -p` runs with Haiku standing in for every tier, $0.86 in total. Without an allow rule the launch is refused; with `Workflow(personal:plan-segment)` it runs. The hook denied all 6 dishonest launches (an edited state, an approval not word for word, `canaryDone` with no canary, a launch by `scriptPath`, approvals reused from a notification turn, a relaunch past an unanswered gate). The canary ran 1 of 2 repos and stopped at gate 5, the approved continuation ran the other, and wave 2 returned gates 4 and 2 with no agents. Both worker commits passed `check_wave.py`, and the routing check flagged the Haiku stand-ins, as it should. No live run has used v3 through v6.
- **The tally on real transcripts:** identical to v2's on the Haiku runs; on four finished Opus workflow runs it reports 29-70% more dollars, all from the `(output est.)` rule (§2.6).

**The other harnesses:**
- **Codex:** native, in phase 2.
- **Cursor:** native already. Phase 3 adds the new scripts, a review subagent and v1's slug fixes.
- **Grok Build:** stays on the passive skill until a signed-in test.
- **Gemini CLI and Muse Code:** passive skill.

---

## 1. Harness-neutral core

### 1.1 Unchanged

All of these stay exactly as they are:
- **Plan structure:** tagging (`personal-plan-tag-tiers`), the no-thrash rule and the ≤ constraint, wave markers.
- **Plan bookkeeping:** the Kickoff, Cost table, Status line, `(done)` markers, Review log, and the Token log with its counting header.
- **Gate rules:** fail-closed gates, approval per gate, `BLOCKED at gate N`, "save before you wait", and unattended runs only on explicit instruction. §1.5 makes Gary's answer to the kickoff question that instruction.
- **Execution rules:** one subagent per git working directory, the 8-item context contract, and the commit policy (subagents commit when told and never push; the parent pushes).

### 1.2 New on every harness

1. **`plan_state.py <plan>`** prints JSON (version 3): the next unit (`kind: wave|fixup`, `wave`, `label`, `fix`, `tier`, `milestone`, open `steps`, `start`), plus `gates`, `stops`, `checkpoints`, `mode` (with `via`: `answer` or `prompt`), `prompt_mode` (the mode line of the Kickoff prompt), `prompt_plan` (its repo and plan path), `cost`, `concerns`, `waivers` and `errors`. It derives each gate like this:

   | Gate | Derived from |
   |---|---|
   | mode | No Kickoff `mode:` line with a confirmed answer (§1.5) |
   | 0 | Tagging errors: a ≤ violation, a step before any marker, a marker number used twice, duplicate IDs, `(done)` out of order, a `--- WAVE` line or a Review log line outside the grammar. Also: unattended mode with no Cost table Total, an unattended record whose signal isn't tokens (§1.5 step 3), and a Kickoff prompt whose mode line doesn't name the confirmed mode, names one before the answer, or that names no repo and plan. Order comes from file position, since a re-plan's waves take the next unused numbers |
   | 1 | `BLOCKED at gate 1`; a fix-up whose group's latest Review log line records a failed check (§2.3 step 5); or a group whose last two or more Review log lines are CONCERNS |
   | 2 / 3 | A unit starts in `[deep]`/`[xdeep]` right after an `[exec]` / `[fast]` unit |
   | 4 | A unit starts in another milestone (`m{N}` from the step ID or the enclosing heading) |
   | 5 | `BLOCKED at gate 5`, which the parent writes after the canary |
   | 7 | The first unit of an `[xdeep]` wave only, so a canary's continuation isn't asked twice; and every fix-up of an `[xdeep]` wave, whose `N-fix` or `N-fix2` row is unplanned |
   | 6, and 7 on a step-up | The workflow adds these when `stepUp` is set |
   | guard | Projected spend passes the guard (§1.5) |

   Every gate derives from the plan in every mode. The mode only splits them: in gated mode `stops` is every gate; in unattended mode §1.5 says which are `checkpoints`.

   Four cases the table doesn't show:
   - **A wave that spans milestones** (in a plan the passive driver grouped) splits into units, and the markers aren't renumbered.
   - **Fix-ups come from the Review log.** The k-th CONCERNS line in a row for a group makes the next unit a fix-up of that group, labeled `N-fix` for the first and `N-fix<k>` after (`N-fix2`, `N-fix3`), the numbering §4 adds to the standard. Its review is logged as `review wave-N-fix2 (<group-id>) …` and counts toward wave N's group, so a PASS ends the streak, and so does a WAIVED line (§1.5). A failed check is logged as a CONCERNS line too, so it starts or extends the same streak. A second CONCERNS in a row is gate 1; §1.5 says when it stops. When several groups of one wave have streaks, the longest goes first.
   - **A fix-up marker** (`--- WAVE 2-fix [exec] ---`, which the passive driver may write) doesn't count toward the wave total or the numbering check. Steps under it form a unit with its label.
   - **Cost** comes from the plan too: the Cost table's Total and rows (expected) and the Token log's dollars (actual).

2. **One dispatch unit per dispatch turn.** The parent updates the plan, then re-runs `plan_state.py` before every dispatch.

3. **`check_wave.py`** runs twice around each unit.
   - **`snapshot`, before the launch.** It records each directory's HEAD and its dirty paths. It also flags a `.scratch/` that isn't gitignored, and reports the repo's `attribution` setting.
   - **`check`, after the run.** For each group it checks:
     - `from` is an ancestor of HEAD;
     - every commit starts `<step-id> <subject>`, followed by a blank line;
     - no `Co-authored-by` or `Signed-off-by` line appears anywhere;
     - the required trailers sit in the last paragraph;
     - every step has a commit, and the run left no new dirty paths;
     - directories that had no group are unchanged.

     The parent's bookkeeping commits can sit inside a group's range: a fix-up's `from` is the wave's start, and a relaunch's range can span a save-before-you-wait commit. So `check` takes the plan path (`--plan`, or the run record's `args.plan.path`). A commit that touches only the plan and its session handoff, under a subject with no step ID, is listed as `bookkeeping` and skipped; any other commit that touches either file fails, since workers never edit the plan. For a fix-up, `--baseline` takes the snapshot from before the wave it fixes, so a path that wave left behind is checked again rather than hidden by the fresh snapshot.

     It prints each group's `to`, so the Review log range comes from git, not from a reviewer. Any failure is gate 1. Gated, it stops; unattended, most failures get an automatic fix-up instead (§1.5).

4. **Trailers are spelled out.** The parent passes the exact trailer lines from its own attribution: `Assisted-by: Claude Code`, plus `Claude-Session:` when the harness adds one. The worker is told to end each commit with exactly those lines.

5. **Review.** Each working directory gets one read-only reviewer at the author's tier: Opus high, or Opus xhigh after an `[xdeep]` wave. This applies on every adapter that can pin a model per subagent.
   - **A missing review** is gate 1.
   - **CONCERNS** is logged, and the fix-up runs without asking, as orchestrate does today.
   - **A second CONCERNS in a row** is gate 1. Gated, it stops; unattended, it gets automatic fix-ups up to the cap (§1.5).

6. **Gate questions are plain text, on every harness, and they end the turn.** None of these is ever a gate answer: a completion notification, a workflow approval prompt, a hook's continuation prompt (such as the runner Stop hook), or a timer. In unattended mode a checkpoint asks nothing; §1.6 lists what still asks.

### 1.3 What each adapter provides

| | Claude Code | Codex | Cursor | Grok | Gemini | Muse |
|---|---|---|---|---|---|---|
| Dispatch | Workflow `agent()`; fallback `Agent` | `spawn_agent` | `Task` | `spawn_subagent` | `invoke_agent` | `subagent_spawn` |
| Model and effort per child | Per call, plus plugin agent | Locked role | `model` slug | Definition | Definition | None |
| Gates enforced in code | Script plus hook | Optional `PreToolUse` | Optional `subagentStart` | Fails open | Policy | None |
| Unattended confirmation checked in code | Hook | No | No | No | No | No |
| Per-wave handoff commit checked in code | Hook | No | No | No | No | No |
| Task branch checked in code, by name | Hook | No | No | No | No | No |
| Runner signal (§1.5) | `CLAUDE_CODE_REMOTE=true`; assigned branch | None documented | Cloud MCP `run-info`; own branch | None | None | None |
| Real usage | Transcripts (output est. for Opus subagents) | Rollouts | None | `grok usage` | Chats | None |
| Verdict | **Native, phase 1** | **Native, phase 2** | **Native; fixes in phase 3** | Passive | Passive | Passive |

### 1.4 Detection order

1. **Inside a subagent?** If the instructions say the final message is a return value, or there is no subagent tool, don't orchestrate. Report gate 0 to the caller.
2. **Claude Code:** `Agent` and `Workflow` both appear, loaded or deferred.
   - Load their schemas with ToolSearch before checking anything else.
   - If `Agent` has no `model` field, `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` hid it: go passive.
   - If `personal:plan-worker` isn't among Agent's subagent types, the plugin's agents aren't loaded (the plugin isn't installed, or sync installed it without them): go passive.
   - If `Workflow` is missing (disabled, or Pro without the `/config` opt-in), use the Agent path.
3. **Cursor:** `Task` with `model`, and no `Agent`.
4. **Codex:** `spawn_agent`.
5. **Grok:** `spawn_subagent`. Passive until phase 4.
6. **Gemini:** `invoke_agent`. Passive.
7. **Muse:** `subagent_spawn`. Passive.
8. **Nothing matches:** passive skill.

Grok and Muse also have a lowercase `workflow` tool. Requiring `Agent` and `Workflow` together keeps them from matching as Claude Code.

A cloud session gets the plugin only through account sync (runbook m2, m5). In this session sync first installed the published `personal` plugin (version 0007, main's c2b7c97, not this branch) at the 21:07 UTC start, the first under 2.1.292 with `CLAUDE_CODE_SYNC_PLUGINS=1` and `CLAUDE_CODE_SYNC_SKILLS=1` set; its earlier starts and resumes on 2.1.289 and 2.1.291 got nothing, and which change made the difference isn't known. Sync copied every file under the plugin root, so the kit's files would very likely arrive too. UNVERIFIED (phase 0 criterion 7): whether a fresh session start gets the skills and the `hooks/hooks.json` SessionStart, and whether the synced manifest's `agents`, `workflows` and `hooks` fields are registered. Until they are, step 2 goes passive in a cloud session, and §1.7 stops at every STOP.

### 1.5 Mode: gated or unattended

**The kickoff question.** Once per plan run, after the Kickoff and Cost table are written and before the first dispatch, the parent:
1. **Reads the runner signals** (table below). The proposal is its judgment; Gary's answer decides.
2. **Finds the task branch** in each working directory and in the repo that holds the plan, each on its own (git.md "Task branches and shared branches"). Orchestrate runs only on a task branch, on every machine (decision 6). Where the checked-out branch isn't one (a shared branch, a detached HEAD, Gary's own branch), the kickoff cuts one per core.md "Cut a task branch": its name rules, `git switch -c <branch> --no-track`, and `git push -u origin <branch>` right away. A runner cuts before it saves, without asking, and says the name is a guess. A workstation names the branch in the question and cuts it after the answer, which is core.md's yes. Each repo that needs one gets the same name unless it is taken there; the handoff lists every repo's branch, and so does the Kickoff prompt's `On branch` line when they differ (below). Cutting from Gary's own branch, which core.md allows today only on a runner, is mine (§4).
3. **Saves first:** writes `mode: pending | proposed <mode> (harness=<h> runner=<r>[; <note>]) | guard 3x min $50 | fixups 2` into the Kickoff block and `BLOCKED at gate mode` into the Status line, moves the plan to `specs/handoffs/plan-{topic}-{word}.md`, and writes the handoff beside it. On a task branch it commits both and pushes (§1.6). A workstation still waiting to cut commits nothing before the answer; `git switch -c` carries both files along. The Kickoff prompt has no mode line yet. The signal is fixed tokens, so a new session can compare its own environment with it: `harness` is `claude-code`, `codex`, `cursor`, `grok`, `gemini` or `muse`, and `runner` is `cloud`, `self-hosted`, `ci` or `none` (a workstation), read from the runner signals below; the note after `;` is free text for Gary. An unattended record whose signal doesn't parse is gate 0 (mine).
4. **Asks one question and ends the turn.** For example, on a runner:

       Plan plan-auth-otter: 4 waves, expected ~$26 API-equiv (Cost table above).
       Gates it crosses: 5 (canary, wave 1); 4 and 2 (before wave 3); 7 (before wave 4, [xdeep], ~$14).
       Runner detected (CLAUDE_CODE_REMOTE=true). Proposed mode: unattended.
         unattended: gates 2, 4, 5 and 7 are logged, not asked. A failed commit check or a
           CONCERNS gets an automatic fix-up, up to 2 per group. I stop to ask for information,
           at a plan error, a scope breach, a failure after one retry (at once on the [xdeep]
           wave), a group's third failed check or review, unplanned [xdeep] or Fable work, or
           projected spend past 3x expected or $50, whichever is higher (~$78).
         gated: every gate stops, and so does every failed check or repeat CONCERNS.
       Either way, after every wave I commit and push the plan and its handoff
       (specs/handoffs/handoff-auth-otter.md), and every message that stops or asks ends
       with a short handoff summary. Opening or merging a PR, tags, remote branch deletes,
       deploys and permission prompts wait for you.
       Reply unattended or gated.

   The question always carries `Proposed mode: <mode>.` and a closing `Reply ...` line; the hook looks for both before it counts an answer (rule 7). With no runner signal the question says what it checked, so Gary can correct it. On a workstation it also names the branch it will cut, if any, and asks where to orchestrate, which replaces the standard's separate destination question:

       No runner signal (CLAUDE_CODE_REMOTE unset, no assigned branch). Proposed mode: gated.
       main is a shared branch, so the run goes on a new task branch, feature/auth-otter:
       your answer is the yes to cut it, and I push it at once.
       Reply gated or unattended; add here to orchestrate in this chat (default: new chat).

   `unattended` no longer implies `here`: the pasted prompt confirms the mode in the new chat (mine). A runner orchestrates in its own chat and asks no destination; Gary may still start a new session from the Kickoff prompt.
5. **Records the answer** in the Kickoff block and clears the `BLOCKED`:

       mode: unattended | proposed unattended (harness=claude-code runner=cloud; CLAUDE_CODE_REMOTE=true) | guard 3x min $50 | fixups 2 | confirmed 2026-10-06 session 6333c263-f7c1-58ee-bb8f-25209c81c588: unattended

   The words are Gary's whole message, whitespace collapsed, and they come last on the line, so they may hold any character. Unattended needs a reply that names `unattended`, as the question asks and core.md's "say so explicitly" requires (decision 9). A yes to a gated proposal records gated, which relaxes nothing. Anything else (silence, a bare yes to unattended, a question back, "hmm") dispatches nothing: the parent re-asks, and so does the hook. The answer is Gary's next message after the kickoff question, and only that: an unattended answer must not ask back or negate (`what does unattended mean?`, `don't run unattended` re-ask; mine, erring toward asking), and words that are the Kickoff prompt or hold its mode line never count as an answer, so a paste confirms only by the prompt path below. An answer that declines the branch cut (`gated, but stay on main`) dispatches nothing either, since orchestrate runs only on a task branch: the parent re-asks once, naming the two ways on, cutting the branch or running `personal-plan-model-tiers` on the current branch under core.md's shared-branch rules, with the plan back in `.scratch/` (mine). `plan_state.py` reports `gate-mode` until a confirmed line exists, and the workflow never accepts an approval for it. It reads `guard` and `fixups` only from before `confirmed`, so Gary's words never set them. In the same edit the Kickoff prompt gets its mode line (below).
6. **Saves the answer, then halts or dispatches.** A workstation cuts its branch first. The parent refreshes the handoff with the mode, commits the plan (Kickoff block, Cost table, Token log counting header) and the handoff in one commit, and pushes, before it halts for a new chat and before the first dispatch (§1.6). For a new chat it prints the Kickoff prompt with the kickoff summary and the short handoff summary, and halts. For `here`, and on a runner, it dispatches.

**The Kickoff prompt.** The active variant's prompt (plan-execution.md "Kickoff template") gets a mode line with the answer, and names the repo that holds the plan and the plan's repo-relative path, since the plan is always tracked in `specs/handoffs/`:

    Prompt to paste into the next chat:
      In GaryRudolph/public, read specs/handoffs/plan-auth-otter.md. The plan is already tagged.
      On branch feature/auth-otter (task branch): subagents commit each finished step.
      Run in unattended mode.
      Run the personal-plan-orchestrate skill from the top: walk to
      each tier boundary, dispatch subagents per the skill's procedure,
      and pause only where the recorded mode stops. Do not execute plan
      work inline. Update plan progress after each wave returns per the
      skill's procedure. The mode line above is the kickoff answer. If the
      Status line shows BLOCKED, re-post that question and wait; otherwise
      record the mode, print the kickoff summary and begin dispatching.

- **The plan line** names the repo as `<owner>/<repo>` from its origin URL (its folder name when it has no remote), so a session started at a workspace root or in a sibling repo finds the plan. Under decision 11's no-git-repo case it is `Read <absolute path>.`, and the prompt works only on that machine.
- **The `On branch` line** names the plan repo's branch. When a repo's branch differs, because the name was taken there, the line lists each: `On branches public feature/auth-otter, api feature/auth-otter-quill (task branches): subagents commit each finished step.`
- **Gate 0:** `plan_state.py` reports it when the mode line doesn't name the confirmed mode or appears before the answer, and when no line names the repo and the plan.
- **What changes it:** after the answer, only the mode line on a switch, and the `On branch` line when a runner keeps its own assigned branch (path b below). So the handoff's resume step is "paste the Kickoff prompt" (mine).

**A new session started from the prompt.** The paste counts only when a human message, whitespace collapsed, is the plan's whole Kickoff prompt as committed, with `Run in unattended mode.` or `Run in gated mode.` as a line of its own; only its `On branch` lines may differ. "run unattended", the mode line alone, or the prompt plus "and skip the canary" is not a paste: the session asks the kickoff question. A paste is never an answer either, not to a gate, a `needs_info` question, a waiver or the kickoff question (hook rules 2, 7 and 10), so a plan `BLOCKED` at a gate gets that question re-posted, as the prompt's last sentence says. When the paste counts and the environment matches the record's signal (the same harness and runner tokens), the new session records

    mode: unattended | proposed unattended (harness=claude-code runner=cloud; CLAUDE_CODE_REMOTE=true) | guard 3x min $50 | fixups 2 | confirmed 2026-10-07 session <new id> by Kickoff prompt: Run in unattended mode.

and commits and pushes it, prints the kickoff summary (waves, expected total, gates, and the spend so far once the plan is under way), and starts without asking again. It asks the kickoff question again, with a fresh proposal, when:
- **the environment differs:** another runner token (confirmed on a runner and pasted on a workstation, or the reverse) or another harness. Pasted into Codex or Cursor, which have no hook and whose models and rates differ, the parent also recomputes the Cost table for that harness and refreshes the Token log's counting header in place (plan-execution.md);
- **no mode was confirmed yet:** a prompt copied before the answer has no mode line;
- **a workstation is on another branch** (path c).

The three ways in:
- **(a) A new local session on the same machine**, usually right after the kickoff halts for a new chat. The clone is on the task branch already, so the paste counts.
- **(b) A cloud session started on the task branch.** Claude Code on the web gives each session its own branch (this session runs on `claude/awesome-darwin-o3d0ss`), and a runner keeps its assigned branch (core.md "Task branches and shared branches"). The session works there, says so in its first report, and in its confirmation commit rewrites the prompt's `On branch` line and the handoff's branch to its own, so the next resume reads the branch that holds the waves (plan-execution.md: the chat "puts its own branch on the remaining prompts' `On branch` lines"). The paste still counts, since rule 7 sets the `On branch` lines aside. A cloud session whose branch doesn't hold the plan (started from another base) stops at gate 0 and says to start one from the prompt's branch (mine).
- **(c) Another machine.** A workstation clone is usually on `main`, where the plan doesn't exist yet. The session fetches, reads the plan from `origin/<branch>` without switching (`git show origin/<branch>:specs/handoffs/plan-auth-otter.md`), and asks the kickoff question with the switch folded in ("I'll switch to feature/auth-otter"). Gary's answer is the yes to both, as core.md's "a workstation proposes switching and commits nothing until I answer" asks. Then `git switch <branch>` makes a local branch that tracks `origin/<branch>` (rule 9 needs `@{u}`), and the session records the answer there. A plan confirmed unattended on a runner re-asks here in any case, since the runner token differs.

Hook rule 7 checks a pasted unattended confirmation against the transcript, the plan's prompt on disk, and the hook's own harness and runner (§2.1). A gated paste needs no proof: it relaxes nothing, and the canary still stops at gate 5.

Rules around it:
- **An invoking message that names the mode** sets the proposed mode, and the kickoff question still runs, so Gary sees the waves, the total and the gates before he opts in. Only where nobody can reply (a CI job, `CI=true`) do the invoking words count as the answer: the parent records them, prints the kickoff summary, and starts. The hook enforces it: an answer counts only right after the kickoff question unless `CI=true` is set for the hook.
- **Switching** takes an explicit message naming the mode, in Gary's own words (one that holds a prompt mode line reads as a paste and counts for nothing). The parent records the new words, date and session, and rewrites the prompt's mode line in the same edit. A switch to unattended also answers a pending gate that unattended mode would pass as a checkpoint, with those words as the approval; it doesn't answer a gate that stops in both modes. A switch moves no file: the plan and handoff are in `specs/handoffs/` in both modes, and rule 9 holds in both. A run already in flight finishes as launched. A later short message (10 words or fewer) that names `gated` and not `unattended` ends unattended, and the hook enforces it; a longer one that only mentions the word doesn't.
- **A new session started any other way.** A gated record carries over, since it relaxes nothing, unless the harness or runner token now differs from the record's signal: then the kickoff question runs again with the new proposal. An unattended record counts only in the session that confirmed it, so the new session asks the kickoff question again, quoting the spend so far. A resumed cloud session keeps its session id and transcript (this one: one id and one transcript across 7 worker exits and a container reboot).
- **The Cost table follows the proposed mode.** Its orchestrator row counts the gate waits that mode will have: gated counts the canary and every gate 2, 3, 4 or 7 the plan crosses, as the standard says; unattended counts one, the kickoff answer. On a runner the row has no new-chat start-up. In both modes each wave's share also covers the handoff refresh, commit and push: about $0.1 a wave (my estimate). When the answer picks the other mode, the parent recomputes that row before any wave runs, and says so. Fix-ups get rows with no expected value, as the standard's rule for waves added later says, labeled with their number (`2-fix2 [exec] repo-b m1 s4`).

**Runner signals.** The parent reads them with one shell call and the harness's own instructions, and writes them as the signal's tokens: `CLAUDE_CODE_REMOTE=true` is `runner=cloud`, or `runner=self-hosted` with `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=self_hosted`; `CI=true` or `GITHUB_ACTIONS=true` is `runner=ci`; a Cursor cloud agent is `harness=cursor runner=cloud`; anything else is `runner=none`.

| Harness | Signal | Evidence |
|---|---|---|
| Claude Code on the web | `CLAUDE_CODE_REMOTE=true`, with `CLAUDE_CODE_REMOTE_SESSION_ID` and `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE` (`cloud_default` here); the system prompt assigns a branch to push | This container's environment (`v3/evidence/runner-env.txt`); core.md "Runners" |
| Claude Code self-hosted runner | `CLAUDE_CODE_REMOTE=true` with `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=self_hosted`; the assigned branch | The 2.1.291 binary's self-hosted session environment block (`v3-review/selfhosted_ctx.txt`); `setup/mac/claude/runner.md` |
| Claude Code Remote Control | None: a workstation session steered from a phone. Propose gated. Whether it sets `CLAUDE_CODE_REMOTE`: UNVERIFIED (the binary starts Remote Control only when it is unset) | `setup/mac/claude/remote-control.md` |
| Codex cloud task | None documented: UNVERIFIED. `CODEX_CI=1` and `CODEX_SANDBOX` are set on local runs too, so neither tells cloud from local. Orchestrate stays out of Codex cloud anyway (§3) | Codex docs `environments/cloud-environments` (`v3/evidence/`); `codex-rs/core/src/unified_exec/process_manager.rs`, `core/src/spawn.rs` |
| Cursor cloud agent | The built-in Cursor Cloud MCP's `run-info` tool, "available during Cloud Agent runs" (an admin can turn it off); the agent's own branch, which it pushes. `CURSOR_AGENT=1` is set in every Cursor agent shell, local or cloud, so it isn't a signal. Hooks get `CURSOR_CODE_REMOTE=true` "when running in a remote workspace"; whether that covers cloud agents: UNVERIFIED | `orch/cursor/cloud-agent_capabilities.md`, `cloud-agent.md`, `hooks.md`; the CLI bundle |
| Grok Build, Gemini CLI, Muse Code | No cloud mode of their own (Grok Bot is a separate product). They run the passive skill (§1.7) | `orch/grokdocs/`, `orch/musedocs/` |
| Any harness in CI | `CI=true` or `GITHUB_ACTIONS=true`: a runner with nobody to answer, so the prompt itself must name the mode | |

`CLAUDE_CODE_SESSION_ATTENDED=1` is also set in this container. It's undocumented, so the parent doesn't use it.

**What each gate does:**

| Gate | Gated | Unattended |
|---|---|---|
| mode | Stops | Stops |
| 0, a plan or launch error | Stops | Stops |
| 1, a failed, crashed or unreviewed group | Stops | One automatic retry inside the run (below), then stops |
| 1, `needs_info` | Stops | Stops at once |
| 1, a `check_wave.py` failure | Stops | Automatic fix-up `N-fix` (below). A scope breach stops at once (proposed; decision 10) |
| 1, a second or later CONCERNS or failed check on a group | Stops | Automatic fix-up `N-fix2` and so on, up to the cap (2 per group, decision 3); the next failure stops |
| 2 / 3, into `[deep]` or `[xdeep]` | Stops | Checkpoint |
| 4, milestone | Stops | Checkpoint. On a project with `specs/`, the parent writes the milestone handoff first (core.md) |
| 5, canary | Stops | Checkpoint. The canary group still runs alone, and the rest of the wave launches only after it passes `check_wave.py` and its review, fix-ups included |
| 6, step-up | Stops | Checkpoint for the automatic step-up into `[exec]` or `[deep]`; stops for `[xdeep]` or Fable |
| 7, `[xdeep]` | Stops | Checkpoint on a wave the Cost table planned, whose cost the kickoff question quoted (decision 2); stops for unplanned `[xdeep]` work: a fix-up, a re-plan row, a step-up. Draft fan-out and `max` still need Gary's gate-7 approval |
| guard | Stops | Stops |
| Each wave's end | Commit the plan and the refreshed handoff and push before the next launch (rule 9) | Same |
| A `BLOCKED at gate N` Status line | Stops | Stops |
| Opening or merging a PR, pushing a tag, deleting a remote branch, a deploy | Waits | Waits |
| A permission prompt | Waits | Waits. On a runner, commit and push before a call likely to trip one (core.md) |

**Checkpoints are logged, not asked.** For each unit the parent:
- ends the wave's Review log note with them: `review wave-3 (repo-a m2 s1) 8d0e4b7..c41f0a2: PASS - cache keys match the spec; passed unattended: gate 4, gate 2 - 2026-10-06`, which keeps the standard's grammar; an automatic fix-up's review names its number: `review wave-2-fix2 (repo-b m1 s4) 846932b..9abcdef: PASS - newline added; passed unattended: gate 1 (fix-up 2 of 2) - 2026-10-06`;
- keeps the latest on the Status line: `| passed unattended: gate 4, gate 2 before wave 3`;
- lists every checkpoint, automatic retry and automatic fix-up, with its reason, under **Deviations from plan** in the Completion summary and in the handoff, so Gary reviews them in one place.

**Automatic retries (unattended only).** The workflow retries each broken group once, inside the same run:
- a worker with no result, or a review that died: the same tier (a dead review reruns only the review);
- `failed` or `low_quality`: an `[exec]` group that ran at medium retries at high, plan-execution.md's step-up for a stalled step, with no gate; any other goes one tier up, into `[exec]` or `[deep]` only, logged as a gate-6 checkpoint;
- never on an `[xdeep]` or Fable wave, never on a launch that is already a step-up Gary approved, never for `needs_info`.

The retry keeps its wave's number and token row, as the standard says of step-up retries. Its prompt names the earlier attempt and says to check its commits. A dead worker's uncommitted edits make the retry return `failed` (the existing "uncommitted changes, do not touch" rule), which stops: fail closed. A second failure is gate 1. The retry runs in the same run so that neither the hook nor `plan_state.py` needs a run history. A fix-up run gets the same retry.

**Automatic fix-ups (unattended only).** A fix-up is its own unit and its own run, scheduled from the Review log (§1.2):
- **What gets one.** A `check_wave.py` failure, which the parent logs as its group's CONCERNS line with a note that starts `check_wave.py:` and quotes the failing output (§2.3 step 5), and a second or later CONCERNS on a group. A first review CONCERNS gets its `N-fix` in both modes, as today.
- **The cap.** Two automatic fix-ups per group in a row (`N-fix`, `N-fix2`; decision 3), recorded on the mode line as `fixups 2` and quoted in the kickoff question. The third failure in a row is gate 1 and stops. A PASS with a clean check ends the streak. A raised cap needs Gary's approval (hook rule 8).
- **A waiver.** At a gate 1 that a streak raises, in either mode, Gary may waive the concern instead of approving the next fix-up (the standard's "re-tag, add a fix-up wave, or waive"). The parent logs `review wave-N (<group-id>) <from>..<to>: WAIVED - <Gary's answer, whitespace collapsed> - <date>`, which ends the streak as a PASS does, and the plan moves on. The hook checks that the words are a human message of this session (rule 10). The line is needed because a failed check starts a streak, so an approval of gate 1 can only launch the next fix-up.
- **What the worker gets.** The failing check output or the concern, verbatim, and the streak's earlier failures. A review concern is fixed with new commits. A failed message check (a first line, a `Co-authored-by` line, a missing trailer) is fixed by rewriting the messages of the commits the check names by SHA, keeping their content and leaving every other commit as it is, the parent's plan and handoff commits included: `git commit --amend` only when HEAD is one of them, otherwise a non-interactive rebase that rewords just those. The parent then pushes with `--force-with-lease --force-if-includes` (core.md: rewrite only your own commits). A failed-check note that also carries the review's CONCERNS gets both instructions. A failed-check fix-up's reviewer is told to check the quoted failure itself too, not to leave it to the script.
- **What stops at once instead** (my reading; decision 10). No group's fix-up can repair a scope breach: edits in a directory with no group, a `from` that is no longer an ancestor of HEAD, or, on a workstation, a new uncommitted path, which may be Gary's own edit (core.md "Stage only what you changed"). These stop at gate 1 in both modes.
- **What still applies.** The cost guard, before every fix-up. Gate 7 on any fix-up of an `[xdeep]` wave, which stops. The in-run retry. Fix-ups and their reasons go in the Review log, the handoff and the Completion summary.
- **Gated mode** stops at each of these.

**The cost guard.** The Cost table's expected values stand in for a budget:

    projected = actual so far (the Token log's dollars)
              + the next wave's expected $ (0 once any step of that wave is done, which
                covers a canary's continuation and a split wave's later units; 0 for an
                unplanned row)
    stop at gate-guard when projected > max(guard × the Cost table's expected total, floor)

- The guard is 3× with a $50 floor, recorded on the mode line (`guard 3x min $50`) and quoted in the kickoff question. Gary set both: below $50 of projected spend the multiple doesn't matter, and above it a plan runs to 3× its expected total (a plan expected at $78 stops past $234). The floor matters only for plans expected under about $17. The standard rates a plan total as good to 2-3×, so 3× trips on a real overrun rather than estimate noise.
- It applies in both modes. It should fire rarely, and a question is worth it when it does.
- A yes at the guard raises the multiple to the next whole one above the projection, or to the multiple or floor Gary names. The hook requires a human approval for any raise (§2.1).
- An unplanned premium tier stops whatever the spend: a step-up into `[xdeep]` or Fable, an `[xdeep]` fix-up, an `[xdeep]` row a re-plan adds (gates 6 and 7 above).
- It checks between runs. One run is one wave, so an overrun is bounded by a wave. The script doesn't use `budget.spent()`, which counts output only and is shared across the session.
- Its inputs are approximate: Claude Code subagent lines are `(output est.)`, and Cursor lines are heuristics until pasted usage replaces them. Over 5 windows of this session between `cost-state` records, the input-side counts matched exactly and the 1k output estimate put dollars at -2% to +17% of exact (`v3-review/calib.py`). That is close enough for a 3× trip.
- It counts only the Token log lines the parent appends after each run (§2.1, trust).
- Fix-ups count like any wave. Their rows have no expected value, so a fix-up adds nothing to the projection before it runs, and its spend counts once it has.

### 1.6 Questions, and saving before them

In unattended mode the parent asks only when it needs information or a decision that is Gary's:
- **An ambiguous spec.** A worker that finds two readings with materially different results returns `needs_info` with one question instead of guessing (new in the worker prompt). The parent asks too when the plan itself leaves a choice open.
- **Missing access or credentials.** A worker's `needs_info`; a push refused by a ruleset or a permission (core.md); a git email mismatch on a workstation.
- **A choice with materially different outcomes.** A re-plan, dropping a wave, a step-up past the automatic one, the guard.
- **A third failure on the same group**, after its two automatic fix-ups, and a scope breach (§1.5).
- **Gate 0, and gate 1** after the automatic retry or at once (the table above).
- **Outward actions**, in every mode, including the PR at plan completion. A worker whose step needs one returns `needs_info` naming it (new in every prompt).

Gated mode asks all of these, plus every gate, every failed check and every repeat CONCERNS.

**The handoff, after every wave, in both modes.** Orchestrate always runs on a task branch, so, gated or unattended, the plan and the session handoff live in tracked `specs/handoffs/` (`plan-{topic}-{word}.md`, `handoff-{topic}-{word}.md`, one `{topic}-{word}`) on every machine, not only on runners, in the repo that holds the plan. They are removed or promoted before the PR merges, per core.md "Runner scratch rides the branch". This is Gary's decision (§5).
- **After each wave's review**, the parent's bookkeeping commit updates the plan and refreshes the handoff, then pushes every working directory. The handoff holds: what's done, with each group's commit range; the Review log verdicts; the fix-ups and their reasons; the Token log total against the Cost table's expected total; the next unit; how to resume (paste the plan's Kickoff prompt, which names the branch, the plan path and the mode; mine); and any pending question, verbatim.
- **At a stop and at completion** the handoff is final: the same fields, plus the question or the PR ask. At completion it carries the Completion summary, and the PR question names the cleanup commit (remove the two files, or promote what's durable to `specs/`).
- **Every message that ends a run, stops at a gate, or asks a question** carries a short handoff summary of about six lines, in both modes: the branch and handoff path, the waves and fix-ups done with their ranges, spend against expected, and the next unit or the question. A reader of the chat has it even if the branch is lost.
- **Nowhere else.** The summary goes in the chat and the handoff on the branch. Posting it to a PR, an issue or any other service is an outward action, which waits for Gary in every mode.
- **While a run works** the parent writes nothing to the tree, in both modes: the plan is tracked, so an edit would show up as a new dirty path to `check_wave.py`.
- **The hook checks it** on Claude Code (rule 9): a launch, in either mode, needs the plan and a handoff refreshed since the plan's last change, committed and pushed.
- **Where nothing can be pushed**, on a workstation, gated only. The plan needs a git repo and the push a remote. A plan in no git repo, such as a cross-repo plan in a plain folder of sibling repos (a layout `personal-makefile` supports), stays with its handoff in that folder's `.scratch/`, refreshed after every wave. A plan in a repo with no remote is committed in `specs/handoffs/` as usual and not pushed, and so is a working directory with no remote. Rule 9 recognizes both. Unattended needs the plan in a repo with a remote, and the hook denies it otherwise, so there the kickoff question proposes gated and says why. This is mine (decision 11).

**Save, then ask** (core.md "Save before you wait", in this order):
1. Update the plan: `(done)` markers, the Review log, the Token log, and the Status line's `BLOCKED at gate N`.
2. Write or refresh the handoff beside the plan in `specs/handoffs/`, in both modes: the question verbatim, the branch, the mode, and how to resume.
3. Commit the plan and the handoff. On a runner, commit everything in the tree, a partial step under an honest subject; a workstation stages only its own paths.
4. Push every working directory that has a remote, in both modes. Worker commits not yet reviewed are pushed too, labeled `UNREVIEWED` in the Status line, the handoff and the question; on a workstation that is decision 12.
5. Ask one plain-text question and end the turn. The message carries the short handoff summary, in both modes.

A usage limit is the one stop where this can't run (§2.4). In both modes the branch still holds the handoff as of the last reviewed wave.

**An answer reaches the worker verbatim.** The next launch approves gate 1 with Gary's words as `approval`, and the group carries `answer: {question, answer}`. The script refuses an `answer` that differs from `approval`, and the hook has already checked `approval` against the human turn.

### 1.7 The passive driver on a runner

`personal-plan-model-tiers` has no unattended mode. Each STOP is a model swap, and only a human can make one: `/model` in the session, or a new session started from the STOP prompt. On a runner it saves (plan, handoff, commit, push) and stops at each STOP marker as today, and Gary starts the next wave on the model the marker names. When the runner is Claude Code with the plugin loaded, its kickoff points to orchestrate instead, which sets the model per subagent. Running every wave on the session's model would remove the stops, but spends `[deep]` rates on `[fast]` work, so it isn't proposed.

It stays unchanged, core.md's branch rules included: always-a-task-branch is orchestrate's rule. Its plan file and STOP prompts already serve as the handoff: each wave's chat updates the plan's `(done)` markers, Status line and Token log before it stops, and the STOP prompt names the plan, the branch and the next model, so the next chat resumes from them. On a runner the plan already rides the branch in `specs/handoffs/`, and the handoff is written at each stop. Gary can extend it: a handoff file refreshed at every STOP on a workstation too, and the short summary in each STOP message.

---

## 2. Claude Code adapter

### 2.1 The pieces, and why

| Piece | Job |
|---|---|
| `personal:plan-segment` workflow (`kit/claude-workflows/plan-segment.js`, 298 lines; Appendix A) | Runs one unit. It validates `args` against `plan_state.py`'s unit and refuses any stopping gate not approved for that wave. When `canaryDone` is false it runs only the first group. It then runs `pipeline(groups, worker, reviewer)`, so each repo's review starts as soon as its worker finishes. In unattended mode it retries each broken group once (§1.5) and returns the checkpoints it passed. A fix-up unit quotes its failed check or concern, verbatim, into the worker and review prompts. It returns result objects only. |
| 5 plugin agents | `plan-worker` (`model: inherit`; the call sets model and effort), `plan-worker-exec` (sonnet, medium; the Agent path's `[exec]`), `plan-worker-xdeep` (opus, xhigh), `plan-reviewer` (opus, high; tools Read, Grep, Glob, Bash), `plan-reviewer-xdeep` (opus, xhigh; same tools) |
| `orchestrate_gate.py`, a `PreToolUse` hook on `Workflow` | Lives in a Claude-only `hooks/claude-hooks.json`. Plugin manifest hook files are "Loaded together with `hooks/hooks.json`" (https://code.claude.com/docs/en/plugins/manifest-reference#fields). It denies a launch unless every rule below holds, and it never allows a launch outright, so the session's permission rules still apply. It fails closed on every failure it can see: bad input, a missing or older `plan_state.py`, any exception, or no decision within its own 20 s deadline deny with exit 2, which blocks even when the JSON is lost, and the hooks file's `\|\| exit 2` covers a `python3` that won't start. Two limits remain: Claude Code cancels a hook at its 30 s timeout and then doesn't block (hence the shorter deadline), and a hooks file that isn't loaded checks nothing (phase 0 criterion 7). |
| `plan_state.py`, `check_wave.py`, `token_tally.py` | §1.2, §1.5 and §2.6 |

The hook's rules for a plan-segment launch:
1. `args.state` equals `plan_state.py` run from disk.
2. Approvals appear only in a turn a human started or a human message joined mid-turn, and `approval` matches that human's message word for word. An approval, a group's `answer`, or a mode answer that is the Kickoff prompt or holds its mode line is denied: a paste starts a session and answers nothing.
3. `canaryDone` is true only after an earlier canary launch in this session.
4. No earlier run in this session is still unfinished.
5. Any gate the last run stopped at is approved. `gate-0` and `gate-mode` are excepted: they clear only from the plan.
6. The launch is by name only, not by `script` or `scriptPath`.
7. An unattended mode is confirmed in this session, for this harness and runner (below).
8. A guard raised since this session's last launch carries an approval of `gate-guard`, and a raised fix-up cap one of `gate-1`, so rule 2 checks Gary's words.
9. Orchestrate runs only on a task branch, in both modes, on every machine. Each group's working directory has the group's `branch` checked out, and neither it nor the branch of the repo that holds the plan is `main`, `master`, `release/*` or the remote's default branch (the name check is mine). The plan and its handoff sit in `specs/handoffs/`, have no uncommitted changes, and the handoff's last commit is the plan's or a later one and is on the branch's upstream. Every working directory of this session's last finished run has its HEAD on its upstream too. So every wave's results and handoff are committed and pushed before the next launch. Gated on a workstation, where nothing can be pushed, a plan in no git repo skips the plan check, a plan in a repo with no remote skips only its push check, and a working directory with no remote isn't checked; unattended needs the plan in a repo with a remote. A repo with a remote must record origin's default branch (`refs/remotes/origin/HEAD`; a cloud checkout has none until the parent runs `git remote set-head origin --auto`), and any git error other than "not a git repository" denies, so a broken config or a dubious-ownership refusal can't pass as a plan in no repo.
10. A WAIVED Review log line added since this session's last launch is a human message of this session, word for word. In any session, a WAIVED line whose words are the Kickoff prompt or hold its mode line is denied.

**How the hook tells a human turn from a notification.** It reads the transcript's own fields rather than a `UserPromptSubmit` recorder. `UserPromptSubmit` also fires on "A background subagent reporting back" (https://code.claude.com/docs/en/hooks#userpromptsubmit) and carries no origin. The live runs showed that the transcript marks notifications with `promptSource: "system"` and `turnOrigin: "task_notification"`. In this cloud session typed prompts carry `promptSource: "sdk"`, `turnOrigin: "human"` and `origin.kind: "human"`, which the hook accepts. Three more record shapes need handling:
- **Compaction summaries** (`isCompactSummary`, `isVisibleInTranscriptOnly`) carry `turnOrigin: "human"` and recap the conversation, "gated" included. The hook skips them. The transcript is append-only, so it still reads every turn from before a compaction.
- **The `[Request interrupted by user]` marker** has no origin fields, so it reads as human. The hook skips it.
- **A message typed while the parent is working** is recorded only as a `queued_command` attachment with `origin.kind: "human"`, then absorbed into the running turn: 3 of about 35 human messages in this session. The hook reads it as human text of the turn that absorbed it, so rule 7's take-back sees it, and an approval may match it.

**How a recorded unattended confirmation satisfies the hook.** The same way a gate answer does, from the transcript, word for word. Rule 7 holds when:
- the mode line's `session` is this session (the hook input's `session_id`);
- its signal names `harness=claude-code` and the hook's own runner token: `cloud`, or `self-hosted` with `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=self_hosted`, from `CLAUDE_CODE_REMOTE=true`; `ci` from `CI` or `GITHUB_ACTIONS`; `none` otherwise. This holds on both paths, so a session that moved to another environment with its id re-asks too;
- for an answer, a human turn in this transcript is the recorded words, after whitespace is collapsed, and it comes right after an assistant message that asked the kickoff question (`Proposed mode:` and then `Reply`), unless `CI=true`. Its words name `unattended` and not `gated`, ask nothing back (no `?`) and negate nothing (no, not, never, without, `n't`), so a bare yes, a question or "don't run unattended" re-asks (decision 9; the last two checks are mine and err toward asking). Words that are the Kickoff prompt or hold its mode line never count here. Unlike a gate answer it may be an earlier turn, since later launches start from notification turns, and any such turn counts, so a later identical message to another question doesn't hide it;
- for a pasted prompt (`by Kickoff prompt`), the recorded words are `Run in unattended mode.`, the plan's Kickoff prompt on disk carries that line, and a human turn here is that whole prompt, whitespace collapsed, with its `On branch` lines set aside (a runner rewrites them to its assigned branch, §1.5 path b). The hook can't see the assigned branch; the parent compares it;
- after the latest such turn, no human message of 10 words or fewer names `gated` and not `unattended`. A false trip errs toward stopping: the parent asks the kickoff question again.

A gated record needs no proof. It relaxes nothing, and its first dispatch is the canary, which stops at gate 5: the same exposure as today's kickoff.

**Gates still derive from the plan in unattended mode.** `plan_state.py` computes every gate from disk and splits it into `stops` and `checkpoints` by the recorded mode. Rule 1 makes the launch carry exactly that split, rule 7 makes the mode behind it real, and the script requires an approval for every stop. The mode decides which gates ask, never which gates exist.

**Why the Workflow tool rather than plain Agent calls:**
- Only there can code refuse to spawn.
- Effort is set per call; the Agent tool has no effort field.
- Returns are checked against a schema.
- Reviews follow their workers without a parent turn in between.
- Diffs never enter the parent's context.

**Alternatives:**
- **Agent calls only:** kept as the fallback path (§2.3) and as phase 0's fail-over.
- **Ultracode in the parent:** rejected. It orchestrates every task in the session, and it lifts the 25-agent warning and auto mode's first-launch prompt.
- **Agent teams:** rejected. They have no per-teammate gates.
- **A script the model writes each run:** rejected. There is no "don't ask again", and the gate logic is new every time.
- **Retries across runs:** rejected. The hook would need a retry chain and `plan_state.py` a run history; a retry inside the run needs neither.
- **Fix-ups inside the run:** rejected. `check_wave.py` runs in the parent, after the run, and each fix-up's Review log line and handoff commit land between runs, where `plan_state.py` and the hook see the streak.

**What enforces what.** This replaces v1's claim that "a parent mistake can only stop a run early".

| Risk | Stopped by |
|---|---|
| The parent forgets a gate | The script, from `plan_state.py`'s stops |
| The parent misstates `prev`, a milestone, `(done)` or the canary | The hook (`plan_state.py` from disk; transcript history) |
| A stale or reused approval | The script (approvals keyed by wave) and the hook (human turn, word for word, owed gates) |
| An unattended mode Gary never confirmed, or one he took back, including mid-turn | The hook (rule 7) |
| An invoking message, a casual mention or a question back recorded as the unattended answer | The hook (rule 7: only right after the kickoff question, outside CI, with no `?` or negation) |
| A pasted unattended prompt that isn't the plan's, or in another harness, runner or session | The hook (rule 7) |
| A pasted prompt used as a gate answer, a `needs_info` answer, a waiver or a mode answer | The hook (rules 2, 7 and 10) |
| A hook that crashes, can't import `plan_state.py`, or stalls | Its exit 2 and its 20 s deadline; not Claude Code's 30 s timeout, nor a hooks file that never loaded |
| Dispatch before a kickoff answer is recorded | `plan_state.py` (`gate-mode`) and the script, which accepts no approval for it |
| A guard or fix-up cap raised without asking, within a session | The hook (rule 8) |
| A waiver Gary never gave, within a session | The hook (rule 10) |
| Fix-ups past the cap | `plan_state.py` (gate 1 stops past `fixups`) |
| A wave's results or handoff left uncommitted or unpushed, in either mode, in any working directory of the last run | The hook (rule 9) |
| A launch off a task branch: `main`, `release/*`, the default branch (or a repo whose default the hook can't see), a detached HEAD, a branch that isn't the group's, a repo git refuses to read | The hook (rule 9) |
| A Kickoff prompt whose mode line disagrees with the record, or that names no repo and plan; an unattended record whose signal isn't tokens | `plan_state.py` (gate 0) |
| Unplanned premium spend unattended | The script (no automatic retry at or into `[xdeep]` or Fable; drafts and `max` need a gate-7 approval) and `plan_state.py` (gate 7 on unplanned `[xdeep]` work) |
| Spend running past the estimate | `plan_state.py`'s guard, between runs |
| Two runs at once in one session | The hook |
| Commit, trailer or scope slips | `check_wave.py`, which makes it gate 1 |
| An `availableModels` substitution | `token_tally.py --check-routing`, which makes it gate 1 |

These still rest on trust:
- **Whether Gary's words mean yes.** The hook checks where the answer came from and that it names unattended without a question or a plain negation, not what it means.
- **Whether the kickoff question was honest.** The hook checks that Gary named unattended, not that the cost and gates the question quoted were right.
- **A gated kickoff record.** The hook doesn't check its words, so a non-answer recorded as gated dispatches the canary, which still stops at gate 5.
- **A guard or fix-up cap raised, or a waiver written, between sessions.** Rules 8 and 10 compare with this session's previous launch only. Rule 9 sees only this session's runs, so a new session's first launch doesn't check the other working directories; its re-entry reconciles from git (§2.3 step 7).
- **Token log lines.** The guard counts only the lines the parent appends after each run.
- **Review log lines.** The parent logs a failed check as CONCERNS and holds back the scope breaches that stop; nothing checks that it did, nor that a PASS came from a reviewer. A breach logged by mistake reaches a worker told to stay in its own directory and to leave alone any path it did not make. It can't repair most breaches, so it returns `failed`, and after the in-run retry that stops.
- **The handoff's content.** Rule 9 checks that it was refreshed, committed and pushed, not what it says. The chat summary isn't checked at all.
- **Which branch is a task branch.** Rule 9 checks names only. A branch an open PR targets, one with someone else's open PR, or one whose PR has merged passes it; the parent's git.md checks at kickoff catch those.
- **The prompt on disk.** Rule 7 compares a paste with the plan's prompt as it is now, `On branch` lines aside, not as the kickoff session wrote it. A parent that rewrote the prompt to match some other message of Gary's gains nothing: that message would hold `Run in unattended mode.`, which no answer may hold, and the rewrite is in the branch history, since rule 9 needs the plan committed and pushed. `plan_state.py` checks that the prompt names a repo and a plan, not that they are this plan's.
- **The runner signal's tokens.** The hook compares tokens with its environment; the parent writes them, and the hook can't see an assigned branch.
- **Outward actions inside a run.** The prompts forbid them and ask for `needs_info`; nothing checks the commands a worker runs.
- **A failure recorded in an earlier session.** The `BLOCKED` line in the plan is the only record, and save-before-you-wait already requires it.
- **The Agent path.** It has no hook, so its gates and its unattended mode rest on the parent, as Cursor's do today.

### 2.2 Tiers to agent, model and effort

| Tier | Worker | Reviewer |
|---|---|---|
| `[xdeep]` | `plan-worker-xdeep`, opus/xhigh (opus/max with `max`). `xdeepDrafts: 2–4` drafts plus a judge, opt-in at gate 7 | `plan-reviewer-xdeep`, opus/xhigh |
| `[deep]` | `plan-worker`, opus/high | `plan-reviewer`, opus/high |
| `[exec]` | `plan-worker`, sonnet/medium (sonnet/high with `execHigh`) | `plan-reviewer` |
| `[fast]` | `plan-worker`, haiku (no effort setting) | `plan-reviewer` |
| Fable step-up (gates 6 and 7) | `plan-worker-xdeep`, fable/xhigh (fable/max with `max`) | `plan-reviewer-xdeep` |

The parent stays on `/model opus` and `/effort high`, and so do `[deep]` workers and the reviews below `[xdeep]`: none is interactive planning, the one case plan-execution.md drops `[deep]` to medium.

**Effort step-ups, set per launch** (plan-execution.md's picker notes):
- **`execHigh`** runs an `[exec]` unit on Sonnet high, for a large codebase or a stalled step. The parent sets it at dispatch, or on a relaunch Gary approves at gate 1. Unattended, an `[exec]` group that fails at medium retries at high in the same run (§1.5), and one that fails at high steps up to `[deep]`, since `[exec]` never goes past high.
- **`max`** runs an `[xdeep]` or Fable worker at max, only on a task type with a measured gain (Fable on terminal or CLI-heavy steps, Opus on multi-app business workflows). Its review, drafts and judge stay at xhigh, the tier's level. Unattended, it needs a human gate-7 approval for the wave, as drafts do.
- Either one on another tier is gate 0.

**No ultracode.** Orchestrate runs `[xdeep]` without it, audit-shaped steps included: workers don't spawn subagents, and ultracode in the parent is rejected (§2.1). The kit's fan-out is one worker per working directory, plus the opt-in drafts. A plan whose `[xdeep]` audit needs ultracode's fan-out runs that wave on the passive driver (mine).

**Why five agents rather than two or three:** the Agent path can't pass effort. So the `[xdeep]` worker and reviewer need definitions that say `effort: xhigh`, the Agent path's `[exec]` worker one that says `effort: medium`, and reviewers need a definition that carries the tool allowlist. The three carry the tier's name, not an effort's.

**Haiku still thinks:** it inherits the session's thinking setting (v1's wire capture showed a 31,999-token budget). The picker note needs updating.

### 2.3 The parent's loop

1. **Preflight**, once per chat and per new working directory:
   - Check the branch and the git email in each working directory and in the repo that holds the plan. Where one isn't on a task branch, the kickoff cuts one (§1.5 step 2). In each repo with a remote and no `refs/remotes/origin/HEAD` (a cloud checkout has none), run `git remote set-head origin --auto`, so rule 9 can see the default branch.
   - Run `check_wave.py snapshot`; it must pass.
   - Note each repo's attribution setting.
   - Tag and group the plan.
   - Write the Kickoff and the Cost table. The Claude Code rows include each wave's review subagent at 0.6× a medium step, and the orchestrator row's gate waits follow the proposed mode (§1.5).
   - Write the Token log's counting header: the Claude Code usage row and the rates of the plan's models. It serves a pasted or passive chat; workflow workers don't need it (§2.6).
   - Read the runner signals, save, ask the kickoff question, record the answer and the prompt's mode line, then commit and push the plan and handoff before halting or dispatching (§1.5). A session started from a pasted Kickoff prompt that counts records its own confirmation instead and asks nothing, or re-posts a `BLOCKED` question (§1.5).
   - Seed the todos.
2. **For each unit:**
   - Update the plan and the handoff, commit both in one commit and push, in both modes (hook rule 9).
   - Run `plan_state.py`. If it reports errors, that is gate 0. If any of `stops` is unanswered, write `BLOCKED`, save (§1.6), ask, and end the turn. `checkpoints` ask nothing.
   - Otherwise build the `args` and take a fresh `check_wave.py snapshot`. Keep the snapshot from before each wave until its groups' streaks end: a fix-up's check uses it as `--baseline`.
   - Call the Workflow tool with `name: "personal:plan-segment"`. SKILL.md must say "call the Workflow tool" in so many words, because that sentence is the opt-in.
3. **Check the launch result:**
   - `error` set means the script failed its syntax check: gate 0.
   - `remote_launched` means the run went to a cloud session and its commits would land elsewhere: gate 0, then use the Agent path.
   - Show any `warning` to Gary.
4. **While the run works**, in both modes, write nothing to the tree: the plan is tracked in `specs/handoffs/`, and `check_wave.py` would flag the edit as a new dirty path. End the turn with one line.
5. **On completion:**
   - Run `check_wave.py check --snapshot <this launch's snapshot> --run <session>/workflows/<runId>.json`; for a fix-up, add `--baseline <the snapshot from before the wave it fixes>`. The run record supplies the plan path, so the parent's bookkeeping commits in the range are skipped.
   - Run `token_tally.py --run <runId> --check-routing --parent-window <previous runId>:<runId> --parent-row "orchestrator-wave-<N> <group-id>"`, where wave N is the unit the previous run carried. For the first run the window is `start:<runId>` and the row `orchestrator-kickoff <plan name>`. Windows don't overlap, so the guard never counts the parent twice.
   - For each group: mark `(done)`, write the Review log line (`from..to` from `check_wave.py`, checkpoints in the note), append Token log lines, update the Status line and the todos. A fix-up's lines use its label: `N-fix`, `N-fix2`. A group whose check failed or whose review returned CONCERNS is still marked `(done)`: its fix-up comes from the Review log, not from open steps.
   - **A failed check** on a group is logged as that group's Review log line, verdict CONCERNS, with a note that starts `check_wave.py:`, quotes the failing output on one line, and ends with the review's verdict (`; review PASS`, or `; review CONCERNS: <its note>`): `review wave-2 (repo-b m1 s4) 846932b..518e99f: CONCERNS - check_wave.py: repo-b: m1.s4 has no commit; review PASS - 2026-10-06`. This keeps the standard's grammar, and `plan_state.py` schedules the fix-up from it. A scope breach (§1.5) gets no such line: it is `BLOCKED at gate 1`.
   - Refresh the handoff (§1.6), in both modes. Commit the plan and the handoff in one bookkeeping commit whose subject doesn't start with a step ID, and push each working directory (hook rule 9 checks both). After a fix-up that rewrote commit messages, the push is `--force-with-lease --force-if-includes`.
6. **Branch on the result:**
   - **A failed check, or `stop: "gate"`:**
     - Unattended, a failed check that isn't a scope breach doesn't stop: go back to step 2, where `plan_state.py` makes the fix-up the next unit, a checkpoint until the cap is spent.
     - Otherwise save (§1.6), writing `BLOCKED` with the gates and any `questions`.
     - Ask one question that names each repo's commit range and the next unit, then end the turn. The message carries the short handoff summary (§1.6).
     - After an explicit answer in the next human turn, approve exactly those gates as `[{gate, wave}]`, with `approval` set to the answer word for word. A `needs_info` group also gets `answer`.
   - **`done`:** go back to step 2 with `approved: []`, without asking. In unattended mode the next unit's checkpoints, an automatic fix-up's gate 1 included, don't ask either.
   - **`end`:** do the final completion per the standard: replace the `(output est.)` lines of sessions that have ended, add the Cost table's actual columns from the Token log, append the Completion summary with the checkpoints, retries and fix-ups, print the table. Write the final handoff. Then save and ask about the PR, with the short handoff summary.
7. **Re-entry.** A fresh chat, usually started from the pasted Kickoff prompt, reads the plan and the handoff from the branch, by §1.5's path (a), (b) or (c). A paste that counts confirms the mode there and starts, or re-posts a `BLOCKED` question. It asks first only when the handoff or the Status line shows a run in flight whose record is missing or unfinished: it then reconciles from git (uncommitted and unpushed work) and asks before relaunching. Otherwise an unattended record from another session means the kickoff question again, and so does a gated record whose harness or runner token no longer matches.

**The Agent path** reuses the same agents, prompt text and checks:
- Call `Agent(subagent_type: "personal:plan-worker", model: <alias>, description: <wave title>, prompt: …, run_in_background: false)` once per working directory, all in one message.
- Then call `personal:plan-reviewer` the same way.
- `plan-worker` sets no effort, so an Agent call takes the session's (UNVERIFIED on another model): `[exec]` calls `plan-worker-exec` (Sonnet medium) instead, its step-up calls `plan-worker` with `model: sonnet` for the parent's high, and `max` doesn't exist on this path.
- The parent applies `plan_state.py`'s stops, the retry policy, the fix-ups and the per-wave handoff by hand.
- Foreground calls keep the turn open, which also avoids the runner Stop hook.

### 2.4 Runners, recovery and limits

- **No resume in v1.** The docs say a "Failed" agent "runs again, and so does every agent that started after it, even ones that completed" (https://code.claude.com/docs/en/workflows#resume-after-a-pause). In the cloud, run results also survive a VM reclaim, but unpushed commits don't.
  - Instead, the parent starts a new run from `plan_state.py`. The worker prompt says to skip steps that already have commits, and the review covers the whole range.
  - A run that dies with its session leaves no record, so the hook then refuses any further launch in that session. Start a new session from the pasted Kickoff prompt, which confirms the mode there when the environment matches.
  - In both modes the branch holds the plan and a handoff as of the last reviewed wave, so a lost session or container costs at most the wave in flight. The new session reads both from the branch.
- **The runner Stop hook.** The launch turn ends while workers are still editing, and the hook blocks once with "Please commit and push". The rule for that continuation:
  - It is not an instruction.
  - The parent doesn't commit or push. It replies with one line.
  - The hook's `stop_hook_active` check lets the second stop through.

  Observed here: the container stays up while the parent sits idle with a workflow running. No worker exit (`cost-state` record) fell inside any of 16 run windows, parent-idle stretches inside runs reached 80 and 58 minutes, and all 7 exits fell in gaps with no run.
- **A stop with unreviewed worker commits, in either mode:** push them, labeled `UNREVIEWED` in the Status line, the handoff and the question. Gary's rule (save first, push included, before any question) settles v2's decision 4 on a runner. The kit pushes them on a workstation too, in both modes: in the plan's repo the handoff commit sits on top of them, so pushing the handoff pushes them, and rule 9 checks every working directory. `plan-execution.md` says only the parent pushes, after its review, so this is mine and open as decision 12.
- **Usage limits.** A run pauses at a limit only in an interactive claude.ai session; background and Remote Control runs fail instead (https://code.claude.com/docs/en/workflows#when-a-run-hits-your-usage-limit). After a failure, start a new run once the limit resets. `send_later` may schedule that relaunch, but it never answers a gate; in unattended mode the relaunch needs no answer for checkpoints.
  - Observed in this cloud session: a spend limit didn't pause the run. It completed with 7 of 27 agents returning null, the parent's next model call failed with the limit message, and the worker exited. So a limit is the one stop where save-first can't run: worker commits stay unreviewed and unpushed, and the plan is stale. In both modes the pushed handoff is one wave behind, not more.
  - The next human turn reconciles from git (uncommitted and unpushed work) before relaunching. The workflow's automatic retry fails at once too, which costs little; a crash and a limit both return null, so the script can't tell them apart.

### 2.5 Permissions

- **`-p` and the SDK:** the allow rule `Workflow(personal:plan-segment)` works. Verified live: without it, the launch was denied with "Review dynamic workflow before running". Interactive sessions get "don't ask again" for a plugin workflow.
- **Workers** use the session's rules. Allow `git add`, `git commit` and each repo's test commands. Reviewers need read-only Bash. Pass other repos with `--add-dir`, as the live runs did.
- **Auto mode:** "the prompt your script passes to `agent()` doesn't count as a request from you" (https://code.claude.com/docs/en/workflows). Worker commits passing in auto mode is an exit criterion for phase 0.
- **Unattended answers no permission prompt.** A prompt mid-run still waits for Gary. Unattended runs work best with the allow rules above in place. Both modes push after every wave, so allow the parent's `git push` too, `--force-with-lease --force-if-includes` included for a fix-up that rewrote messages. Leave `gh pr`, tag and deploy commands out of them, so a worker that tries one meets a prompt instead of running it.

### 2.6 Token tally and the routing check

`token_tally.py` reads `subagents/workflows/<runId>/agent-*.jsonl` and the `.meta.json` labels, and follows the standard's source precedence:
- one call per `message.id`, with its usage from the line that carries `stop_reason`;
- a call with no such line keeps its exact input-side counts and gets 1,000 output tokens, and its token line ends `(output est.) session <id>`;
- workers and reviewers of a fix-up get `wave-N-fix` and `review-wave-N-fix`, then `wave-N-fix2` and so on; an automatic retry keeps its wave's row and is routed by its own tier;
- the parent line comes only from `--parent-window`, between two launches;
- `<model>` drops a trailing `-YYYYMMDD` (`claude-haiku-4-5-20251001` prints as `claude-haiku-4-5`), as the standard's line format says; pricing and `--check-routing` use the raw id.

The parent writes every token line from this tally, so workflow workers get no token instruction, unlike the standard's quote-the-header-into-each-dispatch rule (§4). For example, from the Haiku smoke run and from one of this session's Opus research agents (its label isn't a plan row):

    tokens wave-1 repo-a-m1-s1 (claude-haiku-4-5): input ~50 / cache read ~120k / cache write ~26k / output ~2k | ~$0.05 API-equiv
    tokens research:session-usage (claude-opus-5-5): input ~100 / cache read ~6.3M / cache write ~200k / output ~52k | ~$3.30 API-equiv (output est.) session 6333c263-f7c1-58ee-bb8f-25209c81c588

The committed `(output est.)` rule stands: on this session's Opus 5.5 workflow agents, 6,092 of 6,117 calls had no line with `stop_reason`, and the last copy still carried a placeholder output count. Only the Haiku stand-ins logged one on every call.

**Parent lines and review cost:**
- Parent lines are exact: main-session lines always carry `stop_reason`. With `--parent-window`, each covers one stretch between launches, labeled `orchestrator-kickoff` or `orchestrator-wave-N`. The final completion turn isn't flushed yet, a small tail the standard says to ignore.
- Subagent lines in a live session stay `(output est.)` at completion. Their session's `cost-state` record also covers the parent and every other wave, so the standard keeps the lines rather than merging them.
- Live review cost was $0.06 for two reviews against $0.11 of work. In v1, one review cost $0.23 against $0.06 of work.

---

## 3. The other harnesses

These are v1's verified findings, with the later changes added. Every native adapter runs the kickoff question and reads `plan_state.py`'s `stops`. Each also runs only on a task branch, commits and pushes the plan at kickoff and the handoff after every wave, in both modes, writes the Kickoff prompt's mode line, and in unattended mode runs the automatic fix-ups; only Claude Code's hook checks the branch, the commit and a pasted confirmation.

**Codex (native, phase 2)**
- **Roles:** `plan_xdeep` `gpt-6-astra`/xhigh, `plan_deep` `gpt-6.1-sol`/xhigh, `plan_exec` sol/medium, `plan_fast` `gpt-6-luna`/low, plus one reviewer role each: `plan_review` sol/xhigh and `plan_review_xdeep` astra/xhigh.
  - Copy them into `~/.codex/agents/`; don't symlink. A role locks its model, but it can't restrict tools, so "read-only" is enforced by instructions only.
- **Dispatch:** one `spawn_agent({agent_type, fork_turns: "none", message})` per working directory, all in one turn, then `wait_agent`. Start the parent with `--add-dir`. Raise `[agents] max_threads` above its default of 3 for wider waves.
- **The parent** runs `plan_state.py` and `check_wave.py`, asks every stop in plain text, and never orchestrates under `/goal`.
- **Mode:** no documented cloud signal, so it proposes gated unless Gary says otherwise. A cloud task stays one passive-driver wave (no per-task model), so unattended orchestration is a local opt-in on Codex. Nothing checks the confirmation in code.
- **Tally:** rollout `token_count` events, per the standards' table.
- **Optional:** a `PreToolUse` deny on `.*spawn_agent$` while `plan_state.py` reports unanswered stops. Never use `ask`, which fails open. Untrusted hooks are skipped, so this is defence in depth only.

**Cursor (native now; phase 3)**
- **Keep** `Task` with `model` on every call.
- **Add:**
  - `plan_state.py` and `check_wave.py`;
  - an Opus review subagent per working directory (high, or xhigh after an `[xdeep]` wave) in place of the parent's inline review;
  - the `[exec]` slug `grok-4-7[effort=high,fast=false]`;
  - plain-text gates;
  - optionally, a fail-closed `subagentStart` hook that denies a dispatch while `stops` is non-empty.
- **Mode:** proposes unattended on a cloud agent (the Cloud MCP's `run-info` tool, or its own branch). With no hook to check the confirmation, unattended rests on the parent, as its gates do today. Cursor's cloud agents run only the repo's `.cursor/hooks.json`, so the optional hook needs that file there.
- **Cursor imports Claude plugins.** It may list the `personal:plan-*` agents with `model: inherit`, so the Cursor branch never dispatches them. The Claude hooks file matches only `Workflow`, and Cursor has no tool by that name.

**Grok Build (passive until a signed-in test; phase 4)**
- v1's design stands: `spawn_subagent` with `cwd`, Grok-format agent files, and `[subagents.models]` pins.
- Grok and Muse both load the Claude hooks file (`muse plugins validate` reports `hooks=4`). The hook does nothing for any tool call that isn't a plan-segment launch.

**Gemini CLI (passive)**
- The parent would be Gemini 3.1 Pro, which the standards don't trust with `[deep]` work.
- `[xdeep]` means switching harness.
- Its hooks fail open.

**Muse Code (passive)**
- `subagent_spawn` can't set a model or effort per child, and Muse's tiers differ only by effort.
- The Apple-silicon build has no workflow engine.
- Separately, runbook m7.s4 is out of date.

---

## 4. Repo changes and rollout

Sizes: S is under 30 lines, M is 30–200, L is a rewrite.

| File | Change | Size | Phase |
|---|---|---|---|
| `personal-plan-orchestrate/SKILL.md` | Core and detection go here; per-harness steps move to `adapters/`. Drop "Cursor-only", the #43869 gate and "Out of scope: Claude Code". Say "call the Workflow tool". Add the kickoff question, with its fixed `Proposed mode:` and `Reply` words and the runner signals and their tokens (§1.5), which replaces the separate destination question; task branches only (find or cut one per repo, the mode answer as a workstation's yes, a declined cut); the commit and push of the plan and handoff before any halt or dispatch; the gate table by mode, retries, automatic fix-ups and their cap, the failed-check Review log line, the WAIVED line, the scope breaches that stop, and the snapshot kept as a fix-up's `--baseline`; the guard; questions with save-first, and the per-wave handoff and its chat summary in both modes (§1.6); the Kickoff prompt (plan line, `On branch` lines, mode line), what rewrites it, the three ways into a new session and when it re-asks, and the resume step (§1.5, §2.3). Contract item 7 (token reporting) applies to Cursor `Task` subagents, not to workflow workers; `{wave-n}` in the artifact path takes `N-fix2` | L | 1 |
| `…/adapters/claude-code.md`, `cursor.md`, `codex.md` | §2.3-2.6; today's Task text plus the §3 Cursor fixes; §3 Codex. Each names its runner signal | M each | 1; 1 and 3; 2 |
| `…/claude-agents/` (5 files), `…/claude-workflows/plan-segment.js` | As in `kit/` (Appendix A) | S each; M | 1 |
| `…/scripts/plan_state.py`, `check_wave.py`, `orchestrate_gate.py`, `token_tally.py` | As in `kit/scripts/`: `plan_state.py` (§1.2, §1.5: units, gates split into stops and checkpoints by mode, fix-up labels and the cap, WAIVED lines, the guard, the mode record with `via` and the signal tokens, the Kickoff prompt's mode and plan lines, `kickoff_prompt()`); `check_wave.py` (snapshot and check, the parent's bookkeeping commits skipped with `--plan`, `--baseline` for a fix-up); `orchestrate_gate.py` (§2.1: rules 1-10, exit 2 on its own failure, a 20 s deadline); `token_tally.py` (§2.6) | M | 1 |
| `…/tests/` (5 suites, `orchestrate_check.py`, `test-orchestrate.sh`) | As in `tests/`: 154 tests and the consistency check. `test_token_tally.py` reads the price table from `plan-execution.md`; the node suite skips when node isn't installed; the hook suite builds clones with bare origins and `origin/HEAD` for rule 9 | M | 1 |
| `hooks/claude-hooks.json`, `.claude-plugin/plugin.json` | The `PreToolUse` hook, with its `\|\| exit 2` fallback; manifest `agents`, `workflows` and `hooks` | S | 1 |
| `agents/Makefile` | Add `test-orchestrate` to `test` | S | 1 |
| `standards/plan-execution.md` | Orchestrate's review becomes a subagent per working directory; one unit per dispatch; gates from `plan_state.py`; non-answers; Claude Code `[xdeep]` in orchestrate runs without ultracode, audit-shaped steps included, drafts opt-in (§2.2); Haiku thinks; Cursor `fast=false`; line 14 drops "Cursor". (a) **STOP gate semantics:** the kickoff answer is the explicit opt-in to unattended, and so is the pasted Kickoff prompt in the session it is pasted into, when it is the whole prompt and the environment matches; unattended checkpoints, automatic retries and fix-ups under the `fixups` cap, the cost guard, the scope breaches that stop, questions with save-first, and the short handoff summary in every gate question. (b) **Fix-up waves:** `N-fix`, then `N-fix<k>` (`N-fix2`, `N-fix3`) wherever a wave number appears, with the marker regex `^--- WAVE \d+(-fix([2-9]\|[1-9]\d+)?)? \[(xdeep\|deep\|exec\|fast)\] ---$`. (c) **Review log:** a failed check is a CONCERNS line whose note starts `check_wave.py:`, and `WAIVED - <Gary's words>` ends a streak as a PASS does. (d) **Kickoff:** the active variant gains the `mode:` line with the signal tokens; its prompt gains the plan line (`In <owner>/<repo>, read <repo-relative path>.`, absolute only in decision 11's no-git-repo case), always an `On branch` line (one per repo when names differ), the mode line, and the last sentence (re-post a `BLOCKED` question, else start), so the fill-in rules change; the ask-user rule folds into the kickoff question on a workstation, where new chat stays the default, and is skipped on a runner; the orchestrator row's gate waits follow the mode, with no new-chat start-up on a runner, and its per-wave share covers the handoff. (e) **Progress tracking and Final completion:** an orchestrate run on any machine keeps the plan and handoff in `specs/handoffs/`, refreshes, commits and pushes them after every wave, and writes the final handoff; where nothing can be pushed (decision 11) the plan stays in `.scratch/` or is committed without a push. (f) **Delegating execution to subagents:** orchestrate runs only on a task branch and its kickoff cuts one where missing, so its subagents always commit; the shared-branch rules stay for other delegation and the passive driver. (g) **Token accounting** stays as committed, except that on the Claude Code workflow path the parent writes every token line with `token_tally.py`, so that path is exempt from quoting the header into each dispatch ("Who updates progress"). If decision 12 stands, "Who updates progress" and "Delegating execution to subagents" gain the exception for unreviewed commits pushed at a stop | M | 1 |
| `personal-standards/core.md`, `cursor/rules/personal-core.mdc` | Drop "(Cursor)" after `personal-plan-orchestrate`. "Runner scratch rides the branch" gains: "A `personal-plan-orchestrate` run does the same on any machine, gated or unattended, since it always runs on a task branch: its plan and session handoff live in `specs/handoffs/`, committed and pushed at kickoff, and the handoff is refreshed, committed and pushed after every wave (plan-execution.md)." "Write handoff files" and "Save ephemeral agent plans" name the same case. "Cut a task branch off a shared branch" and "Stay on the current branch" gain: "A `personal-plan-orchestrate` kickoff also cuts one off any branch that isn't a task branch, on a workstation after Gary's answer to the kickoff question, which names it." Cutting from Gary's own branch is mine. Then `make -C agents cursor-core-rule` | S | 1 |
| `personal-plan-model-tiers/SKILL.md` | §1.7: no unattended mode; on a runner, save and stop at each STOP; point to orchestrate on Claude Code; a later fix-up wave is `N-fix2` | S | 1 |
| `personal-handoff/SKILL.md` | The "Which file" table and "On a runner" cover every orchestrate run on any machine, in both modes; the per-wave fields, the chat summary and the resume step (paste the Kickoff prompt) stay in orchestrate's SKILL.md | S | 1 |
| `tag-tiers` SKILL.md, `plugins/README.md`, `specs/agent-distribution.md`, `agents/runbook.md` | Wording; the README rule "manifests are the only per-vendor files" now has exceptions; close "Still open: Claude Code"; fix Muse m7.s4; add the Codex roles step | S | 1-2 |
| `codex-agents/*.toml` (6), `agents/lib/extensions.sh` | Copy mode for Codex roles. The Agerpoint bok shares `extensions.sh`, so port it there too. | S, M | 2 |
| Cursor gate hooks (`agents/lib/hooks.sh`, also shared with the bok) | Optional | M | 3 |

`core.md` changes where it calls orchestrate Cursor-only, where it puts the plan and handoff in `specs/handoffs/` only on a runner, and where it lets only a runner cut a task branch off a branch that isn't shared. Its workstation ask before a cut needs no change: the kickoff question names the branch before anything is committed, and the mode answer is the yes. Its "say so explicitly" rule already covers the kickoff answer, since unattended needs a reply that names it, and the pasted prompt, whose `Run in unattended mode.` line says so; its outward-action and save-first rules apply as written. The proposal counts posting the handoff summary to a PR or anywhere else as an outward action. Run `make -C agents validate test` after each phase.

**Rollout:**
- **Phase 0, spike (S).** Install from a branch through the local marketplace. Run it on the Mac interactively, and once on a cloud runner. Sync serves the published plugin, not a branch (§1.4), so the cloud run needs the kit published first, under another plugin name (`args.plugin` sets the namespace), so that the standards plugin every synced surface gets stays as it is. That copy checks criterion 6 first. Merging the kit to main, with orchestrate's SKILL.md still Cursor-only, waits until criterion 6 holds: if sync rejected the new manifest fields, cloud sessions, Cowork and Chat could lose the standards plugin itself. Exit criteria:
  1. The launch, notification and relaunch loop works interactively.
  2. On the runner, the Stop-hook rule holds.
  3. Worker commits pass in auto mode.
  4. Typed prompts on the Mac look human to the hook's transcript check.
  5. The reviewer's `tools` allowlist is enforced.
  6. claude.ai org sync and Cowork accept the new manifest fields.
  7. A fresh claude.ai/code session gets, through sync, the skills and the `hooks/hooks.json` SessionStart (§1.4), and the synced manifest's `agents`, `workflows` and `hooks` fields are registered: the 5 agents, the `personal:plan-segment` workflow and the `claude-hooks.json` `PreToolUse` hook. The published plugin uses none of those fields. Check with the skill listing and the canary, Agent's subagent types, the Workflow tool's workflow list, and a denied dishonest launch.
  8. On the cloud runner, a typed `unattended` satisfies rule 7, and the plan runs from the kickoff answer to the PR question with no other stop, across a compaction and a later "yes" to another question. A short `gated` typed mid-run stops the next launch. Which branch a cloud session started on an existing task branch is assigned: its own `claude/…` branch, as this session's, or the task branch. A new cloud session started there from the pasted Kickoff prompt records its own confirmation and dispatches with no question, rewriting the prompt's `On branch` line if its branch is its own, and the transcript's text of the paste equals the plan's prompt after whitespace is collapsed (also on the Mac, through the terminal's bracketed paste); the same paste on the Mac gets the kickoff question, and so does a paste used to answer a `BLOCKED` gate, which the session re-posts.
  9. In both modes, on the runner and on the Mac: every wave's bookkeeping commit carries the plan and the handoff and is pushed before the next launch, and every message that stops or asks carries the handoff summary. Unattended: a planted check failure (a step left without a commit) gets `N-fix` with no stop, and that fix-up passes `check_wave.py` in the repo that holds the plan; a group that fails three times in a row stops at gate 1. Gated on `main` on the Mac: the kickoff question names the task branch, the answer cuts and pushes it, and nothing commits before the answer. Gated on the Mac with a cross-repo plan in a plain folder of sibling repos: the plan and handoff stay in the folder's `.scratch/`, and the hook allows the launch. A runner-confirmed plan pasted into a Mac clone on `main`: the session reads the plan from `origin/<branch>`, asks the kickoff question with the switch folded in, and after the answer switches to a local branch tracking `origin/<branch>`. A plugin `PreToolUse` hook that exits 2 blocks the Workflow call.
  10. An `agent()` call and the `-xdeep` agents' frontmatter put `xhigh` on the wire, and `plan-worker-exec`'s puts `medium`, as v1's probe showed for `low` and `max` per call.

  If criterion 1, 2 or 3 fails, ship the Agent path first. If 7 fails for the agents, cloud sessions run only the passive skill until sync registers them, since the Agent path needs them too. If only the workflow or the hook is missing, cloud sessions use the Agent path, whose gates rest on the parent.

  Already observed in this session, with inline-script workflows: relaunches from notification turns in auto mode, with no permission prompt; the container staying up while idle with a run going; a resumed session keeping its id and transcript; cloud prompt fields; the run record written only at the end; a spend limit failing a run; the synced plugin's skills and SessionStart hook at the 21:07 start (§1.4). A named plugin workflow behind the hook is untested in cloud.
- **Phase 1, Claude Code (L).** Dogfood one real plan of 3-5 waves on the workstation, gated, one on the workstation, unattended, and one on a runner, unattended, each with its plan and handoff in `specs/handoffs/` and at least one continued in a new session from its pasted Kickoff prompt, then flip the gate. Compare each plan's actual columns with its expected ones.
- **Phase 2, Codex (M).**
- **Phase 3, Cursor (M).**
- **Phase 4, Grok (M, optional).**

---

## 5. Decisions for Gary

1. *(Settled; see below.)*
2. **Planned `[xdeep]` waves, unattended:** a checkpoint, since the kickoff question quoted their cost, or a stop every time, as gate 7 is today?
3. **Fix-up cap: 2 automatic fix-ups per group**, unattended (`N-fix`, `N-fix2`); the third failure in a row on that group stops and asks. Recorded on the mode line as `fixups 2` and quoted in the kickoff question; a raise needs Gary's approval (hook rule 8). Or 1 (one fix-up, so a group's second failure stops), or 3? Scope breaches are decision 10.
4. **Canary:** one group, once per session, in both modes. Unattended passes it without asking once `check_wave.py` and the review pass. Keep it there, or skip it unattended?
5. **One wave per run.** The parent wakes once per wave, about $0.5-1 a wave (my estimate), mostly re-writing its cache. Fewer, longer runs would save that, but the gates, the git checks and the runner pushes all need the plan updated between waves.
6. *(Settled; see below.)*
7. **Review cost:** one Opus reviewer per working directory per wave, about 0.6× a medium step (~$0.54 at Opus high, ~$1.1 at xhigh after an `[xdeep]` wave), in place of the parent's inline review.
8. **Agerpoint bok:** port the kit? It's namespace-safe: `args.plugin`, plus a check that the manifest name matches the folder.
9. **A bare yes at kickoff.** The kit requires the reply to name `unattended`, as core.md's "say so explicitly" asks, so a "yes" re-asks, and so do a question back and a plain negation. If a yes to the proposal should count, core.md "Wait for approval" must name the kickoff confirmation (and the Cursor rule be regenerated), and the hook checks that the question right before it, which it already requires, proposed unattended. The pasted Kickoff prompt doesn't touch this: its `Run in unattended mode.` line names the mode.
10. **Scope breaches, unattended.** This is my refinement of Gary's words, not something he said. Proposed: edits in a directory with no group, a `from` that is no longer an ancestor of HEAD, or a new uncommitted path on a workstation stop at gate 1 at once, since no group's fix-up can repair them and the last may be his own edit. Or should they get an automatic fix-up like other check failures? The worker is told to stay in its own directory and leave alone paths it didn't make, so it would mostly return `failed`, which stops after the in-run retry anyway, at the cost of a fix-up run.
11. **Nowhere to push, under the per-wave handoff.** This is my refinement of Gary's v5 words, not something he said. Proposed: on a workstation and gated only, a plan in no git repo (a plain folder of sibling repos) keeps the plan and handoff in `.scratch/`, and a repo with no remote commits them without pushing, while unattended needs a repo with a remote. Its Kickoff prompt then works only on that machine: a plan in no git repo gets its absolute path, and an unpushed one can't be fetched elsewhere. The hook and its suite implement it.
12. **Unreviewed worker commits at a stop, on a workstation.** This is mine, not something Gary said: it concerns task branches on a workstation, now the only case there. The kit pushes them in both modes, labeled `UNREVIEWED`, as v2's decision 4 settled for a runner: in the plan's repo the handoff commit sits on top of them and is pushed, and rule 9 checks every working directory of the last run. `plan-execution.md` says the opposite ("only the parent pushes, after its review"; "The parent reviews, then pushes"), so §4 adds the exception to both passages. Or: on a workstation, gated, a stop that leaves commits unreviewed commits the handoff without pushing, and rule 9 skips its push checks while the last run's record shows a group unreviewed (`review: null`), until that group's review passes.

**Settled**, in Gary's words where he gave them:
- **Decision 1, the cost guard:** "if it's under $50 don't worry about the cost guards going above 3x" and "If the original expectation was $78 that would be fine to continue until it was at most 3x that". The guard stops when projected spend passes 3× the expected total or $50, whichever is higher, in both modes (`guard 3x min $50`); `plan_state.py` and hook rule 8 implement it.
- **Automatic fix-ups:** "If unattended, it can also continue with automatic fix-ups." Unattended, a `check_wave.py` failure and a second or later CONCERNS get automatic fix-ups up to the cap (decision 3); gated mode stops at each.
- **The handoff:** "If unattended it should also commit the result to the branch in a handoff update or post handoff summary in the event the work is lost.", then "Actually, for each work, let's keep the handoff and also keep the handoff summaries whether it's attended or unattended". My reading, as stated to him: "each work" is each wave, "attended" is gated mode, and "post handoff summary" is the chat message, not a GitHub post. In both modes each wave's bookkeeping commit refreshes the handoff in `specs/handoffs/` and pushes, every message that ends a run, stops or asks carries a short summary, and nothing is posted outside the branch and the chat (§1.6).
- **The Kickoff prompt:** "Continue keeping the idea that a plan has a prompt to kick off the workflow in a new session if desired." He also asked how a plan made in one session reaches a new session once personal-plan-orchestrate is invoked. The answer is the branch: the kickoff commits and pushes the plan and its handoff before it halts or dispatches, and the prompt names the repo, the plan's path, the branch and the confirmed mode. Pasting it confirms the mode in the new session, which asks again only when the environment differs, no mode was confirmed, or a workstation is on another branch (§1.5, rule 7).
- **Decision 6, task branches:** "What's the easy path? If it's to just use a task branch each time, I'm fine with that. Even on a workstation." Orchestrate runs only on a task branch, on every machine; the kickoff cuts one where needed, a runner without asking and a workstation on the mode answer (§1.5). Nothing that served shared branches remains.
- **Effort**, in the rules he gave: "[fast]: low. Haiku 4.5 has no effort setting, so this applies only when you run fast work on Sonnet." "[exec]: medium. Step up to high on large codebases or when a task stalls, and never go past high." "[deep]: high. Drop to medium for interactive planning where you're in the loop to catch mistakes." "[xdeep]: xhigh. Save max for task types where you've measured a gain, and ultracode for audit-shaped steps." Then: "In this case exec is sonnet, deep and xdeep is opus". The kit runs `[exec]` on Sonnet medium; `[deep]`, the parent and the reviews below `[xdeep]` on Opus high; `[xdeep]` and its review on Opus xhigh; the Fable step-up at xhigh; and `[fast]` on Haiku, which takes no effort. `execHigh`, `max` and ultracode follow §2.2.
- **Also settled, without his words here:** API list rates for every cost; one kickoff question that proposes unattended on a runner and gated on a workstation; a stop on a runner pushes unreviewed commits, labeled `UNREVIEWED` (v2's decision 4, per core.md "Save before you wait"); the committed `(output est.)` rule stands (§2.6).

**Mine, not yet put to Gary:** one automatic fix-up for a first CONCERNS, then ask, in gated mode (my reading of "prompt the user if it needs to know"); cutting a task branch off Gary's own branch; unattended no longer implying `here`; "paste the Kickoff prompt" as the resume step; the paste rule (the whole prompt, `On branch` lines aside), the `by Kickoff prompt` record and the signal tokens; gate 0 for a prompt that disagrees with the record or names no repo and plan; path (b)'s branch rewrite and path (c)'s folded switch; the hook's branch-name check, its `origin/HEAD` requirement, and its answer checks (right after the question, no question back or negation); the re-ask after a declined cut; the `-xdeep` agent names, and `plan-worker-exec` so the Agent path's `[exec]` runs at medium; `execHigh` and the unattended `[exec]` retry at Sonnet high before `[deep]`; `max` per launch on `[xdeep]` or Fable, with a human gate-7 approval unattended; no ultracode in orchestrate, so an audit that needs it runs on the passive driver; decisions 10, 11 and 12.

**Review fixes (this revision).** An adversarial review of v6 raised 14 findings; all 14 are fixed, finding 6 and 7 by a narrower route than suggested:
1. A pasted prompt never answers anything: the hook denies it, or any words that hold its mode line, as a gate approval, a `needs_info` answer, a waiver or a mode answer (rules 2, 7, 10), and the prompt's last sentence re-posts a `BLOCKED` question.
2. The hook fails closed on its own failures with exit 2: the import and the input parse sit inside the guard, a 20 s deadline denies, and the hooks file adds `|| exit 2`. §2.1 names the limits that remain.
3. A mode answer counts only right after the kickoff question (outside `CI=true`), without a question back or a negation, and never as the prompt or its mode line. The suite's invoking-message case now denies.
4. Path (b): a cloud session keeps its assigned branch and rewrites the `On branch` line, and rule 7 sets those lines aside so the paste still counts. Criterion 8 checks which branch a cloud session gets.
5. Path (c): another machine reads the plan from `origin/<branch>`, folds the switch into the kickoff question, and switches to a tracking branch. Criterion 9 has the case.
6. The prompt names the repo (`In <owner>/<repo>, read ...`) and lists each repo's branch when names differ. `plan_state.py` can't see the groups' repos, so gate 0 requires the plan line in every prompt, not only cross-repo ones.
7. Rule 9 denies a repo with a remote whose `origin/HEAD` is unknown, and the preflight runs `git remote set-head origin --auto`; the hook makes no network call (`ls-remote`).
8. Rule 9 treats only "not a git repository" as no repo, with git's messages in the C locale; any other git error denies.
9. The proposal's signal is tokens (`harness=<h> runner=<r>`). An unattended record that doesn't parse is gate 0, and the hook compares tokens on both paths.
10. A harness change is a different environment: the session re-asks, recomputes the Cost table and refreshes the counting header.
11. A declined branch cut dispatches nothing and re-asks once, naming the two ways on.
12. Re-entry asks first only for a run in flight whose record is missing or unfinished.
13. The README recipe uses a fresh `mktemp -d` folder and prints the path it tests.
14. Restated history is gone: Appendix A's copy of the workflow, the per-version Summary blocks and "Settled since" lists, the v1-v2 review table, the v2 correction and the per-version §4 deltas. The container's evidence paths are one note (Appendix B).

**Still UNVERIFIED** (all in phase 0 unless noted):
- **Interactive and runner sessions:** the interactive (Mac) `promptSource` values the hook relies on; whether a fresh session start gets the synced skills and the `hooks/hooks.json` SessionStart (§1.4), and whether the synced manifest's `agents`, `workflows` and `hooks` fields are registered (criterion 7); whether the hook process sees `CLAUDE_CODE_REMOTE` (rule 9's workstation fallback, rule 7's check of a pasted prompt); whether the transcript keeps a pasted prompt's text as pasted, whitespace aside (criterion 8); why each SessionStart part ran twice at that resume.
- **Branches and blocking:** which branch a cloud session started on a task branch gets (criterion 8); that a plugin `PreToolUse` hook's exit 2 blocks a Workflow call, as the hooks docs say (criterion 9).
- **Runner signals:** `CLAUDE_CODE_REMOTE` under Remote Control; any Codex cloud signal; `CURSOR_CODE_REMOTE` on Cursor cloud agents; what `CLAUDE_CODE_SESSION_ATTENDED` means.
- **Effort:** that `xhigh` reaches the API from an `agent()` call and from agent frontmatter (criterion 10); which effort an Agent-path subagent takes on a model other than the session's.
- **Permissions and plumbing:** auto mode on worker commits; plugin agents' `tools` enforcement; claude.ai and Cowork sync.
- **Fable:** its usage-credit consent prompt during a run.
- **Fix-ups and the handoff:** a worker rewriting its own commit messages without an interactive rebase; rule 9's git calls inside the hook, on a runner's checkout and on the Mac (criterion 9).
- **Phase 4:** Grok's resolution of `inherit`/`opus` in Claude agent files.
- **Harnesses I didn't run live:** Cursor IDE and Muse behaviours.

---

## Appendix A: `plan-segment.js`

The workflow is `kit/claude-workflows/plan-segment.js` (298 lines). It passes 52 stub tests; no live run has used it, since the live runs used v2's script with Haiku stand-ins. What it does beyond v2's:
- **Mode.** `unattended` comes from `args.state.mode`, which the hook has checked. Approvals are required for `state.stops`, `state.checkpoints` go into the result, and `gate-0` and `gate-mode` accept no approval.
- **Retries.** Unattended, each broken group gets one retry in the same run (§1.5): an `[exec]` group that failed at medium retries at high, a step-up logs gate 6 as a checkpoint, and retry labels end `(retry)`.
- **Effort.** `execHigh` runs `[exec]` on Sonnet high and `max` an `[xdeep]` or Fable worker at max (§2.2). Each is gate 0 on another tier, and unattended `max` needs a human gate-7 approval for the wave.
- **Canary.** Unattended returns `stop: "done"` with a gate-5 checkpoint instead of stopping.
- **Questions.** Workers may return `needs_info` with a `question`; it is gate 1 in every mode, and a group's `answer` must equal `approval`.
- **Fix-ups.** The title is `Wave <label> of T [tier] <group>`, the prompts quote the failed check or the concern verbatim with the streak's earlier failures, and a failed message check may reword the commits it names, never the parent's plan and handoff commits.
- **Drafts.** Unattended `xdeepDrafts` needs a human gate-7 approval for the wave.
- **Outward actions.** Every prompt forbids opening or merging a PR, pushing a tag, deleting a remote branch and deploying; a worker whose step needs one returns `needs_info`.
- **Task branch only.** Every group names its `branch`; a group that carries v5's `git` field is gate 0. The result's groups carry `branch`, for the hook's push check. State version 3's v6 fields (`prompt_mode`, `prompt_plan`, the signal tokens) aren't read.

The `args` the parent builds (from live run 2, spec text abridged, with the plan path and each group's `branch` as the kit expects them; `state` is `plan_state.py`'s version 3):

```json
{ "plugin": "personal",
  "plan": { "name": "plan-smoke", "path": "/…/repo-a/specs/handoffs/plan-smoke.md" },
  "state": { "...": "plan_state.py output, verbatim (the hook compares it with disk)" },
  "canaryDone": true,
  "approved": [{ "gate": "gate-5", "wave": 1 }], "approval": "yes, continue wave 1",
  "trailers": ["Assisted-by: Claude Code"],
  "groups": [{ "workdir": "/…/repo-b", "steps": ["m1.s2"], "spec": "#### m1.s2 - [exec] Add beta.txt in repo-b\n…",
               "acceptance": "…", "standards": [], "branch": "feature/smoke", "from": "a08d5d2" }] }
```

A group that answers a question adds `"answer": { "question": "Which registry token?", "answer": "<Gary's words, as in approval>" }`.

## Appendix B: evidence

The evidence named in the text (`v3/…` through `v6/…`, `v3-review/…`, the live runs' repos, run records and transcripts, the saved harness docs) lives in this cloud container's scratchpad, not on the branch, and goes with the container. The claims that rest on it are the ones marked observed or UNVERIFIED; phase 0 re-checks each before anything ships. What the branch keeps is the kit, its tests and the README recipe that reproduces the offline results.
