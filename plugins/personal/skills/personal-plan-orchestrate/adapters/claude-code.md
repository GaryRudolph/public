# Claude Code adapter (phase 1: dogfood)

How `personal-plan-orchestrate` runs on Claude Code. [`SKILL.md`](../SKILL.md)
is the core: the kickoff, the mode, the gates, the loop, the handoff. This
file is only what is different here, in the order the loop reaches it: the
dispatch call and its arguments, the hooks that check it, the run's result,
what a runner and a limit do to it, and the tally. Read `SKILL.md` first;
"Each unit" and "When a unit completes" there say when each step below
happens.

`<P>` is the plugin's name (`personal`), as in `SKILL.md` "Detection". `K`
is this skill's `scripts/` folder. The Claude Code path is new and is being
proven on real plans.

## Runner signal and setup

The runner signal is `CLAUDE_CODE_REMOTE=true`, plus the branch the cloud
session was assigned (`SKILL.md` "Runner signals" has the tokens to write
down: `harness=claude-code`, and `runner=cloud`, `self-hosted`, `ci` or
`none`). The gate hook reads the same environment, so the tokens you record
are the ones it compares.

Once per session:
- `C` is `${CLAUDE_CONFIG_DIR:-$HOME/.claude}`. The session's transcript is
  `$C/projects/<slug>/<S>.jsonl`, where `<slug>` is the working directory
  with every character but a letter or digit turned into `-` and `<S>` is
  `$CLAUDE_CODE_SESSION_ID`. A workflow run's record is
  `$C/projects/<slug>/<S>/workflows/<runId>.json`, written when the run
  ends.
- If `K` isn't known from the skill's base directory:
  `find "$C" /root/.claude -path "*<P>-plan-orchestrate/scripts/plan_state.py" 2>/dev/null | head -1`.
- Trailers (contract item 8): `Assisted-by: Claude Code`, plus any trailer
  the harness adds to its own commits (on the web, the `Claude-Session:`
  line; check the attribution note in your system prompt). The parent's own
  commits carry `Assisted-by: Claude Code` and no `Co-authored-by`,
  whatever the CLI's default attribution says.

## The pieces

| Piece | Job |
|---|---|
| `<P>:plan-segment` workflow (`claude-workflows/plan-segment.js`) | Runs one dispatch unit. It checks its `args` against `plan_state.py`'s unit and refuses a stopping gate not approved for that wave. While `canaryDone` is false it runs only the first group. It then runs each group's worker and, as soon as that finishes, its reviewer. Unattended, it retries a broken group once and returns the checkpoints it passed. A fix-up unit quotes its failed check or concern, verbatim, into the worker's and reviewer's prompts. It returns a result object only. |
| Five plugin agents (`claude-agents/`) | `plan-worker` (`model: inherit`; the call sets model and effort), `plan-worker-exec` (Sonnet, high), `plan-worker-xdeep` (Opus, xhigh), `plan-reviewer` (Opus, high; tools Read, Grep, Glob, Bash) and `plan-reviewer-xdeep` (Opus, xhigh; same tools). |
| `hooks/claude-hooks.json` | A `PreToolUse` hook on `Workflow` (`orchestrate_gate.py`) and one on `Bash` (`reviewer_guard.py`). The plugin manifest loads it beside `hooks/hooks.json`. |
| `plan_state.py`, `check_wave.py`, `token_tally.py` | `SKILL.md` lists them after "Detection"; below are the Claude Code arguments. |

The tiers table, with each agent's model and effort, is in `SKILL.md`
"Tiers and models". Why five agents: the Agent path can't pass effort, so
the `[xdeep]` worker and reviewer need definitions that say `effort:
xhigh`, the Agent path's `[exec]` worker one that says `effort: high`
(Sonnet defaults to medium), and the reviewers need a definition that
carries the tool allowlist. Haiku still thinks: it inherits the session's
thinking setting.

## The launch

Call the Workflow tool with `name: "<P>:plan-segment"` (never `script` or
`scriptPath`) and `args` as a JSON object, never a string. Each launch is
one dispatch unit, at the end of "Each unit" step 4.

