# Git Workflow Standards

## Branch Strategy

We follow **GitHub Flow** — short-lived feature branches merged frequently to `main` via pull requests. For apps with scheduled release trains a stabilization branch is acceptable.

- **`main`** — production-ready, always deployable
- **Feature**: `feature/feature-name` or `feature/TICKET-123-feature-name`
- **Bugfix**: `fix/issue-description` or `fix/TICKET-123-description`
- **Release**: `release/v2` (short-lived, for hotfixes only; ideally not needed)

## Worktrees

Worktrees live as **siblings** of the main checkout, not nested inside it. The main checkout keeps the bare repo name (e.g. `public/`).

- **Naming**: `<repo>-<branch-slug>`
- **`<branch-slug>`**: the branch name with any leading type prefix stripped (`feature/`, `feat/`, `fix/`, `bugfix/`, `release/`, `hotfix/`, `chore/`). If no recognized prefix, use the branch name verbatim with `/` replaced by `-`.
- One worktree per branch — reuse rather than re-create.

Example: in `public/` on `main`, branch `feat/all-your-base` lives at `../public-all-your-base`.

```bash
# Create
git worktree add ../public-all-your-base -b feat/all-your-base

# Remove when done
git worktree remove ../public-all-your-base
git branch -d feat/all-your-base
```

## Versioning

See **[versioning.md](versioning.md)** for the full standard, including BNF grammars and per-platform surface tables. Headlines:

- **Contracts** (URL paths, RPC/wire formats, file/serialization formats) → integer-major (`v1`, `v2`, `v3`; `vN.x` only for hotfixes).
- **Artifacts** (service binaries, published packages, libraries, distributed apps) → SemVer 2.0 (`MAJOR.MINOR.PATCH`).
- **Source of truth holds the *last released* version**, not the next planned one. The release pipeline is the only thing that bumps it, at tag time, with the bump level (`patch` / `minor` / `major`) chosen then.
- **No pre-release suffixes.** We do not ship `-rc.N`/`-beta.N`/`-alpha.N`; every tag is stable. Dev builds iterate as `<release>+<sha>` (e.g. `2.4.0+abc1234`) until the release pipeline cuts a stable tag. Build metadata (`+`) is correct here because dev builds are *post*-release; the pre-release form `<release>-<sha>` would sort *before* the released version per SemVer §11, which is reversed.
- **Store-bound `versionCode` / `CFBundleVersion`** = `git rev-list --count HEAD` — total commit count reachable from the build's `HEAD`. Content-addressed, monotonic per branch, and uncapped in practice (Play's 2.1B ceiling translates to 2.1B commits). Requires `fetch-depth: 0` in CI. Hotfix uploads to Play override `BUILD_CODE` to clear the current production `versionCode` (see [Android Play caveat](versioning.md#android-play-caveat-for-hotfixes)).

## AI Agent Behavior

- **Do not auto-commit** — only commit when explicitly asked
- **No co-authored-by** — do not add `Co-Authored-By` trailers for AI agents

## Commit Messages

```
[optional ticket] <imperative description>

[optional body]

[optional footer]
```

### Rules

1. **Subject**: imperative mood ("add" not "added"), no capital after ticket, no period, max 72 chars
2. **Ticket**: bare at start — `PROJ-123 add feature`; omit when there isn't one
3. **Body**: separate with blank line, wrap at 72 chars, explain *what* and *why*
4. **Footer**: `Fixes #123`, `BREAKING CHANGE: description`, `Co-authored-by: Name <email>`

```bash
# Good
add login endpoint
PROJ-123 add login endpoint
fix null values in user response

# Bad
update stuff        # too vague
Fixed bug          # wrong tense
```

### Atomic Commits

Each commit = one logical change. Makes reverting and reviewing straightforward.

## Pull Requests

### Creating

- Rebase on latest `main` before opening
- One feature or fix per PR; keep PRs < 400 lines changed
- PR titles follow commit message format: `PROJ-123 add user authentication`

### PR Body

```markdown
## Summary
Brief description of changes

## Changes
- Added user authentication
- Updated API endpoints
- Added tests

## Test Plan
- [ ] Unit tests pass
- [ ] Integration tests pass

## Breaking Changes
(if any)
```

### Merging

- **Squash and merge** (default for features) — single commit on main
- **Rebase and merge** — for clean branches with good commit history
- Delete feature branches after merging

## .gitignore Essentials

```bash
.env
*.log
.DS_Store
__pycache__/
.venv/
dist/
build/
.idea/
.vscode/
*.key
*.pem
```
