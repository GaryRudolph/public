# Specs

Home for cross-cutting technical specs, designs, and data-model references in
this repo — documents that describe *what we are building and why*, and that
don't belong to a single skill, tool, or language folder.

Per `standards/documentation.md`: spec filenames are lowercase-kebab with no
`-spec` suffix (the folder already implies it); `README.md` is the one
ALL_CAPS filename allowed here. Throwaway drafts and research go to `.scratch/`
(gitignored), not here.

## Index

| Spec | What it covers |
|---|---|
| [agent-distribution.md](agent-distribution.md) | How the personal standards and skills reach every agent (Claude surfaces, Codex, Cursor, Gemini, Muse Code): the plugin layout, the home-directory installer, and the milestones that built them. |
| [plan-orchestration.md](plan-orchestration.md) | How `personal-plan-orchestrate` runs a tagged plan on subagents per tier: the harness-neutral core (gates from the plan, the kickoff's gated or unattended mode, fix-ups, the cost guard, task branches and the per-wave handoff), the Claude Code workflow, hooks and agents, Cursor, and the later phases. |
| [plan-orchestration-phase-1-report.md](plan-orchestration-phase-1-report.md) | The record of orchestrate's phase 0 spike and phase 1 dogfood on Claude Code (2026-10-06 to 2026-10-11): how it was tested, the exit-criteria and dogfood results, what works, the findings and their fixes, the costs, the defaults open to revisit, the open items, and where the evidence went. |

The MacWhisper database spec lives in the notes repo with the whisper skills
that use it (`specs/macwhisper-database.md` there).
