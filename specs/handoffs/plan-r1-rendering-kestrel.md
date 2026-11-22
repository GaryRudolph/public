```
--- KICKOFF: begin orchestration at [deep] ---

  Status: 0/5 groups done | last review: — | current: public m3 s1 [deep] | updated 2026-11-22

  mode: unattended | proposed unattended (harness=claude-code runner=cloud; assigned branch, CLAUDE_CODE_REMOTE=true) | guard 3x min $50 | fixups 2 | confirmed 2026-11-22 session 2ec2fdaa-1eac-5814-b7c2-d7ccce5bf7da: Unattended (Recommended)

  review: every-wave (log-only)

  Next model
    Cursor:      claude-opus-5-5[effort=high]
    Claude Code: /model opus                (/effort high)

  Prompt to paste into the next chat:
    In GaryRudolph/public, read specs/handoffs/plan-r1-rendering-kestrel.md. The plan is already tagged.
    On branch claude/charming-ramanujan-l3dgpq (task branch): subagents commit each finished step.
    Run in unattended mode.
    Run the personal-plan-orchestrate skill from the top: walk to
    each tier boundary, dispatch subagents per the skill's
    procedure, and pause only where the recorded mode stops. Do not
    execute plan work inline. Update plan progress after each wave
    returns per the skill's procedure. The mode line above is the
    kickoff answer. If the Status line shows BLOCKED, re-post that
    question and wait; otherwise record the mode, print the kickoff
    summary and begin dispatching.

---
```

**Cost (API-equiv, Claude Code models)**

| wave | expected tokens | expected $ |
|---|---|---|
| 1 [deep] m3 s1 | ~2.7M | ~$1.4 |
| 2 [exec] m3 s2-s5 | ~5.6M | ~$2.2 |
| orchestrator | ~4.3M | ~$3.8 |
| **Total** | ~13M | ~$7.4 |

Expected values are estimates, good to about 2-3× per wave. Wave 1: one medium `[deep]` step on Opus high plus its Opus review. Wave 2: s2 medium, s3 small (folded `[fast]`), s4 small, s5 large, on Sonnet high, plus an Opus review. Orchestrator: kickoff, two waves, one wait (the kickoff answer, unattended), no new-chat start-up on a runner.

## Shape

Creates:
- `specs/handoffs/design-r1-f9-mcp.md` — s1's design note; its text moves into the PR description and the file leaves before the PR is marked ready
- `specs/reviews/r1/f9.md` — fix claim the remediation plan requires for each finding
- `specs/reviews/r1/f4.md` — fix claim
- `specs/reviews/r1/f1.md` — fix claim
Modifies:
- `agents/allowlists/personal.json`
- `agents/lib/allowlists.sh`
- `agents/lib/allowlists-test.sh`
- `agents/cursor/hooks/enforce-denylist.sh`
- `plugins/personal/skills/personal-standards/standards/security.md`
- `plugins/workstation/skills/personal-allowlist-scout/scripts/scan.py`
- `plugins/workstation/skills/personal-allowlist-scout/reference.md`
- `plugins/workstation/skills/personal-allowlist-scout/tests/test_render_scan.py` (guess: or a sibling test file in that folder)

Consolidation step: skipped. Wave 1 writes a design note only; every code change sits in wave 2, which one worker runs.

## Context

Every step reads this section. m3 of the r1 remediation plan: fix r1.f1, r1.f4 and r1.f9 from the r1 full review, in one PR, in this repo only (nothing is ported to the Agerpoint bok, though `AGENTS.md` says `agents/lib/` is shared with it).

