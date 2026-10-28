# Plan: adopt the orchestrate review's findings into the personal kit

Branch: `claude/beautiful-edison-dbgaz4` (harness-assigned task branch). On
approval this plan is copied to `specs/handoffs/plan-orchestrate-adopt-marlin.md`
and committed with the first step (core.md "Runner scratch rides the branch");
the last milestone removes it.

## Context

Gary uploaded a review of about 110 orchestrate runs of the Agerpoint bok's
copy of this kit. Its diagnosis: the process produces over-decomposed code
nobody wants to maintain (workers see one step's excerpt, reviewers enforce
the 50-line rule mechanically, nothing checks the plan's shape before a line
is written), the canary kills parallelism in every resumed session, reviews
and fix-ups run Opus where a cheaper model or a script would do, and plans
default up to `[deep]`.

Much of the review is bok-specific and doesn't apply here: the final panel,
refuters, triage, the follow-up ledger, the orchestrate roster, CreatePlan
`.plan.md` plans and `harness-cursor.md` don't exist in this repo. Cursor
support stays (Gary's call; Claude Code is primary, Cursor second). The
run-record split (§2.5) and the `.scratch` layout and tidy script (§2.6) are
deferred: this kit's plans are small, its artifact names already follow one
scheme, and both are their own projects.

Decisions Gary made in this session, which amend the spec's decisions 4 and 7:

1. **Canary:** per plan on a workstation (fires only until any group has a
   PASS in the Review log), per session on a runner (a cloud or self-hosted
   session is a new container). Amends decision 4.
2. **Review routing:** Opus high reviews `[exec]` and `[deep]` units, Opus
   xhigh `[xdeep]`; Sonnet high reviews `[fast]` units and check-only fix-ups
   (a fix-up whose only failure was `check_wave.py`), and those fix-ups run
   their worker on Haiku medium. Amends decision 7.
3. **Consolidation step:** both drivers append one final `[deep]` step at
   grouping when a criterion fires (below), in its own wave, and say which
   fired or why it was skipped.
4. **Tagging:** drop the default-up bias; doubt resolves to `[exec]`, the
   review and the escalation path catch the rest. Every `[deep]` tag gets a
   one-line reason in the readout, and the tagger proposes splitting a build
   step whose only deep part is one design choice.

Adopted without a question (uncontroversial here): the Shape section, workers
seeing the whole plan, the reviewer's judgement questions, the 50-line rule
as a smell test, "when not to orchestrate", no diffs in worker artifacts, a
widened `[fast]` tier, and a gate-0 check that every step ID fits a commit
subject (the bok's live blocker in §5; this kit's `check_wave.py` reads the
subject as one token too, so a plan with `#### Phase 1: [exec] …` would
fail the same way). Folding stays: here a group is one worker, not one
agent per step, so unfolding `[fast]` steps would add a parent turn and a
review per wave for nothing.

## Shape of the change

Modifies (no new files except the plan and handoff, and tests inside
existing test files):

- `plugins/personal/skills/personal-standards/standards/plan-execution.md`:
  tiers, checklists, Tag placement, Driver fit, a new "Shape" subsection, a
  new "Consolidation step" subsection, the review routing in Model picker
  notes and Expected cost, the canary rule in STOP gate semantics.
- `plugins/personal/skills/personal-standards/standards/code-style.md`,
  `plugins/personal/skills/personal-standards/core.md`: the 50-line rule
  becomes a smell test; regenerate `cursor/rules/personal-core.mdc`.
- `plugins/personal/skills/personal-plan-tag-tiers/SKILL.md`: Shape, deep
  reasons, split proposals, readout.
- `plugins/personal/skills/personal-plan-model-tiers/SKILL.md`: consolidation
  step at grouping, Sonnet review beat after a `[fast]` wave, no default-up.
- `plugins/personal/skills/personal-plan-orchestrate/scripts/plan_state.py`:
  `shape`, `plan_start`, `canary_passed`, step-ID gate 0.
- `plugins/personal/skills/personal-plan-orchestrate/claude-workflows/plan-segment.js`:
  canary condition, review and check-only fix-up routing, worker and
  reviewer prompts, `newFiles`.
- `plugins/personal/skills/personal-plan-orchestrate/scripts/token_tally.py`:
  `--check-routing` knows the reviewer and check-only fix-up models.
- `plugins/personal/skills/personal-plan-orchestrate/tests/orchestrate_check.py`
  and the suites beside it.
- `plugins/personal/skills/personal-plan-orchestrate/{SKILL.md,gates.md,kickoff.md,contract.md}`,
  `adapters/{claude-code,cursor}.md`, `claude-agents/{plan-worker,plan-reviewer}.md`.
- `specs/plan-orchestration.md`: decisions 4 and 7 amended, a short "2026-10
  review" section naming what was adopted and what was deferred.

## Milestones

### m1 - Standards and tagging (docs)

#### s1 - [exec] Tiers, checklists and Tag placement in plan-execution.md

- "Tiers": delete the **Default-up bias** paragraph. Replace with: doubt
  between `[exec]` and `[deep]` resolves to `[exec]`; the unit's review
  (Opus) and a failed or CONCERNS step's escalation to `[deep]` catch a step
  that needed more. Doubt between `[deep]` and `[xdeep]` still resolves to
  `[deep]` (the upgrade checklist is the gate). Every `[deep]` tag carries a
  one-line reason in the tagging readout.
- Widen `[fast]`: add doc edits, renames, fixture moves, commit rewords and
  plan bookkeeping edits, and applying a design note line by line.
- `[fast]` downgrade checklist, last bullet: "A later `[deep]` or `[exec]`
  group will review this output" → "The unit's review and the tests check
  it" (reviews after a `[fast]` wave run Sonnet high, s3).
- "Tag placement": a step's ID must be one token (no whitespace) so it can
  lead a commit subject; `plan_state.py` reports a violation as gate 0. Add
  `#### Phase 1: [exec] Auth` to the examples as the shape to avoid, with
  the fix (`#### phase-1 - [exec] Auth`, or an `s{N}` prefix).
- "Driver fit": add when orchestrate pays off (work spans repos, needs
  unattended hours, or has independent chains that run at once) and when it
  doesn't (a single-repo feature with a written spec one engineer could do
  in a day: one Opus session, direct or the passive driver). The tagger's
  readout and both fit checks name this case; it's the agent's judgement,
  not a rule.

