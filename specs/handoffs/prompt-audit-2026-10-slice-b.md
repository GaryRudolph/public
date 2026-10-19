# Prompt audit, slice B: plan orchestration and plan execution

## Step 0: assumptions

- **Scope.** This covers the files in the slice request (listed in the inventory below) in `/workspace/public` at `22ca13f`. Read only; no repo file was changed. Tests and specs outside the slice were read only to find every place a removed fact still appears.
- **Targets.**
  - Skill bodies, adapters and the standard, read by the orchestrating parent: **Claude Opus 5.5**.
  - The `[fast]` worker. `plan-segment.js` routes it to `haiku`, which resolves to the newest Haiku. Its prompt is audited against **Claude Haiku 5.5**.
  - `plan-worker-exec`, which pins `sonnet`: **Claude Sonnet 5.5**.
  - `plan-worker-xdeep`, `plan-reviewer` and `plan-reviewer-xdeep`, which pin `opus`: **Opus 5.5**.
  - The Fable step-up route: **Claude Fable 5.1**.
- **Haiku facts used.** These come from the bundled model table and the Haiku 5.5 migration section:
  - `claude-haiku-5-5` costs $0.10 / $0.50 per Mtok when the prompt is 100K tokens or fewer, and $0.50 / $2.50 above that. Cache reads are 0.1x input.
  - It has a 1M context window and adaptive thinking on by default.
  - It takes effort levels `low` through `max`, with a default of `medium`. `budget_tokens` returns a 400.
  - The same text counts as about 30% more tokens than on Haiku 4.5.
  - Haiku 4.5 costs $1 / $5, has 200K of context, uses budget thinking and takes no effort level.

## Summary

The top three findings:

1. **The `[fast]` tier still describes Haiku 4.5 (High).**
   - Affected text: "Haiku takes no effort level", the picker's `(none)`, `(no effort setting)` in two STOP templates and in the SKILL tier table, and "inherits the session's thinking setting (… 31,999-token thinking budget)".
   - Haiku 5.5 takes effort levels and thinks adaptively. The repo's own phase-1 report records `[fast]` runs coming back as `claude-haiku-5-5`.
   - Two existing rules in `plan-execution.md` resolve the fix without a new decision. Line 169 says "`[fast]` runs at `low` where the model takes an effort level", and line 161 says "every Next model row names its level, even a model's default". Together they give `/model haiku (low)` and `fast: { model: 'haiku', effort: 'low' }`.
   - `orchestrate_check.py` requires the picker and `ROUTE` to agree, so both change together, along with the two `plan-segment-test.mjs` assertions.
2. **Haiku 5.5 is missing from the price table, so the tally prices it at $0 (High).**
   - `token_tally.rate_for()` matches by prefix. `claude-haiku-5-5` matches no row, so the line prints `n/a API-equiv` and adds $0 to the total that the cost guard reads.
   - The plan's counting header copies `claude-haiku-4-5 1.00 / 0.10 / 5.00`, so pasted chats price Haiku 5.5 at 4.5 rates (the mis-pricing phase 1 recorded).
   - Two related lines are also wrong. The Expected-cost row `Haiku 4.5 ~2M ~$0.3` and its worked example need a flagged estimate. "Anthropic models have none" (long-context surcharges) is contradicted by Haiku 5.5's 100K split.
3. **`personal-plan-orchestrate/SKILL.md` is too long (Medium).**
   - It is 999 lines and about 9,500 words, about twice the ~500-line guidance.
   - Read paragraph by paragraph, almost all of it is load-bearing: fragile, hook-enforced procedure and author-only context. So the fix is progressive disclosure, not deletion.
   - The split moves kickoff, re-entry and runner signals to `kickoff.md`, gate details to `gates.md`, and the subagent contract to `contract.md` (it is not needed on the workflow path). That leaves about 560 lines.

Not known from the repo:
- No FrontierCode, CursorBench or SWE-bench number for Haiku 5.5 exists anywhere in the repo. The new Expected-cost row is therefore an `est.` derived from Haiku 5.5's list rates and its tokenizer note, not a benchmark.
- Claude Code's default effort for Sonnet 5.5 and for Haiku is not documented in the repo. Those claims are flagged, not rewritten.

**Counts per group:**

| Group | Findings |
|---|---|
| 1 | 3: one medium and one low-medium in 1d (migration-relative phrasing); one low in 1b (arithmetic rubric) |
| 2 | 12: four high stale facts, two medium, six low or flag |
| 3 | 0 |
| 4 | 2 low: per-call Haiku rate card in the tally; Agent-path `[fast]` effort. The roster check found no redundant specialists |

## 1. Inventory

**Prompt surface (audited):**

| File | Lines | Role |
|---|---|---|
| `plugins/personal/skills/personal-plan-orchestrate/SKILL.md` | 999 (about 9.5k words) | Skill body; parent on Opus 5.5 |
| `plugins/personal/skills/personal-plan-orchestrate/adapters/claude-code.md` | 426 (about 4.1k words) | Reference file, loaded after detection |
| `plugins/personal/skills/personal-plan-orchestrate/adapters/cursor.md` | 245 | Reference file |
| `plugins/personal/skills/personal-plan-orchestrate/claude-agents/plan-worker.md` | 15 | Subagent; `model: inherit` |
| `plugins/personal/skills/personal-plan-orchestrate/claude-agents/plan-worker-exec.md` | 16 | Subagent; sonnet / high |
| `plugins/personal/skills/personal-plan-orchestrate/claude-agents/plan-worker-xdeep.md` | 16 | Subagent; opus / xhigh |
| `plugins/personal/skills/personal-plan-orchestrate/claude-agents/plan-reviewer.md` | 13 | Subagent; opus / high; Read, Grep, Glob, Bash |
| `plugins/personal/skills/personal-plan-orchestrate/claude-agents/plan-reviewer-xdeep.md` | 13 | Subagent; opus / xhigh |
| `plugins/personal/skills/personal-plan-orchestrate/claude-workflows/plan-segment.js` | 319 | Workflow: `ROUTE` model and effort (lines 23-29); prompt builders for worker, review, draft and judge (lines 81-161); result schemas |
| `plugins/personal/skills/personal-plan-model-tiers/SKILL.md` | 462 | Skill body |
| `plugins/personal/skills/personal-plan-tag-tiers/SKILL.md` | 114 | Skill body |
| `plugins/personal/skills/personal-standards/standards/plan-execution.md` | 889 (about 17.5k words) | Standard; holds the model picker, price table, Expected cost and templates |

