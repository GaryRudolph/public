# Handoff: allowlist m3, drop Claude Code from the installer

Branch: `claude/awesome-bardeen-qugb3n` (assigned by the harness). Brief: m3 of
the allowlist work from GaryRudolph/public#100 (r1.f1, part of #45).

## Done

- s1 [deep] (commit `m3.s1 drop the claude kind from the allowlist installer`):
  `agents/lib/allowlists.sh` no longer renders `settings.json`. Install,
  dry-run and uninstall clear each `CLAUDE_CONFIG_DIRS` dir (plus the Windows
  Claude dir under WSL) that still has `.settings.<org>-managed.json`: entries
  in that sidecar and in no other org's or the user-managed sidecar come out of
  `settings.json` in place (order kept, backup in `.history/`); the sidecar
  goes, and the user-managed and passthrough sidecars once no other org's is
  left; a file left `{}` is removed. Status/diff report pending cleanup; clean
  covers those `.history/`; restore drops `settings.json`. `validate_meta` still
  renders `claude_permissions`. Existing tests adapted; `make -C agents
  validate test` green.

- Owner answered after s1: continue through ship; shared lib: note it in the
  PR, port to the other bok later.
- s2 [exec] (commit `m3.s2 ...`): T46-T50 upgrade tests in
  `agents/lib/allowlists-test.sh`, a Makefile-level leftover check in
  `agents/tests/test-claude-dirs.sh`; docs updated (allowlists README row,
  agents README, runbook m3.s6 new with Verify now s7, Makefile header, org
  README, spec). T49/T50 caught `gemini_dirs` returning 1 under `set -e`,
  which skipped `claude_dirs` in clean and the uninstall history prompt; fixed.
  `make -C agents validate test` green.

## Pending

- personal-ship-pr: draft PR, /code-review, CI, ready, Copilot rounds. PR says
  the Owner runs `make -C agents install` on the Mac and checks
  `~/.claude/settings.json`. Remove this handoff before marking ready.

## Gotchas

- `agents/lib/` is shared byte for byte with another bok; porting this there
  strips that org's Claude rules from its config dirs unless it also has managed
  settings. Flag in the PR; don't name the org in repo text.
- The allowlist scout (`plugins/workstation/.../personal-allowlist-scout`)
  counts global Claude coverage from each config dir's `settings.json`, which no
  longer holds the org rules: follow-up card.

## Resume

Check out the branch, read this file, answer the question above, continue at s2.