#### s2 - [exec] Shape and consolidation subsections in plan-execution.md

- New "Shape" subsection after "Tag placement": `personal-plan-tag-tiers`
  writes a `## Shape` section before the first milestone heading, after the
  Kickoff block and Cost table when those exist:

      ## Shape

      Creates:
      - `src/search/debounce.py` — no existing module owns timing; one new unit
      Modifies:
      - `src/search/view_model.py`
      - `tests/search/test_view_model.py`

  One line per new file with why it is needed; modified files listed bare.
  Tests and docs count. The kickoff question shows it and Gary trims it
  before anything runs. A worker that creates a file not in Creates reports
  it under `newFiles` with a reason; the reviewer treats an unexplained new
  file as a finding. `plan_state.py` emits the section's text as `shape`.
- New "Consolidation step" subsection after "No-thrash rule": at grouping,
  a driver appends `#### s{K+1} - [deep] Consolidate the plan's code` as the
  last step of the last milestone, in its own wave (its own `--- WAVE N
  [deep] ---` marker, never merged into the previous wave, so one worker
  reads the whole diff), when any of: two or more waves change source code;
  Shape's Creates lists three or more source files (tests and docs
  excluded); a wave runs in more than one working directory of the same
  repo. Skipped when the plan is docs-only, all code changes sit in one
  wave, or every code step touches disjoint files. Step body (verbatim
  template): read `git diff <plan start>..HEAD`; merge duplicated helpers,
  inline one-use wrappers and thin indirections, delete dead code, tighten
  names; no behaviour change; the repo's tests are the check; commit under
  the step ID. The kickoff summary names the criterion that fired or why it
  was skipped; Gary may add or remove the step before the kickoff question.
  Its Cost table row is a medium `[deep]` step plus its review.

