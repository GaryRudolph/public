# Proposal: running personal-plan-orchestrate natively in each harness (v5)

*As of 2026-10-06. Versions: Claude Code 2.1.291 (2.1.292 since this session's 21:07 UTC start), Codex 0.160.1, Cursor CLI 2026.10.01, Gemini CLI 0.62.0, Grok Build 1.0.46, Muse Code 1.4.3. v5, like v4, builds on commit 9e22488: `plan-execution.md`'s source precedence, token line format (`<model>` without a date suffix), the Token log's counting header, Expected cost and Cost table, as committed. v4 added Gary's two decisions on unattended mode to v3. v5 adds his decision to keep the handoff in both modes, and corrects v4 on plugin sync in cloud sessions. Nothing under `/workspace/public` was edited. Evidence is under `…/scratchpad/orch/v2/` through `…/scratchpad/orch/v5/` (Appendix C).*

## Summary

**Claude Code: move the skill onto a saved plugin workflow now.** Issue #43869 ("Subagent model routing is broken — all mechanisms resolve to parent model (Opus)", https://github.com/anthropics/claude-code/issues/43869) is still open as of today. On 2.1.291, though, v1's wire captures show the per-call `model` and `effort`, and plugin-agent frontmatter, reaching the API.

**What v5 adds.** Gary's words: "Actually, for each work, let's keep the handoff and also keep the handoff summaries whether it's attended or unattended". My reading, as stated to him (I read "each work" as each wave, and "attended" as gated mode):
- **The per-wave handoff and its chat summary, in both modes.** On a task branch, gated or unattended, the plan and the session handoff live in tracked `specs/handoffs/` on every machine. After each wave's review the parent's bookkeeping commit refreshes the handoff and pushes. Every message that ends a run, stops at a gate, or asks a question carries a short handoff summary. Both files are removed or promoted before the PR merges (core.md "Runner scratch rides the branch"). Nothing is posted outside the branch and the chat (§1.6).
- **Hook rule 9 in both modes.** On a task branch a launch needs the plan and a refreshed handoff committed and pushed, and every task-branch working directory of the last run pushed (§2.1). Only the hook and its suite change: `plan_state.py`, `check_wave.py` and `plan-segment.js` already treat the plan and handoff commit alike in both modes.
- **On a shared branch the plan and handoff stay in `.scratch/`.** While decision 6 keeps shared-branch support, a gated run whose working directories are all on a shared branch keeps the plan and handoff in gitignored `.scratch/`, still refreshes the handoff after every wave, and lets the chat summary carry the state. A gate there may still offer committing the wave as its own choice, as `plan-execution.md` allows. The hook exempts that launch, and a gated workstation launch with nowhere to push (below). Five refinements are mine and not yet put to Gary (decision 11): on a shared branch the kickoff question names the task branch it would cut and either answer covers the cut, with `gated stay` to stay (§1.5); on Gary's own branch the mode reply also answers core.md's one-time commit ask, and `gated stay` commits nothing; the hook denies a shared-branch group on a runner, which always works on a task branch; a plan already in `specs/handoffs/` of a repo with a remote is always checked; and on a workstation, gated, a plan in no git repo keeps both files in `.scratch/`, and a repo with no remote commits them without pushing (§1.6).
- **Unreviewed worker commits are pushed at a stop on a workstation too**, in both modes, labeled `UNREVIEWED`: the handoff commit on top of them is pushed, and rule 9 checks every working directory. `plan-execution.md` says only the parent pushes, after its review, so this is open as decision 12 (§2.4).
- **The passive driver is unchanged.** Its plan file and STOP prompts already serve as the handoff (§1.7).
- **A correction: a cloud session can get the plugin.** At this session's 21:07 UTC start, the first under Claude Code 2.1.292 and with `CLAUDE_CODE_SYNC_PLUGINS=1` and `CLAUDE_CODE_SYNC_SKILLS=1` set (v4 found no `CLAUDE_CODE_SYNC_PLUGINS`), account sync installed the published `personal` plugin (version 0007, which is main at c2b7c97, not this branch), and its SessionStart hook loaded the standards. The session's start and its seven earlier resumes, on 2.1.289 and 2.1.291, got nothing, though the same 0007 was already published. Two things are still UNVERIFIED: whether a fresh session start gets the skills and the `hooks/hooks.json` SessionStart, and whether the synced manifest's `agents`, `workflows` and `hooks` fields are registered (the published manifest uses none of them). Both stay in phase 0 criterion 7, and the cloud half of phase 0 needs the kit published, since sync serves main (§1.4, §4).

**What v4 adds.** Gary's words: "If unattended, it can also continue with automatic fix-ups. If unattended it should also commit the result to the branch in a handoff update or post handoff summary in the event the work is lost." My reading, as stated to him:
- **Automatic fix-ups, unattended only.** A `check_wave.py` failure and a second or later CONCERNS on a group no longer stop. Each gets an automatic fix-up wave for that group, numbered `N-fix`, `N-fix2`, `N-fix3`, with the failing check output or the review concern quoted into its worker prompt. Two per group (decision 3); the third failure on the group stops and asks. The cost guard still applies. `needs_info`, plan errors, unplanned `[xdeep]` or Fable work, permission prompts and outward actions still stop or wait. Gated mode still stops at each (§1.5).
- **A committed handoff after every wave, unattended only** (v5 extends it to gated mode, above). The plan and the session handoff live in tracked `specs/handoffs/` on every machine, not only on runners. Each wave's bookkeeping commit refreshes the handoff and pushes; a stop or completion makes it final. The message that ends the run or asks carries a short handoff summary, so the chat has it even if the branch is lost. Nothing is posted outside the branch and the chat (§1.6). The hook checks the commit and the push (§2.1, rule 9).
- **The wave-number grammar gains `N-fix2` and up**, in the standard and in every regex and label that reads it (§4).

One refinement is mine and not yet put to Gary: a scope breach (edits in a directory with no group, rewritten history, a commit on a shared branch, or a stray uncommitted path on a workstation) still stops, since no group's fix-up can repair it. It is open as decision 10 (§1.5).

**What v3 adds, from Gary's decisions since v2:**
- **A mode at kickoff.** One kickoff question shows the waves, the Cost table's expected total, the gates the plan crosses, and a proposed mode: `unattended` on a runner, `gated` on a workstation. Gary's answer sets the mode. The Kickoff block records his exact words, the date and the session. No answer, no dispatch (§1.5).
- **Unattended runs without stops, except for information, quality and unplanned spend.** Gates 2, 3, 4 and 5, and gate 7 on a planned `[xdeep]` wave, become logged checkpoints. A broken group gets one automatic retry, never at or into `[xdeep]` or Fable. Outward actions wait in every mode (§1.5).
- **A cost guard instead of a budget.** Before each wave, `plan_state.py` adds the next wave's expected dollars to the Token log's actual spend, and stops when that passes 3× the Cost table's expected total or $50, whichever is higher (Gary's rule).
- **Questions only when information is needed, saved first.** Workers return `needs_info` instead of guessing (§1.6).
- **The hook checks the mode.** An unattended record counts only when a human turn in this session is its words, verbatim, and names `unattended` (§2.1).
- **The token tally follows the standard.** v2's "the last copy is exact" held only for the Haiku stand-ins. Opus workflow agents almost never log a `stop_reason` line, so `token_tally.py` now estimates their output and labels the line `(output est.)`. It drops the model's date suffix, as the line format says. v2's decision 7 is gone (§2.6).
- **The passive driver on a runner** stops at every STOP, as today: a model swap needs a human (§1.7).

**What v2 changed since the review.** I accepted the main findings and changed five things:
- **Gates come from the plan file, not from the parent.** A new script, `plan_state.py`, reads the plan:
  - the wave markers, tags and `(done)` markers;
  - the Status line;
  - the Review log.

  It prints the next dispatch unit and the gates in front of it, and every harness's parent runs it. On Claude Code:
  - The workflow spawns nothing unless each of those gates is approved for that wave.
  - A plugin `PreToolUse` hook re-runs `plan_state.py` from disk.
  - The same hook checks that each approval came from a human turn, word for word.
- **One Workflow run per wave.** The docs say: "For sign-off between stages, run each stage as its own workflow" (https://code.claude.com/docs/en/workflows#behavior-and-limits).
- **Mechanical checks are code.** After every run, `check_wave.py` checks:
  - commit subjects and trailers;
  - that every step has a commit;
  - stray edits, and directories that should be untouched.

  On v1's smoke commits it flags the `Co-Authored-By` trailers that v1's LLM reviewer passed.
- **One Opus reviewer per working directory**, as the standards' review beat requires. The verify panel is gone, and `[xdeep]` drafts are opt-in.
- **No `resumeFromRunId`.** Recovery starts a new run from the plan and git, and workers skip steps that are already committed.

**Tested:**
- **Offline, v5 kit:** 137 tests pass: 48 for the workflow against a stub harness, 40 for `plan_state.py`, 16 for `check_wave.py`, 27 for the hook, 6 for `token_tally.py`. v4 counted 132; its `plan_state.py` suite has 40 cases, not 39. v5 changes only the hook suite. The gated cases now need the committed handoff. Each launches with a task-branch group, as a real launch does: an uncommitted plan edit, a handoff older than the plan, an unpushed bookkeeping commit, a missing handoff, a plan outside `specs/handoffs/`, and an unpushed working directory of the last run each deny a gated launch, and a launch with no groups fails closed. A gated launch whose groups are all on a shared branch passes with its plan in `.scratch/`, but not with one task-branch group, not unattended, and not with a tracked plan left uncommitted. A runner denies any shared-branch group. On a workstation, gated, a plan in no git repo passes from `.scratch/`; in a clone with no remote the plan and handoff must be committed but not pushed, and the last run's working directory there isn't checked; a runner and an unattended launch are denied in both. The final v5 review's mutant, which skips rule 9 for a gated task-branch launch with its plan in `specs/handoffs/`, passed v5's earlier 26 cases and fails 3 now (`v5-final-mut/`). v4 added 38: a check failure becomes a fix-up, a second CONCERNS becomes `N-fix2`, the third failure stops, gated mode still stops at each, the cap comes from the mode line and a raise needs approval, fix-up rows and the guard, a fix-up marker, the handoff committed and pushed before each launch, and the outward-action lines in every prompt. The final v4 review added the rest: a fix-up range that spans the parent's plan and handoff commit, a step commit that touches the plan, a leftover path checked again against the fixed wave's snapshot, the message-rewrite and combined-concern prompts, unpushed commits in another working directory, waivers, and labels outside the grammar. With `plan-execution.md` from HEAD (9e22488) in the plugin copy, the consistency check and every suite pass (`v5/check-head/`). `claude plugin validate` accepts the plugin copy.
  - The final review's fixes are specified below but not yet in the kit or its tests: the hook's turn reading (compaction summaries, the interrupt marker, messages typed mid-turn), rule 7's confirmation and take-back, marker numbering, the guard on split waves, and the model's date suffix. Phase 1 adds each with a stub test. The outward-action lines are now in the kit.
  - v4's suites, run unchanged against the v5 kit, fail 3 hook cases, all intended: a gated launch now needs the committed handoff, an unpushed working directory of the last run now stops a gated launch too, and an unattended plan in no git repo gets its own deny reason. The v5 hook suite fails its 6 new or changed cases on the v4 hook (`v5/v4-suites-against-v5-kit.txt`).
  - v3's suites, run unchanged against the v4 kit, fail only where their fixtures lack v4 state: version-2 state is gate 0 in the workflow, the mode line now carries `fixups`, and an unattended launch needs a committed handoff. All three are intended (`v4/v3-suites-against-v4-kit.txt`).
  - No live run used v3, v4 or v5. Their changes are covered by the stub tests only.
- **Live, v2 kit (unchanged):** 4 `claude -p` runs, with Haiku standing in for every tier, $0.86 in total.
  - Without an allow rule, the launch is refused. With `Workflow(personal:plan-segment)`, it runs.
  - The hook denied all 6 dishonest launches: an edited state, an approval that isn't word for word, `canaryDone` with no canary, a launch by `scriptPath`, approvals reused from a completion-notification turn, and a relaunch past a gate nobody answered.
  - The canary ran 1 of 2 repos and stopped at gate 5. The approved continuation ran the other repo. At wave 2 the script returned gates 4 and 2 and spawned no agents.
  - Both worker commits had the right shape (subject, blank line, `Assisted-by: Claude Code`) and passed `check_wave.py`. The routing check flagged the Haiku stand-ins as misrouted, which is correct.
- **The v3 tally on real transcripts:** identical to v2 on the Haiku smoke runs, where every call has a `stop_reason` line. On four finished Opus workflow runs from this session it reports 29-70% more dollars than v2's tally, all of it from the output estimate (for example $56.16 against $77.07 for an 11-agent run).

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

1. **`plan_state.py <plan>`** prints JSON (version 3): the next unit (`kind: wave|fixup`, `wave`, `label`, `fix`, `tier`, `milestone`, open `steps`, `start`), plus `gates`, `stops`, `checkpoints`, `mode`, `cost`, `concerns`, `waivers` and `errors`. It derives each gate like this:

   | Gate | Derived from |
   |---|---|
   | mode | No Kickoff `mode:` line with a confirmed answer (§1.5) |
   | 0 | Tagging errors: a ≤ violation, a step before any marker, a marker number used twice, duplicate IDs, `(done)` out of order, a `--- WAVE` line or a Review log line outside the grammar. Also: unattended mode with no Cost table Total. Order comes from file position, since a re-plan's waves take the next unused numbers |
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
   - **Fix-ups come from the Review log.** The k-th CONCERNS line in a row for a group makes the next unit a fix-up of that group, labeled `N-fix` for the first and `N-fix<k>` after (`N-fix2`, `N-fix3`), the numbering v4 adds to the standard (§4). Its review is logged as `review wave-N-fix2 (<group-id>) …` and counts toward wave N's group, so a PASS ends the streak, and so does a WAIVED line (§1.5). A failed check is logged as a CONCERNS line too, so it starts or extends the same streak. A second CONCERNS in a row is gate 1; §1.5 says when it stops. When several groups of one wave have streaks, the longest goes first.
   - **A fix-up marker** (`--- WAVE 2-fix [exec] ---`, which the passive driver may write) doesn't count toward the wave total or the numbering check. Steps under it form a unit with its label.
   - **Cost** comes from the plan too: the Cost table's Total and rows (expected) and the Token log's dollars (actual).

2. **One dispatch unit per dispatch turn.** The parent updates the plan, then re-runs `plan_state.py` before every dispatch.

3. **`check_wave.py`** runs twice around each unit.
   - **`snapshot`, before the launch.** It records each directory's HEAD, its dirty paths and a tree object of the working tree. It also flags a `.scratch/` that isn't gitignored, and reports the repo's `attribution` setting.
   - **`check`, after the run.** For each group it checks:
     - `from` is an ancestor of HEAD;
     - every commit starts `<step-id> <subject>`, followed by a blank line;
     - no `Co-authored-by` or `Signed-off-by` line appears anywhere;
     - the required trailers sit in the last paragraph;
     - every step has a commit, and the run left no new dirty paths;
     - directories that had no group are unchanged;
     - nothing was committed on a shared branch.

     The parent's bookkeeping commits can sit inside a group's range: a fix-up's `from` is the wave's start, and a relaunch's range can span a save-before-you-wait commit. So `check` takes the plan path (`--plan`, or the run record's `args.plan.path`). A commit that touches only the plan and its session handoff, under a subject with no step ID, is listed as `bookkeeping` and skipped; any other commit that touches either file fails, since workers never edit the plan. For a fix-up, `--baseline` takes the snapshot from before the wave it fixes, so a path that wave left behind is checked again rather than hidden by the fresh snapshot.

     It prints each group's `to`, so the Review log range comes from git, not from a reviewer. Any failure is gate 1. Gated, it stops; unattended, most failures get an automatic fix-up instead (§1.5).

