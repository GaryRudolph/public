Makes `personal-ship-pr` run on its own from "code is ready" to "merge-ready", so a session no longer stops at the draft PR. It opens the draft unasked and runs the loop as one pre-approved step. It waits on CI and reviews itself, merges `main` only when GitHub reports a conflict, then parks until you merge and says when it's done and archivable. Also: "punch it chewie" / "make it so" as ship triggers and voice lines, and related follow-ons ride in the same PR unless a split criterion says otherwise.

## Review guide

Review tier: [study], because it changes what agents do without asking (open PRs, push fixes, merge `main` in).
Blast radius: every session that loads the personal plugin; docs and a fail-open hook, a revert is safe.
Review time: ~16 min

1. [study] [`core.md`](https://github.com/GaryRudolph/public/compare/main...claude/beautiful-lovelace-5p8obp#diff-c1e2d2bf9b7fab8b83d3edd958794a2bf08b42577e5266e9ccf8a9673588c443): draft unasked, loop is one pre-approved step, conflict rule, "Say when a session is done"
2. [study] [`personal-ship-pr/SKILL.md`](https://github.com/GaryRudolph/public/compare/main...claude/beautiful-lovelace-5p8obp#diff-b6b86f5e3d025c550dd4a4f335a3b64a40d07953e1392be893da684f44abadfc): standing approval, skip line, Waiting, Keeping up with the base, Exits, Status
3. [check] [`ship_pr_hook.py`](https://github.com/GaryRudolph/public/compare/main...claude/beautiful-lovelace-5p8obp#diff-35d0f05865acfd2481e5b4bf729faca956d6b2e170e7152eab42e5dac7e0f069) and [`claude-hooks.json`](https://github.com/GaryRudolph/public/compare/main...claude/beautiful-lovelace-5p8obp#diff-079abf17d0add93ec9efe2304fc74691192ebba0ce030176c98609275aefa028): PostToolUse on PR creation, fails open
4. [check] [`pr_state.py`](https://github.com/GaryRudolph/public/compare/main...claude/beautiful-lovelace-5p8obp#diff-96f08d4e88305c0b7f65c9555d8ddf9a48f22458d6f984a135f33c2266067fa8): PR facts and `--wait-until`, no verdicts
5. [skim] [`git.md`](https://github.com/GaryRudolph/public/compare/main...claude/beautiful-lovelace-5p8obp#diff-2d643ebc49654b24a4c49da2465b6df6fe5e15b39be74a3ceb6d131befb175d8), [`review.md`](https://github.com/GaryRudolph/public/compare/main...claude/beautiful-lovelace-5p8obp#diff-271b89ce066f0a959ad0b8965d678702a86ace1d5573d06ac646d5ca3f7c540f): open the draft when ready, merge not rebase after open, when related work folds in
6. [skim] [`test_ship_pr.py`](https://github.com/GaryRudolph/public/compare/main...claude/beautiful-lovelace-5p8obp#diff-cb936fde61a28c2a5574a6f1b16d1e492bb69959bd1719c8fa7cc643f78f8e61), [`test-ship-pr.sh`](https://github.com/GaryRudolph/public/compare/main...claude/beautiful-lovelace-5p8obp#diff-6205ec7c3a38163e18bd05e7a4a3a20ed87e9289a3116f0a649e3065609c1164), [`agents/Makefile`](https://github.com/GaryRudolph/public/compare/main...claude/beautiful-lovelace-5p8obp#diff-f636515ed16c6c062d2e31157b8ff5e38dd1fb03ce19f1dcc0cf5c4441b9d4ee), [`plugins/README.md`](https://github.com/GaryRudolph/public/compare/main...claude/beautiful-lovelace-5p8obp#diff-8b2fec43efe67316d27984b7b6fe79569fa2e61ffdd6ed811aa114e29338b860)
7. [skim] [`personal-my-voice/SKILL.md`](https://github.com/GaryRudolph/public/compare/main...claude/beautiful-lovelace-5p8obp#diff-9d17946ecfd62d33a0a639ef4ff61b23d946b5ebc87de6322f559ff2f4a0b86e): the two go-ahead lines
8. [skip] [`personal-core.mdc`](https://github.com/GaryRudolph/public/compare/main...claude/beautiful-lovelace-5p8obp#diff-39a8d78a12609c027a769b918fbe42135cdb4da5ab7deaa55bb03bb12d504a79) (make cursor-core-rule)

## Validation

- `make -C agents validate test`: pass, including 40 new ship-pr tests against a fake `gh`
- Session-start parts: all under the hook cap (part 4 at 7,270)
- The hook in a live session, and `pr_state.py` against real GitHub: not run, this cloud session has no `gh` API access; this PR's own loop is the first live run

## Rollback

Revert the squash commit. `PERSONAL_SHIP_PR=0` turns the hook off without a revert.

<details open>
<summary>[study] Where the loop stops</summary>

| Moment | Before | After |
| --- | --- | --- |
| Work done | Often asks before a PR | Opens the draft |
| Draft open, walkthrough shown | Pauses (core "Pause after each step") | Carries on to step 2 |
| `[skim]`, no risk tag | Skips review silently | "Skipping /code-review: reason" |
| Waiting on CI or Copilot | Ends the turn; workstation waits for you | `pr_state.py` in a background Bash, or PR events plus a 30 min `send_later` |
| Conflict | Asks | Merges `main` in, resolves clear ones; asks on a behavior choice or a `[study]` area |
| Merge-ready | Stops | Parks, polls every 15 min for a conflict, ends on merge |
| Related follow-on | Proposes a new PR | Folded in unless a split criterion holds; split ones become cards |

Still stops: CI red not caused by the change, contract/design/security calls, three Copilot fix rounds, a refused draft, and the merge itself.

</details>

<details>
<summary>[check] Hook and script</summary>

The hook matches the same PR-creation shapes as `pr_body_guard.py` (MCP `create_pull_request`, `gh pr create` without `--web`, `gh api` POST to `pulls`) and adds context only; any error prints nothing. `pr_state.py` uses REST only, since GraphQL fails through the cloud proxy, so thread resolution isn't visible: it reports replies and the last author.

</details>

<details>
<summary>Decisions</summary>

- Background Bash, not Monitor: one wake per condition, and no 30-minute cap.
- Parking polls GitHub every 15 minutes in a background process instead of keeping a turn open: no context cost until a conflict or merge.
- A GitHub Action that comments on conflicting PRs when `main` moves would remove the polling. Not built; it needs a workflow in every repo.

</details>

https://claude.ai/code/session_01BNKwNXwU89MusxyHSkNc8M

Assisted-by: Claude Code
