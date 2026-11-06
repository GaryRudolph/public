Two related changes to how sessions hand work to each other. First, on a runner with a harness-assigned branch, that branch is the task branch: a branch a prompt names ("new branch X", `On branch X`, `Base branch X`) is only the topic, and the runner brings X onto its own branch. This came from a lolay/nowline runner that cut a named branch, couldn't open a PR from it (HTTP 500 three times), and couldn't delete it. Second, handing work to a new session picks between a suggested-task card and `create_session`: a card when it can land in the right repos on the right model, otherwise a session on a Claude Code runner after one yes. Every handed-over prompt carries a header and preflight, and dependent cards hold on a `Queue:` line until their prerequisite merges. Fixes r1.f26. Evaluation and probe: `specs/session-queuing.md`.

## Review guide

Review tier: [study], because `core.md`, `git.md` and `plan-execution.md` are the rules every agent session loads, and this changes how they pick branches and start sessions.
Blast radius: every agent session's branch and hand-off behavior; docs only, so a revert restores the old rules.
Review time: ~7 min

1. [study] [`plugins/personal/skills/personal-standards/standards/git.md`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-volta-be4jqf#diff-2d643ebc49654b24a4c49da2465b6df6fe5e15b39be74a3ceb6d131befb175d8): runner branch rule, the three prompt forms, proxy facts
2. [study] [`plugins/personal/skills/personal-standards/core.md`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-volta-be4jqf#diff-c1e2d2bf9b7fab8b83d3edd958794a2bf08b42577e5266e9ccf8a9673588c443): task-branch bullet, "Queue sessions"
3. [study] [`plugins/personal/skills/personal-standards/standards/plan-execution.md`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-volta-be4jqf#diff-e60c1d503447fa58c5d17cc350a5335d5c12bf1a5be635b6c17c97c284cf7b4e): new "Handing work to another session", ask-user rule, STOP `On branch` rule
4. [check] [`plugins/personal/skills/personal-plan-model-tiers/SKILL.md`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-volta-be4jqf#diff-d8d197c7dffa9f28fc0390537498ac0987b4838bb6074bf0a98c2144c82f9d72): new-session dialog, step 7 hand-off
5. [check] [`plugins/personal/skills/personal-plan-orchestrate/adapters/claude-code.md`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-volta-be4jqf#diff-ee7226557908aae91f7fcc62ee54368cbe135d3f85b470d3b7990de05b3cda74): push first, explicit model and permission mode
6. [check] [`plugins/personal/skills/personal-codebase-review/SKILL.md`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-volta-be4jqf#diff-84f4da220c8aefe3daa979f74462c52f6ce4236655150818a371896b43409474): remediation hand-off
7. [skim] [`specs/session-queuing.md`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-volta-be4jqf#diff-a975e2ac6694bbb2fb36baf94b222046d817f97535ef35ec9b6526e80c0b6838), [`specs/README.md`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-volta-be4jqf#diff-00b1d791c652b7d601291cb1555d2feebfc02c6681602802ac272c1ce52295b3)
8. [skip] [`plugins/personal/cursor/rules/personal-core.mdc`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-volta-be4jqf#diff-39a8d78a12609c027a769b918fbe42135cdb4da5ab7deaa55bb03bb12d504a79) (`make -C agents cursor-core-rule`)

## Validation

- `make -C agents validate test`: pass, before each of the four commits.
- `tests/test-session-start.sh`: pass; `core.md` now loads in 4 of the 5 SessionStart parts (the fourth is 644 characters).
- `create_session` probe on this repo: ran, results in `specs/session-queuing.md` (PR 47 opened from the probe's `outcome_branch` against a non-default base, then closed).
- A card started from a real `spawn_task`, and the hold on a `Queue:` line: not run, need a human click.

## Rollback

Revert the squash commit. Docs and rules only; nothing persisted.

<details open>
<summary>[study] Runner branches, and how sessions hand work over</summary>

Branch handling on a runner with an assigned branch:

| Prompt says | Before | After |
|---|---|---|
| "new branch X off main" | Counted as a branch named for the work; the runner could cut X | X is the slug only; the runner stays on its assigned branch |
| `On branch X` | Runner stays on its branch, X not brought over (r1.f26: plan and earlier waves missing) | Runner fetches X and fast-forwards or merges it onto its branch |
| `Base branch X` | (no such form) | Brought over the same way; PR opens against X |

Handing work to a new session:

| | Before | After |
|---|---|---|
| Way | Card (`spawn_task`); `create_session` only for orchestrate's and the passive kickoff's next session on a runner | Card when it can land right; else on a runner, one dialog to start sessions, no answer queues cards |
| Repo and model | Whatever the card gives; nothing checks | Header names repos, model, effort, branch; preflight checks repo and model, then relaunches or prints the prompt |
| Card title | `2 after 1: Backfill status` | `2 after 1 [exec]: Backfill status` |
| Dependents | Prompt checks "a merged PR, a pushed branch" with no way to find it | Finds the prerequisite's PR by `Queue: <set> <n>` in its description; holds, asking for "ready" |
| Proxy claims in git.md | Proxy refuses pushes to any branch but the assigned one; `gh` doesn't go through it | What nowline showed: the push worked, the PR 500'd, both delete paths were refused |

</details>

<details>
<summary>[check] Skill procedures</summary>

`personal-plan-model-tiers` splits "New session" into "Start a new session now" and "Queue a card" on a runner with `create_session`, with any non-answer queuing a card, and starts the session on the task branch with the tier's model. Orchestrate's adapter pushes before naming the branch and passes `model` and `permission_mode`, since the probe's child got `default` when it was left unset. Orchestrate's Kickoff prompt still goes over with no header: its hook only accepts a paste that matches the plan's prompt. Codebase-review remediation hands over one card or session per finding group, all unnumbered.

</details>

## Decisions

- Cards stay the default, since they keep the click; `create_session` is offered only when a card would land wrong.
- A held dependent never polls; "ready" from the Owner is the yes even if the search finds nothing.
- Not verified: which model a card's session gets, and what effort a started session gets. The preflight and header cover both.
- `kickoff.md` path (b) keeps stopping at gate 0 when the branch has its own commits rather than merging.

https://claude.ai/code/session_01BNKwNYJ9a86zACDMFsmRNQ

Assisted-by: Claude Code