#### s3 - [exec] Review routing, canary and worker prompt rules in plan-execution.md

- "Model picker" notes, the review bullet: reviews run Opus high after an
  `[exec]` or `[deep]` wave, Opus xhigh after `[xdeep]`, and Sonnet high
  after a `[fast]` wave or a check-only fix-up (whose worker runs Haiku
  medium, the `[fast]` row). Cursor: the passive review beat after a
  `[fast]` wave names `claude-sonnet-5-5[effort=high]`; orchestrate on
  Cursor reviews inline until phase 3, unchanged.
- "Expected cost", the review bullet and the orchestrator row: a `[fast]`
  wave's review is 0.6× the Sonnet 5.5 (high) row, about 0.6M and $0.21;
  recompute the worked example (wave 3's review drops from $0.54 to $0.21).
- "Review beat": the `[fast]` wave's REVIEW marker uses the Sonnet rows.
- "STOP gate semantics", the unattended checkpoint sentence: the canary
  fires on a workstation only until any group has a PASS in the Review log,
  and on a cloud or self-hosted session's first launch.
- "Delegating execution to subagents": a subagent gets the whole plan
  read-only, the Shape section and `git log --stat <plan start>..HEAD`,
  and the scope rule reads "do not implement later steps; prefer extending
  a file an earlier step created over adding a new one".

#### s4 - [exec] The 50-line rule as a smell test

- `code-style.md` line 40: "**Large functions**: about 50 lines is a smell
  test, not a gate. Split where the pieces have names of their own;
  extraction that threads intermediate state through new parameters is
  worse than the long function."
- `core.md` line 31: "Functions short (about 50 lines is a smell, not a
  gate); extract logic that has a name of its own".
- Run `make -C agents cursor-core-rule` to regenerate
  `plugins/personal/cursor/rules/personal-core.mdc`.

#### s5 - [exec] personal-plan-tag-tiers: Shape, reasons, splits

- Procedure step 2: no default-up; a `[deep]` tag needs a reason.
- New step 3 "Propose splits": a step tagged `[deep]` only for one design
  choice inside a build step is listed in the readout as a proposed split
  (`s3 → s3 [deep] decide <choice>, output a design note; s4 [exec] build
  it`, renumbering the later steps of that milestone). Applied only on
  Gary's yes and only before any wave marker exists; cross-references in
  the plan are updated with the renumbering.
- New step 4 "Write the Shape section" per the standard, reading the repo
  to tell new files from existing ones. Idempotent: an existing `## Shape`
  is kept, with a line per step added since.
- Readout (step 5): add the `[deep]` reasons, the proposed splits, the
  Shape summary (N new, M modified), and the "one session" fit case from
  s1.

#### s6 - [exec] personal-plan-model-tiers: consolidation and Sonnet review beat

- Step 2: drop "default-up bias" from the sanity pass.
- Step 3: after grouping, apply the consolidation criteria from s2 and
  append the step and its wave marker when one fires; say which in chat.
- Step 4: the REVIEW marker after a `[fast]` wave uses the Sonnet rows from
  s3.
- Step 7 / Kickoff: the kickoff summary shows the Shape section.

### m2 - Orchestrate kit scripts

#### s1 - [exec] plan_state.py: shape, plan_start, canary_passed, step-ID gate 0

- `shape`: the text of the `## Shape` section (empty string when absent).
- `plan_start`: the `<from>` of the first Review log line, else null.
- `canary_passed`: true when any Review log line has verdict PASS.
- Gate 0: a step ID containing whitespace, `errors` naming the line and the
  fix. Keep the slug fallback for a heading with no prefix (already one
  token).