- Tracking issue: https://github.com/GaryRudolph/public/issues/45
- The Owner's walk outcomes, authoritative for every decision and fix note: https://github.com/GaryRudolph/public/issues/45#issuecomment-7074013504
- The remediation plan: https://github.com/GaryRudolph/public/issues/45#issuecomment-7074103845
- Register: `specs/reviews/2026-11-04-r1-full-findings.md`, sections r1.f1, r1.f4, r1.f9. Its locations are at fe5a3fe; re-read each at HEAD. Where a recommendation there differs from the walk comment or this plan, the walk comment and this plan win.
- Prerequisites merged: #90 (installer state: f11's baseline is this org's on-disk sidecar, so an entry dropped from the meta or re-rendered in a new form replaces the old one instead of being promoted to user-managed) and #89 (the scout's Cursor CLI exact form, `reference.md` section 3).
- The meta (`agents/allowlists/personal.json`) has only `allow` and `deny` per section; `agents/lib/allowlists.sh` renders it into Cursor IDE `permissions.json`, Cursor CLI `cli-config.json`, Claude Code `settings.json` and a Gemini policy TOML, Unix and (under WSL) Windows. Since #90 (f2) the installer owns only `permissions.allow` and `permissions.deny` in the two `permissions` files; `ask`, `defaultMode` and the rest pass through as the user's.
- Claim files: for each finding, `specs/reviews/r1/f<K>.md` in the shape of `specs/reviews/r1/f18.md` and `f6.md` (four lines: `Finding:`, `Claim: fixed`, `Change:`, `Evidence:`). Touch nothing else under `specs/reviews/`.
- Every step ends with `make -C agents validate test` passing.

--- WAVE 1 [deep] ---

### m3 - Rendering (f1, f4, f9)

#### ⬜ s1 - [deep] f9 design: how "allow writes with a rollback, prompt on sends" renders

The Owner's f9 decision: allow MCP writes that have a rollback (version history) or are creates the Owner deletes afterward; prompt on anything that sends to people, changes sharing, or can't be recovered. Notion, Google Docs, Figma and Miro keep their wildcards minus the sharing and permission tools. Slack and Google Workspace allow reads and prompt on send. Firebase allows reads and prompts on writes, deletes and deploys.

The seven entries today (`agents/allowlists/personal.json`, `mcp.allow`): `notion:*`, `slack:*`, `miro-mcp:*`, `firebase:*`, `figma:*`, `googledocs:*`, `googleworkspace:*`. Read `render_target_schema` in `agents/lib/allowlists.sh` for how each target renders them today: Cursor IDE `mcpAllowlist` as written (`server:tool`), Cursor CLI `Mcp(server:tool)`, Claude Code `mcp__<server>__*` (it keeps only the server part, so `notion:notion-search` would render today as a whole-server wildcard), Gemini none (MCP is out of scope there).

1. Look up each server's current tool names from its maintainer's docs or source (the official Notion, Slack, Miro, Firebase, Figma MCP servers; for `googledocs` and `googleworkspace`, find which server the names refer to and say how sure you are). Record each tool with what it does and its class under the decision: read, write with rollback, create, send to people, sharing or permission change, unrecoverable (delete, deploy). Cite the source URL and the date for each server.
2. A deny blocks rather than prompts, and in every harness a tool that matches no allow entry prompts. Choose between:
   - (a) enumerate the allowed tools by name in the meta's `mcp.allow`, rendered by name in every harness, so everything else (including tools a server adds later) prompts;
   - (b) a new meta `mcp.ask` list, rendered as Claude Code's `permissions.ask` beside the wildcard allow, with enumeration in harnesses that have no ask list.
   Weigh at least: what each does when a server adds a tool (fail open or closed); whether a harness accepts the rendered form (check Claude Code's and Cursor's current docs for MCP permission syntax, including a per-tool form and whether Cursor CLI has an ask list); and that since #90 the installer treats `permissions.ask` as the user's passthrough, so (b) would mean managing a third list through the sidecar, union, promotion and passthrough code.
3. Write `specs/handoffs/design-r1-f9-mcp.md`: options, choice, why; the per-server table (tool, class, allowed or prompted, source); the exact new `mcp.allow` (and `mcp.ask`, if chosen) entries; how each target renders them, including the Claude Code renderer change; and anything s2 below must do differently from its text. Under 150 lines. Its text goes into the PR description later.

Acceptance: the note exists and is committed under `m3.s1`; every one of the seven servers has a sourced tool list or an explicit "could not confirm, so <fail-closed choice>"; the choice names what s2 changes. No code changes in this step.

--- WAVE 2 [exec] ---

#### ⬜ s2 - [exec] f9 apply: rewrite the seven MCP entries and render them everywhere

