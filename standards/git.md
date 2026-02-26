# Git Workflow Standards

## Branch Strategy

We follow **GitHub Flow** — short-lived feature branches merged frequently to `main` via pull requests. For apps with scheduled release trains a stabilization branch is acceptable.

- **`main`** — production-ready, always deployable
- **Feature**: `feature/feature-name` or `feature/TICKET-123-feature-name`
- **Bugfix**: `fix/issue-description` or `fix/TICKET-123-description`
- **Release**: `release/v2` (short-lived, for hotfixes only; ideally not needed)

## Versioning

Simplified scheme with always-incrementing major versions:

- **Standard releases**: `v1`, `v2`, `v3`, `v4`, ...
- **Hotfixes** (rare): `v2.1`, `v2.2` — next planned release is still `v3`

Use minor versions **only** for critical security vulnerabilities, data loss bugs, or service outages. Regular bug fixes wait for the next major version.

```bash
# Standard release — tag main directly
git tag v3 && git push origin v3

# Hotfix — branch from prior tag, fix, tag, delete branch
git checkout -b fix/critical-issue v3
# ... fix and commit ...
git checkout -b release/v3.1 v3
git merge fix/critical-issue
git tag v3.1 && git push origin v3.1
git push origin --delete release/v3.1
```

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
