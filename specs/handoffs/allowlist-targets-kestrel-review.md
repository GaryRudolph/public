Gemini allows now match the exact command. `git log` no longer also approves
`git log --output=<path>`, and `rg` no longer approves `rg --pre <prog>`. Each
allow in `~/.gemini/policies/<org>-managed.toml` is now a `commandRegex` that
pins both ends of the command; denies stay `commandPrefix`. The allowlist
scout reads that form back as exact.

This also records what Cursor IDE, Cursor CLI and Gemini each offer for
delivering these rules, from current vendor docs and the Gemini source,
along with the Owner's call per target:

- **Cursor IDE:** unchanged. Prefix allows, with the installed deny hook.
- **Cursor CLI:** unchanged. The installer writes it.
- **Gemini:** the installer writes it, with exact allows.

None of the three can take allows from a plugin or extension, and a hook
answering `allow` never skips the prompt.

Refs r1.f1 (m4), part of https://github.com/GaryRudolph/public/issues/45

## Review guide

Review tier: [study] [security]. This changes what Gemini runs without
asking, though only by narrowing it.
Blast radius: Gemini sessions on a machine that reruns `make
install-allowlists`. A command that used to auto-run with extra arguments
(`git log -5`) now prompts. Rolling back means reverting and re-running the
installer.
Review time: ~15 min

1. [study] [security] [allowlist.jq](DIFF:agents/lib/allowlist.jq) `gemini_allow_regex` and [allowlists.sh](DIFF:agents/lib/allowlists.sh) `render_gemini_toml`: is the escaping right, and does the end pin hold?
2. [check] [scan.py](DIFF:plugins/workstation/skills/personal-allowlist-scout/scripts/scan.py) `gemini_exact_from_regex`: does it accept only our form?
3. [check] [allowlists-test.sh](DIFF:agents/lib/allowlists-test.sh) and [test_render_scan.py](DIFF:plugins/workstation/skills/personal-allowlist-scout/tests/test_render_scan.py)
4. [skim] [README.md](DIFF:agents/allowlists/README.md), with the per-target findings, decisions and sources, and the scout's [reference.md](DIFF:plugins/workstation/skills/personal-allowlist-scout/reference.md)

### Validation

- `make -C agents validate test`: pass. This adds T23b (escaping) and
  updates T23 and T42c.
- Scout tests: pass. 40 tests, 3 of them new (`GeminiPolicy`).
- The real `personal.json` rendered, then matched with Gemini's own pattern
  (`\x00"command":"(?:<re>)` over the sorted args, each top-level pair
  wrapped in `\0`). The match ran in Python `re`, not RE2, but these
  escapes behave the same in both. Every one of the 162 entries matches
  itself, and none matches itself plus ` --x` or `x`.
- Not run: a live Gemini CLI. The matching was checked against the source at
  v0.70.0 (`packages/core/src/policy/utils.ts`, `stable-stringify.ts`).

### Rollback

Revert the commit and re-run `make install-allowlists`. The installer
rewrites `<org>-managed.toml` and keeps the old one in `.history/`.

<details open><summary>[study] Gemini render</summary>

| | Before | After |
| --- | --- | --- |
| Allow `git log` | `commandPrefix = "git log"`, which also matches `git log -p`, `git log --output=x` | `commandRegex = "git log\""`, which matches `git log` only |
| Allow `make test.x` | `commandPrefix` | `commandRegex = "make test\\.x\""` |
| Deny `rm -rf /` | `commandPrefix`, priority 900 | unchanged |

Gemini searches `\x00"command":"(?:<re>)` in the JSON of the arguments.
Inside that value every literal `"` is `\"`, so the bare `"` at the end of
the regex can only be the closing quote. The entry goes in JSON-escaped,
then RE2-escaped, then TOML-escaped by `tojson`. A compound command is
split, and each part is checked on its own. A redirection still asks.

Note: `allowlist.jq`, `allowlists.sh` and `allowlists-test.sh` are shared
byte for byte with the other bok's `agents/lib/`. This needs porting there.

</details>

<details><summary>[check] Scout read-back</summary>

`gemini_exact_from_regex` accepts a regex only when every RE2 metacharacter
in it is escaped, it ends in `"`, and the rest decodes as a JSON string.
Anything else covers nothing, so the scout keeps proposing the command. The
`commandRegex` value is decoded with `json.loads`. The old `_toml_strings`
unescaped in the wrong order for `\\"`, and `commandPrefix` still uses it.

</details>

<details><summary>[skim] Docs</summary>

The README gains "What each harness offers": org controls, what a plugin or
extension can carry, what a hook's `allow` does, and the exact-match form
for each target, with sources. It also records the Owner's per-target calls
and three things only a Mac test can settle.

</details>

### Decisions

- **Gemini allows stay in the installer.** An extension's `policies/` loses
  every `allow` (tier 2). A `BeforeTool` hook's allow doesn't skip the
  prompt. The admin tier needs a root-owned directory.
- **Gemini denies stay in the user-tier file.** An extension's deny would
  rank below a user allow.
- **Cursor IDE stays as it is**, so `hooks.sh` stays the same everywhere it's
  shared.

Assisted-by: Claude Code

https://claude.ai/code/session_01BNKwNbiwvHFHKm4hE5eTei
