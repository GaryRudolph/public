# Makefile Align — Reference

Canonical vocabulary: `~/Projects/personal/public/standards/makefile.md`.

## repos.mk contract

Include from the workspace root Makefile with `include repos.mk`.

| Variable | Purpose |
|----------|---------|
| `REPOS` | All repo directory names (as cloned) |
| `REPO_URL.<dir>` | Expected `origin` URL for roster checks and clone |
| `REPO_BRANCH.<dir>` | Default branch for `git clone --branch` |
| `REPOS_MAKE_INIT` | Repos whose `make init` the workspace invokes |
| `REPOS_BUILD_ORDER` | Strict dependency order for `make build` |
| `REPOS_MAKE_CI` | Repos in `make ci` / `make pre-commit` pass-through |
| `REPOS_MAKE_CLEAN` | Repos that define `make clean` |
| `REPOS_FOLLOW_ONLY` | Generated mirrors; skip push; tag in roster |
| `REPOS_GH` | Repos with Actions workflows; typically `$(filter-out $(REPOS_FOLLOW_ONLY),$(REPOS))` |

Variable names use dots and hyphens in the suffix (`REPO_URL.nowline-api`) — GNU Make
permits this.

Internal helper at parse time:

```make
_REPO_SPECS := $(foreach r,$(REPOS),$r:$(REPO_URL.$r):$(REPO_BRANCH.$r))
```

Parse in bash: `dir="${spec%%:*}"`, `rest="${spec#*:}"`, `url="${rest%:*}"`,
`branch="${rest##*:}"`.

## Workspace doctor modes

**Preferred (nowline pattern):** workspace root has `triage.yaml` with `delegate:`
entries. `make doctor` runs `triage --profile $(MODE)` once from the workspace root.

**Fallback:** no root `triage.yaml`. Loop `$(MAKE) -C <r> doctor MODE=$(MODE)` for
each repo in `REPOS_MAKE_CI`.

## Workspace gh-runs fan-out

Canon pattern (nowline):

- Iterate `REPOS_GH`, not raw `REPOS`
- `$(MAKE) --no-print-directory -C "$$r" gh-runs-<verb> GH_LIMIT=$(GH_LIMIT) || true`
- One repo's failure must not abort the sweep

## Help awk pattern

Workspace and leaf templates use:

```make
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_.-]+:.*?##/ {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2} /^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0,5)}' $(MAKEFILE_LIST)
```

Adjust column width (`%-16s`) per repo if needed.

## Confirm macro

```make
confirm = @if [ -z "$($(1))" ]; then \
  printf 'Refusing to run "make %s": %s\nThis pushes to a remote. Re-run with %s=1.\n' "$@" "$(2)" "$(1)"; \
  exit 1; \
fi
```

Two-tier prod guard (nowline-infra pattern): separate `CONFIRM_APPLY=1` (dev) from
`CONFIRM_APPLY_PROD=1` (prod/org/platform stacks).

## Per-stack recipe expectations

These are **expectations**, not prescriptions — preserve existing recipes when
aligning; only add stubs when a core verb is missing.

### Go (nowline-api, triage)

| Target | Typical recipe |
|--------|----------------|
| `init` | `go mod download` |
| `build` | `go build ./...` |
| `lint` | `go vet ./...` + gofmt drift check |
| `format` | `gofmt -w .` |
| `test` | `go test ./...` |
| `ci` | `build lint test` |
| `doctor` | `triage --profile $(MODE)` |

### pnpm / Node (nowline, nowline-app, nowline-site)

| Target | Typical recipe |
|--------|----------------|
| `init` | `pnpm install --frozen-lockfile` |
| `build` | package-specific build |
| `lint` | biome / eslint static check |
| `format` | biome format or documented no-op |
| `typecheck` | tsc / astro check (domain target, not core) |
| `ci` | repo-specific gate chain |
| `doctor` | `triage --profile $(MODE)` |

### Terraform (nowline-infra)

| Target | Typical recipe |
|--------|----------------|
| `init` | `terraform init` per stack (`STACK=` required) |
| `lint` | custom lint + optional tflint |
| `format` | `terraform fmt -recursive` |
| `ci` | `fmt-check lint validate-all` |
| `doctor` | `triage --profile $(MODE)` |