Implement `specs/handoffs/design-r1-f9-mcp.md` (s1's note; where it says s2 differs from this text, the note wins).

- Rewrite the seven `mcp` entries in `agents/allowlists/personal.json` per the note.
- In `agents/lib/allowlists.sh` `render_target_schema`, render every target correctly: Claude Code renders `server:*` as `mcp__<server>__*` and `server:<tool>` as `mcp__<server>__<tool>` (never a server wildcard for a named tool); Cursor CLI `Mcp(server:tool)`; Cursor IDE `server:tool`; Gemini unchanged (out of scope, say so in the header comment if it isn't already). If the note chose an ask list, wire it through every place that handles `allow`/`deny` for those kinds (render, union, user-edit promotion, passthrough, status, diff) and keep the f2 rule that a user's own `ask` entries survive.
- Tests in `agents/lib/allowlists-test.sh`: replace T15's `mcp__notion__*` and `mcp__slack__*` assertions with ones matching the new entries; add a test that no rendered target auto-approves a Slack or Google Workspace send, a Firebase write, delete or deploy, or a sharing or permission tool on Notion, Google Docs, Figma or Miro (by name from the note), and that a named tool renders per tool in Claude Code and Cursor CLI.
- Add the rule to `plugins/personal/skills/personal-standards/standards/security.md` as a short section (agent tool permissions: auto-approve MCP writes that have a rollback, or are creates the Owner deletes afterward; prompt on anything that sends to people, changes sharing or permissions, or can't be recovered; prefer naming allowed tools over a server wildcard so a tool the server adds later prompts). Keep the file's voice; no other standards file changes.
- Write `specs/reviews/r1/f9.md` (Finding r1.f9, Claim fixed, Change, Evidence with the rendered entries and the test names).

Acceptance: `make -C agents validate test` passes; the new tests fail against the old `personal.json` entries; commit under `m3.s2`.

#### ⬜ s3 - [fast] f4: drop the secret-reading and data-sending shell allows

In `agents/allowlists/personal.json` `shell.allow`, remove exactly `op read`, `op run`, `curl -X GET`, `curl --get`, `curl -G` and `wget --method=GET`. Keep `git log`, `git show` and `git diff` (the Owner's call). Leave the blank-line grouping tidy (drop the now-empty curl/wget group). Grep the repo (excluding `specs/reviews/`) for tests or docs that assert any removed entry and update them. Commit under `m3.s3`; `make -C agents validate test` passes.

#### ⬜ s4 - [exec] f4: the scout never proposes --output, --pre or --upload-pack

In `plugins/workstation/skills/personal-allowlist-scout/scripts/scan.py`, make `_classify_text` treat a command that passes `--output`, `--pre` or `--upload-pack` (as `--flag value` or `--flag=value`) as a class the scout never proposes, never Build & test or Inspect: `--output` writes any path, `--pre` and `--upload-pack` run any program. Pick the class from `reference.md`'s class definitions (likely Destructive) and add the flags to the table there. Match whole flags only: `--output-format`, `--prefix` and `--pre-release` must not trip it. Check the flag in both the command text and the recipe or script body, so a package.json script named `lint` running `rg --pre x` is caught. Tests in the scout's suite (`tests/`, run by `make -C agents test-allowlist-scout`): a Makefile `test` target running `git log --output=/tmp/x`, a script running `rg --pre cat`, a target running `git fetch --upload-pack=x`, each not proposed; `--output-format=json` and `--prefix` still classify as before.

Then write `specs/reviews/r1/f4.md`: Change covers s3 and s4 (the six removed entries, git log/show/diff kept by the Owner's decision, the classifier rule); Evidence names the tests. Commit under `m3.s4`; `make -C agents validate test` passes.

#### ⬜ s5 - [exec] f1: wrap shell allows and denies for Claude Code and Cursor CLI

`render_target_schema` in `agents/lib/allowlists.sh` (the `cursor_cli` and `claude` cases) adds `.shell.allow` and `.shell.deny` unwrapped, so neither tool reads them. Wrap them; Cursor IDE `terminalAllowlist`/`terminalDenylist` and Gemini stay as they are.

- **Claude Code**, allows and denies: `Bash(<entry>:*)`. Check Claude Code's current permission-rule docs first (code.claude.com docs, "permissions"/"settings"): if `:*` is deprecated in favour of another prefix form but still accepted, keep `:*` (it matches the scout's `reference.md` section 3 and `.claude/settings.json`) and record what the docs say in the claim's Evidence; if it is no longer accepted, use the documented prefix form in both the installer and the scout and say so.
- **Cursor CLI allows**: the exact form in the scout's `reference.md` section 3: `Shell(<base>:<args>)` for a multi-word entry (base is the first word, args the rest, literal), `Shell(<word>)` for a one-word entry, and no rule for an entry containing `*` or `?` or a colon in its first word.
- **Cursor CLI denies**: the prefix form `Shell(<base>:<args>*)` for a multi-word entry, `Shell(<word>)` for a one-word entry, and an entry whose args already hold a glob renders as written (`rm -rf /*` is `Shell(rm:-rf /*)`). Every meta entry is a prefix elsewhere, and an exact deny of `rm -rf /` would let `rm -rf / --no-preserve-root` through. The Owner chose this on 2026-11-22. Note in the claim that the prefix deny also blocks longer commands such as `rm -rf /tmp/x` in Cursor CLI, which is the safe direction.
- Keep the jq readable (a small jq function per form beats one long expression). Mention in the file's header comment which form each target gets.
- Fix the bare-form assertions in T14 (`agents/lib/allowlists-test.sh`, around line 460) and T15 (around 475), and add assertions for each form: a multi-word allow, a one-word allow, a skipped glob allow (Cursor CLI), a multi-word deny, a one-word deny, a glob deny, for both targets.
- Fix the header of `agents/cursor/hooks/enforce-denylist.sh`, which says these denies are honored in Cursor CLI and Claude Code; say what is true after this change. Grep `agents/`, `plugins/` and `specs/agent-distribution.md` for other claims that the installer writes bare strings there, and fix them.
- Scout: `_unwrap_token` in `plugins/workstation/skills/personal-allowlist-scout/scripts/scan.py` treats a bare (unwrapped) entry in the Cursor CLI and Claude Code files as covering nothing, so the scout proposes the wrapped rule. Say so in `reference.md` section 3. Test in the scout's suite.
- Upgrade test in `allowlists-test.sh`: a HOME whose live `cli-config.json` and `settings.json` and this org's sidecars hold the previous render (bare shell strings, and the previous `mcp__<server>__*` wildcards from before s2), as the old installer wrote them; `install` leaves only wrapped shell entries, no bare string in `permissions.allow` or `permissions.deny`, none of the old MCP wildcards that s2 removed, and nothing promoted into `.cli-config.user-managed.json` or `.settings.user-managed.json`.
- Write `specs/reviews/r1/f1.md`.

Acceptance: `make -C agents validate test` passes; the new assertions fail against the old renderer; commit under `m3.s5`.

## Review log

## Token log

**Counting header (Claude Code)**

- Line, one per model a chat ran, appended below: `tokens <row> <group-id> (<model>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv`. `<row>` is `wave-N`, `review-wave-N`, or `wave-N-fix` and `review-wave-N-fix` for a fix-up wave; `<group-id>` is the wave's group id with hyphens (`public-m3-s2-s5`); `<model>` is `message.model` without a date suffix. Round counts to two significant figures with `k` or `M`.
- Usage: `~/.claude/projects/<slug>/$CLAUDE_CODE_SESSION_ID.jsonl` (`<slug>` is the working directory with every character but a letter or digit turned into `-`, matched by prefix when long; without the id, the newest `.jsonl` there), plus its subagents' `<session-id>/subagents/**/agent-*.jsonl` in the same directory. Sum `message.usage` over assistant lines once per `message.id`, from the line with `stop_reason`: input `input_tokens`, cache read `cache_read_input_tokens`, cache write `cache_creation.ephemeral_5m_input_tokens` (with `ephemeral_1h_input_tokens` too, `cache write ~40k 5m + ~8k 1h`), output `output_tokens`. A call with no `stop_reason` line keeps its input-side counts, takes output as about 1,000, and its line ends `(output est.) session <id>`.
- Rates by `<model>`, $ per Mtok input / cached / output: `claude-opus-5-5` 4.00 / 0.20 / 20.00; `claude-sonnet-5-5` 2.00 / 0.10 / 10.00.
- `$C` = (input × in + cache read × cached + 5m write × in × 1.25 + 1h write × in × 2.00 + output × out) / 1M.
- In another harness, or on a model not listed here, count and price per plan-execution.md "Token accounting" and "Model price table" instead.
