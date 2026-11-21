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
- f9: Owner's rule is "allow writes that have a rollback (version history) or
  that create something the Owner deletes after". Pending: confirm the per-server
  application, including prompting for anything that sends to people or changes
  sharing, since version history doesn't undo a leak.

## Pending

Walk the remaining findings one at a time, then the session plan. Proposed
sessions (not started): allowlist installer state (f11, f12, f13, f2); then
rendering (f1, f4, f9); then config dirs (f17); scout (f6, f14); guards (f7,
f8, f16); secrets kit (f5, f24, f19 nit); session doctor (f3, f10, f22);
facts and docs (f15, f20, f23, f25, f26 claim). `agents/lib` changes need a
port session in the Agerpoint bok.