**Code read for model IDs, prices and consistency:**
- `plugins/personal/skills/personal-plan-orchestrate/scripts/token_tally.py`: parses the price table, uses prefix `rate_for`, has the `DATE_SUFFIX` comment, and loads aliases from the picker.
- `plugins/personal/skills/personal-plan-orchestrate/tests/orchestrate_check.py`: the picker, `ROUTE` and agent frontmatter must agree.
- `plugins/personal/skills/personal-plan-orchestrate/tests/plan-segment-test.mjs`, `tests/test_token_tally.py`, `tests/test_plan_state.py`.
- `plan_state.py`, `check_wave.py` and `orchestrate_gate.py`: grepped only. They contain no model IDs or prices.

**Plan-segment skill:** `personal:plan-segment` is the workflow `claude-workflows/plan-segment.js` (manifest `"workflows"`). It has no separate skill folder.

**Related locations outside the slice:** `specs/plan-orchestration-phase-1-report.md:169`, `specs/agent-distribution.md:45,178-181`, `specs/plan-orchestration.md:247,253,314`.

**Not read:** `hooks/claude-hooks.json` and the settings files (hook and settings config).

**Provenance:** `git blame` on `plan-execution.md`:
- The picker row (148), the `[fast]` effort note (169) and the Haiku Expected-cost row (335) date from 2026-10-06 (`bf5da80`).
- The price table row (206) and "Anthropic models have none" (219) date from 2026-10-01 (`c2b7c97`).
- Line 161 ("Haiku takes no effort level … 31,999-token thinking budget") was last edited 2026-10-11 (`6a86125`), four days after Haiku 5.5 launched on 2026-10-07. The budget anecdote is a Haiku 4.5-era mechanism: `budget_tokens` returns a 400 on Haiku 5.5.

## 2. Findings (highest confidence first)

