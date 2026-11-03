# personal-codebase-review reference

## Log

`specs/reviews/README.md`, created by the first review:

```markdown
# Reviews

Reviews of the default branch, oldest first. What each kind covers and how
the log works: Gary's `codebase-review.md` standard. Remediation is tracked
in each review's issue.

| Review | Date | Kind | Range | Findings | Issue | Outcome | Record |
| --- | --- | --- | --- | --- | --- | --- | --- |
| r1 | 2026-11-03 | full | ..9d02f6a | 1 high, 4 medium, 2 low | #12 | open | [summary](2026-11-03-r1-full.md) |
```

The facts script reads rows that start `| r{N} |` and splits on `|`: keep
eight cells, short SHAs in Range, and no `|` inside a cell. An `estate` row
in a member repo has that member's own range and links the home record:
`[nowline-workspace r2](https://github.com/<owner>/nowline-workspace/blob/main/specs/reviews/<file>)`.

## Register

`{date}-r{N}-{kind}-findings.md`, written before the summary:

```markdown
# r7 incremental review: findings

- Kind: incremental
- Range: <full from SHA>..<full to SHA>
- Repo: garyrudolph/public
- Follows: r6
- Reviewers: correctness (/code-review high), drift, tests, duplication; Opus, high
- Verifier: dropped 3 of 11
- Accepted, not raised again: r3.f2, r5.f1

## correctness

### r7.f1 - <title>

- Severity: high
- Dimension: correctness
- Kind: fix
- Location: `path/file.go:88` at 9d02f6a
- Evidence: <what the code does, with the lines>
- Verified: <how the verifier confirmed it>
- Recommendation: <the change>
- Status: open
```

An estate register adds `- Members: <name> <from>..<to>, <name> <from>..<to>`
and `- Home: <owner>/<repo>` to the header; the next estate review reads its
members from there. Field lines keep the `- Name: value` shape; the facts
script reads `Severity`, `Kind`, `Status`, `Location`, `Reason` and
`Resolution`. `accepted` and `deferred` need a `- Reason:` line.

## Summary

`{date}-r{N}-{kind}.md`, derived from the register, and the review PR's body:

````markdown
Incremental review of `main` from 4be1c09 to 9d02f6a (34 commits, 2,140
changed lines), following r6. Register: `2026-11-03-r7-incremental-findings.md`.

## Review guide

Review tier: [skim], records only; the decisions below are the reading.
Verdict: 1 high, 4 medium, 2 low; 2 decisions for you.
Review time: ~6 min

## Decisions for you

1. **r7.f3 Retry policy lives in two places.** Now: `sync/` retries 3 times
   with its own backoff; `upload/` uses `internal/retry`. Proposed: both use
   `internal/retry`. Options: consolidate (recommended), or document why
   `sync/` differs.
2. ...

## Fix now

- r7.f1 high: retry loop in `sync/upload.go` swallows the final error
- r7.f2 medium: ...

## Since last review

...before/after Mermaid, only where structure changed...

## Rules changed

- Proposed: `AGENTS.md` "Retries go through `internal/retry`" (r5.f4, r7.f3)

<details>
<summary>Fix review</summary>

| Finding | Was | Now | By |
| --- | --- | --- | --- |
| r6.f2 | open | fixed | #130 |

</details>

<details>
<summary>Details by dimension</summary>

...low and info findings, what each reviewer covered...

</details>

Previously accepted, not raised again: r3.f2 (vendored parser), r5.f1 (CLI flag spelling).

Assisted-by: Claude Code
````

Keep the visible part near 250 words, and drop empty sections. A full
review replaces "Since last review" with "Architecture": the current shape
drawn from the code, beside the previous full review's when there is one.

## Issue

Title: `r7 incremental review: 1 high, 4 medium, 2 decisions`. Body:

```markdown
Review record: <link to the summary on the review PR's branch, then on main>

Decisions
- [ ] r7.f3 Retry policy lives in two places (recommendation: consolidate)

Fixes
- [ ] r7.f1 high: retry loop in `sync/upload.go` swallows the final error
- [ ] r7.f2 medium: ...

Remediation PRs cite the finding ID (`Fixes r7.f1`). The next review's fix
review records the outcome; don't edit `specs/reviews/` in a fix PR.
```

