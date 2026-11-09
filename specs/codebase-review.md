# Codebase review

Why the standards add a review of `main`, separate from the review of each
change, how it's shaped, and the evidence behind the choices. The rules are
in `standards/codebase-review.md`; the `personal-codebase-review` skill runs
them.

## Problem

Every review the standards had was per change. `personal-review-guide`
writes the PR guide, a fresh-context reviewer (`/code-review`, Claude Code
Review, a subagent) checks the diff, and orchestrated plans review each wave
and read the whole plan's diff once in the consolidation step. Each of those
sees one change. Nothing looks at `main` after integration, so the drift no
single PR shows goes unseen: architecture wandering from the specs and ADRs,
helpers duplicated across PRs that never saw each other, tests thinning one
loosened assertion at a time, sibling repos diverging.

Agents make this worse in a measurable way. GitClear's 2025 study (211M
lines) found copy-pasted lines rising from 8.3% to 12.3% while moved
(refactored) lines fell from 25% to under 10%, the first time copy-paste
exceeded refactoring. Thoughtworks has rated "complacency with AI-generated
code" Hold in three straight Radar volumes.

## Recommendation

Three layers, each with one job:

| Layer | Reviews | When | Lives in |
| --- | --- | --- | --- |
| Per change | A branch's diff, line by line | Each PR, each plan wave | The PR; `interim` drafts are removed before it opens |
| Incremental | `main` since the last anchor, line by line plus drift | A milestone lands, a complex change merges, churn passes a threshold | `specs/reviews/` |
| Full | `main` at a commit: architecture, contracts, boundaries, hotspots | Adoption, before a major release, when the anchor is lost | `specs/reviews/` |

An **estate** review runs across several repos that coordinate (nowline's
OSS and commercial repos, say) and looks only at architecture across them
and major duplicated code. It needs no workspace repo: members come from a
`repos.mk`, the previous estate record, or a list or wildcard the Owner gives.

Each review produces two documents, the findings register first and a
summary derived from it, lands them in a PR whose body is the summary, opens
one GitHub issue to track the work, and leaves remediation to its own PRs.
The log in `specs/reviews/README.md` records each review's commit range, so
the next incremental knows where to start.

## Decisions

- **Reviews of `main` only.** Repos merge by squash, so a task branch's
  commits vanish at merge and can't anchor anything. A per-change review
  stays with its PR, as before; an optional `interim` review goes where
  drafts go and is removed with them.
- **Full is architectural, incremental is line-level.** Reading every line
  of a codebase is neither affordable nor useful once each line was reviewed
  as a diff. A full review reads structure (architecture against specs and
  ADRs, contracts, module boundaries and dependency direction, test
  strategy, dependency currency, security posture) and samples hotspots,
  files that are both large and frequently changed. An incremental review
  reads every changed line since the anchor, which is what `/code-review`
  is built for.
- **Estate reviews stay architectural.** Contract breakage between repos is
  a CI gate's job (`buf breaking`, oasdiff, Pact `can-i-deploy`), not a
  periodic review's. The estate review asks which repo owns what, whether
  the contracts between them still make sense, and where the same code has
  been written twice.
- **Each member repo logs the estate review too**, in an `estate` row
  numbered in its own sequence. The row doesn't move the member's
  incremental anchor, since an estate review doesn't read lines.
- **Estate findings are delegated by name, not linked.** A finding that
  needs work in a member is copied into that member's register under the
  member's own ID, with `Estate: nowline-workspace r2.f3`; the home finding
  lists `Contained: nowline-core r8.f1, ...`. Each repo then tracks, fixes
  and verifies its share on its own, with no PR crossing repos, and the
  next estate review rolls the members' statuses up into the home.
- **Remediation is separate.** The review PR records what was found; the
  issue is the work queue; fixes are ordinary PRs that cite finding IDs. A
  fix PR adds one claim file per finding (`specs/reviews/r7/f2.md`), so
  what's been addressed is visible in the repo without opening the issue,
  and parallel fix PRs never touch the same file. A claim isn't a status:
  the next review's fix review reads it with the issue and the code, sets
  the status in the register, and deletes it. Fix PRs touch nothing else in
  `specs/reviews/`, so the fixer never grades its own work and the log row
  never conflicts.
- **Accepted findings stay accepted.** A finding marked `accepted` with a
  reason is handed to the reviewers as known and listed at the bottom of
  the summary, not raised again unless the code under it changed.
- **Recurring findings become rules.** A log that only accumulates findings
  is a graveyard. When a finding class recurs, the fix is a rule in
  `AGENTS.md`, `REVIEW.md` or a linter, and the summary says so.
