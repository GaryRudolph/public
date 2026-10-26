# Review guides for agent-made changes

Status: m2.s1 done; m2.s2 next. Running m2 to m3 unattended (Gary, after m1). Branch `claude/epic-ramanujan-3sdejf` (harness-assigned).

## Context

Line-by-line review doesn't scale with agent output. Gary wants to understand what matters in a change at two moments: in the session before a PR opens, and in the PR itself, for him and for other readers. What matters is the contracts and APIs, orchestration and control flow, error handling, data and schema, and blast radius.

Per-repo rules such as nowline's before/after diagram gate (`lolay/nowline` `AGENTS.md` "Visual changes") should plug in. The before/after idea should also work in general: a preview at plan time when it's cheap, and a report at completion. The review itself is tiered, the same way model tiers grade plan steps, so the reader knows what to study and what to skim. It's written to be read on GitHub from a phone, with a stated time to understand.

Today the standards have no review guidance:
- The only PR template is `git.md` "PR Body": Summary, Changes, Test Plan, Breaking Changes.
- `documentation.md` has no diagram guidance.
- `specs/agent-distribution.md` rated a `personal-pr` skill "Low; skip" because harnesses already write PR bodies.

This plan adds a comprehension procedure, not a body template. It reads the base and head, grades risk, draws before/after diagrams, and runs per-repo review surfaces.

## What the field converged on (Aug to Oct 2026)

No vendor ships this end to end, but the parts are established.

**Anthropic**, "How the Claude Code team does code review" (Oct 15 2026):
- Aim for the least human review that doesn't raise reverts.
- Show evidence instead of saying "done".
- A fresh-context reviewer checks the diff against the PR's stated intent.
- The PR template asks for Testing, Risk, and How to revert.
- Approvals are tiered by risk: low needs 0 humans, medium 1, high 2. "The change sets the tier, not the author."
- Engineers ask Claude for an explainer of the slice they care about.
- Reverts fell more than 40% while merged PRs doubled.

**Claude Code docs:**
- The output-style example "Diagrams first" uses Mermaid kept under 15 nodes.
- `/code-review` and the Code Review app find bugs but don't explain the change.
- `REVIEW.md` tunes what the app flags.

**Codex**, "issue to tested PR":
- Sections: Changes, Acceptance evidence (before/after/status), Validation, Reviewer focus, Remaining risk and rollback.
- "Never describe an unrun check as passing."

**Review tools:**
- Warp's PR skill puts `## Review guide` (reading order, where to look, blast radius) right after the summary.
- CodeRabbit orders changes in reading order and gives an effort score from 1 to 5. Its diagrams (sequence, state, ER) appear only where structure changed.

**Practitioners:**
- Willison: prove the code works, with commands, their output, and a test that fails on revert. Agent-written PR text needs review too.
- Osmani: write a statement of purpose, keep a decision log, read rewritten tests first, watch for comprehension debt, and treat AI review as "a sensor, not a verdict."

**Gap:** nobody ships a real before/after diagram diff. The known failure is a hand-drawn diagram going stale after the next push, so regenerate diagrams from the code each time.

## Design

### Review tiers

These mirror the model tiers. Each area of the change gets a tag, and the PR's own tier is the highest of those tags.

Each area of the change (a file group, or a key hunk) gets one tag:

| Tag | Reviewer does | Typical |
| --- | --- | --- |
| `[study]` | Read every line and question the design | Public contract or wire format, schema or migration, auth, security, secrets, concurrency or retries, irreversible ops |
| `[check]` | Read the named hunks and confirm them against the evidence | Orchestration and control flow, error handling, rewritten or deleted tests, config that changes behavior |
| `[skim]` | Glance for surprises | Internal refactors covered by tests, docs, renames |
| `[skip]` | Trust the tooling | Generated files, lockfiles, vendored code, formatting |

Bias toward the deeper tag: if an area could be either of two tags, it gets the deeper one. Upgrade and downgrade checklists live in the standard, in the same style as the `[fast]` and `[xdeep]` checklists in `plan-execution.md`.

