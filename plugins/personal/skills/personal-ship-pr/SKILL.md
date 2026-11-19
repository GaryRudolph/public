---
name: personal-ship-pr
description: >-
  Take a finished change from draft PR to merge-ready: open it as a draft
  with the review guide, run /code-review medium on a [check] or [study]
  PR and fix CI, remove the runner's handoff files, mark it ready, work
  Copilot's review in rounds until every comment has an outcome, then stop
  and report the tally for the Owner to merge. Never merges. Triggers:
  "open a PR", "PR this", "ship it", "get this ready to merge", the work on
  a task branch is done, and a personal-plan-orchestrate run completes.
---

# personal-ship-pr

The loop around a PR, from draft to the Owner's merge. The rules it applies
live in the standards; this file adds the order, the waits and the exits.
Read [`review.md`](../personal-standards/standards/review.md) "Agent reviews
on a PR" for the triage, and [`git.md`](../personal-standards/standards/git.md)
"Pull Requests" for the description and trailers.

Asking for a PR is approval for the whole loop. It stops only where a step
below says so.

## 1. Open the draft

Run `personal-review-guide` in `walkthrough` mode, then `pr` mode, with the
PR opened as a draft. The walkthrough sets the PR tier, which decides
step 2. If the repo can't take a draft (the API refuses one), ask before
opening it ready for review. Subscribe to the PR's activity where the
harness can.

## 2. Draft round: `/code-review` and CI

The point: a fresh-context review catches what Copilot would, before a push
can buy a Copilot round. Start it as soon as the draft is open, without
asking.

- **`[check]` or `[study]` PR:** run a fresh-context review of the PR:
  `/code-review medium <number>` on Claude Code, without `--comment` or
  `--fix`; elsewhere the harness's range review on merge-base`..HEAD`
  (`personal-codebase-review`'s reference.md "Harnesses"). Triage its
  findings as review.md says.
- **`[skim]` or `[skip]` PR:** skip it; Copilot's review is enough.
- **CI:** wait for the checks on the head commit and fix what this change
  broke. A failure the change didn't cause goes in the report, not in a fix.

Batch the fixes into one push. Run `/code-review` once; run it again only
when the fixes rewrote a `[study]` area.

## 3. Mark it ready

On a runner, or after a `personal-plan-orchestrate` run on any machine,
the push before ready removes the `specs/handoffs/` files (git.md
"Merging"), so Copilot reviews the change that will merge. From here
the PR's description and threads hold the state; later turns skip the
handoff step in "Save before you wait".

When CI is green on that commit, mark the PR ready (`update_pull_request`
with `draft: false`). If a ruleset reserves that for the Owner, ask.

## 4. Copilot rounds

1. Wait for Copilot's review of the head commit, and for any other review
   the repo requests (Claude Code Review, a reviewer a ruleset adds). Where the ruleset doesn't
   request it (Copilot isn't a requested reviewer a few minutes after the
   ready or the push), request it with `request_copilot_review`. If nothing
   posts within about 30 minutes, say so once and go to step 5, where the
   missing review is reported as waiting on the Owner.
2. Triage every comment from each of them (review.md). A comment that repeats one already
   declined gets a reply linking the earlier one, and no change.
3. If anything is to be fixed, make one push, reply on every thread, and
   start the next round. Otherwise the loop is done.

Stop after three rounds that each needed a fix: once Copilot has reviewed
the third fix push, go to step 5 and report what's still open. Copilot
can find something new on every push forever.

The loop is done when every comment has an outcome and a reply, not when
every comment was fixed. A decline or a deferral is an outcome.

## 5. Merge-ready, then stop

Check:

- The required checks are green on the head commit.
- Copilot's latest review covers the head commit, or the report says
  why not (it never posted, or the round cap was hit), and no other
  requested review is pending.
- Every thread has a reply.
- Nothing waits on the Owner, or the report names what does.
- No `specs/handoffs/` plan, session handoff or review draft is on the
  branch. Milestone handoffs are allowed.
- GitHub reports the PR as mergeable.

If the branch is behind and the repo requires it to be up to date, update
it (`update_pull_request_branch`) as the last push, then `git pull
--ff-only` so the checkout has GitHub's merge commit before any later
commit. Wait for CI, and don't request another Copilot review for it. On a
conflict, ask. If a ruleset requests a review on that push, wait for it
and triage it as one more round; otherwise a head whose only change since
Copilot's last review is that base merge counts as reviewed.

Then report: the PR link, the tier, CI status, the tally (`/code-review: 2
fixed. Copilot: 3 fixed, 1 declined (why), 1 deferred (card)`), whether an
approval stands, and what waits on the Owner. Don't merge. The Owner
merges, or says "merge it", and then git.md "Merging" applies.

## Without PR events

On a workstation, where the harness doesn't deliver PR activity, say what
you're waiting for (CI, Copilot's review) and end the turn. Pick the loop
up at that step when the Owner says it has landed.
