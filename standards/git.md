# Git Workflow Standards

## Branch Strategy

We follow **GitHub Flow** — short-lived feature branches merged frequently to `main` via pull requests. For apps with scheduled release trains a stabalization branch is acceptable.

### Main Branch
- **`main`** - Production-ready code, always deployable

### Supporting Branches
- **Feature branches** - `feature/feature-name` or `feature/TICKET-123-feature-name`
- **Bugfix branches** - `fix/issue-description` or `fix/TICKET-123-description`
- **Release branches** - `release/v2` (short-lived, for hotfixes only; ideally not needed)

### Branch Naming
```bash
# Good
feature/user-authentication
feature/PROJ-123-add-login
fix/memory-leak
fix/PROJ-456-null-pointer
release/v2
release/v2.1

# Avoid
feature/stuff
my-branch
test
bugfix
```

## Versioning Convention

### Version Numbering

Use a simplified versioning scheme with always-incrementing major versions:

- **Standard releases** - `v1`, `v2`, `v3`, `v4`, etc.
- **Hotfixes** (rare cases only) - `v1.1`, `v2.1`, `v3.1`, etc.

### Rules

1. **Major versions always increment** - Each new release increments the version number
   - After `v1` comes `v2`, after `v2` comes `v3`, etc.
   - Never reset or decrement version numbers

2. **Hotfixes use minor versions** - Only in rare cases for critical production fixes
   - If `v2` has a critical bug, release `v2.1`
   - If another critical bug appears, release `v2.2`
   - The next planned release is still `v3` (not `v2.3`)

3. **Prefer major versions** - Default to incrementing the major version
   - Minor versions are exceptional, not the norm
   - Most bug fixes should wait for the next major version

### Examples

```bash
# Good - standard progression
v1  → v2  → v3  → v4
v1  → v2  → v2.1 → v3  # v2.1 is a hotfix
v1  → v1.1 → v2  → v2.1 → v2.2 → v3  # Multiple hotfixes

# Avoid
v1.0  → v1.1  → v1.2  # Use major versions instead
v1.2.3  # Avoid semantic versioning with patch numbers
v2  → v1.5  # Never go backwards
```

### When to Use Minor Versions (Hotfixes)

Only use minor versions for:
- **Critical security vulnerabilities** in production
- **Data loss or corruption bugs** affecting users
- **Service outages** that must be fixed immediately

Do NOT use minor versions for:
- Regular bug fixes (wait for next major version)
- New features (always a new major version)
- Performance improvements (wait for next major version)
- Non-critical fixes (wait for next major version)

### Tagging Releases

```bash
# Standard release - tag main directly
git checkout main
git tag v3
git push origin v3

# Hotfix workflow (rare) - only when patching a prior release
# 1. Create bugfix branch from the prior version tag
git checkout -b fix/critical-security-issue v3

# 2. Make fix and commit
git commit -m "fix: critical security issue"

# 3. Create release branch from the version tag
git checkout -b release/v3.1 v3

# 4. Merge bugfix into release branch
git merge fix/critical-security-issue

# 5. Tag the release
git tag v3.1
git push origin v3.1

# 6. Delete the release branch - it's no longer needed
git push origin --delete release/v3.1
git branch -d release/v3.1
```

**Note:** Release branches should be as short-lived as possible and ideally not needed at all. For standard releases, tag `main` directly. Only create release branches for hotfixes on prior versions, and delete them immediately after tagging.

## Commit Messages

### Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- **feat** - New feature
- **fix** - Bug fix
- **docs** - Documentation changes
- **style** - Code style changes (formatting, missing semicolons, etc.)
- **refactor** - Code refactoring without changing functionality
- **perf** - Performance improvements
- **test** - Adding or updating tests
- **chore** - Maintenance tasks, dependencies, config
- **ci** - CI/CD changes
- **build** - Build system changes

### Examples

**Simple commit:**
```
feat(auth): add login endpoint

Implements OAuth 2.0 authentication with JWT tokens.
```

**Detailed commit:**
```
fix(api): prevent race condition in user creation

Race condition occurred when multiple requests tried to create
users with the same email simultaneously. Added database-level
unique constraint and proper error handling.

Fixes #123
```

**Breaking change (shorthand):**
```
feat(api)!: change user endpoint response format

User endpoint now returns { data: user } instead of user
directly. Update all API clients accordingly.

Migration guide: https://docs.example.com/migration/v2
```

Append `!` after the type/scope to signal a breaking change inline. Optionally also include a `BREAKING CHANGE:` footer for longer explanations.

### Commit Message Rules

