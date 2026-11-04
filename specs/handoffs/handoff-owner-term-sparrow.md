# Handoff: the Owner rename

Branch: `claude/kind-shannon-gjsytu` (assigned by the harness), on `main` at `2ee641e` (after #39).

Done: "the Owner" defined once in `core.md`; every role use of "Gary" replaced across plugins, specs and agents docs, pronouns included; `make -C agents validate test` passes. Plan: `plan-owner-term-sparrow.md`. Review guide draft: `plan-owner-term-sparrow-review.md`.

Pending questions (verbatim):
1. Open the PR now?
2. `specs/plan-orchestration-phase-1-report.md` still says "Gary" 12 times. Rewrite it too, or leave it?

To resume: on a yes to 1, `git rm` this handoff, the plan and the review draft in one commit, push, then open the PR to `main` with the draft's text as the body (REST, not `gh pr create`).
