# Handoff: allowlist targets review (m4 s1, s2)

Branch: `claude/amazing-meitner-zf682z` (assigned by the harness). Part of
r1.f1, https://github.com/GaryRudolph/public/issues/45, after
https://github.com/GaryRudolph/public/pull/100.

## Done

- s1: the vendor findings are in `agents/allowlists/README.md` under "What
  each harness offers", with sources.

## s2 proposal, per target

**Cursor IDE: plugin hook for denies and the flag seatbelt; the installer
keeps the allows.**

- **Allows stay in the installer.** No hook or plugin can auto-run a command,
  and Run Mode controls on the team dashboard are Enterprise only.
- **The deny hook moves into the personal plugin.** `enforce-denylist.sh` goes
  into `plugins/personal/hooks/cursor-hooks.json` (`beforeShellExecution`). It
  reads a rules file rendered from `personal.json` into the plugin, kept
  current by a check like `agents/org`'s. `hooks.sh` then stops installing the
  denylist hook.
- **The flag seatbelt stays.** Prefix allows stay, per the Owner's call, and
  the hook routes known exec, write and network flags to approval.
- **The seatbelt asks instead of denying.** Rather than deny and tell the
  agent to retry with `required_permissions ["all"]`, the hook answers `ask`.
  This depends on a local test confirming that `ask` prompts in Allowlist mode
  and for commands already on the allowlist.

**Cursor CLI: keep the installer; the same plugin hook is a backstop.**

- `cli-config.json` keeps its exact allows and prefix denies.
- The plugin hook also fires in the CLI. That covers the reported case where a
  project `.cursor/cli.json` replaces the global denies.
- A local test needs to confirm that `Shell(git:log)` does not match
  `git log -5`.

**Gemini CLI: keep the installer and switch allows to exact
`commandRegex`.**

- An extension can't ship allows, since its tier 2 `allow` rules are dropped.
  A hook `allow` doesn't skip the prompt either.
- The only org-level path is a root-owned admin dir, which is still a local
  install.
- Allows become `commandRegex = "<RE2-escaped, JSON-escaped entry>\""`.
- Denies stay `commandPrefix` in the same user-tier file. An extension's tier
  2 deny would rank below a user allow.

## Pending question

The question goes to the Owner in one AskUserQuestion call, one question per
target. Each recommends the option above, with these alternatives:

- **Cursor IDE:**
  - keep the hook in the installer;
  - try an exact `git:log` form instead of the seatbelt.
- **Cursor CLI:**
  - add no plugin backstop.
- **Gemini CLI:**
  - keep `commandPrefix`;
  - use the admin tier.

## Resume

Read the README section and this file, then re-ask if there is no answer on
record. The build gets planned once the answers are in. Remove this file
before the PR is marked ready.