```json
{ "plugin": "<P>",
  "plan": { "name": "plan-auth-otter", "path": "/abs/path/specs/handoffs/plan-auth-otter.md" },
  "state": { "...": "plan_state.py's output, verbatim; re-run it after your last plan edit" },
  "canaryDone": true,
  "approved": [{ "gate": "gate-5", "wave": 1 }],
  "approval": "yes, continue wave 1",
  "trailers": ["Assisted-by: Claude Code"],
  "groups": [{ "workdir": "/abs/path/repo-b", "branch": "feature/auth-otter",
               "steps": ["m1.s2"], "spec": "#### m1.s2 - [exec] Add beta.txt\n…",
               "acceptance": "…", "standards": [], "from": "a08d5d2" }] }
```

- `canaryDone` is false on this session's first launch and true after.
- `approved` is `[]` except in the turn Gary's answer started (or joined):
  then one `{gate, wave}` per gate he answered, `wave` being the launched
  unit's wave number ("After an answer" in `SKILL.md` says which gates).
  `approval` is a top-level string beside `approved`, never inside its
  items, holding his message verbatim.
- A `needs_info` group adds `"answer": {"question": "…", "answer": "<the same words as approval>"}`.
- A fix-up unit's groups are the ones `plan_state.py`'s `next.groups` names.
- Optional, each needing Gary's approval: `stepUp` (`"deep"`, `"xdeep"`,
  `"fable"`: gate 6, plus gate 7 into `[xdeep]` or Fable), `max: true` and
  `xdeepDrafts: 2-4` (an `[xdeep]` or Fable unit only; gate 7 in every
  mode).

**The launch result.** `async_launched` with a `runId`: end the turn with
one line. `error` set: the script failed its own check, gate 0.
`remote_launched`: the run went to a cloud session whose commits land
elsewhere, gate 0; use the Agent path. Show any `warning` to Gary. A hook
deny reads `PreToolUse:Workflow hook error: personal-plan-orchestrate gate:
…` even when the hook exited 0: it is a deny. Quote it, fix what it names
(table below), and never work around it.

## The hooks

**The gate hook** denies a launch unless:
1. `args.state` equals `plan_state.py` run from disk.
2. Approvals ride only in a turn a human message started or joined, and
   `approval` is that message verbatim. An approval, a group's `answer`, a
   waiver or a mode answer that is the Kickoff prompt or holds its mode line
   is denied: a paste answers nothing.
3. `canaryDone` is true only after an earlier canary launch in this session.
4. No earlier run of this session is unfinished.
5. Any gate the last run stopped at is approved. `gate-0` and `gate-mode`
   clear only from the plan.
6. The launch is by name.
7. An unattended mode was confirmed in this session, for this harness and
   runner, and not taken back (`SKILL.md` "Reading the answer", decision 9
   and the mode switch).
8. Every group's directory and the plan's repo are on a task branch with
   `origin/HEAD` known, the branch being the group's.
9. The plan and a refreshed handoff are committed and pushed, and so is
   every working directory of the last run.
10. A raised guard or fix-up cap carries its approval, and a new `WAIVED`
    line is Gary's message verbatim.

It never allows a launch outright, so the session's permission rules still
apply. It fails closed: bad input, a missing or older `plan_state.py`, any
exception, or no decision within its own 20 s deadline deny with exit 2,
which blocks even when the JSON is lost, and the hooks file's own fallback
covers a `python3` that won't start. Two limits stay: Claude Code cancels a
hook at its 30 s timeout and then doesn't block, and a hooks file that isn't
loaded checks nothing. Quote the reason, then:

| The deny says | Fix |
|---|---|
| `args.state differs from plan_state.py` | Re-run `plan_state.py` after your last plan edit and pass it verbatim. |
| `task branch: … no branch checked out`, `is on X, not the group's branch`, `shared branch` | Cut or switch to the task branch (`SKILL.md` "Task branches"); the group's `branch` is the directory's. |
| `origin's default branch is unknown` | `git -C <dir> remote set-head origin --auto`. |
| `unattended mode is not confirmed` | Another session, harness or runner confirmed it, or no human turn here is the answer: ask the kickoff question again. |
| `a yes to a gated proposal records gated` | Record gated, or ask again with an unattended proposal. |
| `a later short human message names gated` | Record gated (the take-back), or ask again. |
| `per-wave handoff: … not pushed`, `uncommitted changes`, `no session handoff`, `changed after the handoff` | Refresh the handoff, commit both in one bookkeeping commit, push every working directory. |
| `run <id> has not finished` | Wait for its notification. A run with no record after a crash: start a new session from the Kickoff prompt. |
| `the last run stopped at <gates>` | Approve each in the turn Gary's answer starts, or relaunch only after he answers. |
| `approvals can ride only on a launch in the turn …`, `args.approval is not the human's last message` | Relaunch with `approved: []`, or with his message verbatim. |
| `the approval is the pasted Kickoff prompt` | Re-post the `BLOCKED` question and wait. |
| `canaryDone is true, but …` | Pass `canaryDone: false` for this session's first launch. |
| `the cost guard rose`, `the fix-up cap rose` | Approve `gate-guard` or `gate-1` with Gary's answer, or restore the line. |
| `the WAIVED line … is not a human message of this session` | The waiver must be Gary's message verbatim, typed in this session. |
| `hook error (…)` | A bug or a missing file; report it, don't retry blind. |

