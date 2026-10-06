# Agent standards and skills distribution

How personal standards and skills reach every agent Gary uses: Claude Code
(Mac, cloud, self-hosted runner), Cowork, Claude chat, Codex/ChatGPT, Cursor,
Gemini CLI, and Muse Code. Setup steps live in
[`../agents/runbook.md`](../agents/runbook.md).

Status: m1, m3, m5, and m6 implemented on branch
`claude/standards-skills-evaluation-0lf34z`; m2 is manual setup; m4 (model-tier
refresh) is done except for the Claude Code orchestrate decision.

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
| 9 | **The model names in the plan-tier rules were behind** (Opus 4.8, Sonnet 4.6); the current family is Opus 5.5, Sonnet 5.5, and Haiku 4.5. | `standards/plan-execution.md`, `personal-plan-orchestrate`, `personal-plan-model-tiers` (fixed in m4) |

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
                 plugins/personal/  plugins/workstation/
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
  `workstation` holds the skills that need this Mac (allowlist-scout), so
  they stay out of cloud sessions' context. The MacWhisper skills later
  moved to the notes repo as repo-local skills.
- **Always-on core.** In Claude Code and Cowork, the plugin's SessionStart
  hook prints `core.md`. Hook output is capped at 10,000 characters and
  `core.md` is about 11,000 (14,300 before m5), so the hook runs in up to
  three parts of 9,000 characters each, split on line boundaries. The hook
  stays silent in any tool whose home file still has the `personal` block,
  so nothing is injected twice while a machine is mid-migration. Chat
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
  target; per-tool modes (m6) retire the old block and links for any tool
  that has moved to its plugin; `LEGACY_SKILLS_SRC` sweeps links that still
  point at the old `agents/skills/`.
- **Versioning.** No `version` field, so each commit on `main` is a new
  version and synced surfaces pick it up at their next session start.

### Trade-offs

- Git records `agents/AGENTS.md` as a type change, so `git log --follow`
  doesn't trace `core.md` back to it. Use `git log -- agents/AGENTS.md` for
  the history before this change.
- Unpushed edits don't reach cloud or the runner. On the Mac, the local
  marketplace loads the working tree directly (runbook m3.s4).
- Chat gets skills but no always-on core.

## Milestones

### m1 - Plugin layout and installer (done on this branch)

Marketplace and plugins, SessionStart hook, `personal-standards` skill,
file moves with inward symlinks, relative skill paths, installer multi-source
support, `~/.agents/skills`, plugin mode and legacy sweep (with tests),
`make validate` and `make package`, and fixes for findings 3 to 8.

### m2 - Account and settings rollout

Follow the runbook, m2 to m5. Done when the canary answers correctly in
chat, Cowork, Claude Code on the Mac, a cloud session, and a runner session.

### m3 - Cross-vendor plugin manifests (done on this branch)

Each plugin carries `.codex-plugin/plugin.json`,
`.cursor-plugin/plugin.json`, and `gemini-extension.json` next to
`.claude-plugin/`. Codex and Cursor marketplaces sit at
`.agents/plugins/marketplace.json` and `.cursor-plugin/marketplace.json`.
`agents/lib/manifests-check.py` (part of `make test`) fails when names,
descriptions, or marketplace listings drift apart.

- **One hook file for three tools.** Claude Code, Codex, and Gemini share
  the `hooks/hooks.json` format. The command resolves the plugin root from
  `CLAUDE_PLUGIN_ROOT`, which Claude and Codex export, or from Gemini's
  `${extensionPath}` substitution. The script prints JSON for Gemini, which
  rejects plain stdout, and plain text for the others. Each tool stays
  silent when its own home file already has the `personal` block.
- **Cursor stays off the Claude-format hook file.** Its manifest points at
  an empty `hooks/cursor-hooks.json`.
- **Per-tool route switches.** `CLAUDE_MODE`, `CODEX_MODE`, `GEMINI_MODE`,
  and `CURSOR_MODE` (`home` | `plugin`) let one machine use a tool's plugin
  without also getting the old block and symlinks; see m6.
- **Not verified in the tools themselves.** None of the Codex, Cursor, or
  Gemini CLIs were available to load the manifests, so the first install of
  each is the real test. The runbook (m7) says what to check.
- **Gemini installs from a local path only.** It installs from GitHub only
  when `gemini-extension.json` sits at the repo root, so these subfolder
  extensions use `gemini extensions link <path>`.
- **Muse Code has no plugin format** that I found; it imports skills.

### m4 - Refresh the model-tier table (mostly done)

