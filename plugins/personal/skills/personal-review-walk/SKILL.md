---
name: personal-review-walk
description: >-
  Walk the Owner through a review's outcomes one item at a time: a short
  one-paragraph overview of a single decision, finding or recommendation,
  then the choices for that item alone in a dialog, the answer recorded,
  then the next item. Answers go into a walk file in specs/handoffs/ that is
  committed (and on a runner pushed) after every answer, so a respawned
  session resumes at the first open item. Ends with a tally, one summary on
  the source, and remediation cards for the fixes. Sources: a
  personal-codebase-review tracking issue and its findings register, a PR's
  review comments, /code-review output, a plan's open questions. Triggers:
  "walk me through the findings", "go through the decisions", "one by one",
  "triage the review", "let's go through issue #N", "continue the walk",
  "where were we".
---

# personal-review-walk

The Owner decides; this skill paces it. One item per turn, so each answer
gets the Owner's full attention and nothing is decided in a batch by
default.

## Start

1. **Find a walk already under way.** Look for `specs/handoffs/walk-*.md`
   (on a workstation's shared branch, `.scratch/walk-*.md`) whose `Source:`
   matches. If one exists, this is a resume: skip to "Each item" at its
   first `Outcome: pending` item, or to "End" when none is pending (its
   `skipped` items still get their second pass). Trust the file, not the conversation: a
   respawned or summarized session may remember answers the file never got,
   and the file wins.
2. **Collect the items.** From a tracking issue, its checkboxes, with each
   finding's full entry from the register it links (on the review branch if
   the review PR hasn't merged). From a PR, its unresolved review threads
   that need the Owner's call. From `/code-review`, its findings. From a
   plan, its open questions. Skip items that already have an outcome at the
   source (a ticked box with a PR link, a resolved thread).
3. **Order them.** The source's order when it gives one (a tracking issue
   lists decisions first, then fixes in its stated order). Otherwise
   decisions first, then by severity, keeping items that touch the same
   files next to each other.
