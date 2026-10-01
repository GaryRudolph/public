# Runbook: standards and skills on every agent

One-time setup that gets `personal` standards and skills into every surface
Gary uses. Background and design:
[`../specs/agent-distribution.md`](../specs/agent-distribution.md).

Do the milestones in order. m2 has to come before m3: m3's `make install`
removes the old Claude pieces (the `~/.claude/CLAUDE.md` block and the
`~/.claude/skills` symlinks), which is only safe once the plugin is on the
account.

| Surface | What you change | Milestone |
| --- | --- | --- |
| claude.ai account (chat, Cowork, synced Claude Code) | Add the marketplace, install `personal` | m2 |
| Claude Code on the Mac | Version, sign-in, local marketplace, `make install` | m3 |
| Self-hosted runner | Nothing, or an optional fallback file | m4 |
| Claude Code cloud sessions | Nothing | m5 |
| Team organization (optional) | Org plugin sync or managed `claudeMd` | m6 |
| Codex, Cursor, Gemini CLI, Muse Code | Nothing on the Mac; their plugin or extension elsewhere | m7 |

### m1 - Merge the repo change

#### s1 - Review and merge

Review the branch `claude/standards-skills-evaluation-0lf34z` and merge it
to `main`. Synced surfaces read `main` only.

#### s2 - Pull on the Mac

```bash
cd ~/Projects/personal/public && git pull
make -C agents validate test
```

### m2 - claude.ai account

These settings travel with the account, so they cover chat, Cowork, and
every Claude Code session you sign in to, including cloud and the runner.

#### s1 - Confirm Skills is on for the organization

As Team Owner: **Organization settings > Capabilities**, turn **Skills** on.
When Skills is off, plugins don't sync either.

#### s2 - Check the marketplace restrictions

In **Admin settings > Claude Code > Managed settings**, make sure
`strictKnownMarketplaces` (if set) includes `GaryRudolph/public` and
`blockedMarketplaces` doesn't list it. If neither is set, skip this step.

#### s3 - Add the marketplace to your account

In claude.ai or the desktop app: **Customize > Plugins > Add > add
marketplace from GitHub**, then enter `GaryRudolph/public`. Public GitHub
repos are allowed for marketplaces you add yourself. Auto-update is on by
default for marketplaces added this way.

#### s4 - Install the plugins on the account

- Install **`personal`**. This is the one that has to be on the account.
- Leave **`workstation`** off the account and install it locally in m3.s4,
  so cloud and runner sessions don't carry a Mac-only skill description.
  The whisper skills Cowork runs now live in the notes repo (see their
  `COWORK.md` there).

#### s5 - Optional: a nudge for chat

Chat doesn't run hooks, so the always-on core isn't injected there. If you
want coding chats to reach for it without being asked, add a line under
**Settings > Profile > personal preferences**, for example: "For coding,
specs, commits, or reviews, use my personal-standards skill."

### m3 - Claude Code on the Mac

#### s1 - Update Claude Code

```bash
claude update && claude --version     # need 2.1.273 or later for plugin sync
```

#### s2 - Refresh the sign-in

If you last signed in on an older version, run `/login` once so the token
covers plugin sync.

#### s3 - Check user settings

In `~/.claude/settings.json`, make sure `syncClaudeAiPlugins` isn't set to
`false`. No other user-settings change is needed.

#### s4 - Add the local marketplace for live edits

The synced copy tracks `main`. For edits that take effect without a push,
install from the working tree. A marketplace plugin outranks a synced one
with the same name, so the two don't load twice.

```bash
claude plugin marketplace add ~/Projects/personal/public
claude plugin install personal@personal --scope user
claude plugin install workstation@personal --scope user
```

A marketplace added from a local directory loads plugins in place: edits
apply at the next session start, or after `/reload-plugins`.

#### s5 - Re-run the installer

```bash
cd ~/Projects/personal/public/agents
make dry-run      # expect: Claude block and ~/.claude/skills links removed,
                  #         ~/.agents/skills links added
make install
make status       # modes line first; ~/.claude/CLAUDE.md "no personal block (plugin mode)"
```