4. **Trailers are spelled out.** The parent passes the exact trailer lines from its own attribution: `Assisted-by: Claude Code`, plus `Claude-Session:` when the harness adds one. The worker is told to end each commit with exactly those lines.

5. **Review.** Each working directory gets one read-only reviewer at the author's tier: Opus high, or Opus max after an `[xdeep]` wave. This applies on every adapter that can pin a model per subagent.
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

A cloud session gets the plugin only through account sync (runbook m2, m5). v3 and v4 said this session had none of it, and until 21:07 UTC that held. Its start (2.1.289) and seven resumes on 2.1.289 and 2.1.291 listed no `personal:*` skill, though version 0007 had been published since 2026-10-02, and v4 found no `CLAUDE_CODE_SYNC_PLUGINS`. The 21:07 start was the first under 2.1.292, and `CLAUDE_CODE_SYNC_PLUGINS=1` and `CLAUDE_CODE_SYNC_SKILLS=1` are set now; which of the two changes made the difference isn't known. At that start sync installed the published plugin under `~/.claude/plugins/synced/<org>_<account>/personal` (the bucket folder dates from the session's first start, `personal/` from 21:07:05): its skills, `hooks/`, `scripts/`, the Cursor rule, and the Codex, Cursor and Gemini manifests. Its SessionStart hook loaded the standards, canary included, and the 9 `personal:*` skills are listed. It is the published version, not this branch: version 0007, updated 2026-10-02T00:29:34Z, which is main's c2b7c97. Every file matches main except that sync puts each SKILL.md description on one line; this branch's `personal-repo-baseline` skill is missing (`v5/evidence/synced-plugin.txt`). Sync copied every file under the plugin root, the non-default `hooks/cursor-hooks.json` included, so the kit's files would very likely arrive too. Two things are UNVERIFIED (phase 0 criterion 7): whether a fresh session start, not only this resume, gets the skills and the `hooks/hooks.json` SessionStart; and whether the synced manifest's `agents`, `workflows` and `hooks` fields are registered, which the published manifest doesn't use. Until they are, step 2 goes passive in a cloud session (no `personal:plan-worker` subagent type, though the skills are listed), and §1.7 stops at every STOP. Each SessionStart part ran twice at that start; a doubled `PreToolUse` deny is harmless.

### 1.5 Mode: gated or unattended

**The kickoff question.** Once per plan run, after the Kickoff and Cost table are written and before the first dispatch, the parent:
1. **Reads the runner signals** (table below). The proposal is its judgment; Gary's answer decides.
2. **Saves first:** writes `mode: pending | proposed <mode> (<signal>) | guard 3x min $50 | fixups 2` into the Kickoff block and `BLOCKED at gate mode` into the Status line, then saves per §1.6, in both modes. On a task branch that moves the plan to `specs/handoffs/`, writes the handoff beside it, commits both and pushes. Where a commit needs Gary's yes first (a shared branch, or his own branch on a workstation), both stay in `.scratch/` until the answer, and the question asks.
3. **Asks one question and ends the turn.** For example, on a runner:

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

   With no runner signal the question says what it checked ("No runner signal (CLAUDE_CODE_REMOTE unset, no assigned branch). Proposed mode: gated."), so Gary can correct it. On a workstation it also asks where to orchestrate ("add `here` to orchestrate in this chat; default: new chat; unattended means here"), which replaces the separate destination question. An `unattended` answer implies `here`, since an unattended record counts only in the session that confirmed it. A runner orchestrates in its own chat: a new chat there is a new session Gary would have to start. On a workstation it names the task branch the plan and handoff are on. On a shared branch, while decision 6 keeps shared-branch support, it names the task branch it would cut ("Either way I first cut feature/auth-otter and move the plan there; reply gated stay to stay on main, with the plan and handoff uncommitted"), so either answer covers the cut (core.md "Cut a task branch": ask with the name before anything is committed). `gated stay` keeps a gated run on the shared branch (§1.6); unattended always runs on a task branch. A launch with any task-branch group needs the plan tracked, so `stay` is offered only when every working directory is on a shared branch or on Gary's own branch. The `stay` choice is mine (decision 11). On Gary's own branch on a workstation, core.md's one-time ask before committing or pushing there rides in the question, and the mode reply answers it ("Either way I commit and push the plan, its handoff and each wave on feature/auth-otter; reply gated stay to commit nothing there"). `gated` or `unattended` is the yes, and covers every per-wave commit and push. `gated stay` is the no: as on a shared branch, the plan and handoff stay in `.scratch/`, and each group launches with `git: shared`, the workflow's commit-nothing mode, since core.md allows no commit there without the yes. Unattended needs the yes. This is mine too (decision 11).
4. **Records the answer** in the Kickoff block and clears the `BLOCKED`:

       mode: unattended | proposed unattended (CLAUDE_CODE_REMOTE=true) | guard 3x min $50 | fixups 2 | confirmed 2026-10-06 session 6333c263-f7c1-58ee-bb8f-25209c81c588: unattended

   The words are Gary's whole message, whitespace collapsed, and they come last on the line, so they may hold any character. Unattended needs a reply that names `unattended`, as the question asks and core.md's "say so explicitly" requires (decision 9). A yes to a gated proposal records gated, which relaxes nothing. Anything else (silence, a bare yes to unattended, a question back, "hmm") dispatches nothing: the parent re-asks. `plan_state.py` reports `gate-mode` until a confirmed line exists, and the workflow never accepts an approval for it. It reads `guard` and `fixups` only from before `confirmed`, so Gary's words never set them.
5. **Saves the answer, in both modes.** On a task branch it refreshes the handoff with the mode, commits the plan and handoff in one commit and pushes, before the first dispatch (§1.6). After a cut it first moves both from `.scratch/` to `specs/handoffs/` on the new branch. After `gated stay` both stay in `.scratch/`, uncommitted.

Rules around it:
- **An invoking message that names the mode** sets the proposed mode, and the kickoff question still runs, so Gary sees the waves, the total and the gates before he opts in. Only where nobody can reply (a CI job, `CI=true`) do the invoking words count as the answer: the parent records them, prints the kickoff summary, and starts.
- **Switching** takes an explicit message naming the mode. The parent records the new words, date and session. A switch to unattended also answers a pending gate that unattended mode would pass as a checkpoint, with those words as the approval; it doesn't answer a gate that stops in both modes. A switch moves no file: on a task branch the plan and handoff are in `specs/handoffs/` in both modes, and rule 9 holds in both. A switch to unattended on a shared branch first asks to cut the task branch, with its name, and takes effect after the yes; after `gated stay` on Gary's own branch it first asks to commit there. A run already in flight finishes as launched. A later short message (10 words or fewer) that names `gated` and not `unattended` ends unattended, and the hook enforces it; a longer one that only mentions the word doesn't.
- **A new session.** A gated record carries over, since it relaxes nothing, unless the runner signal now differs from the record's `proposed (...)` signal: then the kickoff question runs again with the new proposal. An unattended record counts only in the session that confirmed it, so a new session asks the kickoff question again, quoting the spend so far. A resumed cloud session keeps its session id and transcript (this one: one id and one transcript across 7 worker exits and a container reboot).
- **The Cost table follows the proposed mode.** Its orchestrator row counts the gate waits that mode will have: gated counts the canary and every gate 2, 3, 4 or 7 the plan crosses, as the standard says; unattended counts one, the kickoff answer. On a runner the row has no new-chat start-up. In both modes each wave's share also covers the handoff refresh, commit and push: about $0.1 a wave (my estimate). When the answer picks the other mode, the parent recomputes that row before any wave runs, and says so. Fix-ups get rows with no expected value, as the standard's rule for waves added later says, labeled with their number (`2-fix2 [exec] repo-b m1 s4`).

**Runner signals.** The parent reads them with one shell call and the harness's own instructions:

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
| 7, `[xdeep]` | Stops | Checkpoint on a wave the Cost table planned, whose cost the kickoff question quoted (decision 2); stops for unplanned `[xdeep]` work: a fix-up, a re-plan row, a step-up. Draft fan-out still needs Gary's gate-7 approval |
| guard | Stops | Stops |
| Each wave's end, on a task branch | Commit the plan and the refreshed handoff and push before the next launch (rule 9) | Same |
| A `BLOCKED at gate N` Status line | Stops | Stops |
| Opening or merging a PR, pushing a tag, deleting a remote branch, a deploy | Waits | Waits |
| A permission prompt | Waits | Waits. On a runner, commit and push before a call likely to trip one (core.md) |

**Checkpoints are logged, not asked.** For each unit the parent:
- ends the wave's Review log note with them: `review wave-3 (repo-a m2 s1) 8d0e4b7..c41f0a2: PASS - cache keys match the spec; passed unattended: gate 4, gate 2 - 2026-10-06`, which keeps the standard's grammar; an automatic fix-up's review names its number: `review wave-2-fix2 (repo-b m1 s4) 846932b..9abcdef: PASS - newline added; passed unattended: gate 1 (fix-up 2 of 2) - 2026-10-06`;
- keeps the latest on the Status line: `| passed unattended: gate 4, gate 2 before wave 3`;
- lists every checkpoint, automatic retry and automatic fix-up, with its reason, under **Deviations from plan** in the Completion summary and in the handoff, so Gary reviews them in one place.

**Automatic retries (unattended only).** The workflow retries each broken group once, inside the same run:
- a worker with no result, or a review that died: the same tier (a dead review reruns only the review);
- `failed` or `low_quality`: one tier up, into `[exec]` or `[deep]` only, logged as a gate-6 checkpoint;
- never on an `[xdeep]` or Fable wave, never on a launch that is already a step-up Gary approved, never for `needs_info`.

The retry keeps its wave's number and token row, as the standard says of step-up retries. Its prompt names the earlier attempt and says to check its commits. A dead worker's uncommitted edits make the retry return `failed` (the existing "uncommitted changes, do not touch" rule), which stops: fail closed. A second failure is gate 1. The retry runs in the same run so that neither the hook nor `plan_state.py` needs a run history. A fix-up run gets the same retry.

