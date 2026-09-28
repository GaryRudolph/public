# Makefile Conventions

Recommended Makefile contract for single repos and multi-repo estates (workspace /
polyrepo / submodule layouts). Full templates, audit workflow, and per-stack recipe
expectations: `agents/skills/personal-makefile/` in the personal bok.

Placeholders: `<estate>`, `<repo>`.

## When to use a workspace Makefile

A **workspace** repo (thin orchestrator + `repos.mk` manifest) is justified only when
an estate spans **more than one git repo** and cross-repo convenience (`make init`,
`make ci`, `git-pull`, etc.) pays for the extra layer. Single repos need no manifest.
Every child repo must remain fully usable on its own.

## Universal conventions

| Rule | Detail |
|------|--------|
| Shell | `SHELL := bash` — recipes may use `[[ … ]]`, `set -o pipefail` |
| Default goal | `.DEFAULT_GOAL := help` — bare `make` prints grouped targets |
| Self-documenting help | `## comment` after a target; `##@ Section` for headers; awk help target |
| Help regex | `[a-zA-Z0-9_.-]+` in the awk pattern (covers digits and dots in target names) |
| Phony | Every non-file target listed in `.PHONY` |
| Recipes | Tab-indented (Make requirement); no magic strings in bodies — extract variables |
| Verb names | Standard set below; use `format`, never `fmt` |
| Danger guards | Remote-mutating targets refuse without `CONFIRM_*=1` (see Danger section) |

## Standard target vocabulary

### Leaf repo (source of truth for build logic)

| Target | Purpose |
|--------|---------|
| `help` | List targets (default goal) |
| `init` | Idempotent bootstrap (deps, hooks, codegen) |
| `doctor` | Read-only tool/environment check; `MODE=default\|release` |
| `build` | Compile / bundle / render artifacts |
| `lint` | Static check, no writes |
| `format` | Auto-fix formatting; documented no-op when no formatter exists |
| `test` | Run test suite |
| `ci` | Full pre-push gate — what CI runs |
| `pre-commit` | Alias of `ci` |
| `clean` | Remove local build artifacts |
| `gh-runs-list` | List in-flight Actions runs (`status != completed`) |
| `gh-runs-watch` | Watch in-flight runs to completion |
| `gh-runs-status` | Last completed run per workflow; `skipped`/`neutral` are not failures |
| `bump` | Bump version; `LEVEL=patch\|minor\|major` |

**Domain extensions** — repo-specific families use a shared prefix and their own
`##@` section (e.g. `assets-*`, `secrets-*`, `##@ Determinism`). They supplement,
not replace, the core verbs.

**Release / Danger** (when applicable):

| Target | Section | Notes |
|--------|---------|-------|
| `bump` | `##@ Release` | Version bump |
| `deploy`, `release`, `publish-*` | `##@ Danger` | Require `CONFIRM_*=1` |

Every leaf defines the **full core verb set**. Where a verb does not apply, provide
a documented no-op (e.g. `format: ## No-op: no formatter configured`).

### Workspace repo (thin orchestrator)

Same target **names** as leaves where they fan out; workspace recipes delegate via
`$(MAKE) -C <dir>`. Child Makefiles own build logic.

| Target | Workspace behavior |
|--------|-------------------|
| `help` | Self-documenting (same awk pattern) |
| `init` | Clone missing repos (from manifest), run per-repo `make init`, then `doctor` |
| `doctor` | Repo roster + root `triage --profile $(MODE)` when `triage.yaml` exists; else delegate `make doctor` to each child |
| `build` | Fan-out in `REPOS_BUILD_ORDER` (dependency order; stops on first failure) |
| `ci`, `pre-commit` | Dumb pass-through to `REPOS_MAKE_CI`; collect all failures |
| `clean` | Fan-out to `REPOS_MAKE_CLEAN` |
| `git-status`, `git-fetch`, `git-pull`, `git-push` | Cross-repo git convenience |
| `gh-runs-list`, `gh-runs-watch`, `gh-runs-status` | Delegate to each repo in `REPOS_GH`; `--no-print-directory`, `|| true` |

Workspace section order: `##@ Develop`, `##@ Git`, `##@ GitHub`.

Leaf section order: `##@ Develop`, `[domain sections]`, `##@ GitHub`, `##@ Release`,
`##@ Danger`.

## Delegation model

- Recursion only at **repo boundaries** via `$(MAKE) -C`; no nested build logic in
  the workspace Makefile.
- `repos.mk` is the machine manifest: `REPOS`, `REPO_URL.<dir>`, `REPO_BRANCH.<dir>`,
  and participation lists (`REPOS_MAKE_INIT`, `REPOS_BUILD_ORDER`, `REPOS_MAKE_CI`,
  `REPOS_MAKE_CLEAN`, `REPOS_FOLLOW_ONLY`, `REPOS_GH`).
- Submodule estates use the same target names; `init` runs `git submodule update
  --init --recursive` instead of (or in addition to) clone loops.
- `REPOS_FOLLOW_ONLY` repos are skipped for push and flagged in roster checks.

## Danger guards

Remote-mutating targets sit under `##@ Danger` and use a confirm macro:

```make
confirm = @if [ -z "$($(1))" ]; then \
  printf 'Refusing to run "make %s": %s\nRe-run with %s=1.\n' "$@" "$(2)" "$(1)"; \
  exit 1; \
fi
```

- Dev/default: `CONFIRM_<ACTION>=1` (e.g. `CONFIRM_DEPLOY=1`).
- Production guard variant: `CONFIRM_<ACTION>_PROD=1` for prod/org stacks (e.g.
  `CONFIRM_APPLY_PROD=1`).

CI sets the confirm variable inline in deploy workflows; humans and agents hit the
guard on manual runs.

## `gh-runs-status` conclusions

Map GitHub run `conclusion` to three buckets:

| Conclusion | Display | Meaning |
|------------|---------|---------|
| `success` | green ✓ | Passed |
| `skipped`, `neutral` | dim ⊘ or `-` | Not a failure |
| `failure`, `cancelled`, `timed_out`, `action_required`, `stale` | red ✗ | Failed or blocked |

Two-bucket logic (`success` else ✗) is incorrect — it marks skipped workflows as
errors.

## Documentation

- Non-trivial Makefiles carry a companion [`Makefile.md`](../documentation.md) at the
  repo root (same casing rule as other companion docs).
- Narrative reference: target tables, mermaid overview, idempotent `init` behavior,
  delegation semantics, and workflow → target map for CI.

## Common tooling

| Tool | Role | Install |
|------|------|---------|
| `triage` | `doctor` tool checks via `triage.yaml` | `brew install lolay/tap/triage` |
| `gh` | GitHub Actions lane (`gh-runs-*`) | `brew install gh`; `gh auth login` |
| `checkmake` | Optional Makefile linter | `brew install checkmake` |

## Workspace `.gitignore` (allowlist)

Polyrepo workspaces that track only orchestration files use an allowlist root
`.gitignore` (`/*` then selective `!/name` un-ignores) so checked-out child repos
and worktree siblings stay ignored automatically.

## Audit and align

Use the `personal-makefile` skill to audit an estate (dry-run report) or apply fixes
repo-by-repo with explicit confirmation. The skill never bootstraps a workspace when
one is absent — it flags that as an observation only.
