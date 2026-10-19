# Prompt audit, slice A: core standards, subagents, and personal-* skills

## Assumptions (Step 0)

- **Scope:** the files named in the slice request (listed below). Settings JSON files were skipped: `templates/claude-settings.json` and `templates/github-merge-settings.json` were checked for existence only, and `hooks/*.json` was grepped only for the `session-start.sh` part count. Template files that skills copy into other repos (`templates/**/*.Makefile*`, `Makefile.md` templates, the secrets kit) are scaffolding for other repos, not instructions to this session, so they were not audited as prompt text. Scripts were read only to confirm that the commands, flags and keys the prose names still exist.
- **Target model:** Claude Opus 5.5 for every file, except `claude-agents/plan-worker-exec.md`, which pins `model: sonnet` and is audited against Sonnet 5.5. `plan-worker.md` uses `model: inherit` and the reviewer and xdeep files pin `opus`, so they are audited against Opus 5.5.
- **Provenance:** the git history is short: 50 commits, 2026-09-27 to 2026-10-16. Every line in scope was written for current-generation models, so the "mitigation for a retired model" argument (1d) does not apply anywhere in this slice.
- **Read-only:** no file in the repo was edited. The hunks below are proposals only.

## Summary

This slice is mostly clean. Most of `core.md` is real policy that states its reason: the task-branch and shared-branch rules, the runner push and save rules, approval that fails closed, AI attribution, and venv/npx use. The git rules are fragile operations, so their exact wording stays (keep list 3 and 5), even where they repeat each other across lines 44, 49 and 52, because those copies agree (keep list 8). `core.md:44` quotes Claude Code's built-in default ("Commit or push only when the user asks. If on the default branch, branch first."). That quote still matches the current harness text word for word, and the override is load-bearing.

The findings with the most impact:

1. **The verification canary block (`core.md:101-112`) is the one pressure-language cluster in the always-on file.** It uses `EXACTLY` plus three stacked "Do not" lines. It also says a correct reply confirms the `agents/Makefile` install, which is false in plugin and cloud sessions, where `session-start.sh` supplies `core.md`. `personal-standards/SKILL.md:20-22` already states the same rule plainly, and `manifests-check.py` treats that plain form as the working answer path.
2. **The "Wait for approval" rule (`core.md:55`) shouts and repeats itself, and also cites a section path that doesn't exist.** It has a capitalized `NEVER` and a sentence that repeats the one before it ("Skipping or dismissing a prompt is never a yes"). Its cross-reference `§"Model-tier stop points" -> "STOP gate semantics"` describes a nesting that `plan-execution.md` does not have: "STOP gate semantics" is a top-level `##` at line 852.
3. **`core.md:62` conflicts with the allowlist scout.** Line 62 says scripts "emit no verdicts, classifications, or findings". The allowlist scout's `scan.py` classifies commands and emits a proposal, and `SKILL.md:4-6,48` tells the agent to trust that output except for the `unclassified` entries. This is flagged because it is a design decision for Gary.

Both reference files over 100 lines open without a table of contents: `personal-makefile/reference.md` (243 lines) and `personal-allowlist-scout/reference.md` (194 lines). Every `SKILL.md` is well under 500 lines (the longest is 228). Every repo path, section heading, make target, script flag and JSON key named in these files was checked and resolves, apart from the section-nesting finding H1.

**Counts per group:**

- **Group 1 (dated prompt text):** 4. That is 2 medium (M1, M2) and 2 low (L1, L2).
- **Group 2 (configuration files):** 9. That is 1 high (H1), 3 medium (M3, M4, M5-flag) and 5 low (L3-L6, L8).
- **Group 3 (tool descriptions):** not applicable. No tool definitions are in scope. The subagent `description` fields are routing text, and their "Never use it proactively" is calibrated trigger text, which keep list 6 protects.
- **Group 4 (request config and architecture):** not applicable, because there is no request-building code. The subagent roster check found no redundant agents (see below). One out-of-scope architecture note (L7) is listed with the low items.

## 1. Inventory