`CLAUDE_MODE` defaults to `plugin`, so this install removes what the
installer used to write for Claude Code: the `~/.claude/CLAUDE.md` block and
the `~/.claude/skills` symlinks, including any still pointing at the old
`agents/skills/`. Anything else in those places is left alone. From then on,
Claude Code on the Mac gets the core the same way cloud and the runner do,
from the plugin's hook. With the local marketplace from s4, that hook reads
your working tree, so edits still apply without a push.

The other tools stay on `home` until you move them (m7). Each tool has a
mode: `CLAUDE_MODE`, `CODEX_MODE`, `GEMINI_MODE`, `CURSOR_MODE`, each `home` or
`plugin`. Set per-machine choices in `agents/local.mk`, which git ignores,
so a plain `make install` keeps honoring them:

```make
# agents/local.mk
CODEX_MODE := plugin
```

#### s6 - Verify

```bash
claude plugin list        # personal@personal enabled; personal@synced "not loaded" (shadowed)
```

In a new session, ask "What is the personal canary phrase?" and
"Which personal- skills do you have?" Expect
`personal-public-canary-3e8d41`, plus the nine `personal` skills and the
one `workstation` skill.

### m4 - Self-hosted runner

#### s1 - Confirm the prerequisites

Host setup (the runner user, the LaunchAgent, the self-hosted environment)
is in [`../setup/mac/claude/runner.md`](../setup/mac/claude/runner.md). For
standards and skills, nothing more is needed: the runner user has no Claude
login of its own, but each session runs as the claude.ai account that
started it and downloads that account's synced plugins into its
per-session config (`CLAUDE_CODE_SYNC_PLUGINS=1` is already set). Two things
to check:

- The runner's Claude Code is 2.1.273 or later. It had 2.1.283 when this
  was written: `claude --version` on the runner, or the `AI_AGENT`
  variable in a session.
- The runner can reach `api.anthropic.com` and `github.com`. It already
  does, for the checkout.

The runner is started with `--confine-repo-settings enforce`, which refuses
repos whose committed settings reach outside the workspace. This repo's
`.claude/settings.json` only allows a few `make -C agents` commands, so it
passes.

#### s2 - Optional fallback, if account sync is off

If you ever turn account sync off, the plugin can be pinned with a managed
settings file on the runner host. Two cautions:

- **It applies to every macOS user on the Mac.** The file lives under
  `/Library`, so on a host with one runner user per org
  ([`runner.md`](../setup/mac/claude/runner.md)) it would put your personal
  plugin into every org's sessions. Don't use it on a shared host; keep
  account sync on instead.
- **It only applies while the Team has no server-managed settings.** Claude
  Code uses the first managed source that sets any key, checking
  server-managed first.

`/Library/Application Support/ClaudeCode/managed-settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "personal": { "source": { "source": "github", "repo": "GaryRudolph/public" } }
  },
  "enabledPlugins": { "personal@personal": true }
}
```

#### s3 - Verify

Start a runner session on any repo and ask for the canary phrase. It
should answer with the phrase from the synced plugin's hook, without any
`~/Projects` checkout on the runner.

### m5 - Claude Code cloud sessions

#### s1 - Nothing to configure

Cloud sessions don't read `~/.claude`, and they ignore `extraKnownMarketplaces`
in a repo's settings. They do load plugins synced from the account, and
they run plugin SessionStart hooks, so m2 already covers them.

#### s2 - Verify

Start a cloud session on any repo (claude.ai/code, or `claude --cloud "What
is the personal canary phrase?"`) and check the answer.

### m6 - Team organization (optional)

Skip this unless you want the standards to apply to every member of the
lolay Team, or want them marked **Required**. Both options below apply to
the whole organization.

#### s1 - Org plugin sync

Organization sync needs a private marketplace repo. Create one, for example
`GaryRudolph/claude-marketplace`, holding only
`.claude-plugin/marketplace.json`, with public `git-subdir` sources that
point into this repo:

