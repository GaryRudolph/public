---
name: personal-review-guide
description: >
  Write the review guide for an agent-made change so a human understands it
  in about 2 minutes on a phone: tag each area [study], [check], [skim] or
  [skip], set the PR's tier (the highest tag), blast radius and review time,
  read the code at the base commit and at head, draw before/after Mermaid
  only where structure changed, run the repo's own review surfaces, and
  write the PR description, collapsible by tier. Three modes: plan (the
  shape of the change, previewed when cheap), walkthrough (the draft
  description before asking to open a PR), pr (publish or refresh the
  description). Triggers: "walk me through it", "explain the change",
  "review guide", "write the PR description", "before and after", "what
  should I review", before asking to open a PR, and when a plan changes a
  contract, a flow, a schema or a review surface.
---

# personal-review-guide

Runs the procedure in
[`../personal-standards/standards/review.md`](../personal-standards/standards/review.md),
which says what a good guide looks like: the tiers and their checklists,
the description layout, evidence, diagrams, the plan-time preview, review
surfaces, and the draft. Read it first; this file doesn't repeat it.
[`reference.md`](reference.md) has the bucket table, the diagram recipe, the
review time arithmetic, and the shapes of the plan section and the terminal
summary.

Harnesses already write PR bodies, so this isn't a template. What it adds
is the reading: the guide comes from the code at the base commit and at
head, the tags come from the standard's checklists, and the before/after is
drawn or rendered, never recalled.

## Modes

| Mode | When | Writes |
| --- | --- | --- |
| `plan` | A plan changes a contract, a flow, a schema, or a review surface | A "Shape of the change" section in the plan |
| `walkthrough` | The work is done and you're about to ask to open a PR, or Gary asks for a walkthrough | The draft, shown as an Artifact page where the harness has one, plus the terminal summary |
| `pr` | Opening a PR, or a push that changes a tagged area, the tier, or the evidence | The PR description, from the draft |

Not every turn needs a walkthrough. The pre-PR one is the one that counts.

## Procedure

### 1. Facts

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT:-<plugin root>}/skills/personal-review-guide/scripts/review_facts.py" [--base <ref>] [--committed]
```

It prints the base and merge-base, commits, each changed file with
`+added -deleted`, its bucket, totals, test lines removed, paths naming a
sensitive area, the repo's review surfaces (and other `AGENTS.md` or
`CLAUDE.md` headings about before/after, renders or snapshots), the PR
template, and the plan, handoff and review files. Use `--committed` in `pr`
mode, so the guide describes what's pushed. In `plan` mode the diff is
usually empty: work from the plan and the base code.

Buckets are path hints, not tags. A `source` file can be `[study]` and an
`api` file `[skim]`.

### 2. Group and tag

Group the changed files into areas, by what a reviewer would read
together: a contract and its handler, a migration and the code that reads
the new column. Tag each with the review.md checklists, deepest first, with
default-up bias. A review surface's `Tag` is the floor for any area that
touches it. Read every file in a `[study]` or `[check]` area; for `[skim]`
read enough to be sure nothing in the checklists applies; for `[skip]`,
name the tool that produced it.

### 3. Read base and head

For each `[study]` and `[check]` area, read the code at the merge-base
(`git show <merge_base>:<path>`) and at head. The before side of every
table and diagram comes from the base read, not from the plan or memory.

### 4. Draw and render

- Contracts: a before/after table, three or four narrow columns.
- Control flow, lifecycle, data: a before/after Mermaid pair, only where the
  structure changed (reference.md "Diagram recipe").
- Review surfaces: run each surface the change touches, per its `Render`
  and `Before` lines, into `.scratch/`. Never switch branches or add a
  worktree to get the before; use the surface's own recipe, or
  `git archive <merge_base> | tar -x -C .scratch/base`. In `plan` mode
  follow the surface's `Preview` (`if-cheap` when omitted).

### 5. Tier, blast radius, review time

The PR tier is the highest area tag. Write the blast radius as who or what
breaks and how reversible it is. Estimate the review time with the
arithmetic in reference.md; above about 30 minutes, say so and propose a
split.

### 6. Write the draft

Follow review.md "Description layout": intent, `## Review guide`,
Validation, Rollback, then one `<details>` per tier, deepest first, with
`[study]` open, then Decisions. Validation lists only what ran, with
results, and `not run` with a reason for the rest. Keep the visible part
near 250 words.

The draft goes where plans go, named after the plan with `-review` added
(review.md "The draft"): `specs/handoffs/plan-{topic}-{word}-review.md` on a
runner, committed and pushed with the step, or `.scratch/` on a
workstation; `{topic}-{word}-review.md` when there's no plan. Overwrite it
on every run.

If the repo has a PR template, keep its sections and order, and put the
review guide's sections in after the intent; an AI assistance or trailer
section stays last.

### 7. Show it

- `plan`: put the "Shape of the change" section in the plan (reference.md)
  and let it ride the plan's approval. If the preview isn't cheap, write
  `Preview skipped: <reason>; before/after at completion`. A surface with
  `Preview: required` stops for agreement before implementing.
- `walkthrough`: publish the draft as an Artifact page when the harness
  has one (it renders Mermaid and can embed rendered images), and print the
  terminal summary (reference.md). Without Artifacts, print the summary and
  the draft's path.
- `pr`: opening a PR waits for Gary's ask, as always. When he asks, the
  description is the draft, with the trailer paragraph last. On later
  pushes to a PR this session opened or drives, regenerate the draft and
  update the description when a tagged area, the tier, or the evidence
  changed, and say in the report what changed in the guide. On Claude
  Code's cloud proxy use REST (`gh api` or the GitHub MCP tools), not
  `gh pr create`, which goes through GraphQL.

The personal plugin's PreToolUse hook denies creating a PR whose body has
no `## Review guide` heading or `Review tier:` line. A repo or machine that
doesn't want it sets `PERSONAL_REVIEW_GUIDE=0` in the harness environment.

## Don't

- Don't describe a check that didn't run as passing, or draw a before from
  memory.
- Don't pad: drop sections and tiers with nothing to say.
- Don't review your own change and call it reviewed. The guide is the
  author's account; a fresh-context reviewer (Claude Code Review,
  `/code-review`, a subagent) checks the code against it.
