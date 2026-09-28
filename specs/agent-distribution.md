# Agent standards and skills distribution

How personal standards and skills reach every agent Gary uses: Claude Code
(Mac, cloud, self-hosted runner), Cowork, Claude chat, Codex/ChatGPT, Cursor,
Gemini CLI, and Muse Code. Setup steps live in
[`../agents/runbook.md`](../agents/runbook.md).

Status: m1 implemented on branch `claude/standards-skills-evaluation-0lf34z`;
m2 onward are manual or follow-up work.

## Evaluation of the previous setup

### What it did

`agents/Makefile` wrote a marker-delimited block into each tool's home config
(`~/.claude/CLAUDE.md`, `~/.gemini/GEMINI.md`, `~/AGENTS.md`,
`~/.codex/AGENTS.md`, Xcode). Each block `@`-imported `agents/AGENTS.md`, or
inlined it for Codex. It also symlinked `agents/skills/*` into
`~/.claude/skills` and `~/.cursor/skills`. The standards were cited as
absolute `~/Projects/personal/public/standards/...` paths.

### What was good, and stays

- One canonical source, with block markers that leave other installers'
  content alone.
- Sandboxed tests for every installer pass, plus the canary phrase for
  checking end to end.
- A clear precedence order: project, then organization, then personal.
- The standards themselves, and the "facts in script, judgment in agent"
  split in the skills.

### What broke or went stale

| # | Finding | Evidence |
| --- | --- | --- |
| 1 | **Nothing reached the runner, cloud sessions, Cowork, or chat.** Everything depended on files in `$HOME` on the Mac. | A session on the self-hosted runner runs with a per-session `CLAUDE_CONFIG_DIR`. Its debug log shows 0 user/project skills and no CLAUDE.md or AGENTS.md found, and `~/Projects/personal/public` doesn't exist there. The only skills it had were Anthropic's, synced from the claude.ai account. |
| 2 | **Absolute `~/Projects/...` paths** in `AGENTS.md` and five skills don't resolve on any other machine. | `grep -r '~/Projects/personal/public' agents/skills` |
| 3 | **Docs said Codex and Gemini have no skills system.** Both now read `SKILL.md` folders from `~/.agents/skills` (Gemini also from `~/.gemini/skills`). | `agents/README.md`, `agents/skills/README.md` |
| 4 | **A stale Cursor rule** described a `SHARED.md` → `AGENTS.md` sync (`make sync`) that no longer exists. | `.cursor/rules/agents-codex-sync.mdc` |
| 5 | **The project `.claude/settings.json` held one-off commit allowlist entries** with `/Users/gary/...` paths. | `.claude/settings.json` |
| 6 | **Three whisper skills linked to `../../../../specs/`**, one level above the repo. | `personal-whisper-{split,combine,split-combine}-db/SKILL.md` |
| 7 | **The Go standards weren't listed** in `AGENTS.md`. | `AGENTS.md` language list |
| 8 | **Cowork setup for the whisper skills relied on `~/.claude/skills/...`** existing. | `COWORK.md` file-access tables |
| 9 | **The model names in the plan-tier rules are behind** (Opus 4.8, Sonnet 4.6); the current family is Opus 5.5, Sonnet 5, and Haiku 4.5. | `core.md`, `standards/plan-execution.md` (not changed here; see m4) |

### What changed in the platforms

- **Plugins now sync from the claude.ai account.** A plugin turned on for
  the account (or by the organization) loads in chat, in Cowork, and in every
  Claude Code terminal session signed in with that account, as
  `<name>@synced`. That includes cloud and self-hosted runner sessions.
  Requires Claude Code v2.1.273 or later; the runner has v2.1.283.
- **Cloud sessions don't read `~/.claude`**, and they don't add marketplaces
  that a repo lists in `extraKnownMarketplaces`: that needs the trust dialog,
  which a cloud session never shows. So per-repo settings can't do this job.
- **Team plans get server-managed settings** (`claudeMd`, `enabledPlugins`,
  `extraKnownMarketplaces`), but they apply to every member of the
  organization.
- **Organization plugin sync** (Organization settings > Plugins & skills)
  requires a private marketplace repo. `GaryRudolph/public` is public, so it
  can only be added personally, through Customize > Plugins.
- **Agent Skills is a shared format.** Codex, Gemini CLI, Cursor, and Muse
  Code all read `SKILL.md` folders. Claude Code reads `AGENTS.md` natively.

## Options considered