| File | Lines | Loads |
|---|---|---|
| `/workspace/public/AGENTS.md` | 19 | Repo instruction file, every session in this repo |
| `plugins/personal/skills/personal-standards/core.md` | 112 (22,871 chars) | Every session. SessionStart hook in 3 parts (8,941 / 8,589 / 5,341 bytes); `~/.claude/CLAUDE.md` block on workstations; generated Cursor rule `plugins/personal/cursor/rules/personal-core.mdc` |
| `plugins/personal/skills/personal-standards/SKILL.md` | 59 | Skill trigger (description loads every request) |
| `plugins/personal/skills/personal-plan-orchestrate/claude-agents/plan-worker.md` | 15 | Subagent, `model: inherit` |
| `.../claude-agents/plan-worker-exec.md` | 16 | Subagent, `model: sonnet` (Sonnet 5.5), effort high |
| `.../claude-agents/plan-worker-xdeep.md` | 16 | Subagent, `model: opus`, effort xhigh |
| `.../claude-agents/plan-reviewer.md` | 13 | Subagent, `model: opus`, effort high, read-only tools |
| `.../claude-agents/plan-reviewer-xdeep.md` | 13 | Subagent, `model: opus`, effort xhigh, read-only tools |
| `plugins/personal/skills/personal-handoff/SKILL.md` | 100 | Skill |
| `plugins/personal/skills/personal-makefile/SKILL.md` | 150 | Skill |
| `plugins/personal/skills/personal-makefile/reference.md` | 243 | Reference, read at skill start |
| `plugins/personal/skills/personal-new-project/SKILL.md` | 148 | Skill |
| `plugins/personal/skills/personal-release/SKILL.md` | 193 | Skill |
| `plugins/personal/skills/personal-repo-baseline/SKILL.md` | 228 | Skill |
| `plugins/personal/skills/personal-secrets/SKILL.md` | 153 | Skill |
| `plugins/workstation/skills/personal-allowlist-scout/SKILL.md` | 169 | Skill |
| `plugins/workstation/skills/personal-allowlist-scout/reference.md` | 194 | Reference, read at skill start |

**Supporting files read for fact checks only:** `scripts/handoff-facts.sh`, `scripts/latest_versions.py`, `scripts/release_facts.py`, `templates/bump_version.py`, `templates/changelog.py`, `templates/release.yml`, `scripts/merge_settings.py`, the secrets kit `Makefile`, `scan.py`, `render.py`, `plugins/personal/scripts/session-start.sh`, `session-doctor.py`, `agents/Makefile` (targets), `agents/lib/cursor-core-rule.py`, `agents/lib/manifests-check.py` (canary check), and the relevant headings of `standards/{git,plan-execution,makefile,architecture,documentation,versioning}.md` and `standards/secrets/repository.md`.

**Symlinks reported, not probed:** `/workspace/public/standards` points to `plugins/personal/skills/personal-standards/standards`, and `agents/AGENTS.md` points to `.../personal-standards/core.md`. Both match what `AGENTS.md` says. **Outside the project, not probed:** every `~/Projects/personal/public/...` path (each maps onto an in-repo `standards/` file, and all of those exist) and the "Agerpoint bok" `agents/lib/`.

## 2. Findings (ordered by confidence)