- **One model, the strongest, in a fresh context.** No second model family;
  see the evidence below.
- **Milestones carry review gates, between plans rather than inside them.**
  When `m{N}` lands on `main`, the session that starts `m{N+1}` runs an
  incremental review before planning it, and folds the findings in. That's
  the earliest point the review sees integrated code, and the latest point
  its findings are cheap to act on. It isn't a plan step: a plan worker
  can't spawn reviewers, push its own branch or edit the plan, and a plan's
  files leave the branch before its PR merges. The milestone handoff marks
  it pending, and a numbered task card can queue it ahead of `m{N+1}`.
- **A monthly cadence is optional.** `status` mode says whether a review is
  due and is a no-op otherwise, so a scheduled task can run it without
  producing noise. Not built in; offered once the first review has shown
  whether the output is worth reading monthly.

## Evidence

No vendor or practitioner publishes a standard for periodic, whole-codebase
review of agent-written code. Per-PR review is well served; the layer after
integration is assembled from other practices.

- **Audit reports** (Trail of Bits, e.g. the OSTIF Mosquitto report): pin
  the reviewed version to a full commit SHA; an executive summary, a
  findings table, then detailed findings with severity; a later fix review
  marks each finding Resolved, Partially Resolved, Unresolved or
  Undetermined. That's the register, the summary and the fix review here.
- **Harness engineering** (Böckeler on martinfowler.com; OpenAI's Codex
  write-up, read through secondary summaries): fast checks at commit, a
  broader review "that can take into account the bigger picture" after
  integration, background agents that grade quality and open small
  refactor PRs, and recurring problems fixed by improving the rules.
- **Claude Code**: `/code-review` accepts a commit range or a path and can
  run from a scheduled task, so "since the last review" is one argument.
  Ultrareview takes a commit or tag as base and caps a review near 8,000
  changed lines, a useful threshold for splitting a range into path
  slices. The best-practices guide says the reviewer shouldn't be the
  author, and warns that a reviewer asked to find problems always finds
  some, so not every finding deserves a fix.
- **Anthropic's own SDLC**: codebases tiered by risk, scheduled scans,
  review agents that must prove a finding is real before posting it.
- **GitHub Code Quality** scans the whole default branch on a schedule: the
  one vendor feature that reviews `main` rather than a diff.
- **Cross-model review** (arXiv 2610.01471, read through summaries): on
  code, a fresh session of the same model scored about as well as a
  top-tier model from another family (F1 40.7% against 37.2%), and a
  lightweight second model added nothing; the other family won only on
  documents. Reviewer strength matters more than family, so the standard
  asks for the strongest available model in a fresh context, with the right
  command and prompt.
- **Cross-repo**: nothing found on agent reviews that span repos. Scorecards
  (Backstage), batch changes (Sourcegraph) and contract gates cover
  conformance and breakage; the estate review is our own design.

What cut against the log, and how the design answers it: squash merges
erase branch SHAs (anchor on `main` only); vendors keep live findings in
trackers, not files (the issue is the work queue, the register is the
record); logging alone changes nothing (fix review plus rules); long gaps
make ranges too big to review (churn triggers, and a range past about
8,000 changed lines split into path slices, each reviewed line by line; a
full review would skip exactly the lines that changed).

## Sources

- Claude Code `/code-review`: https://code.claude.com/docs/en/code-review-local
- Claude Code Ultrareview: https://code.claude.com/docs/en/ultrareview
- Claude Code best practices: https://code.claude.com/docs/en/best-practices
- How Anthropic secures its AI-native SDLC: https://claude.com/blog/how-anthropic-secures-its-ai-native-software-development-lifecycle
- Böckeler, Harness engineering: https://martinfowler.com/articles/harness-engineering.html
- GitHub Code Quality: https://docs.github.com/en/code-security/concepts/about-code-quality
- OSTIF Eclipse Mosquitto report with fix review: https://ostif.org/wp-content/uploads/2023/11/OSTIF-Eclipse-Mosquitto-Final-Report-with-Fix-Review-1.pdf
- Trail of Bits skills: https://github.com/trailofbits/skills
- Thoughtworks Radar, complacency with AI-generated code: https://www.thoughtworks.com/radar/techniques/complacency-with-ai-generated-code
- GitClear 2025: https://www.gitclear.com/ai_assistant_code_quality_2025_research
- When does a second model help? (arXiv 2610.01471): https://agentpatterns.ai/verification/cross-model-review-independence/
- Agentic code review patterns: https://bdfinst.github.io/ai-patterns/agentic-code-review/