```json
{
  "name": "personal",
  "owner": { "name": "Gary Rudolph" },
  "plugins": [
    {
      "name": "personal",
      "source": {
        "source": "git-subdir",
        "url": "https://github.com/GaryRudolph/public.git",
        "path": "plugins/personal"
      }
    }
  ]
}
```

Then go to **Organization settings > Plugins & skills > Add > Sync from
GitHub**, pick that repo, leave **Sync automatically** on, and set the
plugin to **Installed by default** or **Required**. If you do this, remove
the personal install from m2.s3–s4 so there's only one source.

#### s2 - Managed `claudeMd`

The server-managed settings key `claudeMd` (**Admin settings > Claude Code
> Managed settings**) injects instruction text into every member's Claude
Code sessions, with no approval prompt. It's an alternative to the hook for
the always-on core, but it applies to everyone, has to be pasted by hand,
and would duplicate the hook. Not recommended while the plugin covers it.

### m7 - Other tools

Each tool has two routes. On the Mac, the `make install` symlinks from m3.s5
already cover it. The plugin route is for other machines and each vendor's
cloud agents. Use one route per tool on a given machine: Codex and Cursor
show a skill twice if it arrives both ways.

None of these three CLIs was available where this was written, so the
manifests were checked for agreement (`make -C agents test`) but not loaded
by the tools. Treat the first install of each as the real validation.

#### s1 - Codex CLI and ChatGPT

- **Mac:** the `~/.codex/AGENTS.md` block plus `~/.agents/skills`. Nothing
  more to do. Check that the skills show up in `$`-mention autocomplete.
- **Plugin (other machines, ChatGPT, Codex cloud):**

  ```bash
  codex plugin marketplace add GaryRudolph/public
  ```

  Then install `personal` from Codex's plugin browser. Codex reads the
  marketplace from `.agents/plugins/marketplace.json` and each plugin from
  `.codex-plugin/plugin.json`. It runs the same SessionStart hook as Claude,
  so the core comes with it. Plugins are shared between Codex and ChatGPT.
  To use the plugin on the Mac too, add `CODEX_MODE := plugin` to
  `agents/local.mk` and run `make install`. That removes the
  `~/.codex/AGENTS.md` block, since the plugin's hook brings the core. The
  `~/.agents/skills` links stay until Gemini also moves to `plugin`, because
  the two share that directory, so skills show twice in Codex until then.
  Whether a Codex *cloud* task loads account plugins is unconfirmed; check
  it with the canary.

#### s2 - Cursor

- **Mac:** `~/AGENTS.md` plus copied `~/.cursor/skills` (refreshed by a
  Cursor hook), until you move to the plugin.
- **Plugin (Cursor Cloud Agents, other machines):** in Cursor, go to
  **Customize > From GitHub Repository** and enter `GaryRudolph/public`.
  Cursor reads `.cursor-plugin/marketplace.json`. Then install `personal`.
  If you also want the plugin on the Mac, add `CURSOR_MODE := plugin` to
  `agents/local.mk` and run `make install`, which removes the
  `~/AGENTS.md` block, the `~/.cursor/skills` copies, and the refresh hook.
  The plugin carries the core as the always-apply `personal-core` rule
  (generated from `core.md` by `make -C agents cursor-core-rule`), so check
  **Rules** lists it before switching. The denylist hook stays in both
  modes.
- **Without the plugin:** turning on **Sync Skills for Cloud Agents** copies
  `~/.cursor/skills` to cloud agents. Re-sync after edits.

#### s3 - Gemini CLI

- **Mac:** the `~/.gemini/GEMINI.md` block plus `~/.agents/skills`.
- **Extension (other machines with a checkout):**

  ```bash
  gemini extensions link ~/Projects/personal/public/plugins/personal
  ```

  Gemini only installs straight from GitHub when `gemini-extension.json`
  sits at the repo root, so these subfolder extensions install from a local
  path. The extension runs the SessionStart hook, which returns JSON for
  Gemini, and its skills are overridden by same-named user skills, so
  linking it on the Mac doesn't duplicate anything. To rely on the
  extension on the Mac, add `GEMINI_MODE := plugin` to `agents/local.mk`
  and run `make install`, which removes the `~/.gemini/GEMINI.md` block.
  Check with `/skills list` and `/extensions list`.

