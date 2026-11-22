# Handoff: r1 rendering (m3: f1, f4, f9)

- Plan: `specs/handoffs/plan-r1-rendering-kestrel.md`
- Branch: `claude/charming-ramanujan-l3dgpq` (runner-assigned task branch, cut from `main` be8c1f6)
- Queue: r1-fixes-lantern 3, after 1 (#90) and 2 (#89), both merged
- Mode: unattended, confirmed 2026-11-22 in this session (dialog: Unattended, This session)
- Done: wave 1 [deep] m3 s1, 8d34bd1..ab8298b, review CONCERNS (renderer guard claim; per-tool record not durable); fix-up 1-fix 8d34bd1..d6ba861, review PASS; wave 2 [exec] m3 s2-s5, 8757ea0..6fff233 (6359f57 s2, d6c1c0d s3, 84e1680 s4, 6fff233 s5), review CONCERNS (T41 checks the removed f4 entries only in Claude Code); fix-up 2-fix 8757ea0..58c4451, review PASS
- Next unit: none; plan complete. Next: personal-ship-pr (draft PR, then #45 ticks)
- Expected total: ~$7.4 API-equiv; guard $50
- Spend: ~$14.5 API-equiv (Token log), against ~$7.4 expected; guard $50 never neared
- Resume: the plan is complete; the PR carries the state from here

## Decisions so far

- review wave-1 (public m3 s1): f9 takes option (a). `mcp.allow` names every tool that may run (217 `<key>:<tool>` entries, listed in `specs/handoffs/design-r1-f9-mcp.md` "New entries"); every other tool prompts in all three harnesses. No `mcp.ask` list and no ask plumbing: `permissions.ask` stays the user's. Claude Code renders `server:tool` as `mcp__server__tool` and `server:*` as `mcp__server__*`; Cursor IDE, Cursor CLI and Gemini rendering unchanged. T8 and T15 render the fixture meta, so s2 adds `figma:get_screenshot` to the fixture and a new test that installs the real `personal.json` (no server wildcard for the seven keys; 18 named send, share, write and deploy tools absent). See the note's "What s2 does differently".
- review wave-1-fix (public m3 s1): the Claude Code renderer uses the note's guarded `claude_mcp` (an entry must match `^[^:]+:.+$`, else `error("bad mcp entry: " + .)`); split at the first `:`.
- review wave-2 (public m3 s2-s5): `validate_meta` renders every target before any write, so a malformed entry that only one render rejects writes nothing. Claude Code keeps `Bash(<entry>:*)` (the docs call `:*` an equivalent trailing wildcard, not deprecated), but an entry that holds a `*` (`rm -rf /*`) renders `Bash(<entry>)` as written. A Cursor CLI deny with a colon in its first word errors the render. Unsafe flags (`--output`, `--pre`, `--upload-pack`) class as Destructive, checked first.

## Environment notes

- Runner identity commits as noreply@anthropic.com; accepted per core.md.
- github.com is unreachable from this container; `gh api` works for issue comments, and `developers.google.com/<path>.md.txt` and `docs.slack.dev/<path>.md` return plain text through curl.

## Deviations from plan

- Wave 1 review CONCERNS: automatic fix-up 1-fix (unattended).
- Wave 2 review CONCERNS: automatic fix-up 2-fix (unattended).
- First 2-fix launch refused by the workflow's own check before any agent ran: the parent passed steps `m3.s4` instead of the group's; relaunched corrected.
- Wave 2 worker: an entry holding `*` renders `Bash(<entry>)` in Claude Code, not `Bash(<entry>:*)` as the plan text said (the docs show `rm -rf /*:*` would miss the entry itself); review confirmed.

## Follow-ups (not in m3)

- scan.py reads `Bash(cmd)` with no `:*` as a prefix, though Claude Code treats it as exact (worker surprise, wave 2).
- From the design note: Cursor's docs don't document `mcpDenylist`; claude.ai connector tools (`mcp__claude_ai_<server>__*`) aren't covered by the meta.

- Fit check skipped: the Owner's prompt said the plan isn't direct-sized and to run a driver.
- Consolidation step skipped: wave 1 is a design note only; all code is in wave 2.

## After completion

- `personal-ship-pr`: PR description gets s1's design note, one `Fixes r1.f<K>` line each for f1, f4, f9, `Part of #45`, and `Queue: r1-fixes-lantern 3`. Remove this handoff, the plan and the design note before marking ready.
- Then re-read #45's body, tick only f1, f4, f9 and append the PR link to each.