The tier-to-model mapping in `standards/plan-execution.md`, and the slugs in
`personal-plan-orchestrate` and `personal-plan-model-tiers`, now name Opus 5.5
and Sonnet 5.5 (`core.md` carries no model names). The Claude Code column uses
the version-less aliases `opus`, `sonnet`, and `haiku`, which resolve to the
newest model of each tier, so only the Cursor column needs future bumps. Thinking
is set with `/effort`, since Opus 5.5 and Sonnet 5.5 can't turn thinking off.

The 2026-10-01 refresh added an `[xdeep]` tier above `[deep]`, turned the
picker into one row per harness (Claude Code, Cursor, Codex, Gemini CLI,
Muse Code, Grok Build), and priced every model in it. For the moment,
`[xdeep]` runs Opus 5.5 at max effort, plus ultracode (Claude Code's
multi-agent mode) in Claude Code, with Fable 5.1 as the alt when a
different model is wanted. Opus 5.5 beats Fable 5.1 on every benchmark
Anthropic published, at 40% of the per-token price, so `[xdeep]` now buys
depth with token volume rather than a pricier model. Claude Code `[deep]`
dropped from `xhigh` to `high`, matching Cursor. Revisit when the next
Fable ships. In Cursor,
`[exec]` moved to Grok 4.7, which bills from Cursor's included pool and
scores within 4 points of Sonnet 5.5 on CursorBench 4.0; `[deep]` stays on
Opus because Grok trails it by about 10. Cursor slugs now use the bracket
parameters from Cursor's subagent docs.