| Option | Reaches | Cost | Verdict |
| --- | --- | --- | --- |
| A. Keep the installer; upload skill zips to claude.ai by hand | Chat, Cowork, synced sessions | Manual re-upload after every edit; drifts | Rejected |
| B. Server-managed `claudeMd` plus an org-synced plugin | All Claude Code, org-wide | Needs a private marketplace repo; applies to every Team member | Optional (runbook m6) |
| C. **Repo as plugin marketplace, added to Gary's claude.ai account; installer kept for other tools** | Every Claude surface, plus local Codex/Gemini/Cursor/Muse | One-time account setup; push to update | **Chosen** |
| D. Commit `.claude/settings.json` plugin config to each repo | Local Claude Code only | Per repo; ignored by cloud sessions | Rejected |

## Design

```
                 GaryRudolph/public (main)
                 .claude-plugin/marketplace.json
                 plugins/personal/  plugins/personal-workstation/
                    |                                   |
        claude.ai account (Customize > Plugins)    make install (Mac)
                    |                                   |
   +-------+--------+---------+---------+       +------+-------+----------+
   chat  Cowork  Claude Code  cloud   runner    ~/.agents  ~/.cursor  home-file
               (Mac, synced   session session   /skills    /skills    blocks
                or local                        Codex,     Cursor     Claude, Codex,
                marketplace)                    Gemini                Gemini, Cursor,
                                                                      Xcode
```

- **One tree, two plugins.** `personal` holds everything that works
  anywhere: the `personal-standards` skill (`core.md` plus the full
  `standards/`), the planning skills, and the Makefile skill.
  `personal-workstation` holds the skills that need this Mac (MacWhisper,
  allowlist-scout), so they stay out of cloud sessions' context.
- **Always-on core.** In Claude Code and Cowork, the plugin's SessionStart
  hook prints `core.md`. Hook output is capped at 10,000 characters and
  `core.md` is about 14,000, so the hook runs in up to three parts of 9,000
  characters each, split on line boundaries. On the Mac the hook stays
  silent when `~/.claude/CLAUDE.md` already has the `personal` block. Chat
  runs no hooks, so there the `personal-standards` skill (whose description
  covers any coding work) carries the core.
- **Inverted symlinks.** Plugins can't reach outside their own folder, so
  the real files moved into the plugin. `standards/` and `agents/AGENTS.md`
  are now symlinks pointing in, which keeps every existing `~/...` path
  working locally.
- **Paths.** Skills cite `../personal-standards/standards/<file>`, which
  resolves in the plugin cache and through `~/.agents/skills` symlinks. For
  the `~/Projects/...` paths in `core.md`, the hook and `SKILL.md` tell the
  agent where to find the same file on machines where that path doesn't
  exist.
- **Installer.** `SKILLS_SRC` is now a list; `~/.agents/skills` is a new
  target; `CLAUDE_SKILLS_MODE=plugin` (the default) keeps `~/.claude/skills`
  clear so a skill doesn't load twice; `LEGACY_SKILLS_SRC` sweeps links that
  still point at the old `agents/skills/`.
- **Versioning.** No `version` field, so each commit on `main` is a new
  version and synced surfaces pick it up at their next session start.

### Trade-offs

- Git records `agents/AGENTS.md` as a type change, so `git log --follow`
  doesn't trace `core.md` back to it. Use `git log -- agents/AGENTS.md` for
  the history before this change.
- Unpushed edits don't reach cloud or the runner. On the Mac, the local
  marketplace loads the working tree directly (runbook m3.s4).
- Chat gets skills but no always-on core.
- `personal-workstation`'s whisper skills cite `specs/macwhisper-database.md`,
  which is outside the plugin. That works on the Mac (local marketplace or
  symlinks) and nowhere else, which is where they're meant to run anyway.

## Milestones

### m1 - Plugin layout and installer (done on this branch)

Marketplace and plugins, SessionStart hook, `personal-standards` skill,
file moves with inward symlinks, relative skill paths, installer multi-source
support, `~/.agents/skills`, plugin mode and legacy sweep (with tests),
`make validate` and `make package`, and fixes for findings 3 to 8.

### m2 - Account and settings rollout

Follow the runbook, m2 to m5. Done when the canary answers correctly in
chat, Cowork, Claude Code on the Mac, a cloud session, and a runner session.

### m3 - Cross-vendor plugin manifests

Add `.cursor-plugin/plugin.json` (Cursor team marketplace and Cloud Agents),
`.codex-plugin/plugin.json` (Codex and ChatGPT), and
`gemini-extension.json` next to each `.claude-plugin/`. The folder layout
already matches, since all of them use `skills/<name>/SKILL.md`. Check each
vendor's current manifest schema before writing them; none were confirmed
for this spec. Also confirm where Muse Code reads user-level skills and
instructions (`~/.config/muse/`) and add an installer target if needed.

### m4 - Refresh the model-tier table

Update the tier-to-model mapping in `core.md` and
`standards/plan-execution.md` to the current models, and decide whether
`personal-plan-orchestrate` should also drive Claude Code subagents, which
now take a per-agent model.