1. **Subject line (first line)**
   - Use imperative mood ("add" not "added" or "adds")
   - Don't capitalize first letter
   - No period at the end
   - Maximum 72 characters
   - Be specific and descriptive

2. **Body (optional)**
   - Wrap at 72 characters
   - Explain *what* and *why*, not *how*
   - Separate from subject with blank line
   - Use bullet points for multiple points

3. **Footer (optional)**
   - Reference issues: `Fixes #123`, `Closes #456`
   - Note breaking changes: `BREAKING CHANGE: description`
   - Credit co-authors: `Co-authored-by: Name <email>`

### Good vs Bad Commits

```bash
# Good
feat(user): add email verification
fix(api): handle null values in user response
refactor(auth): extract token validation logic
docs(readme): add installation instructions

# Bad
update stuff        # Too vague
Fixed bug          # Not descriptive, wrong tense
WIP                # Not descriptive
asdfgh            # Not descriptive
```

## Commit Practices

### Atomic Commits
- Each commit should represent one logical change
- Should be able to revert without breaking other features
- Makes debugging and code review easier

```bash
# Good - atomic commits
git commit -m "feat(user): add User model"
git commit -m "feat(user): add UserRepository"
git commit -m "feat(user): add UserService"
git commit -m "test(user): add user service tests"

# Avoid - mixed changes
git commit -m "add user feature and fix login bug and update docs"
```

### Commit Frequency
- Commit early and often (in feature branches)
- Each logical step should be a commit
- Don't commit broken code to shared branches
- Can squash commits before merging to main

### What Not to Commit
```bash
# Add to .gitignore
.env
.env.local
*.log
.DS_Store
__pycache__/
*.pyc
*.pyo
.venv/
venv/
dist/
build/
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
*.swp
*.swo
.idea/
.vscode/
*.key
*.pem
```

## Pull Request Workflow

### Creating a PR

1. **Before creating PR:**
   ```bash
   # Update your branch with latest main
   git fetch origin
   git rebase origin/main

   # Run tests
   pytest

   # Run linting
   ruff check .
   ```

2. **Create descriptive PR:**
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
   - [ ] Manual testing completed

   ## Screenshots
   (if applicable)

   ## Breaking Changes
   (if any)

   ## Related Issues
   Closes #123
   Related to #456
   ```

3. **Keep PRs focused:**
   - One feature or fix per PR
   - Reasonable size (< 400 lines changed ideally)
   - Split large changes into multiple PRs

### PR Title Format
```
feat(scope): brief description
fix(scope): brief description
docs: update README
```

### Reviewing PRs

**As a reviewer:**
- Review within 24 hours
- Check for functionality, style, tests, docs
- Be constructive and specific in feedback
- Approve when ready or request changes

**As an author:**
- Respond to all comments
- Make requested changes or explain why not
- Mark conversations as resolved
- Re-request review after changes

### Merging Strategies

**Squash and merge (recommended for features):**
```bash
# Creates single commit on main
# Good for: Feature branches with many WIP commits
git merge --squash feature-branch
```

**Rebase and merge:**
```bash
# Maintains linear history
# Good for: Clean branches with good commit history
git rebase main
git merge feature-branch
```

**Merge commit:**
```bash
# Preserves all commits
# Good for: Release branches, preserving history
git merge --no-ff feature-branch
```

## Branch Management

### Creating Branches
```bash
# Create and switch to new branch
git checkout -b feature/user-auth

# Or with newer syntax
git switch -c feature/user-auth

# From specific commit or branch
git checkout -b hotfix/critical-bug origin/main
```

### Keeping Branches Updated
```bash
# Rebase on main (recommended)
git fetch origin
git rebase origin/main

# Or merge main into branch
git merge origin/main
```

### Deleting Branches
```bash
# Delete local branch
git branch -d feature/completed-feature

# Delete remote branch
git push origin --delete feature/completed-feature

# Prune deleted remote branches
git fetch --prune
```

## Common Workflows

### Feature Development
```bash
# 1. Create feature branch
git checkout -b feature/new-feature

# 2. Make changes and commit
git add .
git commit -m "feat: add new feature"

# 3. Push to remote
git push -u origin feature/new-feature

# 4. Create pull request on GitHub/GitLab

# 5. After approval, merge via UI

# 6. Delete local branch
git checkout main
git pull
git branch -d feature/new-feature
```

### Hotfix Workflow (Critical Production Fixes)
```bash
# 1. Create bugfix branch from the version tag needing the fix
git checkout -b fix/critical-bug v2

# 2. Fix and commit
git add .
git commit -m "fix: resolve critical bug"

