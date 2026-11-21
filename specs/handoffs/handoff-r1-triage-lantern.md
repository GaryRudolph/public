# Handoff: r1 issue triage (#45)

Branch: `claude/adoring-dijkstra-7trvfb`. No code changes; this session triages
issue #45 (r1 full review) and walks the Owner through each open finding, one
at a time: a problem paragraph, a fix trade-off paragraph, then a question.

## State of r1 at 6513660

- Fixed with claims: f18, f21.
- Fixed in substance, no claim file yet: f26 (#48).
- Mostly moot: f19 (CI installs sops and age; keyless-first ordering is a nit).
- Open, untouched: f1-f8, f11-f15, f20, f23-f25.

## Decisions so far

- f16: (a) gate on the computed limit.
- f22: (a) `doctor` in `agents/Makefile` plus root `triage.yaml`.
- f17: (a) `CLAUDE_CONFIG_DIRS` list looped by the Claude targets.
- f10: keep the session-doctor hook running `make doctor` on runners only;
  locally the hook only tells the agent to run it before its first build, so
  it goes through Claude Code's folder trust and permissions. f3's host check
  is still fixed.
- f9: allow writes with a rollback (version history) or creates the Owner
  deletes after; prompt on anything that sends to people or changes sharing,
  since history can't undo a leak. Notion, Google Docs, Figma, Miro keep
  wildcards minus sharing and permission tools; Slack and Google Workspace
  allow reads and prompt on send; Firebase allows reads and prompts on writes,
  deletes and deploys. The fixing session lists each server's real tool names.
- f12: validate every live file and sidecar with `jq empty` before writing
  any target; on any failure write nothing, name the file, exit non-zero.
- f11: fix; diff live against this org's last-rendered sidecar (meta render
  only on first install). Must land before f1, f4, f9.
- f13: fix; guard only when a live file exists that no org's sidecar explains.
- f2: fix; replace only allow and deny. Must land before f17.
- f1: fix allows and denies (Bash(...:*) for Claude Code, Shell(...) for
  Cursor CLI); ship with f4, after f11.
- f4: remove op read, op run, curl -X GET, curl --get, curl -G,
  wget --method=GET; keep git log/show/diff; scout classifies --output, --pre,
  --upload-pack as unsafe.
- f6: exact command form where Cursor CLI supports it, else don't write
  multi-word commands for Cursor CLI; same rule for f1's rendering; add scout
  tests and a test target.
- f14: declined; rely on makefile.md's CONFIRM_* danger guards, review
  aggregate targets by eye. Record as accepted in r2.

## Pending

Walk the remaining findings one at a time, then the session plan. Proposed
sessions (not started): allowlist installer state (f11, f12, f13, f2); then
rendering (f1, f4, f9); then config dirs (f17); scout (f6, f14); guards (f7,
f8, f16); secrets kit (f5, f24, f19 nit); session doctor (f3, f10, f22);
facts and docs (f15, f20, f23, f25, f26 claim). `agents/lib` changes need a
port session in the Agerpoint bok.