A complex change mixes tags. For example, its contracts are `[study]` while its tests are `[skim]`. The PR gets one tier, the highest tag among its areas, so that example PR is `[study]`. The areas keep their own tags, so the reader still knows which parts don't need studying. The PR's tier suggests how many humans should review it: none for `[skim]` or `[skip]`, one for `[check]`, two for `[study]`. Gary's repo rules decide. The change sets the tier, not the author.

The blast radius line sits next to the tier. It says who or what breaks if the change is wrong (callers, users, data, deploys) and how reversible it is.

### Time to understand

The always-visible part of the guide is meant to be read in about 2 minutes on a phone, so keep it to roughly 250 words, with tables counting toward that. Each collapsed block fits about one phone screen.

The guide states `Review time: ~N min`, estimated by the agent from the tags. Above about 30 minutes, it says so and proposes splitting the PR, which is consistent with `git.md`'s 400-line guidance.

### One document, three moments

| Moment | Trigger | Output |
| --- | --- | --- |
| Plan | The plan touches a contract, a flow, a schema, or a repo review surface | A "Shape of the change" section in the plan, with before and after (see the preview gate below) |
| Pre-PR | Work is done, before asking to open a PR, or "walk me through it" | The draft PR description, shown as an Artifact page (renders Mermaid). The terminal gets the PR tier, review time and reading order |
| PR | Opening or updating the PR | The same description, posted, and regenerated on each push that changes a tagged area |

### Description layout (mobile-first)

Always visible:
- Intent (one paragraph, linking the issue, spec or plan)
- `## Review guide`: a `Review tier:` line with the PR's tier and why, blast radius, review time, and the reading order as a tagged list of areas
- Validation (commands and their results; unrun checks say "not run")
- Rollback

Below that, one `<details>` block per tier present, deepest first, so each tier collapses and expands on its own:
- `[study]` starts expanded (`<details open>`), since it's the part that has to be read.
- `[check]`, `[skim]` and `[skip]` start collapsed. `[skip]` is just a file list.

Each tier block holds that tier's areas, using whichever of these apply:
- Contracts (a before-to-after table)
- Control flow (before/after Mermaid, only if the flow changed)
- Data and schema
- Error handling (new failure modes, retries, anything swallowed)

Decisions (alternatives ruled out) gets its own collapsed block at the end. Leave a blank line after each `<summary>`. Tiers and sections with nothing to say are dropped. Mermaid source and `<details>` tags land on `main` through the squash, and that's accepted. Still unverified: whether the GitHub mobile app draws Mermaid. Check it on the dogfood PR; the mobile browser does draw it.

### Draft on the branch

The draft is the source the skill regenerates from, and it lives where plans already live:
- On a runner, `specs/handoffs/`, committed so it survives the container.
- On a workstation, `.scratch/`.

It's named with a `-review` suffix on the plan's stem, so a plan and its review sort together: `plan-auth-otter.md`, then `plan-auth-otter-review.md`. Without a plan, the name is `{topic}-{word}-review.md`.

The PR description is published from the draft. The draft is removed before merge along with the other `specs/handoffs/` files, since the squash already carries the description to `main`. It supplements the description and never replaces it.

### Plan-time preview gate

The default is `if-cheap`. If a before/after can be made in a few minutes, it's shown with the plan and rides the plan's existing approval stop; no extra gate is added. Ways to make one cheaply:
- Mermaid drawn from the base commit's code next to the proposed shape
- A render of existing fixtures next to a mock

If the preview would need the real implementation, the plan says `Preview skipped: <reason>; before/after at completion` and moves on. The before/after report at completion is always made.

