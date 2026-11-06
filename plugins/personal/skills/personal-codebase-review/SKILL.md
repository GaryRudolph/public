---
name: personal-codebase-review
description: >
  Review the default branch rather than a diff: an incremental review of
  every line since the last logged review (Claude Code's /code-review on
  the commit range, plus a drift pass and a fix review of open findings), a
  full review of architecture, contracts, boundaries and hotspots at one
  commit, or an estate review of architecture and duplicated code across
  repos that coordinate, with or without a workspace repo. Writes a
  findings register and a PR-shaped summary to specs/reviews/, logs the
  review with its commit range so the next incremental knows where to
  start, and drafts the review PR and a tracking issue; remediation is
  separate. Modes: status, incremental, full, estate, interim. Triggers:
  "review main", "codebase review", "full review", "incremental review",
  "review since the last review", "estate review", "review across repos",
  "is a review due", a milestone's review gate, and after a [study]-tier
  PR or an [xdeep] step merges.
---

# personal-codebase-review

Runs [`../personal-standards/standards/codebase-review.md`](../personal-standards/standards/codebase-review.md),
which says what each kind covers, when one is due, what the record looks
like, and what the outputs are. Read it first; this file doesn't repeat it.
[`reference.md`](reference.md) has the templates, the dimension prompts, the
hotspot formula, and the harness table.

This is a review of `main`, not of a branch. A branch's own review is the
PR's job ([`personal-review-guide`](../personal-review-guide/SKILL.md) plus a
fresh-context `/code-review`); `interim` mode only names that review and
puts its draft where drafts go.

## Modes

| Mode | Does | Writes |
| --- | --- | --- |
| `status` | Reports the last review, the anchor, days and churn since, and whether a review is due | Nothing |
| `incremental` | Line-level review of `<anchor>..<head>`, drift pass, fix review | Register, summary, log row |
| `full` | Architecture, contracts, boundaries, hotspots at `<head>`, fix review | Register, summary, log row |
| `estate` | Architecture and duplication across member repos | Register and summary in the home repo, a log row in every member |
| `interim` | The branch's own review before its PR | A draft in `.scratch/` or `specs/handoffs/`, removed before the PR opens |

With no mode, run `status` and propose one.

## Procedure