| # | Location | Evidence | Pattern | Why obsolete | Confidence | Action |
|---|---|---|---|---|---|---|
| H1 | `plugins/personal/skills/personal-standards/core.md:55` | `the per-gate mechanics live in ... plan-execution.md §"Model-tier stop points" -> "STOP gate semantics".` | G2 Volatile specifics (section path) | `plan-execution.md:852` is a top-level `## STOP gate semantics (fail closed)`, a sibling of `## Model-tier stop points` (`:5`), not nested under it. The repo contradicts the path, so a reader following it looks in the wrong 850-line section. | High | rewrite: `plan-execution.md` §"STOP gate semantics" |
| M1 | `core.md:101-112` | `respond with EXACTLY the following string and nothing else ... Do not paraphrase. Do not add quotes. Output the bare string. ... A correct response confirms the install at ~/Projects/personal/public/agents/Makefile is working` | G1a pressure language / G1e no-provenance prohibition run; G2 stale fact | Capitalized `EXACTLY` plus three stacked prohibitions for one format requirement is first-draft emphasis. Current models follow a plainly stated "only this string" closely. The repo already relies on the plain form: `SKILL.md:20-22` answers the canary in chat, where no hook runs (`manifests-check.py:54`). The closing claim is false in plugin and cloud sessions, where `session-start.sh` injects core.md and the agents/Makefile install may not exist. The format pin (bare string, no quotes) is kept (keep list 7). | Medium | rewrite (hunk 2) |
| M2 | `core.md:55` | `it is NEVER a blanket approval ...` and `A missing, timed-out, dismissed, skipped, or ambiguous response is never approval (fail closed): hold and re-ask rather than assume. Skipping or dismissing a prompt is never a yes.` | G1a caps emphasis; G1c padding (repetition as reinforcement) | The constraint is real policy and stays. Only the volume and the repeat go. On a highly steerable model the caps `NEVER` adds no information beyond "not". The final sentence repeats "dismissed, skipped ... never approval" one clause earlier, and duplicated rules make the model reconcile wordings. | Medium | rewrite (hunk 3); the prohibition is unchanged in substance |
| M3 | `plugins/personal/skills/personal-makefile/reference.md:1-5` | 243-line reference with 13 `##` sections, no contents list at the top | G2 skill structure (Anthropic skill-authoring guidance: reference files over ~100 lines open with a TOC) | `SKILL.md:15` makes the agent read this file before every run. A partial read (`head`, offset) cannot see that "Known defects" (`:162`) or "Template customization" (`:230`) exist. | Medium | add TOC (hunk 4) |
| M4 | `plugins/workstation/skills/personal-allowlist-scout/reference.md:1-8` | 194-line reference, 6 numbered `##` sections, no contents list | Same as M3 | Same as M3. `SKILL.md:16` calls this file "the single source of truth" and requires it read first. Note: line 5-6 claims the agerpoint copy is byte-identical, so port the hunk there too. | Medium | add TOC (hunk 5) |
| M5 | `core.md:62` vs `personal-allowlist-scout/SKILL.md:4-6,48,54-67` (and `scripts/scan.py`) | core: `scripts gather mechanical facts ... and emit no verdicts, classifications, or findings; ... Script-emitted judgments get trusted un-reasoned`. scout: `classifies each discovered command by access/intent, and proposes the safe subset`; `The script emits a JSON proposal`; deep-eval only `repos[*].unclassified` | G2 instruction files contradict each other | When the scout runs, both texts are loaded. core says not to trust script classifications; the scout says to accept them and re-judge only the unclassified remainder. The scout does not name the rule it overrides, and history doesn't order them (core line from 2026-09-27, scout from 2026-09-28). Resolving it either loosens a core rule or reworks `scan.py`, which is Gary's call: (a) add one line to the scout naming it as a deliberate exception and why (the classification is a fixed taxonomy in `reference.md`), or (b) make `scan.py` emit facts only and move classification to the agent. | Medium | flag |
| L1 | `core.md:56` | `Wait for answers — if you ask a question, always wait for a response before proceeding; never assume an answer and continue` | G1c padding (near-duplicate) | Overlaps the fail-closed sentence in line 55. The two agree and sit next to each other, so keep list 8 applies. Merge only if line 55 is being rewritten anyway. | Low | flag |
| L2 | `core.md:8-9` | `Readability over cleverness — descriptive names, self-documenting code`; `Consistency — follow existing patterns in the codebase` | G1c generic virtues | Close to trained defaults and to Claude Code's own "follow existing conventions" guidance. But they sit in Gary's list of core preferences, which sets his quality bar (keep list 1). | Low | flag |
| L3 | `personal-makefile/SKILL.md:99-106`; `personal-allowlist-scout/SKILL.md:81-90` | `with these three options:` followed by four bullets, the fourth being `**Fail closed** — ...` | G2 internal inconsistency | A literal reader could offer "Fail closed" as a dialog option. `personal-repo-baseline/SKILL.md:134` already formats fail-closed as a rule, not an option. Moving fail-closed into a sentence after the list would resolve it. | Low | flag |
| L4 | Descriptions: `personal-makefile/SKILL.md:9-10` (6 phrases), `personal-repo-baseline/SKILL.md:10-13` (8), `personal-allowlist-scout/SKILL.md:9-11` (5), `personal-release/SKILL.md:11-15` (~8) | `Triggers: "align makefiles", "audit make targets", "fix makefile conventions", "standardize makefile", "makefile audit", ...` | G2 trigger-case enumeration | These are near-synonym lists that load on every request. However, `git log -p` shows none of them growing (each is unchanged since creation, 2-4 commits), and trigger text may carry calibrated routing (keep list 6). | Low | flag |
| L5 | `personal-standards/SKILL.md:4-9` | `core working agreements (commit and push freely on a task branch, only when asked on main or another shared branch; stay on the current branch; pause after each step), plus ...` | G2 / G3 split (behavior in routing text) | The parenthetical restates behavior from core.md, which is already in context every session, inside a description that loads on every request. The routing part (topics plus "Use whenever ...") is enough to trigger the skill. | Low | flag |
| L6 | `core.md:79-99` vs `personal-standards/SKILL.md:52,55` | core's "Standards Reference" lists 10 topic files plus languages; it omits `versioning.md` and `secrets/README.md`, which the SKILL index lists | G2 duplicated info drifting apart | The two lists don't contradict each other. core's list is just incomplete. `versioning.md` is cited at `core.md:36`, and secrets reach the agent through the `personal-secrets` skill trigger. | Low | flag (add two bullets if desired) |
| L7 | `core.md` size vs `plugins/personal/hooks/hooks.json:6-8` | 3 `session-start.sh N` entries; core.md splits into 8,941 + 8,589 + 5,341 bytes at `max_chars=9000` | Out of pattern scope (G4-adjacent architecture note) | About 3.6K characters of headroom remain. Past that, `session-start.sh` would emit a part 4 that no hook entry requests, so the tail of core.md (Standards Reference and the canary) would silently stop loading in cloud and runner sessions. Not prompt cruft, but it limits any future addition to core.md. | Low | flag |
| L8 | `core.md:55` | `If you want me to run multiple steps unattended, say so explicitly (e.g. "run unattended" / "auto-approve the next N steps")` | G2 clarity (pronoun inversion) | Everywhere else in the file "I" is Gary and "you" is the agent. This sentence reverses the roles, so a literal reader could take it as telling the agent to ask Gary to say so. The intent is "unattended runs need an explicit instruction from me". Suggested text: `Unattended runs need my explicit instruction ("run unattended" / "auto-approve the next N steps"); ...` | Low | flag |