# 3. Create release branch from the version tag
git checkout -b release/v2.1 v2

# 4. Merge bugfix into release branch
git merge fix/critical-bug

# 5. Tag the hotfix version
git tag v2.1
git push origin v2.1

# 6. Clean up - delete both branches
git branch -d fix/critical-bug
git push origin --delete release/v2.1
git branch -d release/v2.1
```

**Important:** Release branches are temporary. Once tagged, delete them immediately. The version tag is the permanent reference point.

### Updating Feature with Main Changes
```bash
# Rebase approach (cleaner history)
git checkout feature/my-feature
git fetch origin
git rebase origin/main

# Resolve conflicts if any
git add resolved-files
git rebase --continue

git push --force-with-lease

# Merge approach (preserves history)
git checkout feature/my-feature
git merge origin/main
git push
```

## Resolving Conflicts

```bash
# 1. Fetch latest changes
git fetch origin

# 2. Start rebase or merge
git rebase origin/main
# or
git merge origin/main

# 3. Resolve conflicts in files
# Look for conflict markers:
# <<<<<<< HEAD
# your changes
# =======
# their changes
# >>>>>>> origin/main

# 4. After resolving
git add resolved-files

# For rebase
git rebase --continue

# For merge
git commit
```

## Advanced Git

### Interactive Rebase
```bash
# Clean up last 3 commits
git rebase -i HEAD~3

# Options:
# pick   - keep commit
# reword - change commit message
# edit   - amend commit
# squash - combine with previous
# drop   - remove commit
```

### Cherry-pick
```bash
# Apply specific commit to current branch
git cherry-pick abc123

# Cherry-pick range
git cherry-pick abc123..def456
```

### Stashing
```bash
# Save work in progress
git stash

# Save with message
git stash save "WIP: working on feature"

# List stashes
git stash list

# Apply most recent stash
git stash pop

# Apply specific stash
git stash apply stash@{1}

# Delete stash
git stash drop stash@{0}
```

### Viewing History
```bash
# View commit history
git log --oneline --graph --all

# View changes in a commit
git show abc123

# View file history
git log -p filename

# Find when a bug was introduced
git bisect start
git bisect bad
git bisect good abc123
```

## Git Configuration

### User Settings
```bash
# Set user name and email
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Set default branch name
git config --global init.defaultBranch main

# Set default editor
git config --global core.editor "code --wait"
```

### Useful Aliases
```bash
# Add to ~/.gitconfig
[alias]
  st = status
  co = checkout
  br = branch
  ci = commit
  unstage = reset HEAD --
  last = log -1 HEAD
  lg = log --oneline --graph --all --decorate
  amend = commit --amend --no-edit
```

## Git Hooks

### Pre-commit Hook
```bash
# .git/hooks/pre-commit
#!/bin/bash

# Run linting
ruff check . || exit 1

# Run tests
pytest || exit 1

echo "Pre-commit checks passed"
```

### Commit Message Hook
```bash
# .git/hooks/commit-msg
#!/bin/bash

# Validate commit message format
commit_msg=$(cat "$1")
pattern='^(feat|fix|docs|style|refactor|perf|test|chore|ci|build)(\(.+\))?!?: .{1,72}'

if ! [[ $commit_msg =~ $pattern ]]; then
  echo "Invalid commit message format"
  echo "Use: <type>(<scope>): <subject>"
  exit 1
fi
```

## Best Practices

### Do's
- ✅ Write clear, descriptive commit messages
- ✅ Commit early and often (in feature branches)
- ✅ Keep commits atomic and focused
- ✅ Pull latest changes before starting work
- ✅ Create feature branches from main
- ✅ Delete branches after merging
- ✅ Use meaningful branch names
- ✅ Review your changes before committing

### Don'ts
- ❌ Don't commit sensitive data (keys, passwords)
- ❌ Don't commit to main directly
- ❌ Don't push broken code to shared branches
- ❌ Don't rewrite published history (unless force-with-lease)
- ❌ Don't commit large binary files
- ❌ Don't mix unrelated changes in one commit
- ❌ Don't use vague commit messages

## Recovery and Undo

```bash
# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes)
git reset --hard HEAD~1

# Undo changes to a file
git checkout -- filename

# Restore deleted file
git checkout HEAD -- filename

# Undo a public commit
git revert abc123

# Recover deleted branch
git reflog
git checkout -b recovered-branch abc123
```

## Resources

- [Git Documentation](https://git-scm.com/doc)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Git Flight Rules](https://github.com/k88hudson/git-flight-rules)