**Automatic fix-ups (unattended only).** A fix-up is its own unit and its own run, scheduled from the Review log (§1.2):
- **What gets one.** A `check_wave.py` failure, which the parent logs as its group's CONCERNS line with a note that starts `check_wave.py:` and quotes the failing output (§2.3 step 5), and a second or later CONCERNS on a group. A first review CONCERNS gets its `N-fix` in both modes, as today.
- **The cap.** Two automatic fix-ups per group in a row (`N-fix`, `N-fix2`; decision 3), recorded on the mode line as `fixups 2` and quoted in the kickoff question. The third failure in a row is gate 1 and stops. A PASS with a clean check ends the streak. A raised cap needs Gary's approval (hook rule 8).
- **A waiver.** At a gate 1 that a streak raises, in either mode, Gary may waive the concern instead of approving the next fix-up (the standard's "re-tag, add a fix-up wave, or waive"). The parent logs `review wave-N (<group-id>) <from>..<to>: WAIVED - <Gary's answer, whitespace collapsed> - <date>`, which ends the streak as a PASS does, and the plan moves on. The hook checks that the words are a human message of this session (rule 10). v4 needs the line because a failed check now starts a streak, so an approval of gate 1 can only launch the next fix-up.
- **What the worker gets.** The failing check output or the concern, verbatim, and the streak's earlier failures. A review concern is fixed with new commits. A failed message check (a first line, a `Co-authored-by` line, a missing trailer) is fixed by rewriting the messages of the commits the check names by SHA, keeping their content and leaving every other commit as it is, the parent's plan and handoff commits included: `git commit --amend` only when HEAD is one of them, otherwise a non-interactive rebase that rewords just those. The parent then pushes with `--force-with-lease --force-if-includes` (core.md: rewrite only your own commits). A failed-check note that also carries the review's CONCERNS gets both instructions. A failed-check fix-up's reviewer is told to check the quoted failure itself too, not to leave it to the script.
- **What stops at once instead** (my reading; decision 10). No group's fix-up can repair a scope breach: edits in a directory with no group, a `from` that is no longer an ancestor of HEAD, a commit on a shared branch, or, on a workstation, a new uncommitted path, which may be Gary's own edit (core.md "Stage only what you changed"). These stop at gate 1 in both modes.
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

**The handoff, after every wave, in both modes.** On a task branch, gated or unattended, the plan and the session handoff live in tracked `specs/handoffs/` (`plan-{topic}-{word}.md`, `handoff-{topic}-{word}.md`, one `{topic}-{word}`) on every machine, not only on runners, in the repo that holds the plan. They are removed or promoted before the PR merges, per core.md "Runner scratch rides the branch". This is Gary's v5 decision (§5); v4 had it in unattended mode only.
- **After each wave's review**, the parent's bookkeeping commit updates the plan and refreshes the handoff, then pushes every working directory. The handoff holds: what's done, with each group's commit range; the Review log verdicts; the fix-ups and their reasons; the Token log total against the Cost table's expected total; the next unit; how to resume (the branch, the plan path, and that a new session asks the kickoff question again); and any pending question, verbatim.
- **At a stop and at completion** the handoff is final: the same fields, plus the question or the PR ask. At completion it carries the Completion summary, and the PR question names the cleanup commit (remove the two files, or promote what's durable to `specs/`).
- **Every message that ends a run, stops at a gate, or asks a question** carries a short handoff summary of about six lines, in both modes: the branch and handoff path, the waves and fix-ups done with their ranges, spend against expected, and the next unit or the question. A reader of the chat has it even if the branch is lost.
- **Nowhere else.** The summary goes in the chat and the handoff on the branch. Posting it to a PR, an issue or any other service is an outward action, which waits for Gary in every mode.
- **While a run works** on a task branch the parent writes nothing to the tree, in both modes: the plan is tracked, so an edit would show up as a new dirty path to `check_wave.py`.
- **The hook checks it** on Claude Code (rule 9): a launch on a task branch, in either mode, needs the plan and a handoff refreshed since the plan's last change, committed and pushed.
- **Where nothing can be pushed**, on a workstation, gated only. The plan needs a git repo and the push a remote. A plan in no git repo, such as a cross-repo plan in a plain folder of sibling repos (a layout `personal-makefile` supports), stays with its handoff in that folder's `.scratch/`, refreshed after every wave, as after `gated stay`. A plan in a repo with no remote is committed in `specs/handoffs/` as usual and not pushed, and so is a working directory with no remote. Rule 9 recognizes both. Unattended needs the plan in a repo with a remote, and the hook denies it otherwise, so there the kickoff question proposes gated and says why. This is mine (decision 11).

**On a shared branch** the plan and handoff never commit. The case exists only while decision 6 keeps shared-branch support, for a gated run whose working directories are all on a shared branch (`gated stay`, §1.5). The plan and handoff stay in gitignored `.scratch/`, the parent still refreshes the handoff after every wave, and the chat summary carries the state. A gate question may still offer committing the wave as its own choice, as `plan-execution.md`'s STOP gate semantics allows (`Commit wave 2 to main and start wave 3? yes / commit only / start only / neither`); that commit stages only the wave's paths, and the plan and handoff stay in `.scratch/` either way. Rule 9 exempts the launch. A runner never runs one: core.md keeps a runner on a task branch, and the hook denies a shared-branch group there.

**Save, then ask** (core.md "Save before you wait", in this order):
1. Update the plan: `(done)` markers, the Review log, the Token log, and the Status line's `BLOCKED at gate N`.
2. Write or refresh the handoff beside the plan (`specs/handoffs/` on a task branch, `.scratch/` on a shared branch), in both modes: the question verbatim, the branch, the mode, and how to resume.
3. On a task branch, commit the plan and the handoff. On a runner, commit everything in the tree, a partial step under an honest subject; a workstation stages only its own paths. On a shared branch, commit nothing; a gate's offered commit comes after the answer.
4. On a task branch, push every working directory that has a remote, in both modes. Worker commits not yet reviewed are pushed too, labeled `UNREVIEWED` in the Status line, the handoff and the question; on a workstation that is decision 12.
5. Ask one plain-text question and end the turn. The message carries the short handoff summary, in both modes.

A usage limit is the one stop where this can't run (§2.4). On a task branch, in both modes, the branch still holds the handoff as of the last reviewed wave.

**An answer reaches the worker verbatim.** The next launch approves gate 1 with Gary's words as `approval`, and the group carries `answer: {question, answer}`. The script refuses an `answer` that differs from `approval`, and the hook has already checked `approval` against the human turn.

### 1.7 The passive driver on a runner

`personal-plan-model-tiers` has no unattended mode. Each STOP is a model swap, and only a human can make one: `/model` in the session, or a new session started from the STOP prompt. On a runner it saves (plan, handoff, commit, push) and stops at each STOP marker as today, and Gary starts the next wave on the model the marker names. When the runner is Claude Code with the plugin loaded, its kickoff points to orchestrate instead, which sets the model per subagent. Running every wave on the session's model would remove the stops, but spends `[deep]` rates on `[fast]` work, so it isn't proposed.

v5 leaves it unchanged. Its plan file and STOP prompts already serve as the handoff: each wave's chat updates the plan's `(done)` markers, Status line and Token log before it stops, and the STOP prompt names the plan, the branch and the next model, so the next chat resumes from them. On a runner the plan already rides the branch in `specs/handoffs/`, and the handoff is written at each stop. Gary can extend it: a handoff file refreshed at every STOP on a workstation too, and the short summary in each STOP message.

---

## 2. Claude Code adapter

### 2.1 The pieces, and why

| Piece | Job |
|---|---|
| `personal:plan-segment` workflow (Appendix A, 292 lines) | Runs one unit. It validates `args` against `plan_state.py`'s unit and refuses any stopping gate not approved for that wave. When `canaryDone` is false it runs only the first group. It then runs `pipeline(groups, worker, reviewer)`, so each repo's review starts as soon as its worker finishes. In unattended mode it retries each broken group once (§1.5) and returns the checkpoints it passed. A fix-up unit quotes its failed check or concern, verbatim, into the worker and review prompts. It returns result objects only. |
| 4 plugin agents | `plan-worker` (`model: inherit`; the call sets model and effort), `plan-worker-max` (opus, max), `plan-reviewer` (opus, high; tools Read, Grep, Glob, Bash), `plan-reviewer-max` (opus, max; same tools) |
| `orchestrate_gate.py`, a `PreToolUse` hook on `Workflow` | Lives in a Claude-only `hooks/claude-hooks.json`. Plugin manifest hook files are "Loaded together with `hooks/hooks.json`" (https://code.claude.com/docs/en/plugins/manifest-reference#fields). It denies a launch unless every rule below holds. It fails closed on any error, and it never allows a launch outright, so the session's permission rules still apply. |
| `plan_state.py`, `check_wave.py`, `token_tally.py` | §1.2, §1.5 and §2.6 |

The hook's rules for a plan-segment launch:
1. `args.state` equals `plan_state.py` run from disk.
2. Approvals appear only in a turn a human started or a human message joined mid-turn, and `approval` matches that human's message word for word.
3. `canaryDone` is true only after an earlier canary launch in this session.
4. No earlier run in this session is still unfinished.
5. Any gate the last run stopped at is approved. `gate-0` and `gate-mode` are excepted: they clear only from the plan.
6. The launch is by name only, not by `script` or `scriptPath`.
7. An unattended mode is confirmed in this session (below).
8. A guard raised since this session's last launch carries an approval of `gate-guard`, and a raised fix-up cap one of `gate-1`, so rule 2 checks Gary's words.
9. On a task branch, in both modes, the plan and its handoff sit in `specs/handoffs/`, have no uncommitted changes, and the handoff's last commit is the plan's or a later one and is on the branch's upstream. Every task-branch working directory of this session's last finished run has its HEAD on its upstream too. So every wave's results and handoff are committed and pushed before the next launch. Only a gated launch whose every group is on a shared branch, with its plan outside `specs/handoffs/`, skips the plan check. When `CLAUDE_CODE_REMOTE=true`, the hook denies any shared-branch group. Gated on a workstation, where nothing can be pushed, a plan in no git repo skips the plan check, a plan in a repo with no remote skips only its push check, and a working directory with no remote isn't checked; unattended needs the plan in a repo with a remote.
10. A WAIVED Review log line added since this session's last launch is a human message of this session, word for word.

**How the hook tells a human turn from a notification.** It reads the transcript's own fields rather than a `UserPromptSubmit` recorder. `UserPromptSubmit` also fires on "A background subagent reporting back" (https://code.claude.com/docs/en/hooks#userpromptsubmit) and carries no origin. The live runs showed that the transcript marks notifications with `promptSource: "system"` and `turnOrigin: "task_notification"`. In this cloud session typed prompts carry `promptSource: "sdk"`, `turnOrigin: "human"` and `origin.kind: "human"`, which the hook accepts. Three more record shapes need handling:
- **Compaction summaries** (`isCompactSummary`, `isVisibleInTranscriptOnly`) carry `turnOrigin: "human"` and recap the conversation, "gated" included. The hook skips them. The transcript is append-only, so it still reads every turn from before a compaction.
- **The `[Request interrupted by user]` marker** has no origin fields, so it reads as human. The hook skips it.
- **A message typed while the parent is working** is recorded only as a `queued_command` attachment with `origin.kind: "human"`, then absorbed into the running turn: 3 of about 35 human messages in this session. The hook reads it as human text of the turn that absorbed it, so rule 7's take-back sees it, and an approval may match it.

**How a recorded unattended confirmation satisfies the hook.** The same way a gate answer does, from the transcript, word for word. Rule 7 holds when:
- the mode line's `session` is this session (the hook input's `session_id`);
- a human turn in this transcript is the recorded words, after whitespace is collapsed, and they name `unattended` and not `gated`. Unlike a gate answer it may be an earlier turn, since later launches start from notification turns. Any such turn counts, so a later identical message to another question doesn't hide it;
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
| Dispatch before a kickoff answer is recorded | `plan_state.py` (`gate-mode`) and the script, which accepts no approval for it |
| A guard or fix-up cap raised without asking, within a session | The hook (rule 8) |
| A waiver Gary never gave, within a session | The hook (rule 10) |
| Fix-ups past the cap | `plan_state.py` (gate 1 stops past `fixups`) |
| A wave's results or handoff left uncommitted or unpushed on a task branch, in either mode, in any working directory of the last run | The hook (rule 9) |
| A shared-branch launch on a runner, whose `.scratch/` dies with the container | The hook (rule 9) |
| Unplanned premium spend unattended | The script (no automatic retry at or into `[xdeep]` or Fable; drafts need a gate-7 approval) and `plan_state.py` (gate 7 on unplanned `[xdeep]` work) |
| Spend running past the estimate | `plan_state.py`'s guard, between runs |
| Two runs at once in one session | The hook |
| Commit, trailer or scope slips | `check_wave.py`, which makes it gate 1 |
| An `availableModels` substitution | `token_tally.py --check-routing`, which makes it gate 1 |

These still rest on trust:
- **Whether Gary's words mean yes.** The hook checks where the answer came from, not what it means.
- **Whether the kickoff question was honest.** The hook checks that Gary named unattended, not that the cost and gates the question quoted were right.
- **A gated kickoff record.** The hook doesn't check its words, so a non-answer recorded as gated dispatches the canary, which still stops at gate 5.
- **A guard or fix-up cap raised, or a waiver written, between sessions.** Rules 8 and 10 compare with this session's previous launch only. Rule 9 sees only this session's runs, so a new session's first launch doesn't check the other working directories; its re-entry reconciles from git (§2.3 step 7).
- **Token log lines.** The guard counts only the lines the parent appends after each run.
- **Review log lines.** The parent logs a failed check as CONCERNS and holds back the scope breaches that stop; nothing checks that it did, nor that a PASS came from a reviewer. A breach logged by mistake reaches a worker told to stay in its own directory and to leave alone any path it did not make. It can't repair most breaches, so it returns `failed`, and after the in-run retry that stops.
- **The handoff's content.** Rule 9 checks that it was refreshed, committed and pushed, not what it says. The chat summary isn't checked at all.
- **Each group's `git` field.** The parent declares it (`gated stay` on Gary's own branch launches as `shared` too), and a gated launch whose every group says `shared` skips rule 9's plan check. A false `shared` tells the workers not to commit, and `check_wave.py` fails any commit there, so nothing lands unpushed; but on a workstation the plan and handoff then stay uncommitted in `.scratch/`. On a runner the hook denies it.
- **Outward actions inside a run.** The prompts forbid them and ask for `needs_info`; nothing checks the commands a worker runs.
- **A failure recorded in an earlier session.** The `BLOCKED` line in the plan is the only record, and save-before-you-wait already requires it.
- **The Agent path.** It has no hook, so its gates and its unattended mode rest on the parent, as Cursor's do today.

### 2.2 Tiers to agent, model and effort

| Tier | Worker | Reviewer |
|---|---|---|
| `[xdeep]` | `plan-worker-max`, opus/max. `xdeepDrafts: 2–4` drafts plus a judge, opt-in at gate 7 | `plan-reviewer-max`, opus/max |
| `[deep]` | `plan-worker`, opus/high | `plan-reviewer`, opus/high |
| `[exec]` | `plan-worker`, sonnet/high | `plan-reviewer` |
| `[fast]` | `plan-worker`, haiku | `plan-reviewer` |
| Fable step-up (gates 6 and 7) | `plan-worker-max`, fable/max | `plan-reviewer-max` |

The parent stays on `/model opus` and `/effort high`.

**Why four agents rather than two or three:** the Agent path can't pass effort. So the `[xdeep]` worker and reviewer need definitions that say `effort: max`, and reviewers need a definition that carries the tool allowlist.

**Haiku still thinks:** it inherits the session's thinking setting (v1's wire capture showed a 31,999-token budget). The picker note needs updating.

### 2.3 The parent's loop

1. **Preflight**, once per chat and per new working directory:
   - Check the branch and the git email in each working directory.
   - Run `check_wave.py snapshot`; it must pass.
   - Note each repo's attribution setting.
   - Tag and group the plan.
   - Write the Kickoff and the Cost table. The Claude Code rows include each wave's review subagent at 0.6× a medium step, and the orchestrator row's gate waits follow the proposed mode (§1.5).
   - Write the Token log's counting header: the Claude Code usage row and the rates of the plan's models. It serves a pasted or passive chat; workflow workers don't need it (§2.6).
   - Read the runner signals, save, ask the kickoff question, and record the answer (§1.5). In both modes, on a task branch, move the plan to `specs/handoffs/`, write the handoff, commit both and push.
   - Seed the todos.
2. **For each unit:**
   - Update the plan and the handoff. On a task branch, commit both in one commit and push, in both modes (hook rule 9). On a shared branch, commit nothing.
   - Run `plan_state.py`. If it reports errors, that is gate 0. If any of `stops` is unanswered, write `BLOCKED`, save (§1.6), ask, and end the turn. `checkpoints` ask nothing.
   - Otherwise build the `args` and take a fresh `check_wave.py snapshot`. Keep the snapshot from before each wave until its groups' streaks end: a fix-up's check uses it as `--baseline`.
   - Call the Workflow tool with `name: "personal:plan-segment"`. SKILL.md must say "call the Workflow tool" in so many words, because that sentence is the opt-in.
3. **Check the launch result:**
   - `error` set means the script failed its syntax check: gate 0.
   - `remote_launched` means the run went to a cloud session and its commits would land elsewhere: gate 0, then use the Agent path.
   - Show any `warning` to Gary.
4. **While the run works** (this depends on the branch, not on the mode):
   - On a shared branch the plan is in gitignored `.scratch/`: write `run <runId> in flight` on the Status line and end the turn with one line.
   - On a task branch the plan is tracked in `specs/handoffs/`: write nothing to the tree, since `check_wave.py` would flag the edit as a new dirty path.
5. **On completion:**
   - Run `check_wave.py check --snapshot <this launch's snapshot> --run <session>/workflows/<runId>.json`; for a fix-up, add `--baseline <the snapshot from before the wave it fixes>`. The run record supplies the plan path, so the parent's bookkeeping commits in the range are skipped.
   - Run `token_tally.py --run <runId> --check-routing --parent-window <previous runId>:<runId> --parent-row "orchestrator-wave-<N> <group-id>"`, where wave N is the unit the previous run carried. For the first run the window is `start:<runId>` and the row `orchestrator-kickoff <plan name>`. Windows don't overlap, so the guard never counts the parent twice.
   - For each group: mark `(done)`, write the Review log line (`from..to` from `check_wave.py`, checkpoints in the note), append Token log lines, update the Status line and the todos. A fix-up's lines use its label: `N-fix`, `N-fix2`. A group whose check failed or whose review returned CONCERNS is still marked `(done)`: its fix-up comes from the Review log, not from open steps.
   - **A failed check** on a group is logged as that group's Review log line, verdict CONCERNS, with a note that starts `check_wave.py:`, quotes the failing output on one line, and ends with the review's verdict (`; review PASS`, or `; review CONCERNS: <its note>`): `review wave-2 (repo-b m1 s4) 846932b..518e99f: CONCERNS - check_wave.py: repo-b: m1.s4 has no commit; review PASS - 2026-10-06`. This keeps the standard's grammar, and `plan_state.py` schedules the fix-up from it. A scope breach (§1.5) gets no such line: it is `BLOCKED at gate 1`.
   - Refresh the handoff (§1.6), in both modes. On a task branch, commit the plan and the handoff in one bookkeeping commit whose subject doesn't start with a step ID, and push each working directory (hook rule 9 checks both). After a fix-up that rewrote commit messages, the push is `--force-with-lease --force-if-includes`.
6. **Branch on the result:**
   - **A failed check, or `stop: "gate"`:**
     - Unattended, a failed check that isn't a scope breach doesn't stop: go back to step 2, where `plan_state.py` makes the fix-up the next unit, a checkpoint until the cap is spent.
     - Otherwise save (§1.6), writing `BLOCKED` with the gates and any `questions`.
     - Ask one question that names each repo's commit range and the next unit, then end the turn. The message carries the short handoff summary (§1.6).
     - After an explicit answer in the next human turn, approve exactly those gates as `[{gate, wave}]`, with `approval` set to the answer word for word. A `needs_info` group also gets `answer`.
   - **`done`:** go back to step 2 with `approved: []`, without asking. In unattended mode the next unit's checkpoints, an automatic fix-up's gate 1 included, don't ask either.
   - **`end`:** do the final completion per the standard: replace the `(output est.)` lines of sessions that have ended, add the Cost table's actual columns from the Token log, append the Completion summary with the checkpoints, retries and fix-ups, print the table. Write the final handoff. Then save and ask about the PR, with the short handoff summary.
7. **Re-entry.** A fresh chat that finds `in flight` treats it like `BLOCKED`. With a tracked plan there is no such line; the handoff's next unit and the run record serve instead. If the run record (`~/.claude/projects/<slug>/<session>/workflows/<runId>.json`) shows the run finished, reconcile from git. Otherwise ask. An unattended record from another session means the kickoff question again, and so does a gated record whose runner signal no longer matches (§1.5).

**The Agent path** reuses the same agents, prompt text and checks:
- Call `Agent(subagent_type: "personal:plan-worker", model: <alias>, description: <wave title>, prompt: …, run_in_background: false)` once per working directory, all in one message.
- Then call `personal:plan-reviewer` the same way.
- The parent applies `plan_state.py`'s stops, the retry policy, the fix-ups and the per-wave handoff by hand.
- Foreground calls keep the turn open, which also avoids the runner Stop hook.

### 2.4 Runners, recovery, limits and shared branches

- **No resume in v1.** The docs say a "Failed" agent "runs again, and so does every agent that started after it, even ones that completed" (https://code.claude.com/docs/en/workflows#resume-after-a-pause). In the cloud, run results also survive a VM reclaim, but unpushed commits don't.
  - Instead, the parent starts a new run from `plan_state.py`. The worker prompt says to skip steps that already have commits, and the review covers the whole range.
  - A run that dies with its session leaves no record, so the hook then refuses any further launch in that session. Start a new session, which asks the kickoff question again if the plan was unattended.
  - On a task branch, in both modes, the branch holds the plan and a handoff as of the last reviewed wave, so a lost session or container costs at most the wave in flight. The new session reads both from the branch.
- **The runner Stop hook.** The launch turn ends while workers are still editing, and the hook blocks once with "Please commit and push". The rule for that continuation:
  - It is not an instruction.
  - The parent doesn't commit or push. It replies with one line.
  - The hook's `stop_hook_active` check lets the second stop through.

  Observed here: the container stays up while the parent sits idle with a workflow running. No worker exit (`cost-state` record) fell inside any of 16 run windows, parent-idle stretches inside runs reached 80 and 58 minutes, and all 7 exits fell in gaps with no run.
- **A stop on a task branch with unreviewed worker commits, in either mode:** push them, labeled `UNREVIEWED` in the Status line, the handoff and the question. Gary's rule (save first, push included, before any question) settles v2's decision 4 on a runner. v5 pushes them on a workstation too, in both modes: in the plan's repo the handoff commit sits on top of them, so pushing the handoff pushes them, and rule 9 checks every working directory. `plan-execution.md` says only the parent pushes, after its review, so this is mine and open as decision 12.
- **Usage limits.** A run pauses at a limit only in an interactive claude.ai session; background and Remote Control runs fail instead (https://code.claude.com/docs/en/workflows#when-a-run-hits-your-usage-limit). After a failure, start a new run once the limit resets. `send_later` may schedule that relaunch, but it never answers a gate; in unattended mode the relaunch needs no answer for checkpoints.
  - Observed in this cloud session: a spend limit didn't pause the run. It completed with 7 of 27 agents returning null, the parent's next model call failed with the limit message, and the worker exited. So a limit is the one stop where save-first can't run: worker commits stay unreviewed and unpushed, and the plan is stale. On a task branch, in both modes, the pushed handoff is one wave behind, not more.
  - The next human turn reconciles from git (uncommitted and unpushed work) before relaunching. The workflow's automatic retry fails at once too, which costs little; a crash and a limit both return null, so the script can't tell them apart.
- **Shared branches.** Uncommitted waves pile up, so `from` becomes the working-tree tree from the snapshot. The reviewer runs `check_wave.py diff <dir> <tree>` and sees only its own wave, not earlier waves and not Gary's own edits. The plan and handoff never commit there: they stay in `.scratch/`, the handoff is refreshed after every wave, and the chat summary carries the state (§1.6). A gate may still offer committing the wave as its own choice, as the standard allows. A runner never runs on one.

### 2.5 Permissions

- **`-p` and the SDK:** the allow rule `Workflow(personal:plan-segment)` works. Verified live: without it, the launch was denied with "Review dynamic workflow before running". Interactive sessions get "don't ask again" for a plugin workflow.
- **Workers** use the session's rules. Allow `git add`, `git commit` and each repo's test commands. Reviewers need read-only Bash, plus `python3 …/check_wave.py diff` on shared branches. Pass other repos with `--add-dir`, as the live runs did.
- **Auto mode:** "the prompt your script passes to `agent()` doesn't count as a request from you" (https://code.claude.com/docs/en/workflows). Worker commits passing in auto mode is an exit criterion for phase 0.
- **Unattended answers no permission prompt.** A prompt mid-run still waits for Gary. Unattended runs work best with the allow rules above in place. Both modes push after every wave on a task branch, so allow the parent's `git push` too, `--force-with-lease --force-if-includes` included for a fix-up that rewrote messages. Leave `gh pr`, tag and deploy commands out of them, so a worker that tries one meets a prompt instead of running it.

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

**Correction to v2.** v2 said the last copy of each `message.id` carries the final output count, and asked Gary to drop `(output est.)`. That held only for the Haiku stand-ins: every one of their 22 calls has a `stop_reason` line, and their totals equal Claude Code's `modelUsage` exactly (run 1: input 92, cache read 157,740, cache write 36,200, output 4,254; run 2: input 92, cache read 175,739, cache write 37,583, output 5,777). Across this session's Opus 5.5 workflow agents, 6,092 of 6,117 calls had no line with `stop_reason`, and the last copy still carried the 1-24 placeholder (6,424 of 6,458 at my recount, which grows while this session runs; 6,370 of those end on a placeholder of 24 or less; `v3/evidence/stopreason-opus.txt`). So the committed rule stands, and the v3 tally follows it. On finished Opus runs that adds 29-70% to v2's dollars (`v3/evidence/tally-v2-vs-v3-opus.txt`).

**Parent lines and review cost:**
- Parent lines are exact: main-session lines always carry `stop_reason`. With `--parent-window`, each covers one stretch between launches, labeled `orchestrator-kickoff` or `orchestrator-wave-N`. The final completion turn isn't flushed yet, a small tail the standard says to ignore.
- Subagent lines in a live session stay `(output est.)` at completion. Their session's `cost-state` record also covers the parent and every other wave, so the standard keeps the lines rather than merging them.
- Live review cost was $0.06 for two reviews against $0.11 of work. In v1, one review cost $0.23 against $0.06 of work.

---

## 3. The other harnesses

These are v1's verified findings, with the changes from v2 through v5 added. Every native adapter runs the kickoff question and reads `plan_state.py`'s `stops`. Each also commits and pushes the handoff after every wave on a task branch, in both modes, and unattended runs the automatic fix-ups; only Claude Code's hook checks that commit.

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
  - an Opus-high review subagent per working directory in place of the parent's inline review;
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
| `personal-plan-orchestrate/SKILL.md` | Core and detection go here; per-harness steps move to `adapters/`. Drop "Cursor-only", the #43869 gate and "Out of scope: Claude Code". Say "call the Workflow tool". Add the kickoff question and runner signals (§1.5), the gate table by mode, retries, the guard, and questions with save-first (§1.6). The kickoff question replaces the separate destination question. Contract item 7 (token reporting) applies to Cursor `Task` subagents, not to workflow workers. New for v4: automatic fix-ups and their cap, the failed-check Review log line, the WAIVED line, the scope breaches that stop, the snapshot kept as a fix-up's `--baseline`, and the per-wave handoff with its chat summary (§1.5, §1.6, §2.3); `{wave-n}` in the artifact path takes `N-fix2`. New for v5: the per-wave handoff and its chat summary in both modes on a task branch, with every message that stops or asks carrying the summary; a shared branch keeps both in `.scratch/`, and a gate there may offer the wave's commit; on a shared branch the kickoff question offers the cut, and `gated stay`; on Gary's own branch the mode reply answers the commit ask; where nothing can be pushed, gated only (§1.5, §1.6) | L | 1 |
| `…/adapters/claude-code.md`, `cursor.md`, `codex.md` | §2.3-2.6; today's Task text plus the §3 Cursor fixes; §3 Codex. Each names its runner signal | M each | 1; 1 and 3; 2 |
| `…/claude-agents/` (4 files), `…/claude-workflows/plan-segment.js` | Appendix A | S each; M | 1 |
| `…/scripts/plan_state.py`, `check_wave.py`, `orchestrate_gate.py`, `token_tally.py` | §1.2, §1.5, §2.1, §2.6. v4: `plan_state.py` numbers fix-ups, reads `fixups`, fix-up markers and WAIVED lines, rejects labels outside the grammar, and prints version 3; the hook adds rules 9 and 10 and the cap to rule 8; `token_tally.py` reads `N-fix2` labels; `check_wave.py` skips the parent's plan and handoff commits (`--plan`), fails a worker commit that touches either, and takes `--baseline` for a fix-up. v5: the hook applies rule 9 in both modes on a task branch, exempts a gated all-shared launch with its plan outside `specs/handoffs/`, denies a shared-branch group on a runner, and, gated on a workstation, checks no push where there is no remote and no commit where the plan is in no git repo; the other scripts are unchanged | M | 1 |
| `…/tests/` (5 suites, `orchestrate_check.py`, `test-orchestrate.sh`) | Adds `test_token_tally.py`, which reads the price table from `plan-execution.md`. The node suite skips when node isn't installed. The hook suite builds clones with bare origins for rule 9; v5 runs rule 9's cases in both modes, each gated deny with a task-branch group, and adds a shared-branch, a runner and a nowhere-to-push case | M | 1 |
| `hooks/claude-hooks.json`, `.claude-plugin/plugin.json` | The `PreToolUse` hook; manifest `agents`, `workflows` and `hooks` | S | 1 |
| `agents/Makefile` | Add `test-orchestrate` to `test` | S | 1 |
| `standards/plan-execution.md` | Orchestrate's review becomes a subagent per working directory; the fix-up rule; one unit per dispatch; gates from `plan_state.py`; non-answers; Claude Code `[xdeep]` in orchestrate is Opus max without ultracode, drafts opt-in; Haiku thinks; Cursor `fast=false`. New for v3: STOP gate semantics name the kickoff answer as the explicit opt-in, and define unattended checkpoints, automatic retries, the cost guard and questions with save-first; the active Kickoff variant gains the `mode:` line; the orchestrator row's gate waits follow the mode, with no new-chat start-up on a runner. Line 14 drops "Cursor". The Kickoff ask-user rule folds into the kickoff question on a workstation and is skipped on a runner. Token accounting stays as committed at 9e22488, except that on the Claude Code workflow path the parent writes every token line with `token_tally.py`, so the Kickoff rule "the orchestrate parent quotes it into each dispatch prompt" and "Who updates progress" exempt that path. New for v4: (a) the wave-number grammar: "Fix-up waves" numbers the first fix-up of wave N `N-fix` and the k-th in a row `N-fix<k>` (`N-fix2`, `N-fix3`), wherever a wave number appears (marker, wave title `{n}`, Cost table row, token line `<row>`, counting header, Review log line), and the marker regex becomes `^--- WAVE \d+(-fix([2-9]|[1-9]\d+)?)? \[(xdeep|deep|exec|fast)\] ---$`, so `N-fix1` and `N-fix02` are not labels; (b) the Review log: orchestrate logs a failed check as a CONCERNS line whose note starts `check_wave.py:`, and a waiver as `WAIVED - <Gary's words>`, a third verdict that ends a streak as a PASS does; (c) STOP gate semantics: unattended automatic fix-ups, the `fixups` cap on the mode line, and the scope breaches that stop; (d) the per-wave handoff: Progress tracking's "on a runner the plan lives in `specs/handoffs/`" and the plan-path exception cover an unattended orchestrate run on any machine, and Final completion writes the final handoff. New for v5: (d) covers an orchestrate run on a task branch in both modes, not only unattended. Progress tracking's "Two surfaces" adds that the orchestrate parent refreshes the handoff after every wave, commits it with the plan and pushes, and that on a shared branch both stay uncommitted in `.scratch/`. STOP gate semantics' "A runner also writes the handoff and pushes first" also covers an orchestrate run on a task branch on any machine, and every gate question carries the short handoff summary. The orchestrator row's per-wave share covers the handoff refresh in both modes. Where nothing can be pushed, on a workstation, the plan stays in `.scratch/` if no git repo holds it, and is committed without a push if its repo has no remote. If decision 12 stands: "Who updates progress" ("only the parent pushes, after its review") and "Delegating execution to subagents" ("The parent reviews, then pushes") gain the exception that at a stop an orchestrate run on a task branch pushes worker commits not yet reviewed, labeled `UNREVIEWED`, in both modes on any machine. STOP gate semantics' offered commit on a shared branch stays | M | 1 |
| `personal-standards/core.md`, `cursor/rules/personal-core.mdc` | Drop "(Cursor)" after `personal-plan-orchestrate`. New for v4, widened to both modes in v5: "Runner scratch rides the branch" gains one sentence: "A `personal-plan-orchestrate` run on a task branch does the same on any machine, gated or unattended: its plan and session handoff live in `specs/handoffs/`, and the handoff is refreshed, committed and pushed after every wave (plan-execution.md)." "Write handoff files" reads "(`specs/handoffs/` instead of `.scratch/` on a runner, and for a `personal-plan-orchestrate` run on a task branch)". "Save ephemeral agent plans" reads "on a runner, and for a `personal-plan-orchestrate` run on a task branch, the plan goes to `specs/handoffs/plan-{topic}-{word}.md`". Then `make -C agents cursor-core-rule` | S | 1 |
| `personal-plan-model-tiers/SKILL.md` | §1.7: no unattended mode; on a runner, save and stop at each STOP; point to orchestrate on Claude Code. v4: a later fix-up wave is `N-fix2` | S | 1 |
| `personal-handoff/SKILL.md` | v4, widened in v5: the "Which file" table and "On a runner" cover an orchestrate run on a task branch on any machine, in both modes; the per-wave fields and the chat summary stay in orchestrate's SKILL.md | S | 1 |
| `tag-tiers` SKILL.md, `plugins/README.md`, `specs/agent-distribution.md`, `agents/runbook.md` | Wording; the README rule "manifests are the only per-vendor files" now has exceptions; close "Still open: Claude Code"; fix Muse m7.s4; add the Codex roles step | S | 1-2 |
| `codex-agents/*.toml` (6), `agents/lib/extensions.sh` | Copy mode for Codex roles. The Agerpoint bok shares `extensions.sh`, so port it there too. | S, M | 2 |
| Cursor gate hooks (`agents/lib/hooks.sh`, also shared with the bok) | Optional | M | 3 |

`core.md` changes where it calls orchestrate Cursor-only and where it puts the plan and handoff in `specs/handoffs/` only on a runner. Its "say so explicitly" rule already covers the kickoff answer, since unattended needs a reply that names it, and its outward-action and save-first rules apply as written. The proposal counts posting the handoff summary to a PR or anywhere else as an outward action. Run `make -C agents validate test` after each phase.

**Rollout:**
- **Phase 0, spike (S).** Install from a branch through the local marketplace. Run it on the Mac interactively, and once on a cloud runner. Sync serves the published plugin, not a branch (§1.4), so the cloud run needs the kit published first, under another plugin name (`args.plugin` sets the namespace), so that the standards plugin every synced surface gets stays as it is. That copy checks criterion 6 first. Merging the kit to main, with orchestrate's SKILL.md still Cursor-only, waits until criterion 6 holds: if sync rejected the new manifest fields, cloud sessions, Cowork and Chat could lose the standards plugin itself. Exit criteria:
  1. The launch, notification and relaunch loop works interactively.
  2. On the runner, the Stop-hook rule holds.
  3. Worker commits pass in auto mode.
  4. Typed prompts on the Mac look human to the hook's transcript check.
  5. The reviewer's `tools` allowlist is enforced.
  6. claude.ai org sync and Cowork accept the new manifest fields.
  7. A fresh claude.ai/code session gets, through sync, the skills and the `hooks/hooks.json` SessionStart (so far seen only at this session's 21:07 resume, §1.4), and the synced manifest's `agents`, `workflows` and `hooks` fields are registered: the 4 agents, the `personal:plan-segment` workflow and the `claude-hooks.json` `PreToolUse` hook. The published plugin uses none of those fields. Check with the skill listing and the canary, Agent's subagent types, the Workflow tool's workflow list, and a denied dishonest launch.
  8. On the cloud runner, a typed `unattended` satisfies rule 7, and the plan runs from the kickoff answer to the PR question with no other stop, across a compaction and a later "yes" to another question. A short `gated` typed mid-run stops the next launch.
  9. In both modes, on the runner and on the Mac: every wave's bookkeeping commit carries the plan and the handoff and is pushed before the next launch, and every message that stops or asks carries the handoff summary. Unattended: a planted check failure (a step left without a commit) gets `N-fix` with no stop, and that fix-up passes `check_wave.py` in the repo that holds the plan; a group that fails three times in a row stops at gate 1. Gated on a shared branch on the Mac (`gated stay`): the plan and handoff stay in `.scratch/`, and a gate's offered commit stages only the wave. Gated on the Mac with a cross-repo plan in a plain folder of sibling repos: the plan and handoff stay in the folder's `.scratch/`, and the hook allows the launch.

  If criterion 1, 2 or 3 fails, ship the Agent path first. If 7 fails for the agents, cloud sessions run only the passive skill until sync registers them, since the Agent path needs them too. If only the workflow or the hook is missing, cloud sessions use the Agent path, whose gates rest on the parent.

  Already observed in this session, with inline-script workflows: relaunches from notification turns in auto mode, with no permission prompt; the container staying up while idle with a run going; a resumed session keeping its id and transcript; cloud prompt fields; the run record written only at the end; a spend limit failing a run; at the 21:07 resume, the first on 2.1.292 with both sync variables set, the synced plugin's skills and SessionStart hook (§1.4). A named plugin workflow behind the hook is untested in cloud.
- **Phase 1, Claude Code (L).** Dogfood one real plan of 3-5 waves on the workstation, gated, one on the workstation, unattended, and one on a runner, unattended, each with its plan and handoff in `specs/handoffs/`, then flip the gate. Compare each plan's actual columns with its expected ones.
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
6. **Shared branches:** supported through tree snapshots. Or require a task branch for orchestrate?
7. **Review cost:** one Opus reviewer per working directory per wave, about 0.6× a medium step (~$0.54 at Opus high), in place of the parent's inline review.
8. **Agerpoint bok:** port the kit? It's namespace-safe: `args.plugin`, plus a check that the manifest name matches the folder.
9. **A bare yes at kickoff.** v3 requires the reply to name `unattended`, as core.md's "say so explicitly" asks, so a "yes" re-asks. If a yes to the proposal should count, core.md "Wait for approval" must name the kickoff confirmation (and the Cursor rule be regenerated), and the hook checks that the question before it proposed unattended.
10. **Scope breaches, unattended.** This is my refinement of Gary's words, not something he said. Proposed: edits in a directory with no group, a `from` that is no longer an ancestor of HEAD, a commit on a shared branch, or a new uncommitted path on a workstation stop at gate 1 at once, since no group's fix-up can repair them and the last may be his own edit. Or should they get an automatic fix-up like other check failures? The worker is told to stay in its own directory and leave alone paths it didn't make, so it would mostly return `failed`, which stops after the in-run retry anyway, at the cost of a fix-up run.
11. **Shared branches, Gary's own branch, and nowhere to push, under the per-wave handoff.** These are my refinements of Gary's v5 words, not something he said. Proposed: (a) on a shared branch the kickoff question names the task branch it would cut, either answer covers the cut, and `gated stay` keeps a gated run there with nothing committed, offered only when every working directory is on a shared branch; (b) the hook denies a shared-branch group on a runner; (c) a plan in `specs/handoffs/` of a repo with a remote is always checked, even on a launch whose groups are all on a shared branch; (d) on Gary's own branch on a workstation the mode reply answers core.md's one-time commit ask (`gated` or `unattended` is the yes), and `gated stay` commits nothing, the groups launching as `git: shared`, the workflow's commit-nothing mode (or a no could cut a task branch instead); (e) where nothing can be pushed, on a workstation and gated only, a plan in no git repo (a plain folder of sibling repos) keeps the plan and handoff in `.scratch/`, and a repo with no remote commits them without pushing, while unattended needs a repo with a remote. The hook and its suite implement (b), (c) and (e). If decision 6 requires a task branch, (a) loses `gated stay` and (b) applies on every machine.
12. **Unreviewed worker commits at a stop, on a workstation.** This is mine, not something Gary said. v5 pushes them in both modes, labeled `UNREVIEWED`, as v2's decision 4 settled for a runner: in the plan's repo the handoff commit sits on top of them and is pushed, and rule 9 checks every working directory of the last run. `plan-execution.md` says the opposite ("only the parent pushes, after its review"; "The parent reviews, then pushes"), so §4 adds the exception to both passages. Or: on a workstation, gated, a stop that leaves commits unreviewed commits the handoff without pushing, and rule 9 skips its push checks while the last run's record shows a group unreviewed (`review: null`), until that group's review passes.

**Settled since v4:**
- The handoff, in both modes: Gary's words, "Actually, for each work, let's keep the handoff and also keep the handoff summaries whether it's attended or unattended". My reading, as stated to him: "each work" is each wave, and "attended" is gated mode. On a task branch, gated or unattended, the plan and the session handoff live in `specs/handoffs/` on every machine; each wave's bookkeeping commit refreshes the handoff and pushes; every message that ends a run, stops at a gate, or asks a question carries the short summary; nothing is posted outside the branch and the chat (§1.6). Hook rule 9 applies in both modes on a task branch (§2.1). On a shared branch, while decision 6 keeps it, the plan and handoff never commit: both stay in `.scratch/`, and the chat summary carries the state. The passive driver is unchanged (§1.7).

**Settled since v3:**
- Decision 1, the cost guard: Gary's words, "if it's under $50 don't worry about the cost guards going above 3x" and "If the original expectation was $78 that would be fine to continue until it was at most 3x that". The guard stops when projected spend passes 3× the expected total or $50, whichever is higher, in both modes (`guard 3x min $50`); `plan_state.py` and hook rule 8 implement it, with a floor test.
- v3's 3, what else stops unattended: Gary's words, "If unattended, it can also continue with automatic fix-ups." Unattended, a `check_wave.py` failure and a second or later CONCERNS get automatic fix-ups (§1.5); gated mode still stops at each. The cap is the new decision 3.
- The handoff: Gary's words, "If unattended it should also commit the result to the branch in a handoff update or post handoff summary in the event the work is lost." Unattended, the plan and the session handoff live in `specs/handoffs/` on every machine; each wave's bookkeeping commit refreshes the handoff and pushes; the message that ends the run or asks carries a short summary; nothing is posted outside the branch and the chat (§1.6). Reading "post handoff summary" as the chat message, not a GitHub post, is mine. v5 widens it to both modes (above).

**Settled since v2:**
- v2's 3, CONCERNS: one automatic fix-up, then ask. This is my reading of "prompt the user if it needs to know", not something Gary said; he can make every CONCERNS stop instead. v4 keeps it for gated mode; unattended now gets up to the cap.
- v2's 4, a stop on a runner: push unreviewed commits, labeled `UNREVIEWED`, per core.md "Save before you wait" (push before any question).
- v2's 7, `(output est.)`: the committed rule stands, and the tally follows it (the Opus data, §2.6).

**Still UNVERIFIED** (all in phase 0 unless noted):
- **Interactive and runner sessions:** the interactive (Mac) `promptSource` values the hook relies on; whether a fresh session start gets the synced skills and the `hooks/hooks.json` SessionStart (seen only at this session's 21:07 resume, §1.4), and whether the synced manifest's `agents`, `workflows` and `hooks` fields are registered (criterion 7); whether the hook process sees `CLAUDE_CODE_REMOTE` (rule 9's runner check and its workstation fallback); why each SessionStart part ran twice at that resume.
- **Runner signals:** `CLAUDE_CODE_REMOTE` under Remote Control; any Codex cloud signal; `CURSOR_CODE_REMOTE` on Cursor cloud agents; what `CLAUDE_CODE_SESSION_ATTENDED` means.
- **Permissions and plumbing:** auto mode on worker commits; plugin agents' `tools` enforcement; claude.ai and Cowork sync.
- **Fable:** its usage-credit consent prompt during a run.
- **Fix-ups and the handoff:** a worker rewriting its own commit messages without an interactive rebase; rule 9's git calls inside the hook, on a runner's checkout and on the Mac (criterion 9).
- **Phase 4:** Grok's resolution of `inherit`/`opus` in Claude agent files.
- **Harnesses I didn't run live:** Cursor IDE and Muse behaviours.

---

## Appendix A: `plan-segment.js` (the Claude Code workflow template)

Path: `…/orch/v5/kit/claude-workflows/plan-segment.js`, unchanged from v4. It passes 48 stub tests. No live run has used it: the live runs used v2's script with Haiku in the `ROUTE` models and the agent `model`/`effort` lines (`diff -r v2/check/personal v2/smoke/plug/personal`). `v3/kit.diff` holds every change from v2's kit, `v4/kit.diff` every change from v3's, and `v5/kit.diff` every change from v4's (the hook only). What changed in this script:
- **Mode.** `unattended` comes from `args.state.mode`, which the hook has checked. Approvals are required for `state.stops`; `state.checkpoints` go into the result. `gate-0` and `gate-mode` accept no approval.
- **Retries.** In unattended mode each broken group gets one retry in the same run (§1.5): the same tier for a crash or a missing review, one tier up into `[exec]` or `[deep]` for `failed`/`low_quality`, and never at `[xdeep]`/Fable, after a human-approved step-up, or for `needs_info`. A step-up logs gate 6 as a checkpoint. Retry labels end `(retry)`.
- **Canary.** Unattended returns `stop: "done"` with a gate-5 checkpoint instead of stopping.
- **Questions.** Workers may return `needs_info` with a `question`; it is gate 1 in every mode, and the result lists `questions`. A group's `answer` must equal `approval`.
- **Fix-ups (v4).** The title is `Wave <label> of T [tier] <group>`, so a fix-up reads `Wave 2-fix2 of 4 [exec] repo-b m1 s3`, and its artifact path carries the label. The worker prompt quotes the failed check or the concern verbatim, with the streak's earlier failures. A failed check may have the messages of the commits it names rewritten, never the parent's plan and handoff commits, with `--amend` only when HEAD is one of them; a concern gets only new commits; a check note that carries the review's CONCERNS gets both. The review prompt quotes the same failure, and for a failed check tells the reviewer to check it too. Whether a fix-up's gate 1 stops is `plan_state.py`'s call, through `stops` and `checkpoints`.
- **Drafts.** Unattended `xdeepDrafts` needs a human gate-7 approval for the wave.
- **Outward actions.** Every prompt forbids opening or merging a PR, pushing a tag, deleting a remote branch and deploying; a worker whose step needs one returns `needs_info` naming it. v4 puts these lines in the kit file, with a test.
- **State version 3.**

```js
export const meta = {
  name: 'plan-segment',
  description: 'Run one dispatch unit of a tagged plan for personal-plan-orchestrate: one wave, every working directory executed and then reviewed',
  whenToUse: 'Only when the personal-plan-orchestrate skill launches it with plan_state.py output and the contracts for that unit',
}

// One run = one dispatch unit (a wave, or the part of a wave inside one
// milestone). plan_state.py computes the unit, the gates in front of it, and
// which of them stop in the plan's recorded mode; the PreToolUse hook re-runs
// it from disk, checks approval text against the human's prompt, and checks an
// unattended mode against the human turn that confirmed it. This script
// refuses to spawn anything unless every stopping gate is approved for this
// wave, then runs and reviews each working directory and returns. In
// unattended mode the other gates are checkpoints: logged in the result, not
// asked, and a broken group gets one automatic retry below [xdeep]. A fix-up
// unit (N-fix, N-fix2, ...) quotes the failed check or the review concern from
// the Review log into its worker prompt; plan_state.py decides whether its
// gate 1 stops. It never decides to continue: the parent records the result,
// runs check_wave.py, commits the plan and handoff, and launches the next run.

// Tier routing. Must match plan-execution.md's Claude Code picker row and the
// -max agents' frontmatter (orchestrate_check.py checks both).
const ROUTE = {
  fast: { model: 'haiku' },
  exec: { model: 'sonnet', effort: 'high' },
  deep: { model: 'opus', effort: 'high' },
  xdeep: { model: 'opus', effort: 'max' },
  fable: { model: 'fable', effort: 'max' },
}
const CHAIN = ['fast', 'exec', 'deep', 'xdeep', 'fable']
const MAX = { xdeep: true, fable: true }
const ANGLES = [
  'the simplest design that fully satisfies the spec',
  'risk first: list the failure modes, then design to rule each one out',
  'adversarial: assume a hostile input or caller, then design so it cannot succeed',
  'reuse first: the closest existing pattern in the repo, the standards, or the dependencies',
]

const RESULT = { type: 'object', required: ['status', 'changed', 'decided', 'surprises', 'artifact', 'commits'], properties: {
  status: { type: 'string', enum: ['done', 'failed', 'low_quality', 'needs_info'] }, changed: { type: 'string' }, decided: { type: 'string' },
  surprises: { type: 'string' }, artifact: { type: 'string' }, commits: { type: 'array', items: { type: 'string' } },
  question: { type: 'string' } } }
const REVIEW = { type: 'object', required: ['verdict', 'note', 'findings'], properties: {
  verdict: { type: 'string', enum: ['PASS', 'CONCERNS'] }, note: { type: 'string' },
  findings: { type: 'array', items: { type: 'object', required: ['claim', 'evidence'], properties: { claim: { type: 'string' }, evidence: { type: 'string' } } } } } }
const DRAFT = { type: 'object', required: ['design', 'risks'], properties: { design: { type: 'string' }, risks: { type: 'string' } } }
const JUDGE = { type: 'object', required: ['pick', 'synthesis'], properties: { pick: { type: 'integer' }, synthesis: { type: 'string' } } }

const S = args && args.state
const U = S && S.next
const tier = (args && args.stepUp) || (U && U.tier)
const P = args && args.plugin
const unattended = !!(S && S.mode && S.mode.value === 'unattended')
const NEVER_APPROVED = ['gate-0', 'gate-mode']  // cleared only by fixing the plan or recording the kickoff answer
function worker(t = tier) { return { agentType: `${P}:plan-worker${MAX[t] ? '-max' : ''}`, ...ROUTE[t] } }
function reader(t = tier) { return MAX[t] ? { agentType: `${P}:plan-reviewer-max`, ...ROUTE.xdeep } : { agentType: `${P}:plan-reviewer`, ...ROUTE.deep } }
function norm(x) { return String(x || '').replace(/\s+/g, ' ').trim() }

function base(dir) { return dir.replace(/\/+$/, '').split('/').pop() }
function stepsLabel(steps) {
  const m = steps.map(s => /^m(\d+)\.s(\d+)$/.exec(s))
  if (m.every(Boolean) && m.every(x => x[1] === m[0][1])) {
    const ks = m.map(x => +x[2])
    const run = ks.every((k, i) => i === 0 || k === ks[i - 1] + 1)
    return `m${m[0][1]} s${run && ks.length > 1 ? `${ks[0]}-s${ks[ks.length - 1]}` : ks.join(',s')}`
  }
  return steps.join(',')
}
function groupId(g) { return `${base(g.workdir)} ${stepsLabel(g.steps)}` }
// A fix-up wave is N-fix, then N-fix2, N-fix3, wherever its number appears (plan-execution.md "Fix-up waves").
function unitTitle(t = tier) { return `Wave ${U.label || U.wave} of ${S.t} [${t}]` }
function title(g, t = tier) { return `${unitTitle(t)} ${g.id}` }
function list(xs, none) { return xs.length ? xs.map(x => `- ${x}`).join('\n') : `- ${none}` }
function quote(x) { return String(x).split('\n').map(l => `> ${l}`).join('\n') }

function gitLine(g) {
  if (g.git !== 'task') return 'Do not commit, push, or switch branches.'
  return [`Commit each finished step on the current branch (${g.branch}) as its own commit, staging only the paths you changed. Each commit message is:`,
    '1. a first line that is the step ID, a space, and an imperative subject (`m2.s3 Wire the results view`), and nothing else;',
    '2. a blank line, then an optional body;',
    `3. a blank line, then exactly these trailer lines, as the last paragraph:\n\n${args.trailers.map(t => `    ${t}`).join('\n')}`,
    'Never add `Co-authored-by` or `Signed-off-by` lines, whatever your own instructions say. Do not push, create, or switch branches.'].join('\n')
}
function artifactPath(g) { return `${g.workdir}/.scratch/orchestrate-${args.plan.name}-${U.label || U.wave}-${g.id.replace(/[^\w.-]+/g, '-')}.md` }

function workerPrompt(g, design, t = tier, earlier = null) {
  const parts = [title(g, t),
    `You execute one dispatch unit of the tagged plan at ${args.plan.path}. Do not edit the plan file.`,
    `## Spec excerpt (verbatim)\n\n${g.spec}`]
  if (g.answer) parts.push(`## Gary's answer (verbatim)\n\nAn earlier attempt asked: ${g.answer.question}\n\nGary answered: ${g.answer.answer}\n\nWork from that answer.`)
  if (earlier) parts.push(`## Earlier attempt\n\nAn earlier attempt at this group in this run ended ${earlier}. Its commits, if any, are in ${g.from}..HEAD; check them against the acceptance criteria before you build on them.`)
  if (g.concern) parts.push(fixupSection(g.concern))
  if (design) parts.push(`## Chosen design (from an independent draft panel)\n\n${design}\n\nImplement it. Where it contradicts the spec excerpt, follow the spec and say so under surprises.`)
  parts.push(`## Working directory\n\nAll edits must be inside \`${g.workdir}\`. Do not edit anything outside this directory.`,
    `## Acceptance criteria\n\n${g.acceptance}`,
    `## Scope\n\nExecute only: ${g.steps.join(', ')}. Stop at the end of this group; do not start the next group or any work not listed here.`)
  if (t === 'fast') parts.push('## Mechanical edits\n\nApply exactly what the plan specifies. Do not refactor, rename, or generalize.')
  parts.push(`## Standards to read first\n\n${list(g.standards, 'none beyond the always-on core')}`)
  if (g.git === 'task') parts.push(`## Before you start\n\nRun \`git -C ${g.workdir} log --format=%s ${g.from}..HEAD\`. A step that already has a commit whose subject starts with its ID was done by an earlier attempt: check that commit against the acceptance criteria and skip the step if it holds. If a file you need to change already has uncommitted changes, do not touch it: return \`failed\` and name the file.`)
  parts.push('## When to ask\n\nIf the spec reads two ways that lead to materially different results, or you lack an access, credential or tool the step needs, stop: return `needs_info` with one question in `question`. Do not guess, and do not work around missing access.\n\nDo not open or merge a PR, push a tag, delete a remote branch, or deploy. If a step needs one, return `needs_info` naming it.',
    `## Output\n\nWrite your full output (diffs, decisions, surprises, follow-ups) to \`${artifactPath(g)}\`. Return the structured result: status, what changed, what was decided, any surprises, the artifact path, and the short SHA of every commit you made. Use \`failed\` or \`low_quality\` when you could not meet the acceptance criteria; never report partial work as \`done\`.`,
    `## Git\n\n${gitLine(g)}`)
  return parts.join('\n\n')
}
// The failure is quoted verbatim from the Review log. A failed check may need this group's own commit
// messages rewritten (a subject, a trailer); a review concern is fixed with new commits only. A check
// note that also carries the review's CONCERNS gets both instructions.
function withReview(c) { return c.source === 'check' && /; review CONCERNS:/.test(c.note || '') }
function fixupSection(c) {
  const what = c.source === 'check'
    ? `The commit and scope checks (check_wave.py) failed on this group${withReview(c) ? ', and its review raised CONCERNS' : ''}. Their output (verbatim):`
    : 'The review of this group raised (verbatim):'
  const before = (c.notes || []).slice(0, -1)
  const how = c.source === 'check'
    ? `Fix only that. A step with no commit gets its commit. A new uncommitted path your group's work made is committed under its step, or deleted if it is a by-product (a build output, a temp file), the one case where you touch a path that already has uncommitted changes; leave any path you did not make alone and name it under surprises. A commit message the check rejects (its first line, a Co-authored-by or Signed-off-by line, a missing trailer) is rewritten: change only the messages of the commits the check names by SHA, keep each commit's content, and keep every other commit in ${c.from}..HEAD as it is, message included; some of them are the parent's plan and handoff commits. Use \`git commit --amend\` only when HEAD is one of the named commits; otherwise reword just those commits with a \`git rebase\` onto ${c.from}, run non-interactively (set GIT_SEQUENCE_EDITOR and GIT_EDITOR to commands). List the rewritten commits under surprises. Do not push.${withReview(c) ? `\n\nThe review's concern, after \`review CONCERNS:\` in that output, is fixed separately, as new commits whose subjects start with the step ID they fix; do not rewrite earlier commits for it.` : ''}`
    : 'Fix only that. Make the fix as new commits whose subjects start with the step ID they fix. Do not rewrite earlier commits.'
  return [`## Fix-up ${U.label}`, `${what}\n\n${quote(c.note)}`,
    before.length ? `Earlier failures on this group, oldest first (verbatim):\n\n${before.map(quote).join('\n\n')}` : '',
    how].filter(Boolean).join('\n\n')
}
function changes(g) {
  return g.git === 'shared'
    ? `run \`python3 ${args.checkWave} diff ${g.workdir} ${g.from}\` (this wave's changes only, untracked files included; the tree also holds earlier, already reviewed waves)`
    : `read \`git diff ${g.from}\`, \`git log ${g.from}..HEAD\` and \`git status\``
}
function reviewPrompt(g, r, t = tier) {
  return [`Review ${title(g, t)}. READ-ONLY: do not edit files, commit, push, open or merge a PR, tag, deploy, or start other work.`,
    `In \`${g.workdir}\`, ${changes(g)}, then the worker's artifact \`${r.artifact}\`. Check the change against the spec excerpt, the acceptance criteria and the standards below: does it do what they ask, no more and no less, correctly, with tests where the repo expects them?`,
    `${g.concern && g.concern.source === 'check' ? 'A script checks commit subjects, trailers, step coverage and paths after you. This fix-up exists because that check failed, so check the failure quoted below yourself as well.' : 'A script checks commit subjects, trailers, step coverage and paths after you; leave those to it.'} List only defects the change must fix before the plan builds on it, each with evidence (a file and line, a command and its output, or a quoted spec line). Checks that passed go in the note. Return PASS with no findings when you find nothing real.`,
    `## Spec excerpt (verbatim)\n\n${g.spec}`, `## Acceptance criteria\n\n${g.acceptance}`, `## Standards\n\n${list(g.standards, 'the always-on core')}`,
    g.concern ? `## This is fix-up ${U.label}\n\nThe last ${g.concern.source === 'check' ? (withReview(g.concern) ? 'check_wave.py run and review' : 'check_wave.py run') : 'review'} raised (verbatim):\n\n${quote(g.concern.note)}\n\nCheck that it is fixed, and review the whole range.` : '',
    `## Worker summary\n\nChanged: ${r.changed}\nDecided: ${r.decided}\nSurprises: ${r.surprises}\nCommits: ${r.commits.join(', ') || 'none'}`].filter(Boolean).join('\n\n')
}
function draftPrompt(g, angle) {
  return [`Draft for ${title(g)}. READ-ONLY: do not edit files, commit, push, open or merge a PR, tag, deploy, or run anything else that changes state.`,
    `Design how to carry out the steps below in \`${g.workdir}\`, from this angle: ${angle}. Read the code you need. Return a design an implementer can follow, and the risks it leaves open.`,
    `## Spec excerpt (verbatim)\n\n${g.spec}`, `## Acceptance criteria\n\n${g.acceptance}`, `## Steps\n\n${g.steps.join(', ')}`].join('\n\n')
}
function judgePrompt(g, drafts) {
  return [`Judge for ${title(g)}. READ-ONLY: do not edit files, commit, push, open or merge a PR, tag, or deploy.`,
    `Check each independent draft below against the spec and the code in \`${g.workdir}\`. Pick the strongest (1-based \`pick\`), then write a synthesis that keeps the winner, grafts in the best ideas from the others, and resolves or names every open risk.`,
    `## Spec excerpt (verbatim)\n\n${g.spec}`, `## Acceptance criteria\n\n${g.acceptance}`,
    drafts.map((d, i) => `### Draft ${i + 1}\n\n${d.design}\n\nRisks: ${d.risks}`).join('\n\n')].join('\n\n')
}

function gate(gates, reason, extra) { return { stop: 'gate', gates, reason, unit: U || null, tier: tier || null, mode: unattended ? 'unattended' : 'gated', checkpoints: [], groups: [], ...extra } }

function validate() {
  const e = []
  if (!args || typeof args !== 'object') return ['args missing']
  if (!/^[a-z][a-z0-9-]*$/.test(P || '')) e.push('args.plugin must be the plugin name')
  if (!args.plan || !args.plan.name || !/^\//.test(args.plan.path || '')) e.push('args.plan needs name and an absolute path')
  if (!S || S.version !== 3) e.push('args.state must be plan_state.py output (version 3)')
  if (S && S.errors && S.errors.length) e.push(...S.errors.map(x => `plan: ${x}`))
  if (e.length || !U) return e
  if (!ROUTE[U.tier]) e.push(`unknown tier ${U.tier}`)
  if (args.stepUp && !(CHAIN.indexOf(args.stepUp) > CHAIN.indexOf(U.tier))) e.push(`stepUp ${args.stepUp} is not above [${U.tier}]`)
  const d = args.xdeepDrafts || 0
  if (d && (!MAX[tier] || d < 2 || d > ANGLES.length)) e.push(`xdeepDrafts ${d}: only 2..${ANGLES.length}, and only on an [xdeep] or Fable dispatch`)
  if (d && unattended && !(args.approved || []).some(a => a && a.gate === 'gate-7' && a.wave === U.wave)) e.push('xdeepDrafts in unattended mode needs a human gate-7 approval for this wave')
  const ap = args.approved || []
  if (!Array.isArray(ap) || ap.some(a => !a || typeof a.gate !== 'string' || typeof a.wave !== 'number')) e.push('approved must be [{gate, wave}]')
  else if (ap.length && !(args.approval || '').trim()) e.push('approved is set but approval (the human answer, verbatim) is empty')
  const gs = args.groups
  if (!Array.isArray(gs) || !gs.length) return e.concat('args.groups is empty')
  const dirs = new Set()
  for (const g of gs) {
    const at = g.workdir || '?'
    for (const k of ['workdir', 'spec', 'acceptance', 'from']) if (!g[k] || typeof g[k] !== 'string') e.push(`${at}: missing ${k}`)
    if (!Array.isArray(g.steps) || !g.steps.length) e.push(`${at}: no steps`)
    if (!Array.isArray(g.standards)) e.push(`${at}: standards must be a list`)
    if (g.workdir && (!g.workdir.startsWith('/') || g.workdir.split('/').includes('..'))) e.push(`${at}: workdir must be absolute`)
    if (g.from && !/^[0-9a-f]{7,40}$/.test(g.from)) e.push(`${at}: from must be a commit SHA`)
    if (g.git !== 'task' && g.git !== 'shared') e.push(`${at}: git must be task or shared`)
    if (g.git === 'task' && !g.branch) e.push(`${at}: a task branch needs its name`)
    if (dirs.has(g.workdir)) e.push(`two groups share ${g.workdir}; one subagent per working directory`)
    if (g.answer && (!g.answer.question || norm(g.answer.answer) !== norm(args.approval))) e.push(`${at}: answer must quote the question and carry the human answer verbatim, as approval does`)
    dirs.add(g.workdir)
  }
  if (gs.some(g => g.git === 'shared') && !/^\/.*check_wave\.py$/.test(args.checkWave || '')) e.push('a shared-branch group needs args.checkWave, the absolute path of check_wave.py')
  if (gs.some(g => g.git === 'task')) {
    const t = args.trailers
    if (!Array.isArray(t) || !t.length || t.some(x => typeof x !== 'string' || /^(co-authored-by|signed-off-by):/i.test(x) || !/^[\w-]+: \S/.test(x))) {
      e.push('trailers must list the harness trailer lines, such as "Assisted-by: Claude Code", and never Co-authored-by or Signed-off-by')
    }
  }
  if (e.length) return e
  if (U.kind === 'fixup') {
    const want = [...U.groups].sort().join(' | ')
    const got = gs.map(groupId).sort().join(' | ')
    if (want !== got) e.push(`fix-up groups ${got} do not match the Review log's CONCERNS groups ${want}`)
  } else {
    const all = gs.flatMap(g => g.steps)
    const want = [...U.steps].sort().join(',')
    if (new Set(all).size !== all.length || [...all].sort().join(',') !== want) e.push(`groups cover steps ${all.join(',')}; this unit is ${U.steps.join(',')}`)
  }
  return e
}

// ---- run ----
const errors = validate()
if (errors.length) return gate(['gate-0'], errors.join('; '))
if (!U) return { stop: 'end', gates: [], reason: 'plan complete', unit: null, tier: null, mode: unattended ? 'unattended' : 'gated', checkpoints: [], groups: [] }

const hard = S.stops.filter(g => NEVER_APPROVED.includes(g))
if (hard.length) return gate(hard, hard.includes('gate-mode') ? 'the kickoff question has no recorded answer' : 'the plan has errors')
// Every gate derives from the plan; the mode only says which ones stop.
const required = [...S.stops]
const checkpoints = [...S.checkpoints]
if (args.stepUp) required.push('gate-6')  // a step-up across runs always follows a human answer
if (args.stepUp && MAX[args.stepUp]) required.push('gate-7')
const approved = (args.approved || []).filter(a => a.wave === U.wave).map(a => a.gate)
const stale = (args.approved || []).filter(a => a.wave !== U.wave)
if (stale.length) log(`Ignoring approvals for other waves: ${stale.map(a => `${a.gate}@${a.wave}`).join(', ')}`)
const missing = [...new Set(required)].filter(g => !approved.includes(g))
if (missing.length) return gate(missing, `wave ${U.label || U.wave} [${tier}] needs ${missing.join(', ')} approved`)
if (checkpoints.length) log(`Unattended checkpoints: ${checkpoints.join(', ')}`)

const concernOf = id => (S.concerns.find(c => c.wave === U.wave && c.group === id) || {})
let groups = args.groups.map(g => {
  const id = groupId(g)
  const c = U.kind === 'fixup' ? concernOf(id) : {}
  return { ...g, id, concern: c.note ? c : null, from: c.from || g.from }
})
const canary = !args.canaryDone
if (canary && groups.length > 1) {
  log(`Canary: running ${groups[0].id} only; ${groups.length - 1} group(s) wait for the gate-5 answer`)
  groups = groups.slice(0, 1)
}

const ph = unitTitle()
phase(ph)
async function execute(g) {
  const drafts = args.xdeepDrafts || 0
  let design = null
  if (drafts) {
    const ds = (await parallel(ANGLES.slice(0, drafts).map((a, i) => () =>
      agent(draftPrompt(g, a), { label: `Draft ${i + 1} ${title(g)}`, phase: ph, schema: DRAFT, ...reader() })))).filter(Boolean)
    if (ds.length < 2) return null
    const j = await agent(judgePrompt(g, ds), { label: `Judge ${title(g)}`, phase: ph, schema: JUDGE, ...reader() })
    if (!j) return null
    design = j.synthesis
  }
  return agent(workerPrompt(g, design), { label: title(g), phase: ph, schema: RESULT, ...worker() })
}
function review(g, work, t = tier) {
  return agent(reviewPrompt(g, work, t), { label: `Review ${title(g, t)}`, phase: ph, schema: REVIEW, ...reader(t) })
}
const runs = await pipeline(groups,
  g => execute(g),
  (work, g) => (work && work.status === 'done' ? review(g, work).then(r => ({ work, review: r })) : { work, review: null }))

let out = groups.map((g, i) => ({ id: g.id, workdir: g.workdir, steps: g.steps, from: g.from, git: g.git, tier,
  work: (runs[i] && runs[i].work) || null, review: (runs[i] && runs[i].review) || null }))
const isBroken = x => !x.work || x.work.status !== 'done' || !x.review

// Unattended only: one automatic retry per broken group, never at [xdeep] or Fable, never on a launch that is
// already a human-approved step-up, never for needs_info. A crash or a missing review retries on the same tier;
// failed or low_quality steps up one tier, into [exec] or [deep] only (gate 6 becomes a checkpoint).
function retryTier(x) {
  if (!unattended || args.stepUp || MAX[tier]) return null
  if (x.work && x.work.status === 'needs_info') return null
  if (!x.work || x.work.status === 'done') return tier
  const up = CHAIN[CHAIN.indexOf(tier) + 1]
  return up === 'exec' || up === 'deep' ? up : null
}
const retries = []
const again = out.filter(isBroken).map(x => ({ x, t: retryTier(x) })).filter(r => r.t)
if (again.length) {
  const redo = await parallel(again.map(({ x, t }) => async () => {
    const g = groups.find(y => y.id === x.id)
    const why = !x.work ? 'with no result' : x.work.status === 'done' ? 'with its review missing' : `as ${x.work.status}: ${x.work.surprises}`
    retries.push({ id: x.id, from: tier, to: t, reason: why })
    const work = x.work && x.work.status === 'done' ? x.work
      : await agent(workerPrompt(g, null, t, why), { label: `${title(g, t)} (retry)`, phase: ph, schema: RESULT, ...worker(t) })
    const r = work && work.status === 'done' ? await review(g, work, t) : null
    return { ...x, tier: t, work: work || null, review: r || null }
  }))
  out = out.map(x => (redo.find(y => y && y.id === x.id) || x))
  if (again.some(r => r.t !== tier)) checkpoints.push('gate-6')
}

const broken = out.filter(isBroken)
const questions = out.filter(x => x.work && x.work.status === 'needs_info').map(x => ({ id: x.id, question: x.work.question || x.work.surprises }))
const extra = { groups: out, canary, checkpoints, retries, questions }
if (broken.length) {
  const why = `${broken.map(x => x.id).join(', ')}: ${questions.length ? 'needs an answer, or ' : ''}failed, low quality, or unreviewed${retries.length ? ' after one automatic retry' : ''}`
  return gate(canary && !unattended ? ['gate-1', 'gate-5'] : ['gate-1'], why, extra)
}
if (canary && !unattended) return gate(['gate-5'], 'first-subagent canary', extra)
if (canary) checkpoints.push('gate-5')  // unattended: the parent continues once check_wave.py passes too
return { stop: 'done', gates: [], reason: `wave ${U.label || U.wave} reviewed`, unit: U, tier, mode: unattended ? 'unattended' : 'gated', ...extra }
```

The `args` the parent builds (from live run 2; spec text abridged; the plan path is where v5 keeps it on a task branch, while the live run's was in `.scratch/`; `state` is now version 3, with `mode` (its `guard` and `fixups`), `stops`, `checkpoints`, `cost` and each concern's `notes` and `source`):

```json
{ "plugin": "personal",
  "plan": { "name": "plan-smoke", "path": "/…/repo-a/specs/handoffs/plan-smoke.md" },
  "state": { "...": "plan_state.py output, verbatim (the hook compares it with disk)" },
  "canaryDone": true,
  "approved": [{ "gate": "gate-5", "wave": 1 }], "approval": "yes, continue wave 1",
  "trailers": ["Assisted-by: Claude Code"],
  "groups": [{ "workdir": "/…/repo-b", "steps": ["m1.s2"], "spec": "#### m1.s2 - [exec] Add beta.txt in repo-b\n…",
               "acceptance": "…", "standards": [], "git": "task", "branch": "feature/smoke", "from": "a08d5d2" }] }
```

A group that answers a question adds `"answer": { "question": "Which registry token?", "answer": "<Gary's words, as in approval>" }`.

## Appendix B: every review finding, and what v2 does

| Finding | v2 |
|---|---|
| H1 stale approvals | Accepted. Approvals are `[{gate, wave}]`, and the script honours only `wave == next.wave`. Approvals with an empty `approval` are gate 0. The hook allows approvals only in a turn a human started, word for word. Live: a relaunch from a notification turn was denied. |
| H2 gates hang on parent-supplied fields | Accepted, adapted. `plan_state.py` derives the gates from disk, and the hook denies a mismatch (live). **Rejected: passing the plan text in `args`.** The parent would emit the whole plan as output tokens, and one copy error would block the run; the hook gets the same guarantee from disk. **Rejected: the `UserPromptSubmit` recorder.** It fires on background reports and carries no origin; the transcript's `promptSource`/`turnOrigin` fields do the job (seen live). The claim is reworded in §2.1. |
| H3 resume is unsafe | Accepted, simplified. No `resumeFromRunId` in v1. The worker prompt is idempotent, and recovery relaunches from the plan and git. "Resume only when only reviews remain" was rejected: telling which agents remain needs the run journal, and it saves little. |
| H4 review fan-out | Accepted. One reviewer per working directory at the author's tier, and no verify stage. Live: $0.06 of review against $0.11 of work. |
| H5 trailer fix untested; LLM reviewer missed it | Accepted. `check_wave.py` flags v1's `cdeca40`/`518e99f` three ways each. The prompt spells out the trailer lines. Live v2 commits are correct. What ran is stated against the kit (Appendix A). |
| M1 runner Stop hook | Accepted. A runner writes nothing while a run is in flight, a Stop-hook continuation is not an instruction, and `snapshot` checks that `.scratch/` is ignored. **Rejected: waiting inside the turn.** Monitor and background Bash both end the turn, and foreground `sleep` is blocked. |
| M2 "in flight" on re-entry | Accepted. In flight counts as blocked; the run record is checked; the hook refuses a second run in the same session. |
| M3 launch result | Accepted. `error`, `warning` and `remote_launched` are handled in §2.3 step 3. |
| M4 routing unchecked | Accepted. `token_tally.py --check-routing` caught the Haiku stand-ins live. |
| M5 milestone split splits the drivers apart | Accepted, by another route. `plan_state.py` splits a unit at milestones without renumbering markers, so no change to the passive driver is needed. |
| M6 `fixupOf` | Accepted. Fix-ups come from the Review log, and two CONCERNS in a row is gate 1. That caps depth by construction, with no parent flag. v4: unattended, gate 1 is a checkpoint until the mode line's `fixups` cap, so depth is still capped from the plan. |
| M7 claude.ai/Cowork sync | Accepted. A phase-0 exit criterion. |
| M8 `to` comes from the reviewer | Accepted. `to` comes from `check_wave.py`; reviewers return no `to`; a fix-up's `from` is its CONCERNS line's `from`. v4: `check_wave.py` skips the parent's plan and handoff commits inside that range. |
| L1 six agents | Partly. Four, not two or three: the Agent path can't pass effort, and reviewers need the tool allowlist. |
| L2 three drafts by default | Accepted. Default 0, opt-in 2–4 at gate 7. Drafts run on `plan-reviewer-max`, whose body is now neutral. |
| L3 deferred tools; subagent check | Accepted (§1.4). |
| L4 home mode | Rejected for v1. Claude home mode uses the passive skill: `CLAUDE_MODE` defaults to plugin and cloud is plugin-only. That also avoids touching the shared `extensions.sh`. `agentTypes` is gone. |
| L5 Agerpoint port | Accepted. `args.plugin` sets the namespace, the tally derives the org from its folder, and the check asserts the manifest name. |
| L6 `[xdeep]` canary asks twice | Accepted. Gate 7 applies only at a wave's start. |
| L7 inconsistencies | Accepted. Plain-text gates everywhere; stop values are `gate`, `done` and `end` (with a `gates` list); concurrency is stated as "16, fewer on small machines (2 on a 4-CPU runner)"; one review rule for every adapter. |
| L8 Fable missing | Accepted. A `stepUp: "fable"` route behind gates 6 and 7, reviewed by Opus max. |
| L9 `gitLine` could drop `Claude-Session:` | Accepted. Explicit trailer lines; `Claude-Session:` is kept when the harness gives one. |
| L10 auto mode | Accepted. A phase-0 exit criterion. |
| L11 shared-branch pile-up | Accepted. One unit per run, plus a tree-snapshot diff for the reviewer. |
| L12 runner gate 1 | Settled in v3: save-first pushes them, labeled `UNREVIEWED` (Gary's rule). |
| Alternative 1: Agent-only phase 1 | Partly. The Agent path is the documented fallback and phase 0's fail-over. Workflow stays the target because only there are gates enforced in code. |
| Alternative 2: script reads the plan | Adapted: `plan_state.py` from disk, plus the hook. |
| Alternative 3: hook pair | Adapted: one `PreToolUse` hook that reads the transcript. |
| Alternative 4: deterministic git checks | Adopted. |
| Alternative 5: one wave per run | Adopted (decision 5). |
| (d) shipping the kit | Done. `test-orchestrate.sh` is written (add it to `make test`). The README rule is in §4. The Cursor import and the Grok/Muse hook loading are covered in §3. |

## Appendix C: evidence

v2's paths are under `/tmp/claude-0/-workspace-public/6333c263-f7c1-58ee-bb8f-25209c81c588/scratchpad/orch/v2/`:

| Path | What it holds |
|---|---|
| `kit/` | v2's workflow, the 4 agents, and `scripts/{plan_state,check_wave,orchestrate_gate,token_tally}.py` |
| `tests/` | v2's `test-orchestrate.sh` (57 tests plus the consistency check), `orchestrate_check.py` (passes on the kit, fails on deliberate drift) |
| `check/personal` | The plugin copy with v2's kit added. `claude plugin validate`, `grok plugin validate` and `muse plugins validate` all pass. |
| `smoke/out0.json` | Run without an allow rule: refused |
| `smoke/out1.json` | 4 hook denials, then the canary: `wf_070fee31-1e0`, gate 5 |
| `smoke/out2.json` | The approved continuation (`wf_294a7f67-946`, done), then a notification-turn relaunch: denied |
| `smoke/out3.json` | `wf_e171ffb0-328` returned gates 4 and 2 with 0 agents; the repeat launch was denied for owed gates |
| `smoke/repos/`, `smoke/plug/`, `smoke/old/` | The live repos; the Haiku copy of the plugin; v1's repos for the `check_wave.py` demo |
| Run records and transcripts | `/root/.claude/projects/-tmp-claude-0--workspace-public-6333c263-f7c1-58ee-bb8f-25209c81c588-scratchpad-orch-v2-smoke-repos-repo-a/6333c263-f7c1-58ee-bb8f-25209c81c588{.jsonl,/workflows/,/subagents/workflows/}` |
| `../verify/t1`-`t3` | v1's wire captures of per-call model and effort |

v3's paths are under `…/scratchpad/orch/v3/`:

| Path | What it holds |
|---|---|
| `kit/` | The v3 workflow and scripts; the agents and `check_wave.py` are unchanged |
| `kit.diff` | Every change from v2's kit |
| `tests/` | The v3 suites: 94 tests plus the consistency check; `test_token_tally.py` is new |
| `test-results.txt` | `test-orchestrate.sh` on `check/personal`: every suite passes |
| `v2-suites-against-v3-kit.txt` | v2's suites run unchanged against the v3 kit: 5/13, 9/9, 10/10, 6/25. The failures are fixtures without a `mode:` line or with version-1 state |
| `check/personal` | The plugin copy with the v3 kit and a working-tree draft of `plan-execution.md` that matches neither commit. `claude plugin validate` passes |
| `check-head/personal` | The same copy with HEAD's (9e22488) `plan-execution.md`: the consistency check and all suites pass |
| `../v3-review/` | The final review's evidence: `repro_hook.py` (hook repros), `calib.py` (guard calibration), `selfhosted_ctx.txt` (self-hosted runner environment), `split_guard.md` (guard on a split wave) |
| `evidence/stopreason_check.py`, `stopreason-opus.txt`, `stopreason-haiku-smoke.txt` | The `stop_reason` count over this session's Opus workflow agents and over the Haiku smoke runs |
| `evidence/tally-v2-vs-v3-opus.txt` | v2's and v3's tallies on four finished Opus runs |
| `evidence/runner-env.txt` | This container's `CLAUDE_CODE_*` runner variables |
| `evidence/codex-cloud-environments.md` | Codex's cloud environments doc, fetched today: no runner variable documented |
| `../cursor/cloud-agent_capabilities.md`, `../cursor/cloud-agent.md`, `../cursor/hooks.md` | Cursor's Cloud MCP `run-info`, cloud agents' own branch, and `CURSOR_CODE_REMOTE` |
| `../codex-src/codex-rs/core/src/unified_exec/process_manager.rs`, `../codex-src/codex-rs/core/src/spawn.rs` | `CODEX_CI=1` and `CODEX_SANDBOX`, set on local runs too |

v4's paths are under `…/scratchpad/orch/v4/`:

| Path | What it holds |
|---|---|
| `kit/` | The v4 workflow and scripts; the agents are unchanged from v3 |
| `kit.diff` | Every change from v3's kit (the v3 kit file without the outward-action lines, so they show here too) |
| `tests/` | The v4 suites: 133 tests (v4 said 132) plus the consistency check |
| `test-results.txt` | `test-orchestrate.sh` on `check-head/personal`: every suite passes |
| `v3-suites-against-v4-kit.txt` | v3's suites run unchanged against the v4 kit: 23/24, 9/9, 15/17, 4/4, 6/40. The failures are version-2 state, a mode that now carries `fixups`, and unattended fixtures with no committed handoff |
| `check-head/personal` | The plugin copy with the v4 kit and HEAD's (9e22488) `plan-execution.md`. `claude plugin validate` passes, with one warning: the manifest has no version |
| `../v4-review/repro/` | The final v4 review's repros against the kit before its fixes: a fix-up range that spans the bookkeeping commit (`fixup_range.sh`), and a leftover path a fresh snapshot hides (`leftover.sh`). The new `test_check_wave.py` cases cover both |
| `../v4-prefinal/` | The kit, tests and proposal before the final review's fixes, and `fixup_range_plan.sh`: the first repro with `--plan`, which now passes |

v5's paths are under `…/scratchpad/orch/v5/`:

| Path | What it holds |
|---|---|
| `kit/` | The v5 kit: only `scripts/orchestrate_gate.py` changed (rule 9 in both modes, and its workstation fallback where nothing can be pushed) |
| `kit.diff`, `tests.diff` | Every change from v4's kit, and from v4's suites |
| `tests/` | The v5 suites: 137 tests plus the consistency check |
| `test-results.txt` | `test-orchestrate.sh` on `check-head/personal`: every suite passes |
| `v4-suites-against-v5-kit.txt` | v4's suites run unchanged against the v5 kit: 40/40, 16/16, 20/23, 6/6, 48/48; all three failures are intended. Then the v5 hook suite against the v4 hook: 21/27, the 6 cases v5 adds or changes |
| `finalize_proposal.py`, `../v5-prefinal/` | The final v5 review's fixes to this proposal, and the kit, tests and proposal before them |
| `../v5-review/` | That review's evidence: `repro/edge_cases.py` (a plan in no git repo, a clone with no remote), `repro/gated_task_dirty.py`, and `mut/`, the mutant v5's earlier suite passed |
| `../v5-final-mut/` | The same mutant on the final hook; the final suite fails it 3 times |
| `check-head/personal` | The plugin copy with the v5 kit and HEAD's (9e22488) `plan-execution.md`. `claude plugin validate` passes, with the same warning (no version). Its `personal-plan-orchestrate` and `personal-plan-model-tiers` SKILL.md predate HEAD's; no suite reads them |
| `evidence/synced-plugin.sh`, `evidence/synced-plugin.txt` | What sync installed at the 21:07 resume, compared with main (c2b7c97) and this branch, plus the transcript's skill listings (none with a `personal:*` skill before 21:07) and SessionStart runs |
| `evidence/main-tree/`, `evidence/head-tree/` | `plugins/personal` at main and at HEAD, for that comparison |
