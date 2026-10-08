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
| [changelog-fragments.md](changelog-fragments.md) | Why changelog entries ship as `.changelog/` fragment files instead of `CHANGELOG.md` edits: the departures from HashiCorp's model, the nowline evidence, and nowline's migration checklist. |

The MacWhisper database spec lives in the notes repo with the whisper skills
that use it (`specs/macwhisper-database.md` there).