### 1. Facts

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT:-<plugin root>}/skills/personal-codebase-review/scripts/review_log_facts.py" [--members <list|glob>] [<repo>]
```

It fetches the default branch (unshallowing a shallow clone, so anchors and
hotspots are real) and reads the log and registers from it, not from the
checked-out branch. It prints, per repo: the default branch and
its head SHA, the log's rows, the last anchor and whether it's still on the
default branch, days and changed lines since it by bucket, hotspots, the
open, accepted and oddly-statused findings in earlier registers, unmerged
`review/r*` branches, the last estate's members, and the next `r{N}` (past
any unmerged review). A `found=outside local history` anchor means the fetch
couldn't deepen: fix that, don't fall back to a full review. From a workspace it reads `repos.mk` and looks
for each member inside the workspace, then beside it (how a runner clones
repos), and says which matched; with `--members`
it matches names or a glob against the folders beside the repo (for a
workspace, inside it and then beside it) and, with
`gh`, the owner's GitHub repos; a `github: error` line means `gh` couldn't
list them (a runner bound to its own repos), so use the harness's repo
listing (`list_repos`) or ask. It decides nothing.

### 2. Choose

Apply the standard's "When" table to the facts. Say which kind and why in
one line. `status` stops here. Switch to `full` only when there's no log or
the anchor isn't reachable from the default branch. A large range stays
incremental: over about 8,000 changed lines, propose path slices from the
facts' `since_anchor_by_dir` (each under the cap, related paths together,
generated and vendored paths left out), show them with their line counts,
and wait for a yes (the standard's "Large ranges").

For `estate`, settle members and home before anything else: `repos.mk`,
else the last estate's members, else ask the Owner for a list or wildcard (a
plain question, since the answer is open) and re-run the facts with
`--members`. Show the resolved list (cloned, on GitHub only) and the home
repo, and wait for a yes in the choice dialog. Members that aren't cloned
are cloned read-only into `.scratch/estate/` for the review, or, on a
runner, attached first (`add_repo`) when the harness allows it.

### 3. Branch

The record lands through a PR, so it's written on a task branch cut from the
fetched default branch (core.md "Cut a task branch off a shared branch"):
`review/r{N}-{kind}`, or the harness's assigned branch. In an estate, the
home repo and every member get their own branch. Never review the checked-
out branch's working tree: read the default branch at its head SHA
(`git show <sha>:<path>`, `git archive <sha> | tar -x -C .scratch/r{N}`).

### 4. Review

Dispatch fresh-context reviewers, one per dimension, fewer than 10, on the
strongest model the harness has (reference.md "Reviewers"). Each gets its
prompt from reference.md "Dimension prompts", the range or scope, the
repo's specs and ADRs, the accepted findings (id, location, reason) as
known and not to be raised again unless the code there changed, and the
severity floor.

- `incremental`: correctness is the harness's range review. On Claude
  Code, run `/code-review high <from>..<to>` (xhigh for a range over about
  2,000 changed lines); elsewhere, reference.md "Harnesses". A split range
  gets one correctness review per slice, limited to the slice's paths
  (reference.md "Slices"). Then the drift, tests and duplication reviewers
  on the whole range.
- `full`: architecture, contracts, boundaries, test strategy, dependencies
  and security posture over the whole tree at `<to>`, then hotspots: the
  facts' top files, line by line.
- `estate`: one reviewer for architecture across the members (who owns
  what, the contracts between them), one for duplicated code across them.
  No line review.

Then one verifier, also fresh, tries to disprove each finding (reference.md
"Verifier"). Drop what it can't support; keep the count.

### 5. Fix review

For every open finding in the facts, read its issue and any PR citing its
ID, and the code at its location at `<to>`. Set the new status per the
standard and write it back in this review's PR: the `Status:` and
`Resolution:` lines in the earlier register, and the Outcome cell of each
earlier review touched. Report `other_status_findings` too, and normalize
their status while you're there.

### 6. Write the register, then the summary

The register first, from the verified findings (reference.md "Register").
Then the summary, derived from the register (reference.md "Summary"): it
follows review.md's layout and the standard's sections, with the
decisions as before/after and a recommendation each, diagrams only where
structure changed (before at `<from>`, after at `<to>`, review.md
"Diagrams"), and "Previously accepted" last. Add the log row; create
`specs/reviews/README.md` from reference.md "Log" if it's missing. In an
estate, write each member's `estate` row too.

Name findings that recur (twice across reviews, or three times in this one)
and propose the rule in "Rules changed". Write rules only to the repo under
review, and only as part of this PR when they're a line in its `AGENTS.md`
or `REVIEW.md`; anything else is a decision.

### 7. Show it

Publish the summary as an Artifact page where the harness has one, and
print the terminal summary (reference.md). Commit the record on the task
branch (on a runner, push). Then ask, in one choice dialog, whether to open
the review PR and the tracking issue. The PR body is the summary, with its
`Review tier: [skim]` line; the issue follows reference.md "Issue" and its
number goes back into the log row in a follow-up commit. The PR body guard
needs both the `## Review guide` heading and the `Review tier:` line; the
summary template has them. In an estate, the home PR and issue first, then
one PR per member, each with its log row, a body from reference.md "Member
PR", and the member's own issue for findings that land there.

Remediation isn't part of this run. Offer to start it, as separate PRs that
cite finding IDs: one card or session per group of findings that land
together, handed over as plan-execution.md "Handing work to another
session" says, each prompt behind its header (the repo the findings land
in, the model for the fix's tier). Remediation PRs don't wait on each
other, so none is numbered, and all can start at once. A remediation
prompt names no branch to cut: "work on your assigned branch (on a
workstation, cut `fix/<slug>` off the default branch)" (git.md "Task
branches and shared branches").

## Interim

`interim` reviews the current branch before its PR: run `/code-review` (or
the harness's equivalent) on the merge-base`..HEAD`, verify as above, and
write `{topic}-{word}-interim-review.md` where the review guide's draft
goes (review.md "The draft"). Fix what's clear on the branch. It's removed
with the handoff files before the PR opens and never enters the log.

## Don't

- Don't review a task branch and log it: squash merges erase its SHAs.
- Don't fix findings in the review PR. Remediation is its own PRs.
- Don't raise an accepted finding again unless the code under it changed;
  cite the old ID when it did.
- Don't let the reviewer that wrote the code review it, and don't count an
  agent's review as a person's.
- Don't decide a `decision` finding. Recommend, and wait for the Owner.
