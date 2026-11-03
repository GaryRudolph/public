A runner asked to delete a remote branch now tries `gh api -X DELETE "repos/{owner}/{repo}/git/refs/heads/{branch}"` first, then `git push origin --delete`, and if both are refused hands over that same `gh api` command, filled in, instead of a git one. Claude Code's cloud git proxy refuses pushes to any branch but the assigned one, and the `gh` command names the repo, so it runs from anywhere without a clone or the right remote. The delete still waits for an ask; only the method changes.

## Review guide

Review tier: [check], because it changes what runners do with a remote write.
Blast radius: runner sessions asked to delete a remote branch; text only, a revert is safe.
Review time: ~3 min

1. [check] `plugins/personal/skills/personal-standards/standards/git.md`: Merging, "Delete feature branches after merging"
2. [check] `plugins/personal/skills/personal-standards/core.md`: one clause on the existing remote-branch-delete sentence
3. [skip] `plugins/personal/cursor/rules/personal-core.mdc` (`make -C agents cursor-core-rule`)
4. [skip] `specs/handoffs/branch-delete-heron-review.md` (this draft; removed before merge)

## Validation

- `make -C agents validate test`: pass, same warnings as `main`; part 1 of the session-start text fits the hook cap (8643 characters)
- REST ref delete through the cloud proxy: not run, no branch to delete; if the proxy refuses it, the runner falls through to git, then hands over the command

## Rollback

Revert the squash commit.

<details>
<summary>[check] Standards text</summary>

| Where | Before | After |
| --- | --- | --- |
| git.md Merging | "Delete feature branches after merging" | adds: try `gh api` REST delete, then `git push --delete`, then hand over the `gh api` command |
| core.md | delete waits for me | same, plus the order and the handover, pointing at git.md |

</details>

<details>
<summary>Decisions</summary>

- `gh api` over `gh` subcommands: no `gh` subcommand deletes a branch, and the GraphQL ones are refused by the cloud proxy anyway.
- The full rule lives in git.md; core.md carries a clause, since it loads every session and has a size cap.

</details>