Low and info findings stay out of the issue.

## Terminal summary

```text
r7 incremental, main 4be1c09..9d02f6a (34 commits, 2,140 lines)
1 high, 4 medium, 2 low; 3 dropped by the verifier; 2 decisions
Fix review: r6.f2 fixed, r6.f5 still open
Record: specs/reviews/2026-11-03-r7-incremental.md (branch review/r7-incremental)
Next: open the review PR and issue?
```

## Reviewers

Fresh context, never the session that wrote the code. On Claude Code, the
`Agent` tool with the most capable model the session offers (Opus as of
2026-11), high effort for incremental, xhigh for full and estate and the
verifier. Each reviewer returns findings in the register's field shape, at
or above the floor: `medium` for full and estate, `low` for incremental.

## Dimension prompts

Every prompt starts with: the repo, the kind, the range or commit, where the
code at that commit is (`.scratch/r{N}/` or `git show <sha>:<path>`), the
specs and ADRs to read, the accepted findings, and "Report only what you can
show in the code at that commit, with the lines. No style nits. Fewer,
better findings."

| Dimension | Kinds | Asks |
| --- | --- | --- |
| correctness | incremental | The harness's range review; on Claude Code `/code-review high <from>..<to>` |
| drift | incremental | Did the range change a contract, schema, layer boundary or dependency direction? Is that in a spec, ADR or the PR's review guide? Does the code still match the specs it cites? |
| duplication | incremental, full | Code in the range (or tree) that repeats an existing helper, model, client or algorithm; one-use wrappers; dead code |
| tests | incremental, full | Behavior with no test that fails when it breaks; loosened or deleted assertions; tests that only check mocks |
| architecture | full | Draw the components and their dependencies from the code. Where does it diverge from the specs and ADRs? Cycles, layers skipped, ownership unclear |
| contracts | full | Every API, wire or file format, event, CLI flag and env var the repo exposes or consumes: versioned, documented, consistent with each other |
| security | full | Trust boundaries, authn and authz placement, secrets handling, input validation at the edges (security.md) |
| dependencies | full | Runtimes and libraries behind their latest stable or near end of life; pins that disagree across the repo |
| hotspots | full | Line-by-line on the facts' top hotspot files, as a correctness review |
| estate architecture | estate | Which repo owns which concept and contract; contracts between members that don't fit; responsibilities split or doubled across repos |
| estate duplication | estate | The same model, client, algorithm or config written in two or more members, worth sharing |

## Verifier

One fresh reviewer gets every candidate finding and the code at `<to>`, and
for each one tries to show it's wrong: find the guard, the test, the caller
that rules it out, or reproduce it. It returns `confirmed` with how, or
`dropped` with why. Only confirmed findings enter the register, and the
header records how many were dropped.

## Hotspots

`score = commits touching the file in the last 180 days × the file's lines
at <head>`, for files in the `source`, `orchestration`, `api` and `schema`
buckets (personal-review-guide's bucket table), top 15. Change the window
with `--hotspot-days`. A fixed sort, not a judgment: read the files, and
skip one whose size is data rather than logic.

## Harnesses

| Step | Claude Code | Codex | Cursor | Gemini CLI | GitHub |
| --- | --- | --- | --- | --- | --- |
| Range review | `/code-review high <from>..<to>` | `codex exec review --base <from>` from a checkout of `<to>`, or `--commit <sha>` | Agent with the range and the correctness prompt | `/code-review` extension on a branch at `<to>` | Copilot review covers PRs only |
| Dimension reviewers | `Agent` tool | subagents | `Task` | sequential prompts | n/a |
| Scheduled `status` | a cloud scheduled task, or `claude-code-action` on a cron workflow | a Codex cloud task | Automations | an Action on cron | Code Quality's scheduled scan, as an input |

The record, the log and the outputs are the same everywhere.

## Schedule (optional)

A monthly scheduled task runs this skill in `status` mode on each repo (or
`estate` status on the home repo) and, only when a review is due, runs it
through step 6, pushes the task branch, and reports; opening the PR and
the issue still waits for Gary. A due
review that no one opens is the signal that the cadence is wrong.
