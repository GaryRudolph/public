# Plan: close the Gemini and Cursor IDE prefix-allow gap (r1.f1 follow-up)

Status: on hold. PR 98 merged; the Owner reopened the approach (drop the installer, ship the allowlist as plugin hooks). Do not code this plan until that discussion ends.
Branch: `claude/nice-bohr-xt3iuw` (harness-assigned task branch).
Refs: r1.f1, https://github.com/GaryRudolph/public/issues/45, follow-up recorded in
https://github.com/GaryRudolph/public/pull/98 ("Follow-ups").

## Problem

After PR 98, Claude Code (`Bash(<entry>)`) and Cursor CLI (`Shell(<base>:<args>)`)
get exact allows. Gemini (`commandPrefix`) and Cursor IDE (`terminalAllowlist`, raw
prefixes) still prefix-match every `shell.allow` entry in
`agents/allowlists/personal.json`, so `git fetch --upload-pack=<cmd>`,
`rg --pre <prog>`, `make test x --eval=...`, `git log --output=<path>`,
`sort -o`, `uniq IN OUT`, `tree -o` run with no prompt there.

## Owner decisions (2026-11-23)

1. Gemini: option (a). Render each allow as an exact `commandRegex`.
   Gemini tests the regex against `{"command":"<cmd>"}` with `"command":"`
   prepended, so `<regex-escaped entry>\"` anchors both ends. Denies stay
   `commandPrefix`. Redirection already prompts by default (no `allowRedirection`).
2. Cursor IDE: keep every entry as a prefix. The Owner rejected dropping entries
   ("git log and make test need to be allowed", "even git fetch is allowed").
   Interpreted as option (c): `agents/cursor/hooks/enforce-denylist.sh` routes a
   segment that uses a known exec/write/network flag on an allowed base through
   the existing escalation path (deny with sandbox=true and an agent_message that
   says retry with `required_permissions ["all"]` for an approval card; allow when
   sandbox=false). A seatbelt, not enforcement. Owner to confirm the interpretation.

## Steps (after PR 98 merges; rebase this branch onto main first)

- s1 [exec] `render_gemini_toml`: allows as `commandRegex`, escaping regex
  metacharacters, then TOML-escaping via `tojson`. Skip an allow holding `*`
  (same as the other exact renders).
- s2 [deep] Hook flag table: per base command, the flags that run programs, write
  files or reach outside (git fetch `--upload-pack`/`-u`/`--exec`; git log/show/diff
  `--output`, `--ext-diff`, `--textconv`; rg `--pre`, `--pre-glob`; make
  `--eval`, `-f`/`--file`, `-C`, `VAR=` overrides of SHELL/MAKE; sort `-o`/`--output`;
  uniq second operand; tree `-o`; go test/build `-exec`, `-toolexec`, `-o`;
  cargo `--config`, `-Z`; helm template `--post-renderer`, `--output-dir`;
  kubectl `--kubeconfig`, `--exec`-style plugins; terraform plan `-out`).
  Prefix-match long options so `--upload-p` and `--output-directory` hit.
- s3 [exec] Tests in `agents/lib/allowlists-test.sh` (T41 installs the real meta):
  Gemini file has `commandRegex` for every allow, no allow `commandPrefix`, and the
  regex matches `{"command":"git status"}` but not `"git status --x"`. Hook tests
  for each flag (escalate) and the bare command (allow).
- s4 [exec] Update `specs/reviews/r1/f1.md`, security.md "Agent Tool Permissions",
  hook header. `make -C agents validate test`.