Legacy `fmt` / `fmt-check` targets should converge on `format` (writes) and drift
checking inside `lint` — propose per repo, do not auto-rename without confirmation.

### Xcode / Swift (deskhound-mac)

| Target | Typical recipe |
|--------|----------------|
| `init` | `xcodegen generate` |
| `build` | `debug` or `release` xcodebuild chain |
| `test` | xcodebuild test + coverage |
| `lint` | swiftlint |
| `format` | swiftformat |
| `ci` | often absent — propose adding gate matching CI |

Domain families (`assets-*`, `secrets-*`, `profiles-*`) stay under their own `##@`
sections.

## Rename guidance

There is **no maintained migration map**. For each legacy target:

1. Read the recipe body and CI workflow references.
2. Map to the closest standard verb by **purpose**, not name similarity.
3. Propose in the confirmation step; ask when ambiguous.

Worked examples (illustrations only):

| Legacy | Often maps to | Ask when |
|--------|---------------|----------|
| `fmt` | `format` | Also used as alias target name |
| `check`, `verify` | `ci` or `lint` | Recipe runs tests vs static-only |
| `bump-major`, `bump-minor` | `bump LEVEL=major/minor` | Different versioning scheme |

## Known defects

Audit recipe bodies for these patterns:

### gh-runs-status two-bucket logic

**Defect:** treats every non-`success` conclusion as failure (red ✗), including
`skipped` and `neutral`.

**Detect:** shell branch like `if [ "$$conclusion" = "success" ]; then … else … ✗`
without a `skipped`/`neutral` branch.

**Fix:** three buckets — `success` → ✓, `skipped`/`neutral` → dim ⊘ or `-`, else → ✗.
See `templates/leaf.Makefile` for the canonical recipe (includes age column).

### help regex too narrow

**Defect:** awk uses `[a-zA-Z_-]+` only.

**Fix:** `[a-zA-Z0-9_.-]+`.

### Missing workspace gh-runs resilience

**Defect:** workspace `gh-runs-*` iterates all `REPOS` without `|| true` or uses
`REPOS` instead of `REPOS_GH`.

**Fix:** match `templates/workspace.Makefile`.

## Makefile.md outline

1. Opening paragraph — Makefile is source of truth; `make help` for quick list
2. Target overview — mermaid graph (solid = ordered, dotted = pass-through)
3. Target tables by section
4. Narrative for complex targets (`init`, `doctor`, `ci`, git fan-out, danger guards)
5. `repos.mk` variable reference (workspace only)
6. Worktree / submodule notes if applicable

## Allowlist .gitignore (workspace)

```gitignore
# allowlist: /* ignores root; !/ entries un-ignore tracked workspace files
/*
!/.gitignore
!/README.md
!/Makefile
!/Makefile.md
!/AGENTS.md
!/repos.mk
!/triage.yaml
# … add other tracked root files
```

Child repo directories and worktree siblings stay ignored without listing them.

## Submodule init fragment

Use `templates/workspace-submodules.init.mk` when `.gitmodules` is present. Combines
`git submodule update --init --recursive` with optional per-submodule `make init`.

## External practices

| Practice | When |
|----------|------|
| `checkmake` | Optional lint in CI or pre-commit |
| `make --output-sync=target` | Parallel fan-out with readable interleaved output |
| Env-var guards | Required inputs for deploy/apply targets at recipe boundary |
| Recursion at repo boundaries only | Workspace delegates; leaf owns build graph |

## Template customization

Templates use `{{PLACEHOLDER}}` markers. Replace:

| Placeholder | Example |
|-------------|---------|
| `{{ESTATE_NAME}}` | `nowline` |
| `{{ESTATE_TITLE}}` | `nowline-workspace` |
| `{{REPOS}}` | space-separated dir list |
| `{{INIT_SKIP_NOTES}}` | comments for repos skipped in workspace init |
| `{{STACK_INIT_RECIPE}}` | leaf `init` recipe body |
| `{{STACK_CI_RECIPE}}` | leaf `ci` prerequisite chain |

After rendering, remove unfilled placeholders — they must not ship in estate files.