**The reviewer guard** denies a Bash call that writes (git write
subcommands, file writers, `gh`, in-place edits, redirection to a file)
when the hook input's `agent_type` is `<P>:plan-reviewer` or
`<P>:plan-reviewer-xdeep`. It fails open for every other caller: it sees
every Bash call of every session. It is defence in depth; the reviewer's
instructions still say read-only. UNVERIFIED: that a workflow `agent()`
reviewer reports that `agent_type`; the dogfood tries one denied write.

**What nothing checks:** a worker's outward commands (the prompts forbid
them and ask for `needs_info`), the Kickoff prompt's `plan` line naming this
plan's repo, and the runner tokens against an assigned branch.

## The result

The completion notification starts the turn. Then, for "When a unit
completes" in `SKILL.md`:
- **check:** `python3 $K/check_wave.py check --snapshot <snapshot> --run
  $C/projects/<slug>/<S>/workflows/<runId>.json` (add `--baseline` for a
  fix-up). The record supplies the plan path and the trailers.
- **tally:** see "Tokens" below.
- **The record's `result`:** `stop` (`done`, `gate`, `end`), `gates`,
  `checkpoints` (log them), `retries` (log them), `questions` (a
  `needs_info` group's question, asked verbatim), and per group `work`,
  `review` (verdict, note, findings), `from`, `branch`, `tier`.
- A `stop` of `gate` or a failed check goes to the branch step in `SKILL.md`
  (a fix-up is the next unit, or the stop is asked); `done` goes back to
  "Each unit"; `end` is final completion.

## The Agent path

When `Workflow` is missing. No hook and no script: the parent applies
`plan_state.py`'s stops, the retries, the fix-ups and the per-wave handoff
by hand, as on Cursor. Foreground calls keep the turn open, which also
avoids the runner Stop hook.
- Per working directory, all in one message: `Agent(subagent_type:
  "<P>:plan-worker", model: <opus|sonnet|haiku>, description: <wave title>,
  prompt: <the contract>, run_in_background: false)`. `[exec]` uses
  `<P>:plan-worker-exec` (Sonnet high, since this path can't pass effort),
  `[xdeep]` uses `<P>:plan-worker-xdeep`, and `max` doesn't exist here.
- Then each directory's reviewer the same way (`<P>:plan-reviewer`, or
  `-xdeep`). `run_in_background: false` is required: without it Claude Code
  backgrounds the call.
- The wave title is `Wave {n} of {t} [{tier}] {group-id}`, with `Review`
  ahead of it for a reviewer (the tally labels rows from it).
- Check with `check_wave.py check --snapshot <s> --plan <plan> --group
  '<json>'`, one `--group` per group (`{"id","workdir","steps","from","trailers"}`).
- Tally with `token_tally.py --session-dir $C/projects/<slug>/<S>` and no
  `--run`: it reads the session's `subagents/` transcripts and labels rows
  from each call's `description`, so tally once per wave and append only
  that wave's new lines. This path has no workflow run ids to bound parent
  windows, so write one `orchestrator` line at final completion with
  `--parent-window start:end --parent-row "orchestrator <plan name>"`.
- The unattended mode rests on the parent here, as its gates do.

## Runners, recovery and limits

- **The runner's Stop hook** (`~/.claude/stop-hook-git-check.sh`) is a git
  check: it fires at a turn's end only while the tree is dirty or unpushed,
  as it is while workers run. It is not an instruction (`SKILL.md` "Each
  unit", step 5): reply in one line, don't commit or push. The web harness
  also blocks `sleep N; cmd` chains: don't wait in the shell. The container
  stays up while a run works.
- **A cloud session** gets its own `claude/…` branch from the default
  branch: `SKILL.md` "A new session on a plan already kicked off", path
  (b), fast-forwards it to the prompt's branch.
- **No resume.** Claude Code reruns a failed agent, and every agent that
  started after it, even completed ones. So the parent starts a new run
  from `plan_state.py` instead: the worker prompt says to skip steps that
  already have commits, and the review covers the whole range. A run that
  dies with its session leaves no record, so the hook refuses any further
  launch in that session: start a new session from the pasted Kickoff
  prompt, which confirms the mode there when the environment matches. The
  branch holds the plan and a handoff as of the last reviewed wave, so a
  lost session or container costs at most the wave in flight.
- **A stop with unreviewed worker commits** pushes them, labeled
  `UNREVIEWED` (decision 12, `SKILL.md` "Questions, and saving before
  them"). The handoff commit sits on top of them in the plan's repo, so
  pushing the handoff pushes them, and hook rule 9 checks every working
  directory.
- **Usage limits.** A run pauses at a limit only in an interactive
  claude.ai session; background and Remote Control runs fail instead, and
  on the web a spend limit didn't pause the run: it completed with agents
  returning null, and the parent's next model call failed. So after a limit
  the worker commits stay unreviewed and unpushed, the pushed handoff is one
  wave behind, and nothing can save first. Start a new run once the limit
  resets, after the next human turn reconciles from git. A scheduled
  relaunch may run checkpoints and never answers a gate. The workflow's
  automatic retry fails at once too (a crash and a limit both return null),
  which costs little.

## Permissions

- Workers use the session's rules: allow `git add`, `git commit` and each
  repo's test commands, and the parent's `git push`
  (`--force-with-lease --force-if-includes` included, for a fix-up that
  rewrote messages). Leave `gh pr`, tag and deploy commands out, so a worker
  that tries one meets a prompt. Reviewers need read-only Bash.
- In `-p` or the SDK, allow `Workflow(<P>:plan-segment)`; without it the
  launch is denied with "Review dynamic workflow before running".
  Interactive sessions get "don't ask again" for a plugin workflow.
- Start the session with `--add-dir <repo>` for each working directory
  outside the current one.
- In auto mode, the prompt the script passes to `agent()` doesn't count as
  a request from Gary (Claude Code's workflow docs). That worker commits
  pass under auto mode is a dogfood check.
- Unattended answers no permission prompt: one mid-run still waits for
  Gary. A run works best with the allow rules above in place.
- When the snapshot reports a repo whose `.claude/settings.json`
  attribution would add a `Co-authored-by` line, say so at kickoff:
  `check_wave.py` fails such commits, and `personal-repo-baseline` fixes the
  setting.

## Tokens

`token_tally.py` reads `subagents/workflows/<runId>/agent-*.jsonl` and the
`.meta.json` labels. It follows the standard's source precedence: one call
per `message.id`, with its usage from the line that carries `stop_reason`; a
call with no such line keeps its input-side counts and gets 1,000 output
tokens, and its line ends `(output est.) session <id>` (almost every Opus
subagent call). A fix-up's rows are `wave-N-fix`, then `wave-N-fix2`, with
`review-wave-…` beside them. An automatic retry keeps its wave's row and is
routed by its own tier. `<model>` drops a trailing `-YYYYMMDD`; pricing and
the routing check use the raw id. Workflow workers get no token
instruction: the parent writes every token line from this tally.

After a launch completes:

    python3 $K/token_tally.py --session-dir $C/projects/<slug>/<S> --run <runId> \
      --check-routing --parent-window <prevRunId>:<runId> \
      --parent-row "orchestrator-wave-<N> <group-id>"

Wave N is the unit the previous run carried. For the first run, the window
is `start:<runId>` and the row `orchestrator-kickoff <plan name>`. Windows
don't overlap, so the guard never counts the parent twice. Parent lines are
exact; the final completion turn isn't flushed yet, a small tail the
standard says to ignore. Subagent lines in a live session stay `(output
est.)` at completion: their session's `cost-state` record also covers the
parent and every other wave, so keep the lines rather than merging them.
`--check-routing` exits 2 when an agent ran on another model than its
tier's (an `availableModels` substitution, or a wrong alias): that is gate 1
(`SKILL.md` "When a unit completes", step 2).

## Gotchas

- While an org-synced copy of the plugin under another name (`orch-spike`)
  is installed beside `personal`, two gate hooks run, and a copy that is
  older applies its older rules too.
- The desktop app wraps a pasted message in `<pasted_content>` tags; the
  hook unwraps them before it compares anything, so an unwrapped paste is
  still a paste.
- `ANTHROPIC_DEFAULT_*_MODEL` no longer remaps the workflow's models; the
  routing check catches a substitution anyway.