- `tests/test_plan_state.py`: cases for each; the whitespace case uses
  `#### Phase 1: [exec] Auth`.

#### s2 - [exec] plan-segment.js: canary, routing, prompts

- Canary: `const canaryDue = !S.canary_passed || ['cloud','self-hosted'].includes(S.mode && S.mode.runner)`;
  `const canary = canaryDue && !args.canaryDone && groups.length > 1`. Log
  "No canary: a group of this plan already passed" in the new case. The
  gate hook's rule 3 is unchanged (a first launch still passes
  `canaryDone: false`). Confirm `plan_state.py` exposes the runner token on
  `mode` (it parses `SIGNAL_RE`); add it if only the raw signal is there.
- Review routing: `REVIEW = { fast: sonnet high, exec: opus high, deep: opus high, xdeep: opus xhigh, fable: opus xhigh }`;
  `reader(t)` reads it. A check-only fix-up (`U.kind === 'fixup'` and every
  group's concern has `source === 'check'` and no `; review CONCERNS:`)
  routes its worker to `ROUTE.fast` and its review to `REVIEW.fast`; titles
  and labels carry that tier (`Wave 2-fix of 4 [fast] …`) so
  `token_tally.py` prices and checks it. A fix-up with a review concern
  keeps the wave's tier.
- Worker prompt: after the spec excerpt, "## The whole plan": read
  `args.plan.path` read-only for the steps around yours and the Shape
  section (quoted from `S.shape` when non-empty), and run
  `git -C <workdir> log --stat <S.plan_start or g.from>..HEAD` first.
  Scope: "Execute only: … Do not implement later steps. Prefer extending a
  file an earlier step created over adding a new one; a file you create
  that the Shape section's Creates list lacks goes under `newFiles` with
  one line on why." Output: drop "diffs" from the artifact contents (git
  holds them). `RESULT` gains required `newFiles: string[]`.
