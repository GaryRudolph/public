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

## Pending

- Question to the Owner, verbatim: "s1 is committed and pushed. Go on to s2
  (upgrade tests, docs), then validate/test and ship the PR?"
- s2 [exec]: upgrade tests in `agents/lib/allowlists-test.sh` (HOME rendered by
  the old installer: user entries kept, ours gone, sidecars gone, second install
  a no-op); docs: `agents/allowlists/README.md` "Claude Code, local" row,
  `agents/README.md`, `agents/runbook.md`, `agents/Makefile` header,
  `specs/agent-distribution.md`.
- Then `make -C agents validate test`, then personal-ship-pr. PR says the Owner
  runs `make -C agents install` on the Mac and checks `~/.claude/settings.json`.

## Gotchas

- `agents/lib/` is shared byte for byte with another bok; porting this there
  strips that org's Claude rules from its config dirs unless it also has managed
  settings. Flag in the PR; don't name the org in repo text.
- The allowlist scout (`plugins/workstation/.../personal-allowlist-scout`)
  counts global Claude coverage from each config dir's `settings.json`, which no
  longer holds the org rules: follow-up card.

## Resume

Check out the branch, read this file, answer the question above, continue at s2.