4. **Write the walk file** before the first question, every item snapshotted
   as pending, so the order survives a respawn. Commit it (see "Save every
   answer"). Say how many items there are and roughly how long it'll take.

## The walk file

`{project-root}/specs/handoffs/walk-{topic}-{word}.md`, named like a
handoff (`personal-handoff`; `{topic}` such as `r1-full`). On a
workstation's shared branch, where nothing gets committed without a yes,
`.scratch/walk-{topic}-{word}.md` instead.

Which branch: a task branch with no open PR, or, when the items are a PR's
own review threads, that PR's branch. Never a review PR's branch: nothing
else rides in a review PR (codebase-review.md), and it can merge mid-walk.
After `personal-codebase-review`, that means a new task branch (on a
runner, a new session, queued as a card) or waiting until the review PR
merges.

```markdown
# Walk: r1 full review

Source: #45, register specs/reviews/2026-11-04-r1-full-findings.md at 3f2c1a9
Order: decisions, then fixes in the issue's installer order
Status: 3 of 26 recorded; next r1.f17

## r1.f18 No CI runs `make test` on agent-authored PRs
Kind: decision
Outcome: decided: required test.yml on Ubuntu with sops and age; macOS job non-blocking
Note: macOS stays advisory until it's under five minutes

## r1.f17 Installer configures ~/.claude, sessions run from ~/.claude-lolay
Kind: decision
Outcome: pending
```

`decided`, `accepted` and `deferred` are the register's own statuses, so
the next review's fix review can set them from the posted summary as
written. `fix` leaves the finding `open` until a remediation PR fixes it,
and `skipped` is the walk's own and never leaves it:

| Outcome | Meaning | Register |
| --- | --- | --- |
| `decided: <choice>` | A decision taken; the choice in a few words | `decided` |
| `fix` or `fix: with <id>` | Queue a remediation; `with` groups items that land in one PR | `open` |
| `accepted: <reason>` | Won't change; the reason is required. A finding the Owner thinks is wrong is `accepted: not a defect, <why>` | `accepted` |
| `deferred: <reason>; revisit when <trigger>` | Later, with what brings it back | `deferred` |
| `skipped` | Come back to it at the end | `open` |

`Note:` holds anything the Owner added beyond the choice, in their words.

## Each item

**The overview, one paragraph.** What's wrong or what's being decided,
where (file and line, or the contract), what it costs if left alone, and
the recommendation with its reason. Read the code at its location at the
current head first: if it changed since the review and the item looks
already fixed, say so and offer that as the first option. Keep it to what
the choice needs; link the register entry for the rest.

**The choices, in a dialog.** One `AskUserQuestion` call, for this item
only, with the recommended option first and marked `(Recommended)`. For a
decision, the real alternatives (up to three) plus `Defer`. For a fix,
`Queue a fix`, `Group with <id>` when a neighbour lands in the same files,
`Accept as is` and `Defer`. Up to four questions in the call, all about
this item (which option, and which PR it rides with). The dialog can cover
the message, so the question names the item's ID and title and the
trade-off in a clause. Never put a second item's question in the call.

**The answer.** A pick records its outcome. Words under "Other" are the
Owner's answer: record what they chose, put their words in `Note:`, and
ask again only if the choice is unclear. A question back is a conversation
turn: answer it and ask again. A dismissed or empty dialog records nothing
(fail closed): ask again. "Skip" records `skipped`.

## Save every answer

After each answer and before the next item's overview:

1. Update the item's `Outcome:` and `Note:` lines and the `Status:` line.
2. On a task branch (always, on a runner), commit only the walk file:
   `record r1.f18 outcome: decided` (72-character subject, the usual
   trailers).
3. On a runner, push. A rejected push gets the usual retries; if it still
   fails, stop and say so before asking anything else, since an unpushed
   answer dies with the container.

The next question may be the container's last turn, which is why the push
comes before it, every time. On a workstation's shared branch nothing is
committed; the `.scratch/` file holds the state.

## End

1. **Skipped items.** Walk each `skipped` item once more. A second skip
   leaves it `skipped`, listed in the tally.
2. **Tally.** Counts by outcome and the `fix` groups, as one short block.
3. **One choice dialog** for what happens next, each a separate question:
   - Post the outcomes to the source: on a tracking issue, one comment
     listing every item's outcome and note (the next review's fix review
     can cite it as the `Resolution:` for `decided`, `accepted` and
     `deferred` findings), ending with the GitHub comment footer; on a PR,
     a reply on each thread. Don't tick checkboxes: a tick means a
     remediation PR opened.
   - Queue the remediation: one card per `fix` group, as
     `personal-codebase-review` "Show it" describes (finding IDs, the
     tracking issue, fix claims, no branch named).
   - Record a decision that sets a lasting rule as an ADR or a spec edit,
     on the walk's task branch, shipped with `personal-ship-pr`. A walk
     that ran on a workstation's shared branch proposes a task branch
     first (core.md "Cut a task branch off a shared branch").
4. **The walk file.** Once its content is posted or promoted, `git rm` it
   and commit (on a runner, push); on a workstation's shared branch,
   delete the `.scratch/` file and commit nothing. A walk on a PR's branch
   removes it in its last push; `personal-ship-pr`'s merge-ready check
   catches one left behind. If the branch ends with no net change, say so:
   deleting it is the Owner's call.

## Don't

- Don't batch items into one dialog, or decide one the Owner skipped.
- Don't start fixing mid-walk. A `fix` outcome queues work; the walk keeps
  going.
- Don't edit `specs/reviews/`. The register's status is the next review's
  call; the walk's outcomes reach it through the source.
- Don't post to GitHub item by item. The commits carry the state; the
  source gets one summary at the end, after the Owner says yes.
