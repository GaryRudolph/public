Names the tool behind the session-title emoji rule in `core.md`. The rule said "prefix its title with the same emoji" but never said how, so cloud sessions outside `personal-ship-pr` (the only place `set_session_title` was named) often skipped it. Local CLI and desktop sessions have no model-callable rename at all, so the rule now says they skip the prefix and let the status line carry the state.

## Review guide

Review tier: [skim], one sentence of agent guidance, no contract or flow change.
Blast radius: agent behavior in every session that loads the personal plugin; a revert is safe.
Review time: ~2 min

1. [skim] [`plugins/personal/skills/personal-standards/core.md`](https://github.com/GaryRudolph/public/compare/main...claude/vigilant-rubin-td4ya3#diff-c1e2d2bf9b7fab8b83d3edd958794a2bf08b42577e5266e9ccf8a9673588c443): "Say where a session stands" names `set_session_title` and the local-session skip
2. [skip] [`plugins/personal/cursor/rules/personal-core.mdc`](https://github.com/GaryRudolph/public/compare/main...claude/vigilant-rubin-td4ya3#diff-39a8d78a12609c027a769b918fbe42135cdb4da5ab7deaa55bb03bb12d504a79) (`make -C agents cursor-core-rule`)

## Validation

- `make -C agents validate test`: pass

## Rollback

Revert the squash commit.

<details>
<summary>Decisions</summary>

- No hook: Claude Code hooks can set `sessionTitle` only from `SessionStart` and `UserPromptSubmit`, not `Stop`, where the state is known. A prompt-time 🔄 would stay stale after the turn ends on a local session.

</details>

Assisted-by: Claude Code

https://claude.ai/code/session_01BNKwNZxr2DWtL8sEuCytiD
