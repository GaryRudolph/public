# Runbook: standards and skills on every agent

One-time setup that gets `personal` standards and skills into every surface
Gary uses. Background and design:
[`../specs/agent-distribution.md`](../specs/agent-distribution.md).

Do the milestones in order. m2 has to come before m3: m3 removes the
`~/.claude/skills` symlinks, which is only safe once the plugin is on the
account.

| Surface | What you change | Milestone |
| --- | --- | --- |
| claude.ai account (chat, Cowork, synced Claude Code) | Add the marketplace, install `personal` | m2 |
| Claude Code on the Mac | Version, sign-in, local marketplace, `make install` | m3 |
| Self-hosted runner | Nothing, or an optional fallback file | m4 |
| Claude Code cloud sessions | Nothing | m5 |
| Team organization (optional) | Org plugin sync or managed `claudeMd` | m6 |
| Codex, Gemini CLI, Cursor, Muse Code | `make install`, plus one toggle per tool | m7 |

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
- Install **`personal-workstation`** on the account only if you run the
  whisper skills from Cowork (see its `COWORK.md`). If you don't, leave it
  off the account and install it locally in m3.s4, so cloud and runner
  sessions don't carry seven Mac-only skill descriptions.

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
claude plugin install personal-workstation@personal --scope user
```

A marketplace added from a local directory loads plugins in place: edits
apply at the next session start, or after `/reload-plugins`.

#### s5 - Re-run the installer

```bash
cd ~/Projects/personal/public/agents
make dry-run      # expect: old ~/.claude/skills links removed, ~/.agents/skills added
make install
make status
```

`make install` keeps the `~/.claude/CLAUDE.md` block. The plugin's hook
checks for that block and stays silent, so the core isn't injected twice.

#### s6 - Verify

```bash
claude plugin list        # personal@personal enabled; personal@synced "not loaded" (shadowed)
```

In a new session, ask "What is the personal canary phrase?" and
"Which personal- skills do you have?" Expect
`personal-public-canary-3e8d41`, plus the five `personal` skills and the
seven `personal-workstation` skills.

### m4 - Self-hosted runner

#### s1 - Confirm the prerequisites

No per-session setup is needed. Runner sessions sign in with your claude.ai
account and download synced plugins into their per-session config
(`CLAUDE_CODE_SYNC_PLUGINS=1` is already set). Two things to check:

- The runner's Claude Code is 2.1.273 or later. It had 2.1.283 when this
  was written: `claude --version` on the runner, or the `AI_AGENT`
  variable in a session.
- The runner can reach `api.anthropic.com` and `github.com`. It already
  does, for the checkout.

#### s2 - Optional fallback for the runner only

If you ever turn account sync off, the runner operator can pin the plugin
with a managed settings file on the runner host. This file only applies
while the Team has no server-managed settings, because Claude Code uses
the first managed source that sets any key, checking server-managed first.

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

`make install` (m3.s5) already did the file work. What's left is one step
per tool.

#### s1 - Codex CLI (and ChatGPT's Codex)

- Instructions: the `~/.codex/AGENTS.md` block, inlined by `make install`.
- Skills: `~/.agents/skills/personal-*`. Check with `$` mention
  autocomplete in Codex.
- Codex cloud tasks only read the repo's own `AGENTS.md`. Personal skills
  reach them only once there's a Codex plugin (spec m3).

#### s2 - Gemini CLI

- Instructions: the `~/.gemini/GEMINI.md` block.
- Skills: `~/.agents/skills` (Gemini's alias for user skills). Check with
  `/skills list` in Gemini.

#### s3 - Cursor

- Instructions: `~/AGENTS.md` (ancestor walk) and `~/.cursor/skills`.
- For Cursor Cloud Agents, turn on **Sync Skills for Cloud Agents** in
  Cursor settings. Cursor then copies `~/.cursor/skills` for cloud agents.
  The symlinks point at the repo, so re-sync after edits.

#### s4 - Muse Code

This path isn't confirmed; check it on first use. Muse reads the project
`AGENTS.md` (falling back to `CLAUDE.md`) and repo-local `.claude/skills`
and `.codex/skills`. To bring in the personal skills:

```bash
muse skills import --from codex     # reads ~/.agents/skills
muse skills list
```

If import only looks at `~/.claude/skills`, run
`make install CLAUDE_SKILLS_MODE=symlink` first, import, then
`make install` again. Muse's user-level config is reported to live in
`~/.config/muse/`; where it reads global instructions is still to be
confirmed (spec m3).

### m8 - Verification matrix

Ask "What is the personal canary phrase?" in each surface. Expect
`personal-public-canary-3e8d41`.

| Surface | Expected source | Pass |
| --- | --- | --- |
| Claude Code, Mac | `~/.claude/CLAUDE.md` block | ☐ |
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
  `~/.claude/skills`. Run `make status`; `CLAUDE_SKILLS_MODE` should be
  `plugin`.
- **Only a 2,000-character preview of the standards appears.** A hook part
  went over 10,000 characters. Check that `max_chars` in
  `plugins/personal/scripts/session-start.sh` is still 9000, and that the
  third hook entry is still in `hooks.json`.
- **claude.ai rejects the plugin.** `make validate`; a top-level `bin/`
  inside a plugin folder is the usual cause.

## Rollback

- Take one surface out: `claude plugin disable personal@synced` (Mac or
  runner user settings), or uninstall it under **Customize > Plugins**.
- Go back to Claude skill symlinks:
  `make -C agents install CLAUDE_SKILLS_MODE=symlink`.
- Undo the repo change: revert the merge commit. The old `standards/` and
  `agents/AGENTS.md` paths come back as real files.
