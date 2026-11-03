Status: m3.s2 in progress (m1, m2, m3.s1 done)

# Codebase reviews from main: full, incremental, estate, logged

## Context

Every review today is per change: `personal-review-guide` writes the PR guide, `/code-review` or a subagent checks the diff, and orchestrated plans review each wave plus a whole-plan consolidation diff (`plan-execution.md` "Review beat", "Consolidation step"). Nothing reviews `main` after integration, so drift no single PR shows (architecture wandering from specs, duplication across PRs, thinning tests, repos diverging) goes unseen. This adds a review of `main`: full, incremental, and estate (cross-repo), with a durable log that anchors the next incremental, gates in milestone plans, output a human reads like a PR, and remediation tracked separately.

### Research that shaped it

- No published standard exists for periodic whole-codebase review of agent code. The pieces come from security audits (Trail of Bits: SHA-pinned report, exec summary plus findings register, fix-review statuses), Böckeler/OpenAI "harness engineering" (broader review after integration, background garbage-collection agents, recurring findings become rules), and GitHub Code Quality's scheduled default-branch scan.
- Claude `/code-review` takes a commit range, so incremental reviews delegate to it. Ultrareview caps near 8k changed lines: a practical "split or go full" threshold.
- **Cross-model review** (arXiv 2610.01471): on code, a fresh session of the same model did as well as a top-tier model from another family, and reviewer strength mattered more than family. So no second-family pass: the strongest model, in a fresh context, with the right command and prompt.
- Cross-repo agent review is uncharted. Contract breakage between repos belongs in CI gates (`buf breaking`, oasdiff, Pact), so the estate review sticks to architecture and major duplication.

### Decisions folded in from feedback and research

- **Main only.** `specs/reviews/` records reviews of the default branch, anchored on default-branch SHAs (squash merges erase branch SHAs anyway). Per-PR and session reviews stay with the PR: an optional `interim` review writes where drafts go (`.scratch/`, or `specs/handoffs/*-interim-review.md` on a runner) and is removed with the handoff files before the PR opens. It never touches the log.
- **Full is architectural, incremental is line-level.** Full: architecture vs specs/ADRs, contracts, module boundaries and dependency direction, module-level duplication, test strategy gaps, dependency/toolchain currency, security posture at design level, plus a hotspot read (churn x size) instead of every line. Incremental: `/code-review` on `<anchor>..<head>`, a drift pass on what the range changed (contracts, layering, duplicated helpers), and a fix review of open findings.
- **Estate:** architecture across repos (which repo owns what, contracts between them) and major cross-repo duplication. Per-repo line review stays in each repo's incremental.
- **An estate needs no workspace repo.** Members come from, in order: a `repos.mk` if run from a workspace; the member list saved in the previous estate record; otherwise the skill asks Gary for repos or a wildcard (`nowline*`), matched against sibling folders locally or `owner/nowline*` via `gh` on a runner, and shows the resolved list for confirmation. The record lives in a home repo: the workspace if there is one, else the repo Gary names (default: the one the session runs in). The record saves the member list and each member's range. Every member's own `specs/reviews/README.md` gets an `estate` row too: that repo's range, a link to the home record, and the estate findings that land in that repo. Its kind keeps it from moving the member's incremental anchor, since an estate review doesn't read lines. The rows land through a small PR in each member repo, and a finding that needs work in a member repo gets its issue there, linked from the home tracking issue.
- **Outputs:** a review PR carrying the two documents (register first, summary derived; the summary is the PR body), one GitHub tracking issue per review listing findings and decisions, and remediation in its own PRs referencing finding IDs. The next review's fix review sets prior statuses from issue/PR state, so fix PRs don't edit `specs/reviews/`.
- **Accepted feedback isn't re-raised.** Findings with status `accepted` (with a reason) are fed to reviewers as known; they're re-raised only if the code under them materially changed. The summary ends with "Previously accepted, not re-raised: r3.f2, r5.f1". Single source of truth is the registers; the facts script collects them.
- **Close the loop:** a finding class that recurs gets promoted to a rule (`AGENTS.md`, `REVIEW.md`, a linter); the summary has a "Rules changed" line.
- **Cadence:** milestone gates and complex-change triggers are the core. A monthly scheduled run is optional: `status` decides whether a review is due (30+ days and any churn, or churn past threshold) and is a no-op otherwise. Offered as a card, not built in.

## Design

### Record layout (per repo; same in the estate's home repo)

```
specs/reviews/
  README.md                              # the log, one row per review
  2026-11-03-r7-incremental.md           # summary: human, PR-shaped
  2026-11-03-r7-incremental-findings.md  # register: detail, written first
```

IDs follow milestone/step style: `r{N}`, findings `r{N}.f{K}`. Log row:

`| r7 | 2026-11-03 | incremental | <from>..<to> | 1 high, 4 med | #123 | 3 fixed, 1 accepted, 1 open | [summary](…) |`

The outcome column is updated by the next review's fix review. An estate row lists the members and each one's range; each member's log gets an `estate` row pointing back, so either side finds the other. If the home is a workspace, its `.gitignore` allowlist needs `!/specs`.

Finding fields: id, title, severity (high/medium/low/info), dimension, location (`path:line` at `<to>`), evidence, how it was verified, recommendation, kind (fix or decision), status (open, fixed, decided, accepted, deferred), reason (for accepted/deferred), resolution link.