- Reviewer prompt, after the spec check: the four judgement questions
  (could an engineer who didn't write it understand it in one reading; does
  it duplicate something in the repo or in this plan's earlier commits,
  name the pair; could it be fewer files or public functions with no loss;
  does any helper exist only to satisfy a length rule, extraction that
  threads state through parameters is a finding, not a fix). "About 50
  lines is a smell, not a gate." Unexplained new files (`git diff
  --diff-filter=A --name-only <from>` against Shape and `newFiles`) are a
  finding. A `consolidate` finding naming the files to merge is a
  legitimate CONCERNS. Pass `r.newFiles` in the worker summary.
- `tests/plan-segment-test.mjs`: canary skipped when `canary_passed` and
  runner `none`; canary kept on runner `cloud`; `[fast]` unit's review on
  sonnet; check-only fix-up's worker on haiku and review on sonnet with
  `[fast]` in the labels; review-concern fix-up unchanged; `newFiles`
  required.

#### s3 - [exec] token_tally.py, orchestrate_check.py and the routing check

- `token_tally.py --check-routing`: a `Review …` label's expected model
  follows the `[tier]` in its title through the review table (sonnet for
  `[fast]`, opus otherwise); a worker label with `[fast]` expects haiku.
  Read how it keys the expected model today and extend that table;
  `tests/test_token_tally.py` cases for a sonnet review of a `[fast]` wave
  and a MISROUTED opus review of one.
- `orchestrate_check.py`: parse the review routing from `SKILL.md`'s "Tiers
  and models" table (a new reviewer column per tier) and compare with
  plan-segment.js's `REVIEW` table, as it does `ROUTE` against the picker.
  Keep the reviewer frontmatter check (Opus high stays the default).
- Run `bash plugins/personal/skills/personal-plan-orchestrate/tests/test-orchestrate.sh plugins/personal`.

### m3 - Orchestrate docs and the spec

#### s1 - [exec] SKILL.md, gates.md, kickoff.md

- SKILL.md "Tiers and models": a reviewer column per tier and a row for the
  check-only fix-up (Haiku medium worker, Sonnet high review). "Rules every
  run keeps": the reviewer rule reads "at the tier the standard's review
  routing gives". Gates table, gate 5: "the canary: on a workstation, a
  launch before any group of the plan has a PASS; on a runner, the first
  launch of a session; when its unit has more than one group". "Files a
  run keeps": worker artifacts hold no diffs.
- gates.md: the canary paragraph; the fix-up paragraph says a check-only
  fix-up runs on the `[fast]` row and its review on Sonnet.
- kickoff.md step 2: after grouping, apply the consolidation criteria and
  say which fired; the fit check also names the "one session" case. The
  kickoff question shows the Shape section and asks Gary to trim it (one
  dialog question when the harness has one). Step 4's kickoff summary
  names the consolidation decision.

#### s2 - [exec] contract.md, adapters, agent files

- contract.md: item 1 adds the whole plan read-only and the Shape section;
  item 4's scope wording; item 6 drops diffs and adds `newFiles`; a new
  item 10 with the reviewer's judgement questions and the new-file check.
  Add `git log --stat <plan start>..HEAD` to the resume rule in item 8.
- adapters/claude-code.md: the launch example gains nothing (state carries
  `shape`, `plan_start`, `canary_passed`); the pieces table and
  `canaryDone` bullet say when the script skips the canary; the result
  shows `newFiles`.
- adapters/cursor.md: the check-only fix-up dispatches on the `[fast]` slug
  (`composer-2.5[fast=false]`); the parent's inline review applies the
  judgement questions; the prompt carries the Shape section.
- claude-agents/plan-worker.md: "Read the whole plan read-only; prefer
  extending a file an earlier step created; report new files under
  `newFiles`." claude-agents/plan-reviewer.md: the four questions in one
  bullet; a `consolidate` finding is legitimate.

#### s3 - [exec] specs/plan-orchestration.md

- §1.3 Review: the routing. §1.5 and the canary paragraph: the new rule.
  §5 decisions 4 and 7: amended, dated today, with the old text kept in
  one clause. New §7 "The 2026-10 orchestrate review": what was adopted
  (Shape, whole-plan workers, reviewer questions, consolidation step,
  routing, canary, tagging default, step-ID gate 0) and what was deferred
  (run-record split, `.scratch` layout and tidy script, Sonnet parent) and
  why; what didn't apply (panel, triage, ledger, roster, Cursor removal).
- `make -C agents validate test` must pass.

### m4 - Close out

#### s1 - [fast] Remove the plan and handoff from specs/handoffs

Remove `specs/handoffs/plan-orchestrate-adopt-marlin.md` and its handoff as
the last commit; the PR description (when Gary asks for one) is the review
guide, with the `[study]` area being plan-segment.js's routing and canary
change and `[check]` the standard's tier text.

## Verification

- `make -C agents validate test` (runs `test-orchestrate`, which runs
  `orchestrate_check.py`, the four Python suites and the workflow stub
  harness under node).
- `python3 -I plugins/personal/skills/personal-plan-orchestrate/scripts/plan_state.py <fixture>`
  on a fixture plan with a `## Shape` section, a PASS line and a
  `#### Phase 1:` heading: `shape` and `canary_passed` set, gate 0 names
  the heading.
- Node stub run of plan-segment.js for: a two-group unit with
  `canary_passed: true`, runner `none` (no canary); the same with runner
  `cloud` (canary); a `[fast]` unit (review label `[fast]`, model sonnet);
  a check-only fix-up (worker haiku, review sonnet).
- `grep -n "Default-up\|default-up" plugins/` returns nothing.
- `git diff --stat` shows `personal-core.mdc` regenerated, not hand-edited.
- Read the final plan-execution.md "Model picker" Claude Code row unchanged
  (the workers' routing didn't move), so `orchestrate_check.py`'s picker
  parse still matches `ROUTE`.