### Considered and kept (no finding)

- **`core.md:44-53` (git and runner rules):** these are long, and parts repeat each other (the task-branch carve-out at 44/49/52, runner pushes at 46/48). They are fragile operations with exact commands (`git switch -c <branch> --no-track`, `--force-with-lease --force-if-includes`, `git push -u origin`), and each prohibition carries its reason (VM reclaim, squash re-introduction, background fetches). The copies agree with each other and with `standards/git.md` "AI Agent Behavior". Keep list 3, 5 and 8.
- **`core.md:57-58` (choice dialogs, numbered task cards):** these are format-sensitive output contracts tied to real harness mechanics (`AskUserQuestion`, `spawn_task`, dismiss). Kept.
- **`core.md:61` (doctor):** the `make doctor` / `task doctor` / `triage` order matches `session-doctor.py:9-12,89-96`.
- **`core.md:63` and `personal-new-project/SKILL.md:17`:** "training data is months or years stale" is a stated reason, not a trait claim. Kept.
- **Subagents:** the "Never/Do not" runs in the worker files (lines 11-16) are policy constraints with consequences: no push, no branch moves, no outward actions, no nested spawn, no partial-as-done. A subagent cannot get these elsewhere, because SessionStart output doesn't reach subagents (`core.md:47`). For Sonnet 5.5 (`plan-worker-exec.md`) there are no "do not be lazy", refusal-steering or tool-discouraging lines to remove. "Never report partial work as `done`" matches what current models need. The descriptions' "Never use it proactively" is routing text (keep list 6).
- **Roster (G4):** the three worker files and the two reviewer files have identical bodies and differ only in `model`/`effort` frontmatter. This is not a redundant-agent finding: the Agent path can't pass effort (`plan-worker-exec.md:3`), so the frontmatter is the only place the distinction can live, and `plan-segment.js` and the tests route to each by name.
- **`AGENTS.md`:** clean. `plugins/README.md`, `plugins/personal/cursor/rules/personal-core.mdc`, `agents/lib/`, `specs/agent-distribution.md` and `agents/runbook.md` all exist, and `make -C agents cursor-core-rule`, `validate` and `test` are defined (`agents/Makefile:472,475,422`).
- **Skills (`personal-handoff`, `personal-new-project`, `personal-release`, `personal-repo-baseline`, `personal-secrets`):** clean. Every cited path, heading, flag and key resolves: `handoff-facts.sh` `claude_code_remote`, orchestrate "Files a run keeps", `latest_versions.py` specs, `architecture.md` "Toolchain Floor and Pin", `release_facts.py --next`, `bump_version.py --line/--dry-run`, `changelog.py preview|release --dry-run`, `release.yml` `level`, `merge_settings.py --diff/--write/--take`, the kit's `init doctor src-decrypt src-encrypt build verify mint rotate retire set-keys dist-decrypt dist-decrypt-env`, `OWNER`, `CONFIRM_SET_KEYS`, `FORMAT`, and `repository.md` "Reference implementation" and "Setup runbook". Their audit-first and fail-closed invariants are fragile-operation safeguards. The step workflows order writes after dry-runs, so the order matters.