| # | Location | Evidence (quoted) | Pattern | Why it is obsolete | Confidence | Action |
|---|---|---|---|---|---|---|
| H1 | `standards/plan-execution.md:148, 161, 169, 449, 672`; `personal-plan-orchestrate/SKILL.md:155`; `adapters/claude-code.md:133-135`; `claude-workflows/plan-segment.js:24`; `tests/plan-segment-test.mjs:117-121, 325` | 148: "`/model haiku` (none)". 161: "Haiku takes no effort level, but it still thinks: it inherits the session's thinking setting (a captured orchestrate worker call carried a 31,999-token thinking budget), so `(none)` means no effort setting". 169: "Haiku 4.5 takes none (Claude Code's effort table doesn't list it)". 449 and 672: "/model haiku (no effort setting)". SKILL:155: "Haiku (no effort setting)". Adapter: "Haiku still thinks: it inherits the session's thinking setting." JS: `fast: { model: 'haiku' }`. Test: "fast routes to Haiku with no effort" | G2 Volatile specifics (stale fact); G2 History narratives (pinned model name, incident anecdote) | `haiku` now resolves to Haiku 5.5, which phase-1 report §5.9 confirms. Haiku 5.5 takes `low`..`max` (default `medium`), thinks adaptively, and rejects `budget_tokens`. The repo's own rules then fix the value: 169 says `[fast]` runs at `low` where the model takes an effort level, and 161 says every Next model row names its level. `orchestrate_check.py` makes the picker and `ROUTE` move together | High | rewrite: `(low)` / `effort: 'low'` everywhere above; drop the budget anecdote; update the two test assertions. Gary may prefer `medium` instead (see L4) |
| H2 | `standards/plan-execution.md:206, 221, 315`; `scripts/token_tally.py:62-64`; `tests/test_token_tally.py` | 206: "`claude-haiku-4-5` \| Claude Code `haiku` \| $1.00 \| $0.10 \| $5.00". 315 (counting header template): "`claude-haiku-4-5` 1.00 / 0.10 / 5.00" | G2 Volatile specifics (stale fact) | `rate_for()` is a longest-prefix match, and `claude-haiku-5-5` doesn't start with `claude-haiku-4-5`. Every Haiku 5.5 line therefore prints `n/a API-equiv`, `total += c or 0` adds $0, and the cost guard never sees it. The header template makes pasted chats use 4.5 rates. Phase-1 report:169 records exactly this: "The price table had no `claude-haiku-5-5` row; that line was priced at Haiku 4.5" | High | add a `claude-haiku-5-5` row ($0.10 / $0.01 / $0.50). Keep the 4.5 row for older Token-log lines and dated IDs (the tally test uses `claude-haiku-4-5-20251001`). Fix the header template. Add a tally test that a Haiku 5.5 call is priced |
| H3 | `standards/plan-execution.md:219` | "Long-context surcharges: … Anthropic models have none." | G2 Volatile specifics | Haiku 5.5 has two rate cards: $0.50 / $2.50 (cache read $0.05) when the prompt is over 100K tokens. That is documented in the model table and the migration section | High | rewrite (hunk below) |
| H4 | `standards/plan-execution.md:335, 385-387, 758-760, 778-780` | 335: "Haiku 4.5 \| Claude Code `[fast]` \| ~2M \| ~$0.3 \| est.: Sonnet 5.5 high's token volume ×1.8, the Haiku 4.5 / Sonnet 4.5 input ratio on SWE-bench Verified". 385: "Wave 3 `[fast]`, 4 small steps on Haiku 4.5: 4 × 0.3 × (2M, $0.30)". Cost table examples: "~3.4M \| ~$0.90", "~15M \| ~$6.7" | G2 Volatile specifics; G2 History (pinned model name) | The anchor prices the wrong model at 10x Haiku 5.5's per-token rates. No Haiku 5.5 benchmark exists in the repo, so the replacement must be a labeled estimate: tokens ~2M × 1.3 (Haiku 5.5's tokenizer) ≈ 2.6M; dollars at 1/20 of Sonnet 5.5's blended rate per Mtok ($0.35/M ÷ 20 ≈ $0.0175/M) ≈ $0.05; about 5x that for calls with prompts over 100K tokens. The worked example becomes wave 3 ≈ 3.1M + 1.0M review = 4.1M, $0.06 + $0.54 = $0.60; total ≈ 16M, $6.4; reviews 25% | High (stale); the new figures are `est.` | rewrite as a flagged estimate; re-derive when a benchmark or completed plans' actuals exist |
| M1 | `personal-plan-orchestrate/SKILL.md` (whole file, 999 lines) | Sections: Kickoff 279-481, "A new session on a plan already kicked off" 483-553, Runner signals 252-277, Gates detail 579-670, Subagent context contract 917-982 | G2 "Verbose SKILL.md" (signal: "SKILL.md not readable in one sitting") | The Step 3 deletion rule removes very little: it is fragile, hook-enforced procedure (keep-list 3 and 4) plus author-only context. But each launch pays for about 9.5k words, and much of it is needed only once per plan (kickoff), only on a new session (re-entry), only at a stop or fix-up (gate details), or never on the workflow path (contract, which `plan-segment.js` writes). Anthropic's skill guidance is under ~500 lines with reference files one level deep, and this skill already does that with `adapters/` | Medium | move (split below); the body ends near 560 lines |
| M2 | `adapters/claude-code.md:425-426` | "`ANTHROPIC_DEFAULT_*_MODEL` no longer remaps the workflow's models; the routing check catches a substitution anyway." | G1d Migration-relative phrasing | "no longer" is a diff against an older Claude Code that the model never saw. The current fact is enough | Medium | rewrite |
| M3 | `adapters/claude-code.md:369-374` | "The auto-mode classifier also refused a worker's publish script run without its dry-run flag there; `worker_guard.py` now denies that run itself, so don't rely on the classifier." | G1d Migration-relative ("now"); G2 History narrative | The rule is "the guard, not the classifier, stops it". The story of how that was learned is archaeology. The provenance clause about where it was verified stays, because it is the reason for a fact the docs don't state | Medium | rewrite |
| M4 | `standards/plan-execution.md:171` | "`gpt-5.5` leaves Codex for ChatGPT sign-ins on 2026-10-14." | G2 Time-sensitive content | That date (2026-10-14) has passed (today is 2026-10-19), and no picker cell uses `gpt-5.5`. The sentence guards nothing | Medium | remove |
| L1 | `standards/plan-execution.md:161, 167`; `adapters/claude-code.md:133`; `specs/plan-orchestration.md:253` | 161: "Opus 5.5 and Sonnet 5.5 default to `medium`". 167: "Cursor runs Sonnet 5.5 at high by default (Claude Code: medium)". Adapter: "(Sonnet defaults to medium)" | G2 Volatile specifics (unverifiable) | Per the Sonnet 5.5 migration notes, its **API** default is `high`. The repo scopes "medium" to Claude Code, but nothing in the repo shows how that was checked. No action is needed if Claude Code really defaults Sonnet to medium: `plan-worker-exec` and the workflow both set `high` explicitly, so routing is right either way | Low | flag: confirm Claude Code's Sonnet default. If it is `high`, the `-exec` agent's stated reason ("Sonnet defaults to medium") falls away, though the explicit `effort: high` still pins the level |
| L2 | `standards/plan-execution.md:161`; `specs/agent-distribution.md:180-181` | "Opus 5.5 and Sonnet 5.5 … can't turn thinking off" | G2 Volatile specifics | True for Opus 5.5. Sonnet 5.5 on the API has `thinking: {type: "between_tools"}` (no extended thinking). Whether Claude Code exposes that is not in the repo | Low | flag |
| L3 | `scripts/token_tally.py:157-163` (`cost()`), aggregation in `main()` | Rates are applied per (row, model) after summing calls | G4 No token accounting (partial) | Haiku 5.5's rate card depends on each call's prompt length (input + cache read + cache write > 100K means 5x rates). The tally adds calls up before pricing, so it can't select the card per call. Today's worker calls run about 23-50K of context (standard:389), so the error is usually zero | Low | flag. Sketch: price inside `add()` per call for `claude-haiku-5-5`, with the high card when `input + cache_read + writes > 100_000` |
| L4 | `claude-workflows/plan-segment.js:111` (fast prompt); H1's effort choice | "## Mechanical edits … Apply exactly what the plan specifies." | Keep-list 11 (re-baselining) | The Haiku 5.5 notes say that at `low`, in long agent prompts, it may stop early or report a code change as done without running a check. Two things already catch that here: the `[fast]` checklist (tests cover the change, a later review) and the per-group Opus review. The notes make the verification paragraph conditional ("if it reports results without verifying") | Low | flag. If Review-log CONCERNS on `[fast]` groups cite unverified changes, either switch H1's value to `medium` (Haiku 5.5's documented start for agentic coding), or add the migration guide's verification paragraph to the `t === 'fast'` block |
| L5 | `adapters/claude-code.md` (426 lines), `adapters/cursor.md` (245), `standards/plan-execution.md` (889) | No table of contents at the top | Anthropic skill-authoring guidance (reference files over 100 lines open with a TOC); not an audit row | Helps a partial read see the whole file's scope | Low | add: a one-line TOC of `##` sections at the top of each |
| L6 | `adapters/claude-code.md:296-300` (Agent path) | "`[exec]` uses `<P>:plan-worker-exec` (Sonnet high, since this path can't pass effort)" | G4 roster and effort | After H1, a `[fast]` worker on the Agent path (when `Workflow` is missing) can't get `low`. It runs at whatever effort Claude Code gives Haiku by default. A `plan-worker-fast` definition would close that gap for cents of spend; H1's adapter hunk documents the gap instead | Low | flag (Gary's call); a new agent would also need `orchestrate_check.py` `want` and the manifest |
| L7 | `personal-plan-orchestrate/SKILL.md:311-321`; `standards/plan-execution.md:360-379` | Cost table expected values computed in prose: "row × size factor + review", the orchestrator parts, "+$0.11 per earlier wave" | G1b Arithmetic rubrics the model must compute | It matches the row. But the size and row choice is judgment, the guard math is already in code (`plan_state.py`), and the stated accuracy band (2-3x) dwarfs arithmetic slips. No error from this source is recorded in the phase-1 report | Low | flag; a `cost_estimate.py` that takes (step, size, tier) would move the multiply-and-sum into code |
| L8 | `standards/plan-execution.md:376, 393` | Orchestrator "Each wave … $0.95, plus $0.11 per earlier wave"; "Refresh the anchors when completed plans' actuals keep landing outside 0.5×-2×" | G2 Volatile specifics | Phase-1 report:170 says "The orchestrator row's estimate ran high in all three dogfood runs (0.3-0.7x)", which is outside the standard's own refresh band. The report defers the refresh on purpose ("refresh it after more runs whose logs count the parent fully") | Low | flag |
| L9 | `personal-plan-orchestrate/SKILL.md:50-53` | "Where this file and the standard disagree on how an orchestrate run works (…), this file is newer and wins until the standard catches up." | G1d Migration-relative; G2 Time-sensitive | A line claiming to supersede another is content to assess. On the four listed topics (kickoff question, unattended mode, per-wave handoff, fix-up numbering), the standard and SKILL.md agree today, so the clause may be dead. It is also a reasonable drift guard | Low | flag: keep as a plain precedence rule ("On how an orchestrate run works, this file wins over the standard"), dropping "newer … until the standard catches up" |
| L10 | `specs/agent-distribution.md:45`; `specs/plan-orchestration.md:247` | 45: "the current family is Opus 5.5, Sonnet 5.5, and Haiku 4.5". 247: "`[fast]` on `plan-worker` (Haiku, no effort setting, though it still thinks with the session's setting)" | G2 Volatile specifics (specs, not loaded as prompts) | Same stale facts as H1. 45 is a dated record of an earlier audit; 247 is the kit's design description | Low | 45: optionally append "(Haiku 5.5 since 2026-10-07)", leaving the record as written. 247: "`[fast]` on `plan-worker` (Haiku low)" |
| L11 | `scripts/token_tally.py:37` | `DATE_SUFFIX = re.compile(r"-\d{8}$")  # claude-haiku-4-5-20251001 prints as claude-haiku-4-5` | none | Still correct: Haiku 5.5 IDs carry no date suffix, and older dated IDs still appear in logs | n/a | no change; optionally add to the comment: "current IDs have no suffix" |
| L12 | `tests/test_plan_state.py:298, 313` | `(claude-haiku-4-5)` inside fixture token lines | none | `plan_state.py` reads the line's dollars, not its model, so the fixtures stay valid | n/a | no change needed (cosmetic only) |

**Clean, with nothing to flag:**
- `personal-plan-tag-tiers/SKILL.md`.
- `personal-plan-model-tiers/SKILL.md`, which defers every model fact to the standard.
- The five agent bodies.
- The workflow `meta` description. It is routing text, and the workflow is launched by name only.
- Pressure language. The slice has no all-caps `MUST`/`NEVER`/`ALWAYS`/`CRITICAL`/`IMPORTANT`. The `READ-ONLY` markers in `plan-segment.js` back a hook-enforced read-only guard (keep-list 3 and 5). The many lower-case "never" rules are git, outward-action and gate constraints with reasons, also hook-checked (keep-list 3 and 5).
- No scaffolds from Group 1b (think-step-by-step, prefill, `budget_tokens`, sampling parameters) anywhere in the slice.
- Benchmark tables and picker notes carry "As of" dates (155, 221, 391), which the guide accepts, so they are not flagged.

**Over-specification (1c):**
- These numbered or exact scripts are fragile and stay exact: detection, kickoff steps, "Reading the answer", "Save, then ask", the gate table, the hook deny table, the contract's git instruction, fix-up rebase rules and the Bash-guard lists.
- No judgment task in the slice is scripted as numbered steps. The closest is the no-thrash rule, but that is a deterministic grouping algorithm (and `plan_state.py` checks it), so it is not 1c.

**Group 4, sub-agent roster:**
- `plan-worker`, `plan-worker-exec` and `plan-worker-xdeep` have identical bodies and differ only in `model` and `effort` frontmatter. `plan-reviewer` and `plan-reviewer-xdeep` differ only in `effort`.
- The guide's fix (fold the difference into input) is impossible here. The Agent path "can't pass effort" (`adapters/claude-code.md:130-134`, `specs/plan-orchestration.md:253`), so frontmatter is the only channel. That makes the roster load-bearing, so there is no finding.
- The workflow path passes `effort` itself and could use `plan-worker` alone for `[xdeep]`. The `-xdeep` agents still serve the Agent path, and `orchestrate_check.py` ties them to the picker.

## 3. Proposed diff hunks (high and medium only; one finding per hunk group)

After applying any of these, run `make -C agents validate test`. That command runs `orchestrate_check.py`, `test_token_tally.py` against the real `plan-execution.md`, and `plan-segment-test.mjs`.

### H1: Haiku 5.5 takes an effort level (`low`, per the standard's own `[fast]` rule)

```diff
--- a/plugins/personal/skills/personal-standards/standards/plan-execution.md
+++ b/plugins/personal/skills/personal-standards/standards/plan-execution.md
@@ -148 +148 @@
-| Claude Code | `/model opus` (xhigh), plus ultracode on audit-shaped steps (alt: `/model fable` (xhigh)) | `/model opus` (high; medium for interactive planning) | `/model sonnet` (high) | `/model haiku` (none) (alt: `/model sonnet` (low)) |
+| Claude Code | `/model opus` (xhigh), plus ultracode on audit-shaped steps (alt: `/model fable` (xhigh)) | `/model opus` (high; medium for interactive planning) | `/model sonnet` (high) | `/model haiku` (low) (alt: `/model sonnet` (low)) |
@@ -161 +161 @@
-- **Claude Code uses version-less aliases.** `opus`, `sonnet`, `haiku`, and `fable` (the `[xdeep]` alt) resolve to the newest model of each tier, so the row never needs a version bump. Set effort with `/effort <level>`. A level typed after `/effort`, or confirmed with `Enter` in its slider, is saved as that model's default and carries into its next chat: an Opus chat after an `[xdeep]` one starts at xhigh, and a Sonnet chat after `low` fast work starts at low. So every Next model row names its level, even a model's default; `s` in the slider (v2.1.257+) keeps a level to the session. `/effort max` is never saved and lasts only the session. Opus 5.5 and Sonnet 5.5 default to `medium` and can't turn thinking off; Fable defaults to `high` and always thinks. Haiku takes no effort level, but it still thinks: it inherits the session's thinking setting (a captured orchestrate worker call carried a 31,999-token thinking budget), so `(none)` means no effort setting, not no thinking. On Pro, Max, and Team plans Fable bills to usage credits and asks for consent first.
+- **Claude Code uses version-less aliases.** `opus`, `sonnet`, `haiku`, and `fable` (the `[xdeep]` alt) resolve to the newest model of each tier, so the row never needs a version bump. Set effort with `/effort <level>`. A level typed after `/effort`, or confirmed with `Enter` in its slider, is saved as that model's default and carries into its next chat: an Opus chat after an `[xdeep]` one starts at xhigh, and a Sonnet chat after `low` fast work starts at low. So every Next model row names its level, even a model's default; `s` in the slider (v2.1.257+) keeps a level to the session. `/effort max` is never saved and lasts only the session. Opus 5.5 and Sonnet 5.5 default to `medium` and can't turn thinking off; Fable defaults to `high` and always thinks. Haiku 5.5 takes effort levels too (default `medium`) and thinks adaptively, more or less with its effort. On Pro, Max, and Team plans Fable bills to usage credits and asks for consent first.
@@ -169 +169 @@
-- **`[fast]` runs at `low` where the model takes an effort level.** Haiku 4.5 takes none (Claude Code's effort table doesn't list it). Fast work run on Sonnet 5.5 sets `low`, Claude Code's level for small changes like a rename: FrontierCode 43.4 at $0.17 a step, CursorBench 4.0 35.8% at $0.50 a task. A folded `[fast]` step runs at its `[exec]` wave's level, since folding exists to keep the wave in one chat or dispatch; the Sonnet-low alt is for a whole `[fast]` wave run on Sonnet.
+- **`[fast]` runs at `low`.** Haiku 5.5 sets `low`, its level for short, simple, high-volume tasks; at `low` it more often stops early or skips a check in a long agent prompt, which the [`[fast]` checklist](#fast-downgrade-checklist)'s tests and the review beat catch. Fast work run on Sonnet 5.5 sets `low` too, Claude Code's level for small changes like a rename: FrontierCode 43.4 at $0.17 a step, CursorBench 4.0 35.8% at $0.50 a task. A folded `[fast]` step runs at its `[exec]` wave's level, since folding exists to keep the wave in one chat or dispatch; the Sonnet-low alt is for a whole `[fast]` wave run on Sonnet.
@@ -449 +449 @@
-        Claude Code: /model haiku               (no effort setting)
+        Claude Code: /model haiku               (/effort low)
@@ -672 +672 @@
-        Claude Code: /model haiku               (no effort setting)
+        Claude Code: /model haiku               (/effort low)
--- a/plugins/personal/skills/personal-plan-orchestrate/SKILL.md
+++ b/plugins/personal/skills/personal-plan-orchestrate/SKILL.md
@@ -155 +155 @@
-| `[fast]` | `<P>:plan-worker`, Haiku (no effort setting) | `<P>:plan-reviewer`, Opus high |
+| `[fast]` | `<P>:plan-worker`, Haiku low | `<P>:plan-reviewer`, Opus high |
--- a/plugins/personal/skills/personal-plan-orchestrate/adapters/claude-code.md
+++ b/plugins/personal/skills/personal-plan-orchestrate/adapters/claude-code.md
@@ -133,3 +133,4 @@
 (Sonnet defaults to medium), and the reviewers need a definition that
-carries the tool allowlist. Haiku still thinks: it inherits the session's
-thinking setting.
+carries the tool allowlist. A `[fast]` worker on the Agent path runs at
+Claude Code's default effort for Haiku rather than `low`; the difference
+costs cents, so it gets no definition of its own.
--- a/plugins/personal/skills/personal-plan-orchestrate/claude-workflows/plan-segment.js
+++ b/plugins/personal/skills/personal-plan-orchestrate/claude-workflows/plan-segment.js
@@ -24 +24 @@
-  fast: { model: 'haiku' },
+  fast: { model: 'haiku', effort: 'low' },
--- a/plugins/personal/skills/personal-plan-orchestrate/tests/plan-segment-test.mjs
+++ b/plugins/personal/skills/personal-plan-orchestrate/tests/plan-segment-test.mjs
@@ -117,5 +117,5 @@
-test('fast routes to Haiku with no effort', async () => {
+test('fast routes to Haiku at low effort', async () => {
   const { calls } = await harness({ ...base, state: st(unit(1, 'fast', ['m1.s1'])), groups: [G('/r/a', ['m1.s1'])] })
   assert.equal(calls[0].model, 'haiku')
-  assert.equal(calls[0].effort, undefined)
+  assert.equal(calls[0].effort, 'low')
   assert.match(calls[0].prompt, /Mechanical edits/)
@@ -325 +325 @@
-  assert.deepEqual(calls.map(c => [c.model, c.effort]), [['haiku', undefined], ['sonnet', 'high']])
+  assert.deepEqual(calls.map(c => [c.model, c.effort]), [['haiku', 'low'], ['sonnet', 'high']])
```

Outside the slice, `specs/plan-orchestration.md:247` should match: "`[fast]` on `plan-worker` (Haiku low)". To pick `medium` instead (see L4), replace `low` with `medium` in every line above. The 169 rewrite then needs to say why `[fast]` on Haiku differs from Sonnet-low.

### H2: Price Haiku 5.5, and stop pasted chats from using 4.5 rates

```diff
--- a/plugins/personal/skills/personal-standards/standards/plan-execution.md
+++ b/plugins/personal/skills/personal-standards/standards/plan-execution.md
@@ -206 +206,2 @@
-| `claude-haiku-4-5` | Claude Code `haiku` | $1.00 | $0.10 | $5.00 |
+| `claude-haiku-5-5` | Claude Code `haiku` | $0.10 | $0.01 | $0.50 |
+| `claude-haiku-4-5` | older Token log lines | $1.00 | $0.10 | $5.00 |
@@ -221 +222 @@
-*As of 2026-10-01. Sources: [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing), …
+*As of 2026-10-01 (Claude Haiku 5.5: 2026-10-19). Sources: [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing), …
@@ -315 +316 @@
-    - Rates by `<model>`, $ per Mtok input / cached / output: `claude-opus-5-5` 4.00 / 0.20 / 20.00; `claude-sonnet-5-5` 2.00 / 0.20 / 10.00; `claude-haiku-4-5` 1.00 / 0.10 / 5.00.
+    - Rates by `<model>`, $ per Mtok input / cached / output: `claude-opus-5-5` 4.00 / 0.20 / 20.00; `claude-sonnet-5-5` 2.00 / 0.20 / 10.00; `claude-haiku-5-5` 0.10 / 0.01 / 0.50 (0.50 / 0.05 / 2.50 for a call whose prompt is over 100k tokens).
--- a/plugins/personal/skills/personal-plan-orchestrate/tests/test_token_tally.py
+++ b/plugins/personal/skills/personal-plan-orchestrate/tests/test_token_tally.py
@@ -37,2 +37,3 @@
 agent("h", "Wave 1 of 4 [fast] repo-c m1 s1", [call("g", "claude-haiku-4-5-20251001", 50, True)])
+agent("h5", "Wave 1 of 4 [fast] repo-d m1 s2", [call("h5", "claude-haiku-5-5", 50, True)])
 launch = lambda rid: {"type": "user", "toolUseResult": {"status": "async_launched", "runId": rid}, "message": {"content": []}}
@@ -117,2 +118,8 @@
     assert rc == 0, err
 
+
+@test
+def haiku_5_5_is_priced_not_n_a():
+    line = next(l for l in tally()[1].splitlines() if l.startswith("tokens wave-1 repo-d-m1-s2 "))
+    assert "(claude-haiku-5-5):" in line and "n/a" not in line, line
+
```

(The `…` in the 221 hunk stands for the rest of the sources line, which stays unchanged. The Haiku 5.5 rates come from the bundled model table; per the migration guide, check them against the Claude pricing page before relying on them for a budget.)

### H3: Anthropic now has a long-context rate card

```diff
--- a/plugins/personal/skills/personal-standards/standards/plan-execution.md
+++ b/plugins/personal/skills/personal-standards/standards/plan-execution.md
@@ -219 +219 @@
-Long-context surcharges: Grok 4.7 doubles every rate above 256k input in Cursor (200k on xAI's API). GPT-6 doubles input and cached input and charges 1.5× output above 272k. Gemini 3.1 Pro is $4.00 / $0.40 / $18.00 above 200k. Anthropic models have none. Gemini 3.8 Flash's rates double on 2027-01-01.
+Long-context surcharges: Grok 4.7 doubles every rate above 256k input in Cursor (200k on xAI's API). GPT-6 doubles input and cached input and charges 1.5× output above 272k. Gemini 3.1 Pro is $4.00 / $0.40 / $18.00 above 200k. Claude Haiku 5.5 is $0.50 / $0.05 / $2.50 for a call whose prompt (input plus cache reads and writes) is over 100k; the other Anthropic models have none. Gemini 3.8 Flash's rates double on 2027-01-01.
```

### H4: Haiku 5.5 Expected-cost row and worked example (flagged estimate)

```diff
--- a/plugins/personal/skills/personal-standards/standards/plan-execution.md
+++ b/plugins/personal/skills/personal-standards/standards/plan-execution.md
@@ -335 +335 @@
-| Haiku 4.5 | Claude Code `[fast]` | ~2M | ~$0.3 | est.: Sonnet 5.5 high's token volume ×1.8, the Haiku 4.5 / Sonnet 4.5 input ratio on SWE-bench Verified |
+| Haiku 5.5 (low) | Claude Code `[fast]` | ~2.6M | ~$0.05 | est., unmeasured: no FrontierCode or CursorBench result for Haiku 5.5 yet. Haiku 4.5's estimated ~2M ×1.3 for Haiku 5.5's tokenizer, at its rates for prompts of 100k or less (1/20 of Sonnet 5.5's on input, cache and output); about 5× the dollars where calls pass 100k. Re-derive from a benchmark or completed plans' actuals |
@@ -385,3 +385,3 @@
-- Wave 3 `[fast]`, 4 small steps on Haiku 4.5: 4 × 0.3 × (2M, $0.30) = 2.4M and $0.36, plus its review. About 3.4M and $0.90.
+- Wave 3 `[fast]`, 4 small steps on Haiku 5.5 (low): 4 × 0.3 × (2.6M, $0.05) = 3.1M and $0.06, plus its review. About 4.1M and $0.60.
 - Kickoff on Opus 5.5 (high): about 1.5M and $1.0.
-- Total: about 15M and $6.7. The reviews are 24% of it, and wave 3's review costs more than the wave.
+- Total: about 16M and $6.4. The reviews are 25% of it, and wave 3's review costs about nine times the wave.
@@ -758,3 +758,3 @@
-    | 3 [fast] m3 s1-s4 | ~3.4M | ~$0.90 |
+    | 3 [fast] m3 s1-s4 | ~4.1M | ~$0.60 |
     | kickoff | ~1.5M | ~$1.0 |
-    | **Total** | ~15M | ~$6.7 |
+    | **Total** | ~16M | ~$6.4 |
@@ -778,3 +778,3 @@
-    | 3 [fast] m3 s1-s4 | ~3.4M | ~$0.90 | … | … |
+    | 3 [fast] m3 s1-s4 | ~4.1M | ~$0.60 | … | … |
     | kickoff | ~1.5M | ~$1.0 | … | … |
-    | **Total** | ~15M | ~$6.7 | … | … |
+    | **Total** | ~16M | ~$6.4 | … | … |
```

Arithmetic: 4.0 + 6.1 + 4.1 + 1.5 = 15.7M; $1.6 + $3.2 + $0.60 + $1.0 = $6.4; reviews 3 × $0.54 = $1.62, or 25%.

### M1: Split `personal-plan-orchestrate/SKILL.md` (progressive disclosure; content moves verbatim)

Three new reference files sit beside `SKILL.md`, each linked directly from it (one level deep), each opening with a short table of contents:

| New file | Moved verbatim from SKILL.md | When the parent reads it |
|---|---|---|
| `kickoff.md` | "Runner signals" (252-277), "Kickoff (once per plan)" with "The kickoff question", "Reading the answer" and "The Kickoff prompt" (279-481), and "A new session on a plan already kicked off" (483-553) | At kickoff; in a session that finds a Kickoff block with a `mode:` line; when re-asking or confirming a mode |
| `gates.md` | The paragraphs under the gate table: no gate 5 on a one-group unit, checkpoints, automatic retries, fix-ups, the cost guard, over expected, scope breaches, a waiver (579-670) | When `plan_state.py` reports a stop or checkpoint, a fix-up unit, a failed check or a disclosed breach |
| `contract.md` | "Subagent context contract", items 1-9 and the reviewer paragraph (917-982) | Only on Cursor and the Claude Code Agent path; on the workflow path `plan-segment.js` writes the prompts |

The changes in SKILL.md (abbreviated: each `-` block is the whole range named, moved unchanged):

```diff
--- a/plugins/personal/skills/personal-plan-orchestrate/SKILL.md
+++ b/plugins/personal/skills/personal-plan-orchestrate/SKILL.md
@@ -252,302 +252,14 @@
-## Runner signals
-… (lines 252-553, moved to kickoff.md unchanged)
+## Kickoff and re-entry
+
+[`kickoff.md`](kickoff.md) has the runner signals, the kickoff steps, the
+kickoff question and how to read and record its answer, the Kickoff prompt,
+and what a session does when the plan already has a Kickoff block with a
+`mode:` line. Read it before the kickoff, and in any session that finds such
+a block, before acting. The rules are fixed: the answer is Gary's whole next
+message, a paste or a non-answer confirms nothing, and nothing dispatches
+while Status reads `BLOCKED`.
@@ -579,92 +291,5 @@
-**No gate 5 on a one-group unit.** …
-… (lines 579-670, moved to gates.md unchanged)
+Read [`gates.md`](gates.md) whenever `plan_state.py` reports a stop or a
+checkpoint, the next unit is a fix-up, a check fails, or a worker discloses
+a breach: it has the canary, checkpoints, automatic retries, fix-up
+numbering and instructions, the cost guard, scope breaches and waivers.
@@ -917,66 +542,5 @@
-## Subagent context contract
-… (lines 917-982, moved to contract.md unchanged)
+## Subagent context contract
+
+On the Claude Code workflow path, `plan-segment.js` writes every worker and
+reviewer prompt from the group and `args`. On Cursor and the Agent path you
+write them: follow [`contract.md`](contract.md), items 1-9.
```

Cross-references to update in the same change (all currently cite `SKILL.md`):
- `adapters/claude-code.md`:
  - line 17: "Runner signals" → `kickoff.md`.
  - lines 103-105 ("A session **not** started from a paste") → `kickoff.md`.
  - line 200: "Reading the answer" → `kickoff.md`.
  - line 328: "A new session on a plan already kicked off" → `kickoff.md`.
- `adapters/cursor.md`:
  - line 25: "Runner signals" → `kickoff.md`.
  - line 109: "Subagent context contract" → `contract.md`.
  - line 231: "Reading the answer" → `kickoff.md`.
- `standards/plan-execution.md:862`: "The per-gate table is in `personal-plan-orchestrate`'s `SKILL.md`". The table stays, so no change.

None of the scripts, hooks or tests reads SKILL.md text (grep), so the move changes no enforced behavior. The body ends near 560 lines. "Each unit", "When a unit completes", the handoff and the token tally stay, because every unit needs them.

### M2: Remove migration-relative "no longer"

```diff
--- a/plugins/personal/skills/personal-plan-orchestrate/adapters/claude-code.md
+++ b/plugins/personal/skills/personal-plan-orchestrate/adapters/claude-code.md
@@ -425,2 +425,2 @@
-- `ANTHROPIC_DEFAULT_*_MODEL` no longer remaps the workflow's models; the
-  routing check catches a substitution anyway.
+- `ANTHROPIC_DEFAULT_*_MODEL` doesn't remap the workflow's models; the
+  routing check catches any substitution.
```

### M3: State the guard rule, not its history

```diff
--- a/plugins/personal/skills/personal-plan-orchestrate/adapters/claude-code.md
+++ b/plugins/personal/skills/personal-plan-orchestrate/adapters/claude-code.md
@@ -369,6 +369,5 @@
 - In auto mode, the prompt the script passes to `agent()` doesn't count as
   a request from Gary (Claude Code's workflow docs); worker commits pass
-  under auto mode with the allow rules above (phase 1's dogfood, on the
-  Mac and the web). The auto-mode classifier also refused a worker's
-  publish script run without its dry-run flag there; `worker_guard.py` now
-  denies that run itself, so don't rely on the classifier.
+  under auto mode with the allow rules above (verified on the Mac and the
+  web). `worker_guard.py`, not the auto-mode classifier, is what stops a
+  publish script run without its dry-run flag.
```

### M4: Remove a time-sensitive line whose date has passed

```diff
--- a/plugins/personal/skills/personal-standards/standards/plan-execution.md
+++ b/plugins/personal/skills/personal-standards/standards/plan-execution.md
@@ -171 +171 @@
-- **Codex** runs the GPT-6 family. Set effort with `/model` → "More reasoning…", `model_reasoning_effort` in `config.toml`, or `-c model_reasoning_effort='"xhigh"'`. Skip `ultra`: it hands delegation to the model, and these plans do their own delegation (Claude Code's ultracode on audit-shaped `[xdeep]` steps is the one exception, and it fans out only inside one wave). Astra costs the same as Fable. `gpt-5.5` leaves Codex for ChatGPT sign-ins on 2026-10-14.
+- **Codex** runs the GPT-6 family. Set effort with `/model` → "More reasoning…", `model_reasoning_effort` in `config.toml`, or `-c model_reasoning_effort='"xhigh"'`. Skip `ultra`: it hands delegation to the model, and these plans do their own delegation (Claude Code's ultracode on audit-shaped `[xdeep]` steps is the one exception, and it fans out only inside one wave). Astra costs the same as Fable.
```

## Locations for the Haiku 4.5 → 5.5 change (complete list)

| Location | Today | Should say |
|---|---|---|
| `plugins/personal/skills/personal-standards/standards/plan-execution.md:148` | `/model haiku` (none) | `/model haiku` (low) (H1) |
| `…/plan-execution.md:161` | "Haiku takes no effort level … 31,999-token thinking budget …" | "Haiku 5.5 takes effort levels too (default `medium`) and thinks adaptively" (H1) |
| `…/plan-execution.md:169` | "Haiku 4.5 takes none" | "Haiku 5.5 sets `low`" (H1) |
| `…/plan-execution.md:206` | `claude-haiku-4-5` $1.00 / $0.10 / $5.00 as Claude Code `haiku` | Add `claude-haiku-5-5` $0.10 / $0.01 / $0.50; keep 4.5 for older lines (H2) |
| `…/plan-execution.md:219` | "Anthropic models have none" | Haiku 5.5 is $0.50 / $0.05 / $2.50 for prompts over 100k (H3) |
| `…/plan-execution.md:221` | As of 2026-10-01 | Add the Haiku 5.5 date (H2) |
| `…/plan-execution.md:290` | `claude-haiku-4-5-20251001` is `claude-haiku-4-5` | No change: it illustrates the date-suffix rule, and the 4.5 row stays |
| `…/plan-execution.md:307, 313` | Header example for "Sonnet, Opus and Haiku"; date-suffix example | No change |
| `…/plan-execution.md:315` | `claude-haiku-4-5` 1.00 / 0.10 / 5.00 | `claude-haiku-5-5` 0.10 / 0.01 / 0.50, plus the 100k card (H2) |
| `…/plan-execution.md:335` | Haiku 4.5 ~2M ~$0.3 | Haiku 5.5 (low) ~2.6M ~$0.05, `est.`, unmeasured (H4) |
| `…/plan-execution.md:385-387, 758-760, 778-780` | Example on Haiku 4.5, ~15M / $6.7 | Haiku 5.5, ~16M / $6.4 (H4) |
| `…/plan-execution.md:449, 672` | (no effort setting) | (/effort low) (H1) |
| `plugins/personal/skills/personal-plan-orchestrate/SKILL.md:155` | Haiku (no effort setting) | Haiku low (H1) |
| `…/adapters/claude-code.md:134-135` | "Haiku still thinks: it inherits the session's thinking setting." | Agent-path `[fast]` runs at Claude Code's Haiku default (H1) |
| `…/claude-workflows/plan-segment.js:24` | `fast: { model: 'haiku' }` | `fast: { model: 'haiku', effort: 'low' }` (H1) |
| `…/tests/plan-segment-test.mjs:117-121, 325` | effort `undefined` | `'low'` (H1) |
| `…/tests/test_token_tally.py` | Only a 4.5 call | Add a Haiku 5.5 call asserting it is priced (H2) |
| `…/tests/test_plan_state.py:298, 313` | `(claude-haiku-4-5)` in fixtures | No change needed |
| `…/scripts/token_tally.py:37` | DATE_SUFFIX comment | No change; L3 covers the per-call 100k card |
| `specs/plan-orchestration.md:247` | "Haiku, no effort setting, though it still thinks with the session's setting" | "Haiku low" (L10) |
| `specs/agent-distribution.md:45` | "…and Haiku 4.5" (a dated record) | Optional note: "(Haiku 5.5 since 2026-10-07)" (L10) |
| `specs/plan-orchestration-phase-1-report.md:169` | Records the mis-pricing | No change: historical report |
