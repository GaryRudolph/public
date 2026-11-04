# Codebase Review

How `main` gets reviewed after integration, beside the review of each change. [review.md](review.md) covers a change on its way in: its guide, its tiers, its fresh-context reviewer. This file covers what that can't see: drift across many changes, and across repos that coordinate. The `personal-codebase-review` skill runs it; `specs/codebase-review.md` in the public repo has the reasoning and sources.

Contents:

- [Kinds](#kinds): incremental, full, estate, interim
- [When](#when): milestone gates, complex changes, churn, an optional schedule
- [Anchors](#anchors): commits on the default branch only
- [The record](#the-record): `specs/reviews/`, the log, the register, the summary
- [Findings](#findings): fields, statuses, accepted findings
- [Outputs](#outputs): a review PR, a tracking issue, remediation PRs
- [Estates](#estates): several repos, with or without a workspace
- [Reviewers](#reviewers): fresh context, strongest model, verified findings
- [Closing the loop](#closing-the-loop): fix review, rules
- [Ownership](#ownership)

## Kinds

| Kind | Reads | Range | Logged |
| --- | --- | --- | --- |
| `incremental` | Every changed line since the anchor, plus drift on what changed | `<anchor>..<head>` of the default branch | Yes, and moves the anchor |
| `full` | Structure at one commit: architecture, contracts, boundaries, hotspots | `..<head>` | Yes, and moves the anchor |
| `estate` | Architecture across repos and major duplicated code between them | each member's `<anchor>..<head>` | Yes, in the home repo and in every member; doesn't move a member's anchor |
| `interim` | A branch before its PR, when a session wants one | merge-base`..HEAD` | No. A draft, removed before the PR opens |

**Incremental** is the line-level review. It runs the harness's range review over the commits since the anchor (Claude Code: `/code-review high <from>..<to>`), then a drift pass on what the range changed: a contract or schema altered, a layer reaching past its neighbor, a helper written again beside an existing one, a test loosened. It ends with the [fix review](#closing-the-loop). Above about 8,000 changed lines, it's still incremental: split the range into slices by path, each under the cap, and review every slice (see [Large ranges](#large-ranges)). A full review is no substitute, since it doesn't read the changed lines.

**Full** doesn't read every line; each line was read once as a diff. It reads structure: the architecture against the repo's specs and ADRs (draw it, from the code), every contract the repo exposes or consumes, module boundaries and the direction of dependencies, module-level duplication, test strategy (what has no tests that should, what's tested only through mocks), dependency and toolchain currency against end-of-life dates, and security posture at the design level (trust boundaries, where secrets live, who can call what). Then it reads hotspots, the files that are both large and frequently changed, line by line.

**Estate** is [below](#estates). **Interim** is the per-change review under another name: it lives where drafts live (`.scratch/`, or `specs/handoffs/{topic}-{word}-interim-review.md` on a runner) and goes when the handoff files go ([review.md](review.md) "The draft"). It never touches the log, because nothing it anchors to survives a squash merge.

## When

| Trigger | Kind |
| --- | --- |
| A repo adopts this standard (no log yet) | `full` |
| `m{N}` lands on the default branch and `m{N+1}` follows | `incremental`, run by the session that starts `m{N+1}`, before planning it ([plan-execution.md](plan-execution.md) "Review gate") |
| A `[study]`-tier PR, or a plan with an `[xdeep]` step, merges | `incremental`, as a follow-up card |
| A plan that shipped as one PR merges | `incremental`, from the plan's Completion summary |
| More than about 8,000 changed lines since the anchor | `incremental`, split into path slices ([Large ranges](#large-ranges)) |
| Before a major release, or after a large migration | `full` |
| Repos that coordinate each reached a milestone, or the cross-repo shape changed | `estate` |
| Optional schedule, at most monthly | `status`, then `incremental` only if it's due |

A review is **due** when the anchor is 30 or more days old and anything changed since, or when a trigger above fired and no review covers it. `status` reports the facts (days, commits, changed lines since the anchor) and says whether one is due; on a schedule, it does nothing when none is.

### Large ranges

A range over the cap is split, never skipped or traded for a full review. The facts script prints changed lines by directory; group directories into slices that each stay under about 8,000 changed lines and keep together what a reviewer would read together (a contract and its handlers, a migration and the code reading the new column). Generated and vendored paths get no slice. Show the slices, with their line counts, and wait for a yes before reviewing. Each slice gets its own correctness review of `<from>..<to>` limited to its paths; the drift, tests and duplication passes still look across the whole range, since drift crosses slice lines. It's one review: one `r{N}`, one register listing the slices in its header, one summary, one log row.

## Anchors

An anchor is a full commit SHA on the default branch. A logged review covers `<from>..<to>`, both on the default branch, and the next incremental starts at the last logged `<to>` of an `incremental` or `full` row. Review `origin/<default>` at a fetched SHA, and read the log and registers from it too, never from a task branch: squash merges erase a branch's commits, so its SHAs can't anchor anything. If the last anchor isn't reachable from the default branch (a force-push, a rewritten history), say so in the summary and run a full review.

## The record

```
specs/reviews/
  README.md                              # the log, one row per review
  2026-11-03-r7-incremental.md           # the summary, for humans
  2026-11-03-r7-incremental-findings.md  # the register, the detail
```

Reviews are numbered `r{N}` per repo and findings `r{N}.f{K}`, as milestones and steps are ([documentation.md](documentation.md) "Implementation Milestones"). Files are `{date}-r{N}-{kind}.md` and `{date}-r{N}-{kind}-findings.md`; the date first keeps them in order without padding. `specs/reviews/` isn't a scratch folder: everything in it lands on the default branch.

### The log

`specs/reviews/README.md` opens with one line saying what the folder is and links this standard, then holds one table, oldest row first:

```markdown
| Review | Date | Kind | Range | Findings | Issue | Outcome | Record |
| --- | --- | --- | --- | --- | --- | --- | --- |
| r6 | 2026-09-28 | full | ..4be1c09 | 2 high, 6 medium, 3 low | #88 | 9 fixed, 2 accepted | [summary](2026-09-28-r6-full.md) |
| r7 | 2026-11-03 | incremental | 4be1c09..9d02f6a | 1 high, 4 medium | #123 | open | [summary](2026-11-03-r7-incremental.md) |
| r8 | 2026-11-20 | estate | 9d02f6a..c41e0b7 | 1 medium here | #131 | open | [nowline-workspace r2](https://github.com/<owner>/nowline-workspace/blob/main/specs/reviews/2026-11-20-r2-estate.md) |
```

- **Range**: short SHAs in the table; the summary carries the full ones. A full review's range is `..<to>`.
- **Findings**: counts by severity, `none` when there were none.
- **Outcome**: `open` until a later review's fix review sets it, then the counts by status.
- **Record**: the summary, or for an estate row in a member repo, the home repo's record.

### The register

Written first, by the reviewers and the verifier. The intent line (kind, range with full SHAs, scope, reviewer model), then one `###` per finding in [Findings](#findings) form, grouped by dimension, highest severity first.

### The summary

Written second, from the register, for a human who has about 2 minutes. It follows [review.md](review.md) "Description layout" (a visible part near 250 words, a collapsed block per area, Mermaid only where structure changed, readable on a phone), with these sections:

- **Intent**, no heading: the kind, the range, the scope, and the previous review it follows.
- **Verdict**: one line, with the counts by severity and the review time to read it.
- **Decisions for you**: each finding of kind `decision`, numbered, with the current state, the proposed state, the options, and a recommendation. This is the before/after: what the code does now and what it would do.
- **Fix now**: findings of kind `fix` at high or medium, one line each with its ID.
- **Since last review**: what changed shape between `<from>` and `<to>`, before/after diagrams drawn from each commit ([review.md](review.md) "Diagrams"). A full review draws the current architecture instead, against the previous full review's if there is one.
- **Rules changed**: rules this review added or proposes (see [Closing the loop](#closing-the-loop)).
- **Fix review**, collapsed: the previous reviews' open findings and their new status.
- **Details**, collapsed, one block per dimension: low and info findings, and what each reviewer covered.
- **Previously accepted**, last: `Not raised again: r3.f2, r5.f1`, with titles.

Drop a section with nothing to say.

## Findings

```markdown
### r7.f2 - Retry loop in `sync/upload.go` swallows the final error

- Severity: high
- Dimension: correctness
- Kind: fix
- Location: `sync/upload.go:88` at 9d02f6a
- Evidence: after the third retry the error is logged and `nil` is returned; `TestUploadFails` asserts only the log line.
- Verified: reproduced with a fake that always fails; the caller marks the upload done.
- Recommendation: return the wrapped error after the last attempt, and assert it in the test.
- Status: open
```

| Field | Values |
| --- | --- |
| Severity | `high` (wrong behavior, data loss, a security hole, a broken contract), `medium` (likely to cause one, or significant drift), `low` (cost or clarity), `info` (worth knowing, no action) |
| Kind | `fix` (the answer is clear) or `decision` (more than one reasonable answer, and it's Gary's call) |
| Status | `open`, `fixed`, `decided` (a decision was made; link it), `accepted` (won't change; reason required), `deferred` (later; reason and the trigger to revisit) |
| Resolution | The PR, commit, issue comment or ADR that changed the status |

**Accepted findings** are a decision not to change something. They're handed to every later reviewer as known, with their reason, and listed under "Previously accepted" instead of raised again, unless the code at their location materially changed since, in which case the new finding cites the old ID. The registers are the only list; the skill's facts script collects them.

## Outputs

A review produces three things, in this order:

1. **The review PR**, on a task branch off the default branch: the register, the summary, the log row, and the fix review's status updates to earlier registers. Its description is the summary, which carries the `## Review guide` heading and the `Review tier: [skim]` line the PR body guard needs (nothing in it changes behavior). Opening it waits for Gary, as any PR does. Nothing else rides in it: no fixes.
2. **A tracking issue**, titled `r{N} {kind} review: <verdict>`, listing each decision and each fix as a checklist item with its ID and a link to the register. Its number goes in the log row. Opened with the PR, when Gary asks for the PR.
3. **Remediation PRs**, ordinary changes with ordinary review guides, each citing the finding IDs it addresses (`Fixes r7.f2`) and checking off the issue. They don't edit `specs/reviews/`; the next review's fix review records the outcome.

Low and info findings stay in the register and don't get checklist items.

## Estates

An estate is several repos that coordinate: a product split across services, an OSS core and its commercial repos. The estate review reads what no single repo's review can see: which repo owns what, whether the contracts between them still fit the architecture, and major duplicated code (the same model, client or algorithm written in two repos). It doesn't read lines; each member's incremental does that. Breaking changes to a contract between repos belong in CI gates on each repo (`buf breaking`, oasdiff, Pact), not here.

**Members**, first match wins:

1. A workspace's `repos.mk` ([makefile.md](makefile.md)), when run from one.
2. The member list in the previous estate review's register.
3. A list or wildcard from Gary (`nowline*`), matched against the folders beside the home repo (inside it, for a workspace) and the owner's repos through `gh`. Where `gh` can't list them (a runner bound to its own repos), use the harness's repo listing, or ask. Show the resolved list and wait for a yes before reviewing.

No workspace repo is required. **Home**: the workspace if there is one, else the repo Gary names, by default the one the session runs in. The home repo holds the register, the summary, an `estate` row in its log, and the tracking issue.

**Every member logs it too**: an `estate` row in its own `specs/reviews/README.md`, with its own range, the findings that land in it, and a link to the home record. The row doesn't move the member's incremental anchor. Each member's row lands through a small PR in that repo (its body: the skill's member template), and a finding that needs work in a member gets its issue there, linked from the home issue. A workspace home's allowlist `.gitignore` needs `!/specs`.

## Reviewers

- **Fresh context**: the session or subagent that reviews didn't write the code. The author's account (the review guide, the plan) is input, not evidence.
- **The strongest model the harness has**, at high effort for incremental and xhigh for full and estate reviews. A second model family isn't required: on code, a fresh session of the same model does as well, and reviewer strength matters more than family.
- **By dimension**: correctness (the range review), security, architecture and spec drift, duplication and code health, tests, docs, dependencies. Each reviewer gets the dimension, the range or scope, the repo's specs and ADRs, the accepted findings, and a severity floor. Fewer than 10 reviewers per review.
- **Verified**: a separate pass tries to disprove each finding before it enters the register: reproduce it, find the test that covers it, or read the code that rules it out. A finding it can't support is dropped, and the register says how many were. A reviewer asked to find problems always finds some, so a finding has to earn its place.

## Closing the loop

A log that only accumulates findings changes nothing. Two habits keep it working:

- **Fix review**: every review starts by reading the previous reviews' open findings, sets each one's status from its issue, PRs and the code at `<to>`, and writes it back in the review PR: the `Status:` and `Resolution:` lines in the earlier register, and that review's Outcome cell in the log. The register is the only place later reviews read status from. A finding fixed in the code with no PR citing it is still `fixed`; one with a closed checkbox and unchanged code is still `open`.
- **Rules**: when a finding class shows up in two reviews, or three times in one, the answer is a rule, not another fix: a line in the repo's `AGENTS.md` or `REVIEW.md`, a lint rule, a CI check, or a proposal for these standards. The summary's "Rules changed" names it.

## Ownership

The reviewers' findings are a sensor, not a verdict, and never count as a person's review. Decisions are Gary's: the summary recommends, and the decision is recorded (an issue comment, or an ADR when it's architectural) before its finding moves to `decided`. Whoever runs the review reads the summary before asking to open the PR: a confident, wrong review is worse than none.
