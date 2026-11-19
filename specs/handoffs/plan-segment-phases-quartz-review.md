Declares fixed `Draft`, `Execute` and `Review` phases in `plan-segment.js`'s workflow `meta`, so `/workflows` groups a run's agents by stage. Before, the phase title was computed per run (`Wave 2 of 5 [exec]`), which `meta.phases` can't declare because it must be a pure literal, so every run showed one ad hoc group.

## Review guide

Review tier: [check], because the change touches the workflow's `meta`, and a `meta` the runtime rejects stops every orchestrate launch on Claude Code.
Blast radius: `personal-plan-orchestrate` on Claude Code only. The change is display only: routing, gates, schemas and labels are unchanged. A revert is safe.
Review time: ~3 min

1. [check] [`plugins/personal/skills/personal-plan-orchestrate/claude-workflows/plan-segment.js`](https://github.com/GaryRudolph/public/compare/main...claude/elegant-mayer-6fbupw#diff-61ba8e1bff88d5fc5f33eb456c12ed2babcb328d7f2409ee7e508d041d8a9087): `meta.phases`, each `agent()` call's `phase`, and the unit title moved from `phase()` to `log()`

## Validation

- `make -C agents validate test`: pass
- Script parse check (`meta` stripped, body wrapped in an async function under node): pass
- A live `Workflow` launch of `plan-segment`: not run, needs a tagged plan and a kickoff

## Rollback

Revert the squash commit.

<details>
<summary>[check] Phase grouping</summary>

| Agent | Phase before | Phase after |
| --- | --- | --- |
| Draft N, Judge | `Wave {w} of {t} [{tier}]` | `Draft` |
| Worker, retry | same | `Execute` |
| Reviewer | same | `Review` |

Every label still starts with the unit title (`title(g)`), so the wave and group stay visible on each agent row. The unit title is also logged once at the start of the run.

</details>

<details>
<summary>Decisions</summary>

- Fixed stage phases rather than leaving `meta.phases` out. A per-wave title can't go in a pure-literal `meta`, and a stage view is the more useful one for a single unit.
- No note on wide waves and the session's workflow size guideline. That guideline is about workflows the model writes itself. `plan-segment` is a named workflow the skill launches at the user's request, and `plan_state.py` sets its size.

</details>

Assisted-by: Claude Code