A repo surface can set `preview: required` (nowline's visual changes) or `preview: report-only`.

### Per-repo extension

A repo adds a `## Review surfaces` section to its `AGENTS.md`. Each surface names:
- what counts as a change to it
- its default tag
- how to render before (at the base commit) and after
- where the output goes
- its preview mode

nowline's "Visual changes" maps onto this directly.

## m1 - Standard

#### ~~s1 - [deep] `standards/review.md`~~
Add a new file under `plugins/personal/skills/personal-standards/standards/`. It covers:
- purpose
- review tiers, with the upgrade and downgrade checklists
- the PR tier (the highest area tag) and blast radius
- the `-review.md` naming
- the time-to-understand budget
- the description layout
- evidence rules
- diagram rules: sequence diagrams for call paths, state for lifecycles, ER for data, flowchart for orchestration; under 15 nodes; "before" drawn from the base commit, never from memory
- the preview gate
- the `## Review surfaces` format
- the draft-on-branch rule
- "the author reads and owns the text"

#### ~~s2 - [exec] Cross-links~~
- `git.md` "PR Body": replace the template with the layout from review.md. Keep the squash and trailer rules. Add the review draft to the pre-merge `specs/handoffs/` cleanup.
- `documentation.md`: the plan content list gains "Shape of the change", and a short Diagrams section points to review.md.
- `core.md` Workflow: add one bullet, "hand over a review guide, not a diff". It covers the preview at plan time when cheap, the walkthrough before asking to open a PR, and the guide in the PR description, all through `personal-review-guide`. Also add a Standards Reference line, then run `make -C agents cursor-core-rule`.
- `personal-standards/SKILL.md`: add an index row.

## m2 - Skill `personal-review-guide`

#### ~~s1 - [exec] Facts script~~
Add `scripts/review-facts.sh`. It gathers:
- the base ref (the merge-base with the default branch, or a ref that's passed in)
- commits and the diffstat
- changed files, including renames and deletes
- a bucket for each file (api, schema, orchestration, config/infra, tests, docs, generated), from a fixed path table in `reference.md`; this uses the "fixed table" exception in core.md, and the agent assigns the tags
- lines per bucket
- whether tests were rewritten or deleted
- the `## Review surfaces` text from AGENTS.md or CLAUDE.md
- the PR template path
- any plan, handoff or review files on the branch

It emits no verdicts. Model it on `personal-handoff/scripts/handoff-facts.sh` and `personal-repo-baseline/scripts/repo-facts.sh`.

#### s2 - [deep] SKILL.md and reference.md
The skill has three modes: `plan`, `walkthrough` and `pr`. The procedure:
1. Run the facts script.
2. Read the review surfaces.
3. Tag each area.
4. For tagged areas, read the code at the base (`git show <base>:<path>`) and at the head.
5. Draw only the diagrams whose structure changed.
6. Run the surface renderers.
7. Set the PR tier, blast radius and review time.
8. Write the draft.
9. In `pr` mode, show the description before creating or editing the PR. Opening a PR still waits for Gary.

The description says why this isn't a template skill. `reference.md` holds the bucket table, the description skeleton, and a diagram guide.

#### s3 - [exec] Tests and registration
- `tests/test-review-facts.sh`, run over a temp repo with a base and a head
- a `test-review-guide` target in the `agents/Makefile` `test` list
- a skill row in `plugins/README.md`
- an update to the `personal-pr` row in `specs/agent-distribution.md`

## m3 - Factory hooks

#### s1 - [exec] PR body gate
Add a PreToolUse entry in `plugins/personal/hooks/claude-hooks.json`, next to the existing guards. It fires on PR creation through `gh pr create`, a REST `pulls` POST, or `mcp__github__create_pull_request`. It denies the call when the body lacks `## Review guide` or a `Review tier:` line, and its reason points to the skill. It checks presence only. Add tests beside the existing hook tests.

#### s2 - [exec] Baseline item
Add `.github/pull_request_template.md` to `personal-repo-baseline` using its "Adding an item" recipe:
- When a repo has no template, add one with the layout.
- When a repo has a template without `## Review guide`, propose inserting the section above the template's AI assistance section.
- Optionally, add a REVIEW.md line telling the Code Review app to check the diff against the stated intent and the review tags.

## m4 - Adopt in nowline (separate repo and PR, after m1 to m3 merge)
Turn nowline's "Visual changes" into a `## Review surfaces` entry with `preview: required` and default tag `[check]`, with no change in behavior. Add `## Review guide` to nowline's PR template, above "AI assistance". Queue this as a task card; it isn't done in this session.

## Verification
- `make -C agents validate test`: manifests, cursor rule freshness, and the new facts-script and hook tests.
- Run `review-facts.sh` on this branch and on `/workspace/lolay/nowline`.
- Dogfood: the skill writes this repo's own PR description in `pr` mode, and the hook accepts it. Then open it on the GitHub mobile app to settle the Mermaid question.
- Commit and push each step on `claude/epic-ramanujan-3sdejf`, pausing after each step.
