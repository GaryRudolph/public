---
name: personal-ship-pr
description: >-
  Take a finished change from draft PR to merge-ready without babysitting:
  open it as a draft with the review guide as soon as the work is done,
  run the harness's /code-review at the level the PR's tier and risk tags
  set (or say why it's skipped), fix CI, remove the runner's handoff files,
  mark it ready, work Copilot's review in rounds until every comment has an
  outcome, waiting on CI and reviews itself, then stop, notify, and report
  the tally for the Owner to merge. Never merges. Triggers: "open a PR",
  "PR this", "ship it", "punch it chewie", "make it so" (as the whole
  message, not "make it so that ..."), "get this ready to merge", the work
  on a task branch is done, a PR was just opened (the
  plugin's hook says so), and a personal-plan-orchestrate run completes.
---

# personal-ship-pr

The loop around a PR, from draft to the Owner's merge. The rules it applies
live in the standards; this file adds the order, the waits and the exits.
Read [`review.md`](../personal-standards/standards/review.md) "Agent reviews
on a PR" for the triage, and [`git.md`](../personal-standards/standards/git.md)
"Pull Requests" for the description, trailers and tagalongs.

The loop has standing approval, however it started: the Owner asking ("ship
it", "punch it chewie", "make it so"), the work being done, the plugin's
hook after a PR opened, or an orchestrate run completing. The three
go-ahead phrases count only as the whole message, or as a closer after a
finished change: "make it so the retry backs off" is a feature request,
not a ship. It's one step for
core.md's "Pause after each step" and "Wait for approval": don't stop
between its steps to ask or to show progress. It stops only at an exit
below, or when the Owner said "draft only" or "hold" for this PR. None of
it is a "merge it": the Owner merges.

## 1. Open the draft

Open it as soon as the work on the task branch is done and its checks pass
locally; don't ask first (git.md "Creating"). If you aren't confident it's
done, say what's missing instead of opening it. Fetch and rebase onto the
latest base branch first, and rerun the checks if that brought anything
in: this is the last time the branch is rebased (see "Keeping up with
the base").

Related follow-ons you'd otherwise propose as a new PR go in this one as
tagalongs, before the draft or in a later round, unless one of git.md's
split criteria holds ("Creating", "Related work rides along"). Split-out
work goes to a card.

Run `personal-review-guide` in `walkthrough` mode, then `pr` mode, with the
PR opened as a draft. The walkthrough is shown, not a stop: carry on to
step 2 in the same turn. It also sets the PR tier, which decides step 2. If
the repo can't take a draft (the API refuses one), ask before opening it
ready for review: that's an exit.

## 2. Draft round: `/code-review` and CI

The point: a fresh-context review catches what Copilot would, before a push
can buy a Copilot round.

- **The review:** the harness's own, at the level review.md "Review
  levels" sets from the PR's tier and risk tags: on Claude Code
  `/code-review <level> --max-findings all <number>`, without `--comment`
  or `--fix`; elsewhere the harness's range review on merge-base`..HEAD`
  (`personal-codebase-review`'s reference.md "Harnesses").
- **When it isn't warranted** (a `[skim]` or `[skip]` PR with no risk tag),
  don't run it. Say one line and move on: `Skipping /code-review: tier
  [skim], no risk tags.` The tally repeats it.
- **`[security]`:** also the harness's security review where it has one
  (Claude Code's `/security-review`).
- Triage the findings as review.md says.
- **CI:** wait for the checks on the head commit (see "Waiting") and fix
  what this change broke. A failure the change didn't cause isn't fixed
  here: that's an exit. Leave the PR in draft and report the failure (red
  on the base too, or which service it names).

Batch the fixes into one push. Run the review once; run it again only when
the fixes rewrote a `[study]` area.

## 3. Mark it ready

On a runner, or after a `personal-plan-orchestrate` run on any machine,
the push before ready removes the `specs/handoffs/` files (git.md
"Merging"), so Copilot reviews the change that will merge. From here
the PR's description and threads hold the state; later turns skip the
handoff step in "Save before you wait".

When CI is green on that commit, mark the PR ready (`update_pull_request`
with `draft: false`). If a ruleset reserves that for the Owner, that's an
exit.

## 4. Copilot rounds

1. Wait for Copilot's review of the head commit, and for any other review
   the repo requests (Claude Code Review, a reviewer a ruleset adds).
   Where the ruleset doesn't request it (Copilot isn't a requested
   reviewer a few minutes after the ready or the push), request it with
   `request_copilot_review`. A review whose findings are only in its body
   may send no event, so check the PR's reviews rather than trusting an
   event to come. If nothing posts within about 30 minutes, go to step 5,
   where the missing review is reported as waiting on the Owner.
2. Triage every finding from each of them (review.md): the inline threads
   and the review body, where Copilot lists findings it has no thread for
   (such as "previously missed" ones). A finding that repeats one already
   declined gets a reply linking the earlier one, and no change. A fix the
   size of a tagalong is made here, not deferred.
3. If anything is to be fixed, make one push, reply on every thread, and
   start the next round; otherwise the loop is done. A body-only finding
   has no thread to reply on: its outcome goes in the tally.

Stop after three rounds that each needed a fix: once Copilot has reviewed
the third fix push, go to step 5 and report what's still open. Copilot
can find something new on every push forever.

The loop is done when every finding has an outcome and a reply (or a tally
line), not when every finding was fixed. A decline or a deferral is an
outcome. A finding that needs the Owner (review.md: a contract, design or
security call) doesn't hold the rest: finish the others, then exit with it
open.

## 5. Merge-ready, then stop

Check:

- The required checks are green on the head commit.
- Copilot's latest review covers the head commit, or the report says
  why not (it never posted, or the round cap was hit), and no other
  requested review is pending.
- Every thread has a reply, and every body-only finding a tally line.
- Nothing waits on the Owner, or the report names what does.
- No `specs/handoffs/` plan, session handoff or review draft is on the
  branch. Milestone handoffs are allowed.
- GitHub reports the PR as mergeable.

If the branch is behind and the repo requires it to be up to date, update
it (`update_pull_request_branch`) as the last push, then `git pull
--ff-only` so the checkout has GitHub's merge commit before any later
commit. Wait for CI, and don't request another Copilot review for it. A
conflict goes through "Keeping up with the base". If a ruleset requests a
review on that push, wait for it and triage it as one more round;
otherwise a head whose only change since Copilot's last review is that
base merge counts as reviewed.

Then report: the PR link, the tier, CI status, the tally (`/code-review: 2
fixed. Copilot: 3 fixed, 1 declined (why), 1 deferred (card)`, or
`/code-review: skipped ([skim], no risk tags)`), any tagalongs, follow-on
work queued as cards with the criterion that split each one out, whether
an approval stands, and what waits on the Owner. Don't merge. The Owner
merges, or says "merge it", and then git.md "Merging" applies.

Then park: watch for a conflict until the PR merges or closes ("Keeping up
with the base").

## Keeping up with the base

Other sessions' PRs land while this one waits. Don't poll for that.
Check the PR's `mergeable_state` (from `pr_state.py`, or the GitHub MCP
`pull_request_read`) at times the loop is already awake: every wake for CI
or a review, and before every push.

- `dirty` (it conflicts): `git fetch origin <base>`, then `git merge
  origin/<base>`, not a rebase, now that the PR is open: a rebase would
  orphan the review threads and the commit Copilot reviewed. Resolve,
  rerun the repo's checks, and push it with this round's fixes, or alone.
  A merge that needed resolving is a fix push: Copilot reviews it next
  round.
- `behind` (GitHub reports it only where the repo requires an
  up-to-date branch): during the loop, leave it for step 5, which updates
  it once. While parked, update it (`update_pull_request_branch`), then
  `git pull --ff-only` so the checkout has GitHub's merge commit, wait
  for CI, rerun step 5's checks, and park again.
- Anything else (`clean`, `unstable`, `blocked`): GitHub can merge it, so
  leave it alone.

Resolve a conflict yourself when both sides' intent is clear (two
additions to a list, an import, a rename the other PR did). When the
resolution has to pick one behavior over another, or lands in a `[study]`
area, that's an exit: say which files and what each side wanted.

**Parked.** After step 5, watch until the PR merges or closes, so a
conflict from a later merge gets fixed before the Owner finds it:

- With `gh`: `pr_state.py --pr <n> --wait-until conflict --interval 900
  --timeout 6600` in a background Bash with `timeout` 7200000, so the
  script's own deadline comes first. It costs no context until it exits.
  Exit 3 (nothing yet): re-arm it. Exit 0: if the PR merged or closed,
  stop and report the final status ("Status", "After the merge"), with a
  notification; if
  it's `dirty` or `behind`, handle it as above, wait for CI, and report
  and notify again.
- On the web: a `send_later` check-in every two hours that reads
  `mergeable_state` and does the same, for 24 hours at most. Then stop
  parking and say so in the status line; the Owner can say "keep
  watching".

Stop parking when the PR merges or closes, or the Owner says stop, and
cancel the pending check-in (`delete_trigger`) when you do.

## After the merge

When the PR merges, the final report also says whether a review of `main`
is due, where the repo keeps a `specs/reviews/` log: run
[`../personal-codebase-review/scripts/review_log_facts.py`](../personal-codebase-review/scripts/review_log_facts.py)
and read `since_anchor: commits=`. At 20 or more, add `Review due: <N>
commits on <default> since r<N>` (codebase-review.md "When"). It's
information for the Owner: don't start a review, queue a card for one, or
count it against "done, archivable". Inside a plan, the milestone gate
already covers it; say nothing.

## Status

The Owner may be running several of these, so a report ends with a
status line on its own line, after a blank line: the state's emoji, the
state in bold, then the detail. Where the harness can rename the session
(Claude Code's `set_session_title` on its own session, from
`get_session`), the title starts with the same emoji, updated whenever the
state changes, so the line and the session list match. Only a question
or a block needs the Owner.

Write the line when the state changes, and at the end of a turn that
answers the Owner. A wake that changes nothing (an event for an older
commit, your own reply echoing back) gets one short sentence and no
status line, so the line keeps standing out.

| Emoji | Line | When |
| --- | --- | --- |
| 🔄 | 🔄 **Working:** \<what\> | Mid-loop: reviewing, fixing, pushing |
| ⏳ | ⏳ **Waiting:** \<on CI, Copilot's review\>; nothing needed from you | The loop is waiting on something other than the Owner |
| ❓ | ❓ **Question:** \<the question\> | An exit that needs the Owner's answer: a contract, design or security call, a conflict that picks a behavior, findings past the round cap |
| 🛑 | 🛑 **Blocked:** \<what's wrong and what's needed from you\> | An exit that needs the Owner to act: CI red on the base too, a refused draft, a ruleset step |
| ✅ | ✅ **Merge-ready:** parked for conflicts until you merge | Step 5, parked |
| 🏁 | 🏁 **Done:** archivable | See below |
| 📌 | 📌 **Done, not archivable:** \<what remains\> | The PR merged or closed, something else is still open here |

Done and archivable means all of these: the PR merged or closed; no
watch or check-in is left running for it; the tree is clean and nothing
is unpushed; no question to the Owner is pending; and every follow-up is
queued as a card or written into the PR, not held only in this session.
To stop a merge-ready session's parking, say stop before archiving it:
on the web a check-in already scheduled still fires after an archive.

## Exits

The loop ends only at step 5, or at one of these: a CI failure the change
didn't cause, a finding that needs the Owner's call, a conflict that needs
one, a ruleset
that reserves a step for the Owner, a draft the repo refuses, or the round
cap. At every exit and at step 5, report as step 5 says and send one push
notification where the harness has one (Claude Code's `PushNotification`):
the PR, then the state or what's needed, in a line (`acme/orders#124
merge-ready: Copilot 3 fixed, 1 declined` or `acme/orders#124 blocked,
needs you: CI red on main too`). The Owner may be driving several PRs;
the notification is how they learn which one needs them. At an exit, cancel
any check-in or watch you started for this PR; at step 5, parking takes
over.

## Waiting

Waiting on CI or a review never ends the loop on the Owner. Pick the first
way the harness offers:

- **Claude Code with `gh`** (a workstation, a self-hosted runner): run
  [`scripts/pr_state.py`](scripts/pr_state.py) in a background Bash
  (`run_in_background`, `timeout` up to 7200000), which wakes the session
  when it exits:
  `python3 -I <skill>/scripts/pr_state.py --pr <n> --wait-until checks-done`,
  or `--wait-until review-on-head --timeout 1800` for Copilot (step 4's
  30 minutes; `--reviewer any` for another reviewer; several `--reviewer`
  flags end on the first of them, so wait once per reviewer to wait for
  all), `--wait-until conflict` while parked, or `--wait-until change`
  for anything. Exit 0 means
  the condition holds; exit 3 means `--timeout` (default an hour) passed.
  Then read its JSON and decide. It prints facts only (check states, which
  reviews cover the head, threads and their replies); what failed and why
  is your call. Without `--wait-until` it prints the state once.
- **Claude Code on the web** (no `gh`): `subscribe_pr_activity` delivers
  CI and review events. Before ending a turn to wait, also schedule one
  check-in about 30 minutes out (`send_later`), since a body-only review
  can arrive with no event; on waking, read the PR with the GitHub MCP
  tools and carry on. Cancel it (`delete_trigger`) when an event wakes you
  first or the loop ends.
- **Any other harness** with no way to wake itself: say what you're
  waiting for (CI, Copilot's review) and end the turn. Pick the loop up at
  that step when the Owner says it has landed.

## The hook

On Claude Code the plugin's `PostToolUse` hook
([`scripts/ship_pr_hook.py`](scripts/ship_pr_hook.py)) fires after any call
that may have opened a PR (`create_pull_request` on a GitHub MCP server,
`gh pr create`, a `gh api` POST to `pulls`) and tells the agent to carry
this loop on from step 2. It can't tell whether a conditional command
(`a || gh pr create`) actually ran, so first confirm a new PR exists from
that call; an existing PR doesn't count. It doesn't check whether the
skill is already running: if it is, carry on. `PERSONAL_SHIP_PR=0` in the harness environment turns it
off; ask the Owner rather than setting it yourself.
