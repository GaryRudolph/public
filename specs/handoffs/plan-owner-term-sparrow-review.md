Replaces "Gary" with "the Owner" wherever it names the person the agent works for, as a role, and defines the term once in `core.md`. Follows #39, which introduced the term for its own files; its definition in `codebase-review.md` moves to `core.md`, generalized, and that file now only uses it. Identity, authorship, repo slugs, personal docs and the dated phase 1 report keep the name (list below). Plan: `specs/handoffs/plan-owner-term-sparrow.md`.

One question for the Owner: `specs/plan-orchestration-phase-1-report.md` still says "Gary" 12 times. It's a dated record of who decided what on 2026-10-12, so I left it. Rewrite it too, or leave it?

## Review guide

Review tier: [check], because every session loads the new definition and the skill descriptions steer when skills trigger.
Blast radius: wording only, in loaded standards, skill descriptions and hook, guard and worker-prompt messages. No logic changes; revert is safe.
Review time: ~5 min

1. [check] `core.md`: the definition, after the opening line; `codebase-review.md` drops its own
2. [check] Skill descriptions: `personal-handoff`, `-new-project`, `-release`, `-repo-baseline`, `-secrets`, `-standards` drop the possessive instead of saying "the Owner"
3. [check] Messages and tests: `orchestrate_gate.py`, `worker_guard.py`, `pr_body_guard.py`, `plan-segment.js` (the worker prompt now says `The Owner answered:`), and the matching assertions in `plan-segment-test.mjs`
4. [skim] The rest: `plan-orchestration.md`, `plan-execution.md`, the orchestrate skill's docs, the other skills, `agents/runbook.md`, `agent-distribution.md`, `AGENTS.md`, workstation manifests
5. [skip] `cursor/rules/personal-core.mdc` (`make -C agents cursor-core-rule`)

## Validation

- `make -C agents validate test`: pass (plan-segment 61/61, gate and plan-state suites, session-start). Validator warnings are the same 8 as on `main` (no plugin version).
- Core still splits into 3 parts; part 1 grew to 8,798 of 9,000 characters.
- `git grep -n Gary`: only the Keep list below remains.
- Fresh-context review: not run.

## Rollback

Revert the squash commit.

<details>
<summary>[check] What changed, and the calls I made</summary>

- Definition, in `core.md` (first person, like the rest of it): "The skills and standards files call me **the Owner**: the person the agent works for, who owns the repos it works in and makes the calls the work raises."
- Every occurrence was decided on its own; a script applied the decided edits so each one was an exact, single match.
- Pronouns: about 35 `he`/`his`/`him` referred back to Gary. Each became "the Owner", or "they"/"their" where the Owner is named in the same sentence. None stays "he".
- `adapters/claude-code.md` "## Asking Gary" is now "## Asking the Owner"; the one link to it, in the same file, moved with it.
- Skill and workstation-plugin descriptions drop the possessive ("Cut releases to the personal versioning standard", "Skills that need a local Mac"). Some harnesses read descriptions before `core.md` loads, so the term would be undefined there.
- Two measurement sources in `plan-execution.md` read "in this standards repo": they name a repo, not a person.
- Dated decisions in the living spec now read "(the Owner's choice, 2026-10-12)".

</details>

<details>
<summary>Kept as "Gary", and why</summary>

- Identity and authorship: manifest and marketplace `author`, `owner` and `developerName` fields; the personal plugin's description ("Gary Rudolph's engineering standards"); the SessionStart banner; `personal-standards` description's opening "Gary Rudolph's personal engineering standards"; the attribution lines in `personal-secrets/templates/secrets-repo/README.md` and `personal-release/templates/bump_version.py`, which get copied into other repos.
- Repo slugs and GitHub owners: every `GaryRudolph/...`, `session-doctor.py`'s `DEFAULT_OWNERS` and the test fixtures that rely on it, `latest_versions.py`'s User-Agent.
- `agents/lib/`: no hits, so nothing to port to the bok.
- The canary phrase: no hits.
- The historical record: `specs/plan-orchestration-phase-1-report.md` (the question above).
- Personal docs: `README.md`, `user-manual/`, `dotfiles/`, `setup/mac/README.md`.
- `bin/rmm`: credits a different Gary.

</details>

<details>
<summary>Before merge</summary>

The plan and this draft live in `specs/handoffs/`; both come out in the push that opens the PR.

</details>

https://claude.ai/code/session_01BNKwNXsB9t5Q99RPHeUfyo

Assisted-by: Claude Code
