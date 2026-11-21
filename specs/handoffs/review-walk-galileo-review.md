Adds `personal-review-walk`, a skill for going through a review's decisions, findings or recommendations with the Owner one item per turn: a one-paragraph overview, that item's choices in a dialog, then the next. Every answer goes into a walk file in `specs/handoffs/` that's committed, and on a runner pushed, before the next question, so a cloud worker that respawns mid-walk resumes at the first pending item. Issue #45 (r1, 26 items) is the worked example.

## Review guide

Review tier: [study], because a new skill tells agents to commit and push after every answer, and `core.md` gains an always-on rule.
Blast radius: every session that loads the personal plugin (one more core line, one more SessionStart part); the skill only runs when triggered. Docs only, a revert is safe.
Review time: ~10 min

1. [study] [`personal-review-walk/SKILL.md`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-galileo-mm2t9q#diff-ae0942fa0a9edd918e4c70e3597ca923613559d7c7401cec569cb6005b3313c3): the walk, the walk file, per-answer commit and push, the end-of-walk dialog
2. [check] [`personal-standards/core.md`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-galileo-mm2t9q#diff-c1e2d2bf9b7fab8b83d3edd958794a2bf08b42577e5266e9ccf8a9673588c443): "Walk review outcomes one item at a time"
3. [check] [`hooks/hooks.json`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-galileo-mm2t9q#diff-15fac3e04ee637c7e901946b73dc9e4b39f4c577c38bb32ddb71bc8ca36f2dce): sixth `session-start.sh` part, since core now fills five and the test wants a spare
4. [skim] [`personal-codebase-review/SKILL.md`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-galileo-mm2t9q#diff-84f4da220c8aefe3daa979f74462c52f6ce4236655150818a371896b43409474): offers the walk before remediation
5. [skim] [`personal-standards/SKILL.md`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-galileo-mm2t9q#diff-1a2057f8ab89601b806b95c230f8304914bb569a99b8dff4e03cdfca65515924), [`plugins/README.md`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-galileo-mm2t9q#diff-8b2fec43efe67316d27984b7b6fe79569fa2e61ffdd6ed811aa114e29338b860): index rows; README's stale "three times" line fixed
6. [skip] [`cursor/rules/personal-core.mdc`](https://github.com/GaryRudolph/public/compare/main...claude/peaceful-galileo-mm2t9q#diff-39a8d78a12609c027a769b918fbe42135cdb4da5ab7deaa55bb03bb12d504a79) (`make -C agents cursor-core-rule`)

## Validation

- `make -C agents validate test`: pass, after rebasing onto #86
- A walk of #45: not run, the skill isn't on `main` yet

## Rollback

Revert the squash commit. A walk file left on a branch is plain markdown; `git rm` it.

<details open>
<summary>[study] The walk</summary>

| | Before | After |
| --- | --- | --- |
| Pace | Agent's choice, often all items at once | One item per dialog |
| State | Conversation only | `specs/handoffs/walk-{topic}-{word}.md`, every item snapshotted as pending at the start |
| Save | None | Commit per answer; push per answer on a runner, before the next question |
| Resume | Lost on respawn | First `Outcome: pending` in the file; the file beats the conversation |
| GitHub | n/a | One summary comment at the end, after a yes; no checkbox ticks |

Outcome words match the register's statuses (`decided`, `fix`, `accepted`, `deferred`, `disputed`, `skipped`) so the next review's fix review can carry them over.

</details>

<details>
<summary>Decisions</summary>

- A skill, not just a core rule: the steps (resume, file format, per-answer commit, end-of-walk dialog) are a procedure; core carries one line so the behavior applies even when the trigger phrasing is vague.
- One GitHub summary at the end, not a comment per item: the commits already carry the state, and 26 comments is noise.
- No checkbox ticks: under codebase-review.md a tick means a remediation PR opened.
- The walk never edits `specs/reviews/`; register status stays the next review's call.

</details>

Claude-Session: https://claude.ai/code/session_01BNKwNYEc1BCPepio7t8hR4

Assisted-by: Claude Code
