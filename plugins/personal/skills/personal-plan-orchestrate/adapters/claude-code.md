# Claude Code adapter

How `personal-plan-orchestrate` runs on Claude Code. [`SKILL.md`](../SKILL.md)
is the core: the kickoff, the mode, the gates, the loop, the handoff. This
file is only what is different here, in the order the loop reaches it: the
dispatch call and its arguments, the hooks that check it, the run's result,
what a runner and a limit do to it, and the tally. Read `SKILL.md` first;
"Each unit" and "When a unit completes" there say when each step below
happens.

`<P>` is the plugin's name, read as in `SKILL.md` "Detection" (a renamed
copy of the plugin has its own). `K` is this skill's `scripts/` folder.

Contents: [Runner signal and setup](#runner-signal-and-setup) · [Asking Gary](#asking-gary) · [The pieces](#the-pieces) · [The launch](#the-launch) · [The hooks](#the-hooks) · [The result](#the-result) · [The Agent path](#the-agent-path) · [Runners, recovery and limits](#runners-recovery-and-limits) · [Permissions](#permissions) · [Tokens](#tokens) · [Gotchas](#gotchas)

## Runner signal and setup

The runner signal is `CLAUDE_CODE_REMOTE=true`, plus the branch the cloud
session was assigned (`kickoff.md` "Runner signals" has the tokens to write
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
- Trailers (`contract.md` item 8): `Assisted-by: Claude Code`, plus any trailer
  the harness adds to its own commits (on the web, the `Claude-Session:`
  line; check the attribution note in your system prompt). The parent's own
  commits carry `Assisted-by: Claude Code` and no `Co-authored-by`,
  whatever the CLI's default attribution says.

## Asking Gary

Every fixed-choice question is an `AskUserQuestion` call; open questions
(a worker's `needs_info`, a re-plan) stay text. The dialog waits inside the
turn, so save first ("Questions, and saving before them" in `SKILL.md`).
- **The kickoff question:** the text block first (it keeps its `Reply`
  line, the fallback if Gary declines the dialog and types), then one call
  with two questions:

  ```json
  { "questions": [
      { "header": "Mode", "question": "Proposed mode: unattended. Which mode for plan-auth-otter?",
        "options": [ { "label": "Unattended (Recommended)", "description": "Gates 2, 4, 5 and 7 are logged; stops only for questions, failures, premium work and the guard (~$78)." },
                     { "label": "Gated", "description": "Every gate, failed check and repeat CONCERNS stops." } ],
        "multiSelect": false },
      { "header": "Session", "question": "Run plan-auth-otter in this session or a new one?",
        "options": [ { "label": "New session (Recommended)", "description": "Queue the Kickoff prompt as a new session with clean context." },
                     { "label": "This session", "description": "Dispatch wave 1 now." } ],
        "multiSelect": false } ] }
  ```

  Never fill in `answers`, `annotations` or `response` yourself: the hook
  then counts none of the dialog.
- **The confirmation** in a session that wasn't started from a paste,
  under a matching unattended record: the short text, then one question
  and no session question:

  ```json
  { "questions": [
      { "header": "Mode", "question": "Proposed mode: unattended. Keep the unattended run confirmed in session aeb2cfec for plan-auth-otter?",
        "options": [ { "label": "Unattended (Recommended)", "description": "Dispatch wave 1 now; ~$2.46 of ~$26 spent, guard ~$78." },
                     { "label": "Gated", "description": "Every gate, failed check and repeat CONCERNS stops." } ],
        "multiSelect": false } ] }
  ```
- **A gate or a stop:** one question, its text naming each repo's commit
  range, with options such as `Continue wave 3 [deep] m3 s1`, `Stop here`,
  and the step-up or waiver the gate allows (`Waive: <the concern>`). The
  approval you launch with is the picked label, verbatim, or the words he
  typed under Other.
- **The PR at completion:** `Open the PR` or `Not yet`.

**How the hook reads them.** An answer picked in a dialog is a human
message of the turn it joins, after its question's text: a gate answered
in the turn a completion notification started launches in that same turn.
It counts for nothing when the call's input carried answers, when the
dialog was declined, when it resolved itself while Gary was away
(`afkTimeoutMs`), or when he asked for more questions (`followUp`); re-ask
then. A `Gated` pick in a later dialog is a take-back, like a short typed
message naming gated.

**A new session.** When the session answer is `New session`, after the
save, start or queue it (load a deferred tool with ToolSearch):
- **On a cloud runner** (`runner=cloud`) with
  `mcp__claude-code-remote__create_session`: start it on the task branch.
  `source_url` is the plan's repo (`https://github.com/<owner>/<repo>`),
  `source_revision` and `outcome_branch` are both the task branch, `title`
  is `Orchestrate <plan name>`, and `prompt` is the Kickoff prompt
  verbatim. `outcome_branch` makes the harness assign the task branch
  instead of a fresh `claude/…` one, so the run stays on one branch and
  path (b) has nothing to move. Leave `model` and `permission_mode` unset:
  both inherit this session's. If this session isn't on Opus, pass the
  Opus id. If its permission mode is `plan` (`get_session` with no id),
  use the card below instead: a child in plan mode stalls at plan
  approval. A plan spanning repos passes only the plan's repo; the new
  session attaches the rest with `add_repo` and switches each to its task
  branch. The prompt arrives as `inbound_origin: mcp_create_session`, not
  a human message, so it is no paste: the new session asks Gary to confirm
  unattended with one click ("A session **not** started from a paste" in
  `SKILL.md`, and "The confirmation" above). Say so, with the new
  session's id. If the call fails, fall back to the card.
- **Elsewhere**, queue it with `mcp__ccd_session__spawn_task`: `title`
  `Orchestrate <plan name>`, `tldr` one line naming the waves and the
  mode, and `prompt` the Kickoff prompt verbatim, so the new session's
  first message is a paste the hook accepts. The tool's own description
  says not to use it for parts of your own task; Gary asked for this one.
  On a runner, the card's session gets its own `claude/…` branch, which
  path (b) fast-forwards.

Then print the prompt on its own (standard §"Printing a prompt in chat")
for when neither tool exists or the card is dismissed. For a card or a
paste, say once that the new session picks its own model: `/model opus`,
`/effort high`.

## The pieces

| Piece | Job |
|---|---|
| `<P>:plan-segment` workflow (`claude-workflows/plan-segment.js`) | Runs one dispatch unit. It checks its `args` against `plan_state.py`'s unit and refuses a stopping gate not approved for that wave. While `canaryDone` is false it runs only the first group (the canary, gate 5) when the unit has more than one; a one-group unit runs whole with no gate 5. It then runs each group's worker and, as soon as that finishes, its reviewer. Unattended, it retries a broken group once and returns the checkpoints it passed. A worker's disclosed breach stops the run at gate 1, with no retry. A fix-up unit quotes its failed check, concern or disclosure, verbatim, into the worker's and reviewer's prompts. It returns a result object only. |
| Two plugin agents (`claude-agents/`) | `plan-worker` (`model: inherit`) and `plan-reviewer` (Opus, high; tools Read, Grep, Glob, Bash). Every call sets the tier's model and effort. |
| `hooks/claude-hooks.json` | A `PreToolUse` hook on `Workflow` (`orchestrate_gate.py`) and two on `Bash`, each its own entry: `reviewer_guard.py` and `worker_guard.py`. The plugin manifest loads it beside `hooks/hooks.json`. |
| `plan_state.py`, `check_wave.py`, `token_tally.py` | `SKILL.md` lists them after "Detection"; below are the Claude Code arguments. |

The tiers table, with each tier's model and effort, is in `SKILL.md`
"Tiers and models". Both paths pass model and effort on every call, and
those override an agent's own frontmatter (the Agent tool's `effort` needs
Claude Code v2.1.292+). `plan-reviewer`
exists for its tool allowlist, and its Opus-high frontmatter is only a
default.

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
               "steps": ["m1.s2"], "spec": "#### s2 - [exec] Add beta.txt\n…",
               "acceptance": "…", "standards": [], "from": "a08d5d2" }],
  "decisions": "review wave-1 (repo-b m1 s1) …: PASS - … (verbatim, from the handoff)",
  "environment": "golangci-lint 2.5.0 fails on this module: use 2.6.0" }