## 3. Proposed diff (high and medium only)

Any hunk to `core.md` also needs `make -C agents cursor-core-rule` to regenerate `plugins/personal/cursor/rules/personal-core.mdc`, then `make -C agents validate test`. Hunks 1 and 3 both edit `core.md:55`. Hunk 3 is written against the text after hunk 1. Hunk 2 keeps the `## Verification canary` heading, which `agents/Makefile:305` points users to, and the phrase, which `manifests-check.py:60` matches by regex. Nothing else in the repo matches the removed prose: the `blocks-test.sh` fixture has its own text.

### Hunk 1 (H1): fix the STOP gate section path

```diff
--- a/plugins/personal/skills/personal-standards/core.md
+++ b/plugins/personal/skills/personal-standards/core.md
@@ -55 +55 @@
-- **Wait for approval** — do not proceed to the next step until I confirm. Approval is for the next step, not for git: on a task branch the finished step is already committed (on a runner, pushed) when you ask, and on a shared branch a yes covers a commit or push only when the question named it. A one-time "yes / continue / go ahead" approves only the single step or question it answers; it is NEVER a blanket approval for subsequent steps or future decisions — ask again at the next decision point. A missing, timed-out, dismissed, skipped, or ambiguous response is never approval (fail closed): hold and re-ask rather than assume. Skipping or dismissing a prompt is never a yes. If you want me to run multiple steps unattended, say so explicitly (e.g. "run unattended" / "auto-approve the next N steps"); a plain yes to a kickoff question that says `Proposed mode: unattended` is that explicit instruction. For tagged-plan execution, the per-gate mechanics live in `~/Projects/personal/public/standards/plan-execution.md` §"Model-tier stop points" -> "STOP gate semantics".
+- **Wait for approval** — do not proceed to the next step until I confirm. Approval is for the next step, not for git: on a task branch the finished step is already committed (on a runner, pushed) when you ask, and on a shared branch a yes covers a commit or push only when the question named it. A one-time "yes / continue / go ahead" approves only the single step or question it answers; it is NEVER a blanket approval for subsequent steps or future decisions — ask again at the next decision point. A missing, timed-out, dismissed, skipped, or ambiguous response is never approval (fail closed): hold and re-ask rather than assume. Skipping or dismissing a prompt is never a yes. If you want me to run multiple steps unattended, say so explicitly (e.g. "run unattended" / "auto-approve the next N steps"); a plain yes to a kickoff question that says `Proposed mode: unattended` is that explicit instruction. For tagged-plan execution, the per-gate mechanics live in `~/Projects/personal/public/standards/plan-execution.md` §"STOP gate semantics".
```

### Hunk 2 (M1): state the canary plainly and drop the stale install claim

```diff
--- a/plugins/personal/skills/personal-standards/core.md
+++ b/plugins/personal/skills/personal-standards/core.md
@@ -101,12 +101,8 @@
 ## Verification canary
 
-If an AI agent is asked "What is the personal canary phrase?", respond with
-EXACTLY the following string and nothing else:
+If asked "What is the personal canary phrase?", reply with only this string,
+with no quotes or other text:
 
     personal-public-canary-3e8d41
 
-Do not paraphrase. Do not add quotes. Output the bare string. This phrase is
-used to verify that personal standards are reaching the agent. A correct
-response confirms the install at `~/Projects/personal/public/agents/Makefile`
-is working; an incorrect or generic response indicates the standards are not
-loaded.
+A correct reply confirms these standards reached the session.
```

