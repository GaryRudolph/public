# Git Workflow Standards

## Branch Strategy

We follow **GitHub Flow** — short-lived feature branches merged frequently to `main` via pull requests. For apps with scheduled release trains a stabilization branch is acceptable.

- **`main`** — production-ready, always deployable
- **Feature**: `feature/feature-name` or `feature/TICKET-123-feature-name`
- **Bugfix**: `fix/issue-description` or `fix/TICKET-123-description`
- **Release**: `release/v2` (a major line: `2.*` patches and minors) or `release/v2.4` (a minor line: `2.4.*` patches only). For hotfixes to a released line; ideally not needed. See [versioning.md](versioning.md#hotfix-flow)

These naming conventions apply when a branch is intentionally created (by me or on request) — they are not license for an agent to auto-branch.

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

- **Do not auto-commit** — only commit when explicitly asked, except on a runner (below)
- **Do not auto-push** — only push when explicitly asked, never from a subagent that wasn't told to, except on a runner (below)
- **Runners commit and push their branch** — a session on a cloud runner (Claude Code on the web, or another vendor's cloud agents) or a self-hosted runner commits each finished step and pushes it to the current branch, without asking. The container is ephemeral and no one is watching to say "commit", so the pushed branch is the deliverable. Signs of a runner: the harness says the session is remote or assigns a branch to push, or `CLAUDE_CODE_REMOTE=true`. The other rules here still apply: atomic commits in the usual format, and the force-push rule below. The runner sets its own committer identity; accept it
- **Runners branch off `main`** — a runner that finds `main`, another shared branch, or a detached HEAD checked out cuts a branch before its first change, with the `--no-track` recipe below: `fix/<slug>` for a bug, otherwise `feature/<slug>` (`feature/m{N}-<slug>` for milestone work). `<slug>` is the kebab-case topic the handoff would use, two to four words naming the object of the work, not the verb; if `git ls-remote --heads origin <branch>` shows it taken, append the handoff `{word}`. Push with `git push -u origin <branch>`, and say in the first report and in the handoff that the name was a guess. Never push `main`, even if the branch push is refused. This is the one carve-out from "Do not auto-branch" and "Propose branch changes, then wait", and it never applies on a workstation
- **Runners save before they stop** — before ending any turn that waits for a human (a question, a STOP gate, a blocker, done, running low on context), in this order: update the plan's `(done)` markers and `Status:` line; write or refresh the handoff with the pending question verbatim, the branch, and how to resume; commit everything in the tree, a half-finished step included, with an honest subject (`m2.s3 wire results view (partial, see handoff)`); push; only then ask. The asking turn may be the container's last. Gate semantics don't change; the push makes the stall harmless
- **Runner scratch rides the branch** — `.scratch/` dies with the container, and only the plan and the session handoff in it can't be rebuilt from the pushed branch plus the original ask. On a runner those two go to `specs/handoffs/plan-{topic}-{word}.md` and `specs/handoffs/handoff-{topic}-{word}.md` (create the folder if needed), committed with the step that changed them, as ordinary tracked files: no `git add -f`, no second scratch directory, nothing `.gitignore` hides. Everything else in `.scratch/` may die; a conclusion the tree lacks goes into the handoff as prose. Remove or promote them before merge (see [Creating](#creating) under Pull Requests)
- **Never force-push `main`** (or any shared branch); on your own branch prefer `--force-with-lease`
- **Cut feature branches with `--no-track`** (`git switch -c feature/<name> origin/main --no-track`) so they don't track `main` and a bare `git push` can't land there; first push with `git push -u origin feature/<name>`
- **No co-authored-by** — do not add `Co-Authored-By` trailers for AI agents
- **Do not auto-branch** — never create or switch branches on your own. Default to the branch already checked out; if none was specified, that means `main`. Multi-agent work on one repo especially must not silently move branches. The one exception is a runner that starts on `main` (above).
- **Worktrees only when asked** — create a worktree only on explicit request (see [Worktrees](#worktrees) for layout/naming). Do not spin one up proactively.
- **Propose branch changes, then wait** — if you believe a new branch, branch switch, or worktree is warranted, propose it and wait for explicit confirmation before acting. Silence, a dismissed/skipped prompt, or an ambiguous reply is not confirmation (fail closed). On a runner the only branch you may cut without asking is the one "Runners branch off `main`" describes.

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
- Remove the runner's `specs/handoffs/plan-*.md` and session `handoff-{topic}-{word}.md` in the last commit before opening, or first promote what's durable to `specs/` or a milestone handoff. Milestone handoffs (`handoff-m{N}-…`) stay. A forgotten removal lands plain markdown on `main`; one `git rm` fixes it
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
.scratch/
*.key
*.pem
```