```

- `canaryDone` is false on this session's first launch and true after,
  whether that launch split off a canary or, with one group, ran whole.
- `steps` are the IDs `plan_state.py` reports, which commit subjects carry:
  a heading `#### s2` under `## m1` is `m1.s2`.
- `approved` is `[]` except in the turn Gary's answer started (or joined):
  then one `{gate, wave}` per gate he answered, `wave` being the launched
  unit's wave number ("After an answer" in `SKILL.md` says which gates).
  `approval` is a top-level string beside `approved`, never inside its
  items, holding his message verbatim.
- A `needs_info` group adds `"answer": {"question": "…", "answer": "<the same words as approval>"}`.
- A fix-up unit's groups are the ones `plan_state.py`'s `next.groups` names.
- `decisions` and `environment` are optional strings, the handoff's
  "Decisions so far" and "Environment notes" verbatim (`contract.md` item 9);
  every worker and reviewer of the unit gets them.
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
2. Approvals ride only in a turn a human message started or joined (a
   typed message, or an answer picked in an `AskUserQuestion` dialog), and
   `approval` is that message verbatim. An approval, a group's `answer`, a
   waiver or a mode answer that is the Kickoff prompt or holds its mode line
   is denied: a paste answers nothing.
3. `canaryDone` is true only after an earlier canary launch in this session.
4. No earlier run of this session is unfinished.
5. Any gate the last run stopped at is approved. `gate-0` and `gate-mode`
   clear only from the plan.
