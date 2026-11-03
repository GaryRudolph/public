# Handoff: codebase review mechanism

Branch: `claude/happy-wozniak-jyjnwh` (assigned by the harness), pushed.

## Done

All of the plan (`plan-codebase-review-heron.md`): the spec (`specs/codebase-review.md`), the standard (`standards/codebase-review.md`), the `personal-codebase-review` skill with its facts script and 71-check test, the review gate between milestones (`plan-execution.md` "Review gate", handoff and driver notes), and the `core.md` bullet. A fresh-context review found 11 issues; all fixed. `make -C agents validate test` passes.

## Pending

Question to Gary, verbatim: "Open the PR for the codebase review mechanism?" The PR body is `plan-codebase-review-heron-review.md`.

In the push that opens the PR: `git rm` this handoff, the plan and the review draft from `specs/handoffs/`, commit, push, then open the PR (REST, not `gh pr create`) with the draft as its body.

After merge, queue the cards: first full review of this repo (`r1`); review gates in nowline OSS milestones; review gates in the nowline commercial repos plus the first estate review (`nowline*`, home `nowline-workspace` if confirmed); optional monthly schedule.

## Key decisions

Reviews of `main` only; full is architectural, incremental line-level via `/code-review`; estates need no workspace; one model, strongest, fresh context; fix PRs don't touch `specs/reviews/`; the milestone gate runs between plans, never as a worker step.