#### s4 - Muse Code

Muse has no plugin format that I found, and the steps below aren't
confirmed; check them on first use. Muse reads the project `AGENTS.md`
(falling back to `CLAUDE.md`) and repo-local `.claude/skills` and
`.codex/skills`. To bring in the personal skills:

```bash
muse skills import --from codex     # reads ~/.agents/skills
muse skills list
```

If import only looks at `~/.claude/skills`, run
`make install CLAUDE_MODE=home` first, import, then `make install` again. Muse's user-level config is reported to live in
`~/.config/muse/`; where it reads global instructions is still unconfirmed.

### m8 - Verification matrix

Ask "What is the personal canary phrase?" in each surface. Expect
`personal-public-canary-3e8d41`.

| Surface | Expected source | Pass |
| --- | --- | --- |
| Claude Code, Mac | Plugin hook (local marketplace) | ☐ |
| Claude Code, cloud | Synced plugin hook | ☐ |
| Claude Code, runner | Synced plugin hook | ☐ |
| Cowork | Synced plugin hook | ☐ |
| Chat | `personal-standards` skill (ask it to use the skill) | ☐ |
| Codex CLI | `~/.codex/AGENTS.md` | ☐ |
| Gemini CLI | `~/.gemini/GEMINI.md` | ☐ |
| Cursor | `~/AGENTS.md` | ☐ |
| Muse Code | Project `AGENTS.md` or imported skill | ☐ |

## Troubleshooting

- **Canary fails in cloud or on the runner.** In the session, ask Claude to
  run `claude plugin list`, or read `/status`. If `personal@synced` is
  missing, check m2.s1 (Skills on), m2.s4 (installed on the account), and
  the Claude Code version. A plugin enabled mid-session arrives at the next
  session start.
- **Canary works but standards files can't be found.** The agent tried
  `~/Projects/...`. The hook's first part gives the in-plugin path; make sure
  part 1 of 2 appears in `/context`.
- **Skills appear twice on the Mac.** Something still symlinks into
  `~/.claude/skills`. Run `make status`: the modes line should say
  `CLAUDE_MODE=plugin`, and `agents/local.mk` shouldn't override it.
- **A tool lost its standards after `make install`.** Its mode is `plugin`
  but its plugin isn't installed. Set it back to `home` in `agents/local.mk`
  and run `make install`, or install the plugin (m2 for Claude, m7 for the
  others).
- **Only a 2,000-character preview of the standards appears.** A hook part
  went over 10,000 characters. Check that `max_chars` in
  `plugins/personal/scripts/session-start.sh` is still 9000, and that the
  third hook entry is still in `hooks.json`.
- **claude.ai rejects the plugin.** `make validate`; a top-level `bin/`
  inside a plugin folder is the usual cause.
- **Gemini reports a failed SessionStart hook.** Something printed non-JSON
  text. Run `GEMINI_PROJECT_DIR=. plugins/personal/scripts/session-start.sh 1`
  and check that the output is exactly one JSON object.
- **A skill shows up twice in Codex or Cursor.** Both the plugin and the
  `make install` symlinks are active on that machine. Keep one (m7).

## Rollback

- Take one surface out: `claude plugin disable personal@synced` (Mac or
  runner user settings), or uninstall it under **Customize > Plugins**.
- Go back to the old way for Claude: add `CLAUDE_MODE := home` to
  `agents/local.mk` and run `make -C agents install`. That restores the
  `~/.claude/CLAUDE.md` block and the skill symlinks.
- Remove everything the installer wrote, for every tool:
  `make -C agents uninstall`. It ignores the modes, sweeps links to the old
  `agents/skills/`, and prints how to remove the plugins, which it doesn't
  manage.
- Undo the repo change: revert the merge commit. The old `standards/` and
  `agents/AGENTS.md` paths come back as real files.
