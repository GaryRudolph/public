# Anthropic guidance audit, 2026-10

Checks the personal standards and skills against Anthropic guidance published 2026-09-15 to 2026-10-19, plus a `/doctor prompt-audit` pass (Claude Code 2.1.303's bundled `claude-api` skill, `shared/prompt-audit.md`) run against the plugin source with Opus 5.5 as the target. Nothing in `plugins/` is changed yet; this is the findings list and the proposed hunks.

## Contents

- Verdict
- Contradicted by current guidance (fix)
- No longer needed (remove or simplify)
- Structure (progressive disclosure, load order)
- Decisions for Gary
- Leads that did not check out
- Corrections to the slice reports
- What changed upstream in the window
- Sources
- Detail files

## Verdict

Nothing in the standards fights the direction of Anthropic's guidance (plain register, reasons beside rules, effort over prose, skills under 500 lines). The prompt text is already clean of the dated patterns the audit hunts: no think-step scaffolds, no update suppressors, no anti-formatting rules, one caps cluster. What's wrong is factual drift from the 5.5 releases and two Claude Code changes the orchestrate design predates.

## Contradicted by current guidance (fix)

1. **`[fast]` is still Haiku 4.5.** The `haiku` alias resolves to Haiku 5.5 (Claude Code model-config). About ten places say Haiku "takes no effort level", carry `(none)` / "(no effort setting)", or cite a 31,999-token thinking budget; Haiku 5.5 takes `low`..`max` (default `medium`) and rejects `budget_tokens`. Set `low` per the standard's own rule at `plan-execution.md:169`. Locations: slice B table.
2. **Haiku 5.5 is priced at $0.** `token_tally.rate_for()` prefix-matches, so `claude-haiku-5-5` hits no row and adds $0 to the total the cost guard reads; the counting-header template hands pasted chats 4.5 rates (the phase-1 report saw this). Add `claude-haiku-5-5` $0.10 / $0.01 / $0.50 (over-100K prompts $0.50 / $0.05 / $2.50), keep the 4.5 row for old lines, add a tally test.
3. **Sonnet 5.5 cache reads are $0.10, not $0.20.** Pricing page: cache hits on Opus 5.5 and Sonnet 5.5 are 0.05x input. Fix `plan-execution.md:203-209` and `:315`. (Slice B missed this.)
4. **"Anthropic models have no long-context surcharge"** (`plan-execution.md:219`) is false for Haiku 5.5's two rate cards.
5. **"The Agent path can't pass effort."** Changelog: "Added an `effort` parameter to the Agent tool". The premise behind `plan-worker-exec` and the five-agent roster is gone (`adapters/claude-code.md:130,299`, `plan-worker-exec.md:3`, `specs/plan-orchestration.md:253`). The reviewer agents still earn their place for the tool allowlist; the `-exec` and `-xdeep` workers can likely fold into `plan-worker` with effort passed per call. Needs a spike before deleting, since the gate hook and `orchestrate_check.py` assert the roster.
6. **Handoff naming in `documentation.md:49,109`** predates `core.md` and `personal-handoff`: missing `{word}`, and orchestrate runs also go to `specs/handoffs/`. Same gap in `git.md:153` merge cleanup.
7. **Wrong anchor in `core.md:55`**: "STOP gate semantics" is top-level in `plan-execution.md`, not under "Model-tier stop points".

## No longer needed (remove or simplify)

- **Canary block, `core.md:101-112`**: the one pressure cluster in the always-on file (`EXACTLY`, three "Do not"), and it says a correct answer proves the `agents/Makefile` install, which is false under the plugin. Rewrite plainly, keep the phrase and heading (the check script greps them).
- **"NEVER" and the repeated "skipping is never a yes" in "Wait for approval"**: Claude Code's best-practices page says emphasis on many lines stops working. Keep the fail-closed rule, drop the shout and the repeat.
- **History phrasing** ("no longer", "now") in `adapters/claude-code.md:425` and similar; the expired `gpt-5.5` 2026-10-14 cutoff in `plan-execution.md:171`.
- **Undated "current" claims**: Go 1.27 "current stable" (`go/code-style.md:5`, `go/architecture.md:5`), PostgreSQL 19 "(in beta)" (`python/architecture.md:149`).

## Structure (progressive disclosure, load order)

- **Core loads out of order.** Hooks doc: "All matching hooks run in parallel." This session received part 2, then 1, then 3, so part 2's "(above)" references dangled. Either cut parts on section boundaries with no cross-part positional references, or get core under the 10,000-character hook cap and drop to one part. Core has about 3.6K characters of headroom before a fourth part would be needed, and the hook list only requests three: a fourth part would silently not load.
- **`personal-plan-orchestrate/SKILL.md` is 999 lines** against Claude Code's "Keep `SKILL.md` under 500 lines". Content is load-bearing, so split rather than cut: kickoff and re-entry, gate details, and the subagent contract move to reference files one level deep (slice B has the cut lines and the cross-references to update).
- **Tables of contents.** Agent Skills best practices: "For reference files longer than 100 lines, include a table of contents at the top." Missing in `personal-makefile/reference.md`, `personal-allowlist-scout/reference.md` (and its byte-identical Agerpoint copy), and 23 of 24 standards files over 100 lines. Priority: `git.md`, `documentation.md`, `architecture.md`, `versioning.md`, where rules sit past line 100 (changelog fragments, PR trailer placement, API conventions). Hunks are in slice C.

## Decisions for Gary

- `core.md:62` "scripts emit no classifications" vs `personal-allowlist-scout/scan.py`, which classifies by design. Name it as an exception or rework the script.
- Key rotation order: `secrets/repository.md:455` vs the newer `personal-secrets/SKILL.md:111`. Flag-only because the newer text adds a command.
- Test order: `python/testing.md:189` (number tests when order matters) vs `testing.md:61` (never rely on order). Same commit, so history can't break the tie.
- `[fast]` on Haiku 5.5 at `low` (the standard's rule) or `medium` (Anthropic's start point for agentic coding). `[fast]` is rename-sized work, so `low` fits; measure before changing.
- Idle compaction (2.1.299): a 200K+ conversation idle about 54 minutes compacts before its cache expires. An orchestrate parent waiting at a gate will hit this. The handoff discipline covers recovery, but consider whether the parent should set `idleCompaction: false` or rely on it to cut the resume cost phase 1 measured.

## Leads that did not check out

- **"Claude reads only the first 100 lines unless linked from CLAUDE.md."** No such Claude Code rule. The source is the Agent Skills best-practices page describing model behavior on nested skill references: "Claude might use commands like `head -100` to preview content rather than reading entire files." Its fixes are one-level-deep references and a table of contents in files over 100 lines, both covered above. CLAUDE.md loads in full; SessionStart output is capped at 10,000 characters; Read returns 2,000 lines by default.
- **ALL-CAPS guidance specific to 5.5**: none. The standing advice is the older "dial back any aggressive language" plus Claude Code's "add emphasis to that line alone".

## Corrections to the slice reports

- Slices A and B kept the five-agent roster because effort "can't be passed at dispatch". Superseded by the Agent `effort` parameter (item 5).
- Slice B flagged Claude Code's Sonnet 5.5 default effort as unconfirmed. Claude Code's model-config page confirms `medium` for all three 5.5 models, so the standard's statement stands.
- Slice B's price hunk keeps Sonnet 5.5 cached at $0.20; use $0.10.

## What changed upstream in the window

Models: Opus 5.5 (2026-09-22), Sonnet 5.5 (2026-09-28), Haiku 5.5 (2026-10-07). Sonnet 4.5 deprecated 2026-09-30, retires 2026-11-30. Fable 5.5 is rumor only. Anthropic's model pages say Opus 5.5 is the default pick, Haiku 5.5 suits subagents ("measure it on your own workload"), Sonnet 5.5 pairs best with Opus at lower effort, and for one dependent chain "the orchestrator's model alone at lower effort came out ahead in every case measured" (already in the standard).

Claude Code 2.1.272 to 2.1.303: native AGENTS.md when no CLAUDE.md exists (2.1.277; this repo already benefits, nothing to remove), `/doctor prompt-audit` (2.1.283), auto mode as the default permission mode (2.1.284), mods (2.1.287; plugin hooks modules in `hooks/hooks.json`, which this plugin already uses for SessionStart, so a future mod needs care with that file), Agent `effort` (see item 5), `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL` (2.1.296; orchestrate's routing check should catch it, worth a test), idle compaction (2.1.299), `"attribution": false` (2.1.281; the baseline's object form stays correct).

## Sources

- https://code.claude.com/docs/en/changelog
- https://code.claude.com/docs/en/memory
- https://code.claude.com/docs/en/best-practices
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/hooks
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/model-config
- https://code.claude.com/docs/en/settings-reference#attribution
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- https://platform.claude.com/docs/en/about-claude/pricing
- https://platform.claude.com/docs/en/about-claude/models/choosing-a-model
- https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence
- https://platform.claude.com/docs/en/about-claude/model-deprecations
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5
- https://www.anthropic.com/claude-haiku-5-5
- https://claude.dev/blog/getting-the-most-out-of-opus-5-5/

## Detail files

Full findings tables (file:line, quoted evidence, confidence) and unified-diff hunks:

- `prompt-audit-2026-10-slice-a.md`: `AGENTS.md`, `core.md`, subagent definitions, the non-plan skills
- `prompt-audit-2026-10-slice-b.md`: the plan skills, adapters, `plan-segment.js`, `plan-execution.md`
- `prompt-audit-2026-10-slice-c.md`: the on-demand standards

Remove these files, or promote what's durable, before this branch's PR merges.