Still open: whether `personal-plan-orchestrate` should drive Claude Code
subagents. Their `model` parameter takes aliases, but
[anthropics/claude-code#43869](https://github.com/anthropics/claude-code/issues/43869)
is still open and reports it is ignored, so the harness gate stays.

### m5 - Turn procedures into skills (done)

See [Standards versus skills](#standards-versus-skills) below. Done so far:
`personal-handoff` and `personal-new-project`, plus trimming the matching
`core.md` bullets to short rules that point at the skills (14,300 to about
11,000 characters). The naming and version rules stay always-on, because
plan mode and scaffolding requests won't reliably trigger a skill.
`personal-new-project` ships `latest_versions.py`, which asks npm, PyPI, the
Go proxy, crates.io, RubyGems, Maven Central, GitHub releases, Homebrew, and
endoflife.date and reports what they say. `personal-secrets` ships the secrets standard's
Makefile contract as a tested kit (`templates/secrets-repo/`, exercised by
`tests/test-kit.sh`, which `make test` runs when `sops` and `age` are
installed). Building it turned up two faults in the standard's script
sketches: `build.sh` failed with "no matching creation rules" and left an
empty `dist/` file behind, and it used bash 4 associative arrays that
macOS's bash 3.2 lacks. The standard now points at the kit instead of
carrying inline script bodies. `personal-release` covers the versioning
standard's release and hotfix flows, with `release_facts.py` (facts only,
including the build-version string and version-field drift),
`templates/bump_version.py` (lock-step bump plus changelog move), and
`templates/release.yml`, all tested by `tests/test-release.sh`. It also
fixed `core.md`'s "simplified `v1`, `v2`, `v3`" versioning line, which
described only the contract regime and contradicted the SemVer rule for
artifacts.
`personal-repo-baseline` carries the per-repo settings the plugin can't:
`.claude/settings.json` `attribution` (plugin settings take only `agent` and
`subagentStatusLine`, and cloud sessions read the repo's file, not
`~/.claude/settings.json`) and GitHub's squash-only merge settings. It ships
`repo-facts.sh` (facts only), `merge_settings.py` (adds keys, never drops
one), and `tests/test-repo-baseline.sh`, and `personal-new-project` runs it
last. That doesn't revive option D (committing plugin config,
`enabledPlugins`, to each repo's `.claude/settings.json`): cloud sessions
read that file but still don't load the plugins it names.

### m6 - Retire the old way per tool (done on this branch)

Each tool has a mode in `agents/Makefile`: `CLAUDE_MODE` (default
`plugin`), `CODEX_MODE`, `GEMINI_MODE`, and `CURSOR_MODE` (default `home`).
In `plugin` mode, `make install` removes what the installer wrote for that
tool before:

| Mode | Removes |
| --- | --- |
| `CLAUDE_MODE=plugin` | `~/.claude/CLAUDE.md` block and `~/.claude/skills` links, both sides under WSL |
| `CODEX_MODE=plugin` | `~/.codex/AGENTS.md` block |
| `GEMINI_MODE=plugin` | `~/.gemini/GEMINI.md` block |
| `CURSOR_MODE=plugin` | `~/AGENTS.md` block, `~/.cursor/skills` copies, refresh hook |
| `CODEX_MODE` and `GEMINI_MODE` both `plugin` | `~/.agents/skills` links, which the two share |

The Xcode blocks are always kept, because no plugin carries the core to
them. (The Cursor block used to be kept too; since the Cursor plugin ships
the core as the generated `personal-core` rule, `CURSOR_MODE=plugin`
removes it.) Removal leaves content outside
the block and links the installer didn't make, and a second run is a no-op
(covered by `blocks-test.sh` test 8, `extensions-test.sh` test 12, and
`roundtrip-test.sh`). The installer libs are now shared byte for byte with
the Agerpoint bok (`ORG` selects the identity), which also brought Cursor
copy mode, the managed denylist hook, and a full `make uninstall`.
Per-machine choices go in the gitignored `agents/local.mk`. `make uninstall`
ignores the modes and removes everything, including links to the old
`agents/skills/`, then prints how to remove the plugins, which the Makefile
doesn't manage.

Still local-only, with no plugin equivalent: the allowlists
(`install-allowlists`), because plugins can't ship permission rules, and the
Xcode blocks.

## Standards versus skills

### The test

A **standard** says what good looks like. It's reference material, read
when relevant, and cited by path. A **skill** runs a procedure that a
request triggers ("set up secrets for this repo", "cut a release",
"write a handoff"). It may bundle scripts and templates, and it applies the
standards rather than repeating them. `personal-makefile` is the model: a
workflow skill that loads `standards/makefile.md` and adds detection
scripts and templates.

So no standard should *become* a skill. The standards stay the single
source. The question is which procedures buried in the standards, or in the
always-on `core.md`, deserve a thin skill of their own. Three signals:
there are ordered steps, a clear request triggers it, and a script could
gather facts ("facts in script, judgment in agent").

### Recommendations

| Candidate | Source today | Why a skill | Priority |
| --- | --- | --- | --- |
| `personal-handoff` | `core.md` bullets for handoff files, `.scratch/plan-*` files, milestone handoffs (about 1.8k characters always on) | "Write a handoff" is a direct trigger with a fixed file-name and contents recipe. Moving it out shrinks the always-on core, and a script can pick the `{word}` and list what changed | High |
| `personal-plan-*` (existing) | The 2.6k-character "Plan around model-tier stop points" bullet in `core.md` repeats `plan-execution.md` and the three plan skills | Cut the bullet to a two-line pointer at the skills. With the handoff and new-project moves as well, `core.md` drops from about 14,300 to about 11,000 characters (measured after both moves). The naming and version rules stay always-on, so it stays over the 10,000 cap and the hook still splits it | High |
| `personal-secrets` | `standards/secrets/` (820 lines): consumer step, one-time setup runbook, rotation and offboarding, reference scripts | Longest and most procedural standard. Three clear triggers (set up, add a consumer repo, rotate). The reference scripts could ship in `scripts/` instead of as prose | High |
| `personal-release` | `standards/versioning.md`: promote-to-release and hotfix flows, plus 12k characters of per-platform surfaces | "Cut a release" or "ship a hotfix" is a trigger. A script can detect which platform surfaces a repo has, so the agent loads only those sections | Medium |
| `personal-new-project` | `core.md` "latest stable versions" bullet, plus `architecture.md` "Starting New Projects" | Scaffolding is a trigger, and the version lookups (`npm view`, `pip index versions`, GitHub releases) are exactly the facts a script should gather. Also takes about 1k characters out of the always-on core | Medium |
| `personal-spec` | `documentation.md`: spec structure, spec authoring workflow, milestones and steps | "Write a spec" is a trigger with a structure to follow. Lower value because the rules are short and already in `core.md` | Low |
| `personal-pr` | `git.md`: commit rules, PR body template | Claude Code, Codex, and Cursor all have their own commit and PR flows. A skill adds little beyond the template, which the standard already holds | Low; skip |
| `personal-security-review` | `security.md` pre-deployment checklist plus the language security files | A real trigger, but it overlaps with each tool's built-in security review. Worth it only if the built-in reviews miss your checklist | Low |

Keep as reference only: `code-style`, `architecture` (apart from new
projects), `testing`, `platform-parity`, `swift/state-observation`, and
every language folder. They answer "what should this look like?", and the
`personal-standards` index already loads them on demand.

### Suggested order

1. `personal-handoff`, plus trimming the plan-tier bullet (done). That's the
   biggest context saving, and it's mechanical.
2. `personal-secrets`, moving the reference scripts into the skill (done).
3. `personal-new-project` and `personal-release`, each with a small fact
   script (both done).
