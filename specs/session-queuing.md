# Session queuing: task cards and create_session

How a session that hands work to another session should do it: a suggested-task card the Owner clicks, or a session it starts itself with `mcp__claude-code-remote__create_session`. This is the evaluation and the probe behind the rules now in core.md "Queue sessions" and plan-execution.md "Handing work to another session".

Status: implemented, 2026-11-06. Part 1 of the same work (a runner's assigned branch beats a branch a prompt names) is already in `git.md` "Task branches and shared branches".

## The problem

Cards (`mcp__ccd_session__spawn_task`) take three fields: `title`, `tldr`, `prompt`. The card starts a session in the spawning session's repo, locally or in the cloud, on whatever model the app picks. So a card for work in another repo lands in the wrong primary repo, a card for an `[exec]` wave starts on Opus or a card for a `[deep]` wave on Sonnet, and order and branch have to live in titles and prompts ("Number ordered task cards").

`create_session` takes `source_url`, `source_revision`, `outcome_branch`, `model`, `permission_mode` (no wider than the parent's), `title`, `tags`, `environment_id` and `prompt`, and starts at once. It exists only in Claude Code cloud sessions. The parent hears back only when a child's turn fails; otherwise it checks with `get_session` and `list_events`.

## The probe

One throwaway session, 2026-11-06, from this session (a Claude Code cloud runner on Opus): `create_session` with `source_url` GaryRudolph/public, `source_revision` and PR base `claude/peaceful-volta-be4jqf` (this session's branch), `outcome_branch` `claude/outcome-probe-wren`, `model` `claude-haiku-5-5`. It committed one file, pushed, opened a draft PR, then started a grandchild on `claude-sonnet-5-5` and archived it. Cost: $0.024.

| Question | Result |
|---|---|
| Does `outcome_branch` become the child's assigned branch? | Yes. The child's record lists it as the session's outcome branch, and the harness told the child to develop there. |
| Does a PR from it open under the proxy? | Yes, first try, as a draft ([GaryRudolph/public#47](https://github.com/GaryRudolph/public/pull/47)). |
| Can the PR target a non-default branch? | Yes: base was `claude/peaceful-volta-be4jqf`. So `Base branch X` (a stacked PR onto X) works. |
| Where is the child checked out at start? | On `source_revision`, **not** on `outcome_branch`. The child had to create `claude/outcome-probe-wren` itself. A careless child would have committed onto the parent's branch. |
| Does `model` stick? | Yes, `claude-haiku-5-5` in the record and as the served model. |
| Can a child start a session on a pricier model than its own? | Yes: the Haiku child started a Sonnet grandchild (`configured_model` and `session_context.model` both `claude-sonnet-5-5`). |
| What effort does the child get? | Unknown. `create_session` takes no effort, and the child's record has no `effort_level` (the parent's shows `high`). |
| Permission mode | The child got `default` while the parent's record still read `plan` (the record lagged; the parent had left plan mode). Unclear what it inherits; pass it explicitly. |
| `source_revision` that isn't on the remote yet | The session fails at start (`ref_not_found`, not recoverable). Push before you start a child from your branch. |
| Can the runner delete the branch afterwards? | Not tried; part 1's evidence says no. The Owner deleted it. |

Still unverified: which model a card's session gets (the spawner's or the app default); whether a child with no `source_revision` starts on its `outcome_branch`; branch and PR behavior for a repo added with `add_repo` rather than `source_url`.

## Branching

`outcome_branch` makes the child's assigned branch whatever the parent names, and PRs from it work. That settles the case part 1 couldn't: continuing existing work on X keeps one branch when the parent starts the child with `source_revision` X and `outcome_branch` X. The plan-wave flow stops leaving one branch per wave, which closes the other half of r1.f26. For `Base branch X`, the parent passes `source_revision` X and a fresh `outcome_branch`, and the child opens its PR against X.

Two rules fall out of the probe: push the branch before naming it in `source_revision`, and when `outcome_branch` differs from `source_revision`, the child's prompt says to `git switch -c <outcome_branch> --no-track` before its first commit (the harness says so too, but the prompt shouldn't depend on it).

A card's session gets a fresh `claude/…` branch off the default branch, so it handles `On branch X` and `Base branch X` by merging X in (git.md). That works, but each wave leaves a branch the runner can't delete.

## Approval

A card waits for a click; a session starts spending at once. "Wait for approval" and fail-closed hold if starting sessions is always its own question: `AskUserQuestion` with "Start N sessions now" first, listing each session's repo(s), model, branch and title, and "Queue cards instead" second. A declined, dismissed or timed-out dialog queues cards, which still wait for a click, so nothing starts without a yes. A yes covers the sessions it listed, not later ones. A parent in plan mode doesn't start children (a plan-mode child stalls at plan approval).

## Ordering

For a set where some sessions wait on others, three ways, priced at the [plan-execution.md](../plugins/personal/skills/personal-standards/standards/plan-execution.md) price table:

| Way | Extra cost | Idle time | Needs |
|---|---|---|---|
| (a) Start the independent sessions; the parent subscribes to their PRs and starts each dependent when its prerequisite merges | One parent wake per merge. Within the 1-hour cache, a 150k-token Opus context re-read is about $0.03; past it, about $0.60-0.75 (input at $4/M, cache write a bit more). Plus a short `create_session` turn. | Minutes after a merge | A standing yes for the dependents too, named in the dialog |
| (b) Start all now; dependents check their prerequisite and stop | One wasted start per dependent: the standards and prompt load, about 30-60k input tokens, $0.12-0.24 on Opus, less on Sonnet or Haiku. Then each needs a human "go" later, re-reading that context. Dead sessions clutter the list. | Until the Owner pokes it | Nothing new, but risks a dependent working ahead |
| (c) Start the independent sessions; queue dependents as numbered cards | None | Until the Owner clicks | Today's card numbering |

Recommend (c) by default, and (a) when the Owner picks it in the dialog ("start the rest as their prerequisites merge"). Never (b).

A dependent card still has to know when it may start, and it can't know its prerequisite's branch (a card's session gets a fresh `claude/…` one) or a PR that doesn't exist yet. So each set gets a name, every prompt has its PR description carry `Queue: <set> <n>`, and a dependent searches the repo's PRs for its prerequisite's line. Merged means go; anything else means hold: no work, one line asking the Owner to say ready, end of turn, no polling. A "ready" is the yes even when the search still finds nothing. Clicking a dependent card early then costs one short turn. For (a), the parent finds the prerequisite's PR the same way before it can subscribe to it.

## Model choice

`create_session` takes a model id. From the [Model picker](../plugins/personal/skills/personal-standards/standards/plan-execution.md#model-picker), Claude Code row:

| Tier | `model` | Effort the picker wants | Gap |
|---|---|---|---|
| `[xdeep]` | `claude-opus-5-5` | xhigh, plus `ultracode` as the prompt's first word when audit-shaped | Effort can't be set |
| `[deep]` | `claude-opus-5-5` | high | Opus defaults to medium |
| `[exec]` | `claude-sonnet-5-5` | high | Sonnet defaults to medium |
| `[fast]` | `claude-haiku-5-5` | medium | none (Haiku defaults to medium) |

Effort is the gap in both paths: a card can't set it either. The prompt's header names the effort, and the child's first report repeats it so the Owner can run `/effort` if it's wrong. Whether a child inherits the parent's saved effort is open.

Without `create_session` (a workstation, Cursor, Codex, Gemini): cards where `spawn_task` exists, else printed prompts, both with the header below.

## Multi-repo

One session per repo, each with its own `source_url`, `outcome_branch` and PR, is what the probe verified. One session that attaches the other repos with `add_repo` is unverified for branches and PRs, and part 1's evidence says a PR from a branch the proxy didn't assign can fail. Recommend one session per repo; a session that must read across repos attaches the others read-only.

## Cards, fixed as far as they go

Cards are the easiest path and keep the Owner's click, so they stay the default whenever they can land right. Two things make that more often true, and a third catches the rest.

1. **Set what the tool lets you set.** The spawner reads the card tool's schema when it loads it and sets every field the tool offers for repos, model, effort or branch. Today that's none, so everything below falls to the prompt. If the harness adds those fields, the same rule sets them and the header and preflight shrink, with no rule change; the rule names no field names, so it doesn't go stale.
2. **Put the tier in the title**: `2 after 1 [exec]: Backfill status`, so the model is visible before the click.
3. **A header and a preflight in the prompt.** The prompt opens with what the work needs and a check:

       Repos: GaryRudolph/public (primary), lolay/nowline
       Model: claude-sonnet-5-5 (/model sonnet), effort high (/effort high)
       Branch: work on your assigned branch (on a workstation, cut `fix/<slug>` off the default branch)
       Preflight: before anything else, check `git remote get-url origin` against the primary repo and your model (a runner: `get_session`; elsewhere, your system prompt) against the model above. If either is wrong, do no work and recover as the standards say.

   On a mismatch the session does no work and recovers one of two ways:
   - **Relaunch**, on a runner with `create_session`: start the right session (repos, branch, model) with the same prompt, report its id, and stop. Without asking when the target model costs the same or less than its own (the click already approved the work); with an `AskUserQuestion` first when it costs more (the probe shows it can), failing closed to the printed prompt.
   - **Printed prompt**, everywhere else or when relaunch is declined or fails: the prompt in a `text` fence (plan-execution.md "Printing a prompt in chat"), with the repos to select in order (first is primary), the `/model` and `/effort` to pick, and the branch, above it. When only the model is wrong, it also offers the in-place fix: run `/model` and `/effort`, then say go.

   Either way the wrong session spends one short turn.

## Recommendation by surface

| Surface | Use |
|---|---|
| Claude Code cloud runner (has `create_session` and `spawn_task`) | A card when it can land right: same repos with the same primary, same model and effort as the spawner (or the card tool can set them), and a branch the `On branch`/`Base branch` rules cover. Otherwise offer "Start N sessions now" vs "Queue cards" (fail closed to cards). Plan waves and orchestrate's next session: `create_session` with `source_revision` and `outcome_branch` the task branch, so the run keeps one branch. |
| Claude desktop or CLI on a workstation (`spawn_task`, no `create_session`) | Cards with the title tier, header and preflight; printed prompt as fallback. |
| Cursor, Codex, Gemini, Muse, Grok | Printed prompt with the same header. |

## Rule changes (implemented)

- **core.md "Number ordered task cards"**: renamed "Queue sessions"; it says: a card when it can land right, else offer to start sessions on a runner (one dialog, fail closed to cards); set whatever repo, model, effort and branch fields the card tool offers; tier in the title; every handed-over prompt opens with the header and preflight; dependents stay numbered cards unless the Owner picks auto-start, and find their prerequisite by its queue line.
- **plan-execution.md**: a "Handing work to another session" section holding the header and preflight template, the relaunch and printed-prompt recovery, the tier-to-`model` table and the ordering choice; "Printing a prompt in chat" points to it; the ask-user rule (~740) uses it.
- **personal-plan-model-tiers step 7 and STOP hand-off**: on a runner with `create_session`, offer to start the next wave with `source_revision` and `outcome_branch` the task branch and `model` the wave's tier (closes r1.f26); else a card with header and preflight.
- **personal-plan-orchestrate `adapters/claude-code.md` "A new session"**: already uses `create_session`; add the push-first rule and pass `permission_mode` explicitly.
- **personal-codebase-review remediation offer**: one session or card per finding group with the header; remediation PRs are independent, so all can start at once.
