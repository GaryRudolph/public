# Replace "Gary" with "the Owner" where it names the role

## Context

PR #39 (merged 2026-11-04 00:32, `2ee641e`, already the base of `claude/kind-shannon-gjsytu`) introduced "the Owner" for its own files and defined it in `standards/codebase-review.md`. The rest of the repo still says "Gary" when it means the person the agent works for. Goal: one definition in `core.md`, every role use says "the Owner", identity and history stay.

`git grep -n Gary` on `main`: 273 hits in 55 files. About 120 are role uses; the rest are identity (names, `GaryRudolph/...` repo slugs, manifest authors), personal docs, or history.

Two things the brief didn't mention, both in scope because leaving them breaks the prose:
- **Pronouns.** ~35 `he/his/him` hits refer back to Gary (`plan-orchestration.md:87` "his words never set them", `personal-release` "**He picks**"). Each becomes "the Owner", or "they/their" where the antecedent is the Owner in the same sentence. None stays "he".
- **An anchor.** `adapters/claude-code.md` heading "## Asking Gary" becomes "## Asking the Owner"; its only link is the Contents line in the same file (`#asking-gary` -> `#asking-the-owner`).

## The definition

`plugins/personal/skills/personal-standards/core.md`, right after "Guidelines for AI coding agents working with me." (part 1, which is the one the hook always loads first):

> The skills and standards files call me **the Owner**: the person the agent works for, who owns the repos it works in and makes the calls the work raises.

`core.md` itself stays first person; it has no "Gary" hits. Remove the definition sentence from `standards/codebase-review.md:3` (it becomes a use, not a definition). Size: core is 8,625 / 8,550 / 8,760 chars across three parts today with a 9,000 cap and greedy cuts, so ~170 chars added to part 1 likely spills core into a 4th part. hooks.json asks for 5, and the test only requires asked > needed, so that passes; I'll report the new part count.

## Classification

### Replace (role)