6. The launch is by name.
7. An unattended mode was confirmed in this session, for this harness and
   runner, and not taken back (`kickoff.md` "Reading the answer", decision 9
   and the mode switch).
8. A raised guard carries an approval of `gate-guard`, and a raised fix-up
   cap one of `gate-1`.
9. Every group's directory and the plan's repo are on a task branch with
   `origin/HEAD` known, the branch being the group's; the plan and a
   refreshed handoff are committed and pushed, and so is every working
   directory of the last run.
10. A new `WAIVED` line is Gary's message verbatim, typed in this session.

The numbers are `orchestrate_gate.py`'s.

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
| `no human turn in this session is the recorded mode answer verbatim`, after a dialog | The dialog was declined, resolved itself while Gary was away, ended in a follow-up, or its input carried answers: ask it again. |
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

**The two Bash guards** read the hook input's `agent_type`, which a
workflow `agent()` subagent reports as `<P>:plan-…` (seen in phase 1's
dogfood, on the Mac and the web), and each acts only for its own agents:
- `reviewer_guard.py`, for `<P>:plan-reviewer`,
  denies a Bash call that writes: git write subcommands, file writers, `gh`,
  in-place edits, and redirection to a file (so a reviewer reads output
  inline).
- `worker_guard.py`, for `<P>:plan-worker`, denies the
  outward commands: `git push`, `gh pr` and `gh release` subcommands that
  write, `gh workflow run`, a goreleaser release without `--snapshot` or
  `--skip=publish` (and `goreleaser publish`, `announce`, `continue`), the
  package publishers without `--dry-run`, and a run of the repo's own
  script or make target whose name holds `publish`, `release` or `deploy`
  (`scripts/publish-formula.sh`, `./release.sh`, `make release`, `make
  deploy-prod`, `npm run release`) unless a dry-run form is present:
  `DRY_RUN=1`, `--dry-run`, or for make `-n`. Reading, grepping, linting or
  syntax-checking such a script, and a make variable's value (`make doctor
  MODE=release`), pass.

Each sets heredoc bodies and quoted strings aside first, and fails open for
every other caller, since each sees every Bash call of every session. They
are defence in depth: the prompts still forbid all of it. A deny reaches the
agent as `PreToolUse:Bash hook error: personal-plan-orchestrate reviewer: …`
(or `worker: …`).

**What nothing checks:** a worker's outward command the worker guard
doesn't name (a script whose name doesn't say publish, release or deploy;
the prompt forbids it, and the worker reports any it ran or tried under
`breaches`), the Kickoff prompt's `plan` line naming this plan's repo, and
the runner tokens against an assigned branch.

## The result

The completion notification starts the turn. Then, for "When a unit
completes" in `SKILL.md`:
- **check:** `python3 $K/check_wave.py check --snapshot <snapshot> --run
  $C/projects/<slug>/<S>/workflows/<runId>.json` (add `--baseline` for a
  fix-up). The record supplies the plan path and the trailers.
- **tally:** see "Tokens" below.
- **The record's `result`:** `stop` (`done`, `gate`, `end`), `gates`,
  `checkpoints` (log them), `retries` (log them), `questions` (a
  `needs_info` group's question, asked verbatim), `breaches` (`{id,
  breach}` for every rule a worker disclosed breaking: the run stopped at
  gate 1 for them, and `SKILL.md` "When a unit completes" makes each group
  CONCERNS), and per group `work` (with `breaches` and `surprises`, whose
  `env:` lines go to the handoff's Environment notes), `review` (verdict,
  note, findings), `from`, `branch`, `tier`.
- A `stop` of `gate` or a failed check goes to the branch step in `SKILL.md`
  (a fix-up is the next unit, or the stop is asked); `done` goes back to
  "Each unit"; `end` is final completion.

## The Agent path

When `Workflow` is missing. No hook and no script: the parent applies
`plan_state.py`'s stops, the retries, the fix-ups and the per-wave handoff
by hand, as on Cursor. Foreground calls keep the turn open, which also
avoids the runner Stop hook.
- Per working directory, all in one message: `Agent(subagent_type:
  "<P>:plan-worker", model: <opus|sonnet|haiku|fable>, effort: <level>,
  description: <wave title>, prompt: <the contract>, run_in_background:
  false)`, with the model and effort from `SKILL.md` "Tiers and models".
  `max` doesn't exist here.
- Then each directory's reviewer the same way (`<P>:plan-reviewer`, with
  its tier's model and effort). `run_in_background: false` is required:
  without it Claude Code backgrounds the call.
- The wave title is `Wave {n} of {t} [{tier}] {group-id}`, with `Review`
  ahead of it for a reviewer (the tally labels rows from it).
- Check with `check_wave.py check --snapshot <s> --plan <plan> --group
  '<json>'`, one `--group` per group (`{"id","workdir","steps","from","trailers"}`).
- Tally with `token_tally.py --session-dir $C/projects/<slug>/<S>` and no
  `--run`: it reads the session's `subagents/` transcripts and labels rows
  from each call's `description`, so tally once per wave and append only
  that wave's new lines. This path has no workflow run ids to bound parent
  windows, so the parent writes one line per session: at every save that
  ends a turn to wait or ends the session, `--parent-window start:end
  --parent-row "orchestrator-kickoff <plan name>"` (or
  `orchestrator-resume` in a later session), replacing the line it wrote
  at its previous stop. The guard counts it from then on.
- The unattended mode rests on the parent here, as its gates do.

## Runners, recovery and limits

- **The runner's Stop hook** (`~/.claude/stop-hook-git-check.sh`) is a git
  check: it fires at a turn's end only while the tree is dirty or unpushed,
  as it is while workers run. It is not an instruction (`SKILL.md` "Each
  unit", step 5): reply in one line, don't commit or push. The web harness
  also blocks `sleep N; cmd` chains: don't wait in the shell. The container
  stays up while a run works.
- **A cloud session** gets its own `claude/…` branch from the default
  branch: `kickoff.md` "A new session on a plan already kicked off", path
  (b), fast-forwards it to the prompt's branch. One the kickoff starts
  with `create_session` ("A new session" above) is assigned the task
  branch itself.
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
- **Idle compaction.** Claude Code compacts a conversation over 200K tokens
  left idle about 54 minutes (v2.1.299+), so a parent waiting at a gate can
  come back compacted. Let it: every wait follows a save (`SKILL.md`
  "Questions, and saving before them"), so the plan and the pushed handoff
  hold what the run needs. A parent that finds its context compacted
  re-reads the plan and the handoff and re-runs `plan_state.py` before it
  acts on an answer.

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
  a request from Gary (Claude Code's workflow docs); worker commits pass
  under auto mode with the allow rules above (verified on the Mac and the
  web). `worker_guard.py`, not the auto-mode classifier, is what stops a
  publish script run without its dry-run flag.
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

Wave N is the unit the previous run carried. For a session's first run,
the window is `start:<runId>` and the row `orchestrator-kickoff <plan
name>` in the session that kicked off, `orchestrator-resume <plan name>` in
any later one. At a save that ends a turn to wait or ends the session
(`SKILL.md` "Token tally", the open stretch), tally `--parent-window
<lastRunId>:end` (or `start:end` before any launch) under the same row,
and let the later line of that row replace it if the session goes on.
Windows don't overlap, so the guard never counts the parent twice. Parent
lines are exact; the turn being written isn't flushed yet, a small tail
the standard says to ignore. Subagent lines in a live session stay `(output
est.)` at completion: their session's `cost-state` record also covers the
parent and every other wave, so keep the lines rather than merging them.
`--check-routing` exits 2 when an agent ran on another model than its
tier's (an `availableModels` substitution, or a wrong alias): that is gate 1
(`SKILL.md` "When a unit completes", step 2).

## Gotchas

- While an org-synced copy of the plugin under another name (`orch-spike`)
  is installed beside `personal`, two gate hooks run, and a copy that is
  older applies its older rules too.
- The Mac CLI wraps a bracketed paste in `<pasted_content>` tags (the web
  doesn't); the hook unwraps them before it compares anything, so a
  wrapped paste is still a paste.
- `ANTHROPIC_DEFAULT_*_MODEL` doesn't remap the workflow's models; the
  routing check catches any substitution.