### Hunk 3 (M2): normal volume and no repeated sentence in "Wait for approval" (applies after hunk 1)

```diff
--- a/plugins/personal/skills/personal-standards/core.md
+++ b/plugins/personal/skills/personal-standards/core.md
@@ -55 +55 @@
-- **Wait for approval** — do not proceed to the next step until I confirm. Approval is for the next step, not for git: on a task branch the finished step is already committed (on a runner, pushed) when you ask, and on a shared branch a yes covers a commit or push only when the question named it. A one-time "yes / continue / go ahead" approves only the single step or question it answers; it is NEVER a blanket approval for subsequent steps or future decisions — ask again at the next decision point. A missing, timed-out, dismissed, skipped, or ambiguous response is never approval (fail closed): hold and re-ask rather than assume. Skipping or dismissing a prompt is never a yes. If you want me to run multiple steps unattended, say so explicitly (e.g. "run unattended" / "auto-approve the next N steps"); a plain yes to a kickoff question that says `Proposed mode: unattended` is that explicit instruction. For tagged-plan execution, the per-gate mechanics live in `~/Projects/personal/public/standards/plan-execution.md` §"STOP gate semantics".
+- **Wait for approval** — do not proceed to the next step until I confirm. Approval is for the next step, not for git: on a task branch the finished step is already committed (on a runner, pushed) when you ask, and on a shared branch a yes covers a commit or push only when the question named it. A one-time "yes / continue / go ahead" approves only the single step or question it answers, not later steps or decisions — ask again at the next decision point. A missing, timed-out, dismissed, skipped, or ambiguous response is never approval (fail closed): hold and re-ask rather than assume. If you want me to run multiple steps unattended, say so explicitly (e.g. "run unattended" / "auto-approve the next N steps"); a plain yes to a kickoff question that says `Proposed mode: unattended` is that explicit instruction. For tagged-plan execution, the per-gate mechanics live in `~/Projects/personal/public/standards/plan-execution.md` §"STOP gate semantics".
```

(Optional, low confidence, L8: also change "If you want me to run multiple steps unattended, say so explicitly (e.g. ...)" to "Unattended runs need my explicit instruction (e.g. ...)". This is left out of the hunk because it is a separate, low-confidence finding.)

### Hunk 4 (M3): table of contents for the Makefile reference

```diff
--- a/plugins/personal/skills/personal-makefile/reference.md
+++ b/plugins/personal/skills/personal-makefile/reference.md
@@ -1,5 +1,21 @@
 # Makefile Align — Reference
 
 Canonical vocabulary: `../personal-standards/standards/makefile.md`.
 
+Contents:
+
+- repos.mk contract
+- Workspace doctor modes
+- Workspace gh-runs fan-out
+- Help awk pattern
+- Confirm macro
+- Per-stack recipe expectations (Go, pnpm / Node, Terraform, Xcode / Swift)
+- Rename guidance
+- Known defects
+- Makefile.md outline
+- Allowlist .gitignore (workspace)
+- Submodule init fragment
+- External practices
+- Template customization
+
 ## repos.mk contract
```

### Hunk 5 (M4): table of contents for the allowlist-scout reference (port to the agerpoint copy too, which line 5 says is byte-identical)

```diff
--- a/plugins/workstation/skills/personal-allowlist-scout/reference.md
+++ b/plugins/workstation/skills/personal-allowlist-scout/reference.md
@@ -3,8 +3,17 @@
 Taxonomy, harness token formats, and safety caveats for the allowlist scout
 skill and its supporting scripts (`scan.py`, `render.py`). This file is the
 single source of truth for classification rules. Both the agerpoint and personal
 copies are byte-identical.
 
+Contents:
+
+1. Access / Intent Classification (propose, never-propose, unclassified)
+2. Stack Detection Rules
+3. Harness Token Formats
+4. Prefix-Matching Safety Caveats
+5. Project Tool-Use Preference Is Informational
+6. Coverage Model
+
 ---
 
 ## 1. Access / Intent Classification
```

M5 and every low item are report-only (`flag`), so no hunk is proposed for them.
