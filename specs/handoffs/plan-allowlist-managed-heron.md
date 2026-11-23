# Plan: one canonical allowlist, Claude through managed settings, a smaller local layer

Status: drafted 2026-11-23, waiting for the Owner's go on m1.
Branch: `claude/nice-bohr-xt3iuw` (harness-assigned task branch).
Supersedes: `plan-allowlist-prefix-gap-quill.md` (its Gemini and Cursor IDE work folds into m4).
Refs: r1.f1, https://github.com/GaryRudolph/public/issues/45.

## Goal

`agents/allowlists/personal.json` stays the one canonical file. A merge that changes
what Claude Code should get opens a GitHub issue and posts it to `#infrastructure` in
the Rudolphs Slack, with the steps to paste the rendered managed settings into the
Lolay claude.ai org (a second org later, same file). Claude Code then gets its rules
from managed settings in every surface, cloud included, and the local installer stops
writing Claude Code. Cursor IDE, Cursor CLI and Gemini are then reviewed one by one
for the simplest way to reach each from the same file.

New files in this repo don't name another organization or its repo.

## Decisions taken

- The canonical file is the existing meta format (`shell`, `mcp`, `read`, `write`,
  `webfetch`, each with `allow`/`deny`). No new format; m1 writes it down.
- Claude Code shell allows stay exact and denies stay prefixes (the Owner's calls of
  2026-11-23 and 2026-11-22). The managed-settings render reuses the installer's Claude
  render, so the two can't drift before m3 removes the local one.

## Open questions for the Owner

- Lolay org membership: managed settings apply to every member.
- The second org's claude.ai name, for its entry in m2 (not needed to start).

## m1 - Canonical file, written down and rendered per target

- s1 [deep] `agents/allowlists/README.md`: the format, what each key means, how each
  target reads it (the per-target table below, kept current). A JSON Schema
  (`agents/allowlists/schema.json`) checked by `make -C agents validate`.
- s2 [deep] Move each target's render out of `allowlists.sh` into its own jq file
  under `agents/lib/render/` (`claude.jq`, `cursor-ide.jq`, `cursor-cli.jq`,
  `gemini.jq`), called by the installer and, for Claude, by m2. Behavior unchanged:
  the existing T41/T42/T43 tests pass untouched.
- s3 [exec] Claude render gains `read.deny` as `Read(...)` and `write.deny` as
  `Edit(...)` deny rules (today they reach Cursor CLI only). Tests.

STOP: Owner reviews the README table and the schema.

## m2 - Org pipeline: issue plus Slack on a change

- s1 [deep] `agents/org/`: `settings.json` registry (one entry per org setting: id,
  title, feeding paths, who applies it and where, the pasted file, the steps template),
  `lolay/claude-managed-base.json` (attribution `Assisted-by: Claude Code`; `autoMode`
  environment naming github.com/GaryRudolph and github.com/lolay as trusted source
  control, `$defaults` kept; a commit stamp key rendered last), and
  `lolay/claude-managed-settings.json`, generated, committed, checked stale by
  `make -C agents test`.
- s2 [exec] `agents/org/Makefile`: `render`, `check`, `install` (render, copy to the
  clipboard, print the paste steps).
- s3 [deep] `agents/org/settings_issue.py` plus tests: on a push to `main`, compare each
  setting's pasted file at the commit that last changed it with the last applied one
  (the last issue closed as completed); open or replace an `org-settings:<id>` issue only
  on a real change; post the new issue to Slack, best effort.
- s4 [exec] `.github/workflows/org-settings.yml` (push to `main` on the feeding paths,
  plus a dry-run dispatch; `issues: write` only; `SLACK_BOT_TOKEN` secret and
  `ORG_SETTINGS_CHANNEL` variable), and `make -C agents test-org-settings` failing when
  the workflow's `paths` miss one from the registry. `actions-check.py` covers the new
  workflow.
- s5 [exec] `agents/org/steps/claude-managed-settings.md` and `agents/org/README.md`.

Owner prerequisites before the first real run: a Slack app in the Rudolphs workspace
with `chat:write` only, invited to `#infrastructure`; its token as the
`SLACK_BOT_TOKEN` repo secret; the channel ID as the `ORG_SETTINGS_CHANNEL` repo
variable; the `org-settings:lolay-claude-managed-settings` label.

STOP: Owner merges, follows the first issue, pastes, and confirms a Claude Code session
(local and cloud) shows the managed rules.

## m3 - Local installer stops writing Claude Code

- s1 [deep] Remove the `claude` kind from `allowlists.sh`. `install` on a machine that
  has it removes this org's rendered entries from every Claude config dir (its
  sidecars are the baseline), leaves user entries alone, and deletes the sidecars.
  `CLAUDE_CONFIG_DIRS` handling stays only where something else still needs it.
- s2 [exec] Tests: upgrade from a HOME the current installer rendered; second install
  is a no-op. Runbook, README, `specs/agent-distribution.md` updated.

STOP: Owner runs `make -C agents install` on the Mac and checks `~/.claude/settings.json`.

## m4 - Each remaining target, systematically

- s1 [deep] For Cursor IDE, Cursor CLI and Gemini, read the current docs and answer:
  is there an org or team control; can the plugin or extension we already ship carry
  the rules or a hook; what does a hook's `allow` do (skip the prompt or only not
  block); what exact-match form exists. Write the findings into the m1 README table.
- s2 [deep] Propose per target: plugin hook, extension-shipped policy, or keep the
  installer; with the Gemini `commandRegex` and Cursor IDE flag-seatbelt decisions from
  the superseded plan revisited against the findings.

STOP: Owner decides per target; the build steps get planned then.

## Per-target table (today, before m1)

| Target | Gets the file through | Shell allow | Shell deny | MCP | Reaches cloud |
| --- | --- | --- | --- | --- | --- |
| Claude Code (CLI, IDE, cloud) | Installer, user `settings.json` | exact `Bash(...)` | prefix | named tools | No |
| Claude Code after m2/m3 | Managed settings, pasted from the issue | exact | prefix | named tools | Yes |
| Cursor IDE | Installer, `~/.cursor/permissions.json` | raw prefix | ignored by Cursor; local hook | `server:tool` | n/a |
| Cursor CLI | Installer, `~/.cursor/cli-config.json` | exact `Shell(b:args)`, none for one word | prefix | `Mcp(server:tool)` | n/a |
| Gemini CLI | Installer, `~/.gemini/policies/<org>-managed.toml` | `commandPrefix` | `commandPrefix` | none | n/a |
