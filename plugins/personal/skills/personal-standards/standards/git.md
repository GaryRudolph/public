# Git Workflow Standards

## Branch Strategy

We follow **GitHub Flow** — short-lived feature branches merged frequently to `main` via pull requests. For apps with scheduled release trains a stabilization branch is acceptable.

- **`main`** — production-ready, always deployable
- **Feature**: `feature/feature-name` or `feature/TICKET-123-feature-name`
- **Bugfix**: `fix/issue-description` or `fix/TICKET-123-description`
- **Release**: `release/v2` (a major line: `2.*` patches and minors) or `release/v2.4` (a minor line: `2.4.*` patches only). For hotfixes to a released line; ideally not needed. See [versioning.md](versioning.md#hotfix-flow)

These naming conventions apply when a branch is intentionally created (by me or on request) — they are not license for an agent to auto-branch. The one exception is a task branch cut off a shared branch, a detached HEAD, or (on a runner) any branch that isn't a task branch (see [AI Agent Behavior](#ai-agent-behavior)).

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

These rules beat a harness's built-in git defaults, such as Claude Code's "Commit or push only when the user asks. If on the default branch, branch first."

### Task branches and shared branches

An agent commits and pushes freely on a task branch, and only when asked on a shared branch. A **task branch** is one of three, and nothing else:

- a branch the agent cut this session
- a branch the harness assigned: a Claude Code cloud session's `claude/…`, another cloud agent's own branch, a `claude --worktree` session's `worktree-<name>`
- a branch I named for the work, including in a prompt I paste (a STOP or Kickoff prompt's `On branch <name> (task branch)` line)

A branch is **shared** if any row below is true, even when it's also on that list. A ruleset that only restricts who may push `claude/**` doesn't make a branch shared.

| Shared if | Check |
|---|---|
| It's `main` or the remote's default branch | `git ls-remote --symref origin HEAD` |
| It's a release line | the name matches `release/*` |
| An open PR targets it | `gh api "repos/{owner}/{repo}/pulls?base={branch}&state=open" --jq length` isn't `0` |
| Someone else's open PR comes from it | an author in `gh api "repos/{owner}/{repo}/pulls?head={owner}:{branch}&state=open" --jq '.[].user.login'` isn't `gh api user --jq .login` |
| Its PR has merged | `gh api "repos/{owner}/{repo}/pulls?head={owner}:{branch}&state=closed" --jq 'any(.[]; .merged_at != null)'` is `true` |

On a workstation, any other branch, such as my own existing feature branch, gets a one-time ask before the agent commits or pushes there; a yes makes it a branch I named. On a runner, any branch that isn't a task branch gets a task branch cut from it, as off a shared branch: a runner can't wait for an answer with its work uncommitted. A detached HEAD is neither: cut a task branch. A pasted `On branch <name>` names a branch; it doesn't move you there. On a runner, a new session's harness-assigned branch wins: work there, and if it isn't `<name>`, say so in the first report; the earlier session's branch stays as is. On a workstation with another branch checked out, propose switching to `<name>` and wait, committing nothing until I answer. Use `gh api` (REST): `gh pr view` and `gh pr list` go through GraphQL, which Claude Code's cloud proxy refuses. If the GitHub rows can't be answered, go by the list and the name rows. For multi-repo work, check each repo or working directory on its own, and the git identity in each too.

### Rules

- **Shared branch: commit and push only when asked** — commit only when explicitly asked, during multi-step plans too; push only when asked. Never force-push a shared branch. Never push `main` on your own, not even when a branch push is refused. On a merged branch, cut a new task branch instead of pushing to it
- **Task branch: commit without asking** — commit each finished step. Stage the paths you changed, not `git add -A`: on a workstation the tree may hold someone else's edits, and a file that mixes theirs and yours stays uncommitted until they say. A runner pushes after every commit, except that a subagent's commits are pushed by the parent after its review; a workstation pushes at will. A push rejected as non-fast-forward means the remote moved: rebase onto it (`git pull --rebase`), never force over it, and stop and ask on a conflict. Any other rejection (a ruleset, a permission, GitHub's email privacy check) means stop and report. Rewrite only your own commits, and only with `git push --force-with-lease --force-if-includes`: a bare `--force-with-lease` is defeated by background fetches, which editors run. Opening or merging a PR, pushing a tag, and deleting a remote branch still need an ask, and a project or skill rule that asks before a push wins
- **Subagents commit only when told, and never push** — a subagent commits only when its dispatch prompt says to, never pushes, and never creates or switches branches. The parent reviews and pushes. Claude Code subagents load CLAUDE.md files but not SessionStart hook output, so on a runner a subagent never sees these rules; the dispatch prompt spells out the git instructions
- **Runners** — a session on a cloud runner (Claude Code on the web, or another vendor's cloud agents) or a self-hosted runner. Signs: the harness says the session is remote or assigns a branch to push, or `CLAUDE_CODE_REMOTE=true`. Unpushed work is gone if the VM is reclaimed, so a runner pushes after every commit (a subagent's, once the parent has reviewed it), and the pushed branch is the deliverable. The runner sets its own committer identity; accept it
- **Cut a task branch off a shared branch** — when `main`, another shared branch, or a detached HEAD is checked out (on a runner, any branch that isn't a task branch), the work belongs on a task branch. A runner always works on a task branch: it cuts one before its first change, without asking; an assigned branch already is one. A workstation asks whether to cut one, with the name, at its first pause (end of the first step), before anything is committed; `git switch -c` carries uncommitted edits along, so waiting loses nothing. Without a yes, stay put and commit only when asked (the shared-branch rule). If the harness assigned a branch, that's the branch and nothing is a guess. Otherwise guess: `fix/<slug>` for a bug, else `feature/<slug>` (`feature/m{N}-<slug>` for milestone work), where `<slug>` is the kebab-case topic the handoff would use, two to four words naming the object of the work, not the verb; if `git ls-remote --heads origin <branch>` shows it taken, append the handoff `{word}`. Cut it with no start point, `git switch -c <branch> --no-track`, so uncommitted edits and the checked-out commit come along, off `main`, another shared branch, or a detached HEAD alike. Only off a merged branch, cut from `origin/<default branch>` after a fetch (`git switch -c <branch> origin/<default branch> --no-track`), so its squashed commits don't come back. Its first push is `git push -u origin <branch>`, right away on a runner. A runner says in its first report and in the handoff that the name was a guess. This is the one carve-out from "Do not auto-branch" and "Propose branch changes, then wait"
- **Save before you wait** — before ending any turn that waits for a human (a question, a STOP gate, a blocker, done, running low on context), update the plan's `(done)` markers and `Status:` line and, on a task branch, commit the finished steps; only then ask. A runner, in this order: updates the plan; writes or refreshes the handoff with the pending question verbatim, the branch, and how to resume; commits everything in the tree, a half-finished step included, with an honest subject (`m2.s3 wire results view (partial, see handoff)`); pushes; only then asks. The asking turn may be the container's last. Gate semantics don't change; the push makes the stall harmless. A permission prompt waits for a human too, mid-turn: on a runner, before a tool call likely to trip one, commit what's done and push first
- **Runner scratch rides the branch** — `.scratch/` dies with the container, so on a runner ask of each file in it: could the next session rebuild this from the pushed branch plus the original ask? Script output can; judgment can't. The plan, the session handoff, and any draft or research that was asked for can't, so they go to `specs/handoffs/` under their usual names (`plan-{topic}-{word}.md`, `handoff-{topic}-{word}.md`, a draft under its own kebab-case name; create the folder if needed), committed with the step that changed them, as ordinary tracked files: no `git add -f`, no second scratch directory. Orchestrate outputs, spikes, and anything a command regenerates may die; a conclusion the tree lacks goes into the handoff as prose. Remove or promote them before merge (see [Merging](#merging) under Pull Requests); that turn skips the handoff step in "Save before you wait", and the report and the PR say what's pending
- **Cut feature branches with `--no-track`** so they don't track `main` and a bare `git push` can't land there: a task branch as above, or `git switch -c feature/<name> origin/main --no-track` for a clean start I asked for; first push with `git push -u origin <branch>`
- **AI attribution** — the person directing the agent is the author of what lands on `main` and answers for it. Disclose the agent with an `Assisted-by: Claude Code` trailer, naming the tool, not the model (another harness names itself); never add `Co-authored-by` or `Signed-off-by` for an agent. Branch commits may carry a runner's identity: the squash makes the PR opener the author on `main`. Keep `Claude-Session:` and other provenance trailers on branch commits. The squash message on `main` is the PR's title and description instead, where a session link is plain text above the trailer paragraph (see [PR Body](#pr-body)), so `Assisted-by:` stays the last trailer. Claude Code's `attribution` setting is what makes the harness emit `Assisted-by` (`attribution.commit`, `attribution.pr`), and cloud sessions read it only from the repo's `.claude/settings.json`; the `personal-repo-baseline` skill sets that file and the GitHub squash settings
- **Do not auto-branch** — never create or switch branches on your own. Default to the branch already checked out. Multi-agent work on one repo especially must not silently move branches. The one exception is a task branch cut off a shared branch, a detached HEAD, or (on a runner) any branch that isn't a task branch (above): a runner cuts it, a workstation asks first. A branch or worktree the harness started the session in is the branch already checked out.
- **Worktrees only when asked** — create a worktree only on explicit request (see [Worktrees](#worktrees) for layout/naming). Do not spin one up proactively. A session the harness started in a worktree (`claude --worktree`, a Cursor or Codex worktree agent) was asked for.
- **Propose branch changes, then wait** — if you believe a new branch, branch switch, or worktree is warranted, propose it and wait for explicit confirmation before acting. Silence, a dismissed/skipped prompt, or an ambiguous reply is not confirmation (fail closed). The only branch you may cut without asking is a runner's task branch, cut off a shared branch, a detached HEAD, or any branch that isn't a task branch (above).

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
4. **Footer**: `Fixes #123`, `BREAKING CHANGE: description`, then trailers as one final paragraph (git reads trailers only from the last one): `Co-authored-by: Name <email>` for people, `Assisted-by: Claude Code` for agents

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

### Hot files

Don't make every PR edit one shared file. A file most PRs touch (`CHANGELOG.md`, a hand-kept index or registry, a shared list of routes or flags) turns every merge into a conflict for the PRs behind it, whether approvals land back to back or through a merge queue, which ejects the conflicting PR. Give each change its own file and let a script or the release step build the aggregate: changelog fragments in `.changelog/` ([documentation.md](documentation.md#changelog)), one file per migration or registry entry. Generated files (lockfiles, golden hashes, snapshots) still conflict; regenerate them with the repo's tooling, never merge them by hand.

Merge queues need GitHub Enterprise Cloud for private org repos, and a small repo doesn't need one. Nothing here depends on a queue. A required check's workflow should still list `merge_group:` among its triggers (inert until a queue is enabled), so turning one on later can't stall on a check that never reports.

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

Assisted-by: Claude Code
```

The title and description become the squash commit on `main`, so end the description with the trailers as one final paragraph: `Assisted-by: Claude Code` when an agent helped, and `Co-authored-by: Name <email>` for each human pair. A session link (Claude Code adds one in cloud sessions) goes above that paragraph, never after it: git reads trailers only from the last paragraph, so a link there would hide `Assisted-by:`. This beats the harness's own placement. Co-author lines in branch commit messages don't survive the squash.

### Merging

- Before merging, remove the runner's files from `specs/handoffs/` (`plan-*.md`, the session `handoff-{topic}-{word}.md`, drafts) in the last commit on the branch, promoting anything durable to `specs/` or a milestone handoff first. Milestone handoffs (`handoff-m{N}-…`) stay. A forgotten removal lands plain markdown on `main`; one `git rm` fixes it
- **Squash and merge only**, with the PR title and description as the commit message: one commit on `main`, authored by the PR opener. Merge commits and rebase merges stay off; a rebase merge would put the agent on `main` as author. The `personal-repo-baseline` skill sets this per repo
- When merging with the button, delete any agent `Co-authored-by` line GitHub adds to the message box (it adds one per branch commit author who isn't the PR opener), and check the message ends with the trailer paragraph
- When asked to merge through the API (`merge_pull_request`, `gh pr merge`), pass the squash title and message explicitly instead of trusting GitHub's default: `commit_title` and `commit_message` (`--subject` and `--body` for `gh pr merge`), set to the PR title plus ` (#<number>)`, as the button writes it, and the PR description, with no agent co-author line. `gh pr merge` goes through GraphQL, so on Claude Code's cloud proxy use REST: `gh api -X PUT "repos/{owner}/{repo}/pulls/{number}/merge" -f merge_method=squash -f commit_title=… -f commit_message=…`
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