| Files | Hits | Notes |
| --- | --- | --- |
| `specs/plan-orchestration.md` | 31 + pronouns | Includes "(Gary's choice, 2026-10-12)" -> "(the Owner's choice, ...)" and §5 "Gary's, and the refinements he accepted" -> "the Owner's, and the refinements the Owner accepted". It's a living design spec, not a dated report. Keep `GaryRudolph/public` in the Kickoff example (line 89, a repo slug). |
| `standards/plan-execution.md` | 20 + 2 pronouns | Line 497 "in Gary's standards repo (2026-10)" and line 431 "in Gary's standards repo" -> "in this standards repo": measurement provenance, not a person. |
| `personal-plan-orchestrate/` SKILL.md, adapters/claude-code.md, adapters/cursor.md, kickoff.md, gates.md | 57 + pronouns | Heading/anchor above. Keep kickoff.md:266 `GaryRudolph/public` (slug). |
| orchestrate scripts: `orchestrate_gate.py`, `worker_guard.py`, `plan_state.py`, `check_wave.py`, `claude-workflows/plan-segment.js` | 18 | Deny messages, docstrings, comments, and the worker prompt text `## Gary's answer (verbatim)` / `Gary answered:` -> `## The Owner's answer (verbatim)` / `The Owner answered:`. |
| orchestrate tests: `test_orchestrate_gate.py`, `plan-segment-test.mjs` | 10 | Assertions at mjs:369, 428 change with plan-segment.js; comments, test names and the compaction-summary fixture (py:814) change for consistency. |
| `personal-repo-baseline/SKILL.md` | 11 (lines 115-236) + 4 pronouns | Description line 4: "Audit and apply the per-repo agent baseline". |
| `personal-secrets/SKILL.md` | 8 (lines 29-118) | Description line 4: "Run a SOPS + age secrets repository". |
| `standards/secrets/repository.md:458` | 1 | "with the Owner's go-ahead". |
| `personal-plan-model-tiers/SKILL.md` | 5 + 1 pronoun | |
| `personal-plan-tag-tiers/SKILL.md` | 3 | |
| `personal-handoff/SKILL.md` | 3 | Description: "Write handoff and plan files with the right name...". |
| `personal-new-project/SKILL.md` | 3 + 2 pronouns | Description: "...service to the personal standards: choose a boring stack ... lay the project out per the architecture, testing, ... standards". |
| `personal-release/SKILL.md` | 3 + 1 pronoun | Description: "Cut releases to the personal versioning standard:". |
| `personal-review-guide/SKILL.md`, `scripts/pr_body_guard.py:160` | 3 + 1 pronoun | Guard message: "ask the Owner rather than setting it yourself". |
| `personal-standards/SKILL.md:11, :36` | 2 | :11 description "...commits, or PRs for Gary" -> drop "for Gary" (descriptions are read before core loads in some harnesses, so they don't use the term). :36 "Gary's workstation" -> "the Owner's workstation". |
| `plugins/personal/scripts/session-start.sh:34` | 1 | Comment "On Gary's workstation" -> "On the Owner's workstation". |
| `plugins/workstation/` manifests (claude, codex, cursor, gemini) | 5 | "Skills that need Gary's Mac" -> "Skills that need a local Mac"; codex shortDescription "Allowlist scouting on a local Mac". Public listing text, so no undefined term; all four change together. |
| `AGENTS.md:3` | 1 | "The personal standards load separately". |
| `agents/runbook.md:4` | 1 | "every agent the Owner uses". |
| `specs/agent-distribution.md:3, :72, :198` | 3 | "every agent the Owner uses", "added to the Owner's claude.ai account", "the Owner's effort rules". |
| `standards/codebase-review.md:3` | n/a | Drop the definition sentence. |

Skill descriptions drop the possessive rather than say "the Owner", for the reason in the `personal-standards` row.

### Keep (list these in the PR description)

- **Identity and authorship:** every manifest `author.name` / `developerName` / `owner.name` "Gary Rudolph" and the personal plugin's description "Gary Rudolph's engineering standards..." (claude, codex, cursor, gemini; `.claude-plugin`, `.cursor-plugin`, `.agents` marketplaces); the SessionStart banner (`session-start.sh:68`); `personal-standards/SKILL.md:4` "Gary Rudolph's personal engineering standards"; template attributions copied into other repos (`personal-secrets/templates/secrets-repo/README.md:14`, `personal-release/templates/bump_version.py:4`).
- **Repo slugs and GitHub owners** (identifiers, not the role): every `GaryRudolph/...` URL or slug, `session-doctor.py:45` `DEFAULT_OWNERS`, the `test-session-doctor.sh` fixture URLs that depend on it, `latest_versions.py:32` User-Agent, runbook JSON examples.
- **`agents/lib/`:** no hits, so nothing to port to the bok.
- **Canary phrase:** no hits; unchanged in `core.md` and `personal-standards/SKILL.md`.
- **Historical record:** `specs/plan-orchestration-phase-1-report.md` (12 hits). Propose in the PR: leave it, since it records who did what on 2026-10-12; ask before rewriting.
- **Personal docs about this person:** `README.md:2, :14`, `user-manual/` (README, personal.md), `dotfiles/` (gitconfig, git/README, opencode/README), `setup/mac/README.md`.
- **Someone else:** `bin/rmm:7` "Gary Kerbaugh".

## Steps

1. Edit by hand per occurrence (no sed), file group by file group, including pronouns. Commit per group on `claude/kind-shannon-gjsytu`, push after each commit.
2. `make -C agents cursor-core-rule` after the `core.md` edit; commit the regenerated `plugins/personal/cursor/rules/personal-core.mdc` with it.
3. `make -C agents validate test`. Must pass, including the session-start size test and the orchestrate gate / plan-segment tests.
4. Residual check: `git grep -n Gary` should return only the Keep list; `git grep -n -w -E 'he|his|him' -- plugins specs agents` reviewed for leftovers pointing at the Owner.
5. Review guide via `personal-review-guide` (walkthrough mode): likely `[check]` tier (wording in loaded standards and hook/guard messages, no logic change), with the Keep list and the phase-1 report question in it. Ask before opening the PR.

## Verification

- `make -C agents validate test` green, with the part count reported.
- `python3 -m pytest`-equivalent runs are inside `make test` (`test_orchestrate_gate.py`, `plan-segment-test.mjs`); confirm both ran.
- Residual grep matches the Keep list exactly.