Summary layout reuses `review.md` (tiers, ~250-word visible part, Mermaid rules): intent (kind, range, scope); verdict; **Decisions for you**, each current vs proposed with a recommendation; **Fix now**; **Since last review** with before/after diagrams only where structure changed (before at `<from>`, after at `<to>`); **Rules changed**; **Fix review**; collapsed detail per dimension; **Previously accepted** last.

### Harnesses

Target is Claude Code; the standard stays harness-neutral and the skill's `reference.md` maps each step:

| Step | Claude Code | Codex | Cursor | Gemini CLI | GitHub |
| --- | --- | --- | --- | --- | --- |
| Incremental line review | `/code-review high <from>..<to>` | `codex exec review --base`/`--commit` | Agent with the range | `/code-review` extension | Copilot review (PR only) |
| Dimension subagents | Agent tool | subagents | Task | n/a | n/a |
| Scheduled run | cloud scheduled task, or claude-code-action on cron | Codex cloud task | Automations (cron) | Action on cron | Code Quality scan |

Each harness runs its strongest available model for review (Claude Code: Opus at high effort; full and estate reviews at xhigh), in a fresh context that didn't write the code.

## Implementation

Branch: `claude/happy-wozniak-jyjnwh` (assigned).

### m1 - Spec and standard

#### s1 - [deep] `specs/codebase-review.md` (done)
Problem, the layers, research with sources, decisions above. Row in `specs/README.md`.

#### s2 - [deep] `standards/codebase-review.md` (done)
In `plugins/personal/skills/personal-standards/standards/`: kinds and what each covers, triggers (milestone landed, merged `[study]`-tier PR or `[xdeep]` step, churn threshold, optional monthly), anchors on main, interim reviews, record layout and log grammar, finding fields and statuses, accepted findings, outputs (PR, issue, remediation), summary layout pointing at `review.md`, estate scope, reviewer model (strongest, fresh context), closing the loop, ownership (agent review is a sensor; decisions are Gary's). Index it in `personal-standards/SKILL.md` and `core.md` Standards Reference.

### m2 - Skill `personal-codebase-review`

#### s1 - [deep] `scripts/review_log_facts.py` (done)
Read-only, `python3 -I`, no verdicts. Prints layout (mirroring `personal-makefile/scripts/audit.sh` `detect_layout` and the `repos.mk` parse in its `reference.md`); with `--members <list|glob>` resolves sibling folders or `gh` repos matching the pattern, else the previous estate record's members; per repo: default branch and SHA, log rows, last anchor per kind and whether it's reachable from the default branch, days and churn since (files, lines, by bucket, mirroring `BUCKETS` in `personal-review-guide/scripts/review_facts.py` with a keep-in-step note), open and accepted findings across registers, next `r{N}`, `gh` availability.

#### s2 - [deep] `SKILL.md` and `reference.md` (done)
Modes `status`, `incremental`, `full`, `interim`; `--estate` resolves members (workspace, previous record, or asks for a list or wildcard) and a home repo, and confirms both before reviewing. Procedure: facts, choose kind per the standard, resolve and size-check the range, dispatch dimension subagents (under 10) with accepted findings as context, adversarially verify each finding, write register, derive summary, fix review of prior findings, update log, show it (Artifact page, terminal summary), then on a task branch the docs commit and the PR plus issue wait for Gary's ask. `reference.md`: templates, log grammar, dimension prompts, harness table.

#### s3 - [exec] Tests and wiring (done)
`tests/test-codebase-review.sh` with fixture repos (log with prior reviews, unreachable anchor, accepted finding, a `repos.mk` estate, a plain folder matched by glob, members taken from a previous record). `test-codebase-review` in `agents/Makefile` `test:` and `.PHONY`. Update `plugins/README.md` tree and skills table.

### m3 - Plan integration

#### s1 - [deep] Review gates in `plan-execution.md` and `documentation.md` (done)
"Review gate" beside "Consolidation step": when m{N} lands on main and the plan continues, m{N+1} opens with `s1 - [deep] Review m{N} on main` (incremental), whose findings may amend m{N+1}; same after a merged `[study]`-tier PR or `[xdeep]` step. Single-PR plans put the post-merge review in the Completion summary. Milestone handoffs gain a "Review" line. Pre-PR review stays as is (review guide plus fresh-context `/code-review`), now nameable as `interim`.

#### s2 - [exec] Drivers and core
One-line mentions in `personal-plan-tag-tiers`, `personal-plan-model-tiers`, `personal-plan-orchestrate` SKILL.md (no `plan_state.py` change; the gate needs a merge, so it stops on its own). `core.md` Workflow bullet "Review main, not only the diff" next to the review-guide bullet; `make -C agents cursor-core-rule`.

### After merge: task cards, not work on this branch

Queued with `spawn_task`, each prompt checking the PR merged first:
- Run the first full review of `garyrudolph/public` (`r1`).
- Add review gates to nowline OSS milestones.
- Add review gates to the nowline commercial repos' milestones and run the first estate review (members `nowline*`, home `nowline-workspace` if Gary confirms it).
- Optional: monthly scheduled `status` then incremental, if Gary wants it after `r1`.

## Verification

- `make -C agents validate test` passes, including `test-codebase-review` and the session-start size test after the `core.md` edit.
- `review_log_facts.py` against this repo (no log: next `r1`) and against fixtures.
- `status` mode dry run here, read against the standard.
- Review guide walkthrough of this branch before asking to open a PR.
