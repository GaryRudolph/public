---
name: personal-repo-baseline
description: >
  Audit and apply Gary's per-repo agent baseline: the settings the personal
  plugin can't carry. Today that's the repo's .claude/settings.json ($schema,
  and attribution set to "Assisted-by: Claude Code" for commits and PRs) and
  GitHub's merge settings (squash only, PR title and description as the
  commit message, head branches deleted on merge). Dry-run first; apply repo
  by repo with confirmation; re-run any time to bring a repo up to the
  current baseline. personal-new-project runs it last. Triggers: "repo
  baseline", "set up this repo for agents", "add .claude/settings.json",
  "fix commit attribution", "Claude shows up as co-author", "squash merge
  settings", "update this repo to the baseline", "personal-repo-baseline".
---

# Repo Baseline Skill

Standards reach every session through the `personal` plugin. A few settings
can't: they live in the repo or on GitHub, so each repo needs them once, and
again whenever the baseline grows. This skill audits them and applies what's
missing, and it's safe to re-run.

Load `../personal-standards/standards/git.md` ("AI attribution" under AI Agent
Behavior, and Merging) for the rules these settings serve.

## The baseline

| Item | Lives in | Target | Why it's per repo |
|------|----------|--------|-------------------|
| **Agent attribution** | `.claude/settings.json` | [`templates/claude-settings.json`](templates/claude-settings.json): `$schema`, and `attribution.commit` and `attribution.pr` set to `Assisted-by: Claude Code` | Unset, Claude Code adds `Co-authored-by: Claude`. A plugin's settings carry only `agent` and `subagentStatusLine`, and cloud sessions read the repo's `.claude/settings.json`, never `~/.claude/settings.json` |
| **Merge settings** | GitHub repo settings | [`templates/github-merge-settings.json`](templates/github-merge-settings.json): squash only, `PR_TITLE` and `PR_BODY`, head branches deleted | Squash makes the PR opener the author on `main` and the description, with its `Assisted-by` trailer, the commit message. GitHub's defaults (`COMMIT_OR_PR_TITLE` and `COMMIT_MESSAGES`, merge commits and rebase on) copy every branch trailer onto `main`, and a rebase merge puts the agent there as author |

- **Leave `attribution.sessionUrl` unset** (default `true`) so branch
  commits keep `Claude-Session:`, as git.md wants; `false` drops the link. In
  a PR description the link goes above the trailer paragraph (git.md, PR
  Body), whatever the harness's placement.
- **`includeCoAuthoredBy` is deprecated** — `attribution` replaces it. Propose
  removing a leftover one.
- **Multi-repo cloud sessions don't apply it** — a session with several
  repositories reads only `enabledPlugins` and `extraKnownMarketplaces` from
  each repo's file (Claude Code settings docs, "Settings in cloud sessions"),
  and the plugins those name don't load in the cloud either. `core.md`'s
  attribution rule still holds there.
- **`.claude/settings.local.json` wins on its machine** — report a local
  `attribution` that differs; don't edit it (it's personal and untracked).

### Adding an item

Keep the baseline to what the plugin can't carry. A new item gets a row in the
table above, a template or target values in `templates/`, its facts in
`scripts/repo-facts.sh` (facts only), an apply step under Step 4, and cases in
`tests/test-repo-baseline.sh`. Re-running the skill then brings existing repos
up to date.

## Workflow

### Step 1 — Gather facts

**Facts in script, judgment in agent.** The script prints what each repo has
today; it doesn't compare anything with the templates. Run it read-only:

```
bash <skill-dir>/scripts/repo-facts.sh [<repo> ...]
```

Per repo (default: the current directory) it prints:

- the root, `origin` (credentials masked), its host, the `owner/name`
  parsed from it, the branch, and the commit count
- for `.claude/settings.json`: whether it exists (and where a symlink
  points), whether git tracks it, whether it differs from `HEAD`, origin's
  default branch and whether the file matches it there (local refs, as of
  the last fetch), whether it parses, any duplicate keys, and its contents
  verbatim
- for `.claude/settings.local.json`: key names and its `attribution` value
  only
- GitHub's value for every key in `templates/github-merge-settings.json`,
  plus `full_name`, `default_branch`, and `permissions`, from
  `gh api repos/<owner>/<name>` (REST; Claude Code's cloud proxy refuses
  GraphQL)

It needs bash, git, and python3. Without `gh`, or without access, the GitHub
section says why. It reads GitHub only when origin's host is github.com,
Claude Code's cloud git proxy, or an ssh alias for github.com, such as
`github.com-lolay` (resolved with `ssh -G`; without ssh, a host with no dot
or a `github.com-*` alias is read unresolved). Any other host (GitLab, an IP
address, a local path) gets a "not read" line, since the same `owner/name`
on GitHub would be another repo. A `null` GitHub value means GitHub didn't
return it, usually because the token can't administer the repo;
`permissions` shows what it can do.

### Step 2 — Audit (dry-run, always)

Compare each repo's facts with the templates. Report one block per repo, with
a row per baseline item: current value, target, and the change you propose
(add, replace, or none). First confirm GitHub's `full_name` is the
`owner/name` from origin: an ssh alias can point anywhere, and a rename or
transfer redirects. On a mismatch, say so and leave the GitHub item until
Gary confirms the repo. Call out:

- a `.claude/settings.json` that doesn't parse or has duplicate keys (it needs
  a hand fix first; the merge refuses it)
- an existing `attribution` value that differs from the template,
  `sessionUrl: false`, or a leftover `includeCoAuthoredBy`
- a `.claude/settings.json` git doesn't track, that differs from `HEAD`, or
  that isn't the same on origin's default branch: cloud sessions see it once
  it's on the branch they start from, usually after merge
- a local `attribution` override
- GitHub values that differ, and whether `permissions.admin` allows the change
- a repo that isn't on GitHub yet: its GitHub item waits

Preview the exact settings.json change with:

```
python3 <skill-dir>/scripts/merge_settings.py <skill-dir>/templates/claude-settings.json <repo>/.claude/settings.json --diff
```

**In plan mode, on dry-run-only requests, or when Gary hasn't approved apply:
stop here.** Present the report; write nothing.

### Step 3 — Confirm, repo by repo and item by item

- **settings.json** — show the diff. Ask separately about each existing value
  the template would replace; the merge keeps them unless told.
- **GitHub** — a remote, outward-facing change. Ask in this session, naming
  the repo and each value. A yes to the file isn't a yes to GitHub, and a yes
  for one repo isn't a yes for the next. A runner sends nothing, so it
  doesn't ask; Step 4 hands Gary the command.
- **Fail closed** — no response, a dismissed prompt, or an ambiguous reply
  means skip.

### Step 4 — Apply

**settings.json.** Merge the template in, with one `--take` per replacement
Gary approved:

```
python3 <skill-dir>/scripts/merge_settings.py <skill-dir>/templates/claude-settings.json <repo>/.claude/settings.json --write [--take attribution.commit ...]
```

It adds missing keys, merges objects key by key, and leaves every other
existing value alone unless `--take <dotted.path>` names it. It never removes a
key, puts `$schema` first, writes 2-space JSON, and refuses a file that isn't
a JSON object or has duplicate keys. A file that already matches, whatever
its formatting, is left as it is, and a symlinked file is written through
the link. Removing a key, such as
`includeCoAuthoredBy`, is a hand edit after a yes. The file is an ordinary
change: commit it per `core.md`.

**GitHub.** On a workstation, with Gary's yes for this repo (a runner can't
send it; see below):

```
gh api -X PATCH repos/<owner>/<name> --input <skill-dir>/templates/github-merge-settings.json --silent
```

If he approved only some values, send just those (`-F key=true` for booleans,
`-f key=VALUE` for strings) instead of `--input`, within two limits, since
GitHub can refuse the PATCH with a 422: the two `squash_merge_*` values go
together, as one of the pairs Settings offers (the baseline's `PR_TITLE`
with `PR_BODY`; `COMMIT_OR_PR_TITLE` only with `COMMIT_MESSAGES`), and at
least one merge method stays on. If his subset breaks either, say which and
ask again. It needs admin on the repo.

**On a runner, don't send the PATCH.** Claude Code's cloud GitHub proxy
refuses repository settings writes (HTTP 403 "Repository settings writes
are not permitted through this proxy."); reads go through. So when
`CLAUDE_CODE_REMOTE=true`, or a PATCH already got that 403, don't attempt or
retry it, with or without a yes. Give Gary the command to run on a
workstation:

```
gh api -X PATCH repos/<owner>/<name> -F allow_squash_merge=true -F allow_merge_commit=false -F allow_rebase_merge=false -f squash_merge_commit_title=PR_TITLE -f squash_merge_commit_message=PR_BODY -F delete_branch_on_merge=true
```

plus the Settings path below (a subset he wants follows the limits above),
and once he says it's done, re-run the audit (Step 5).

If `gh` is missing or the call is refused, don't work around it: give Gary the
values to set by hand in Settings → General → Pull Requests:

- **Allow merge commits**: off
- **Allow squash merging**: on, with the default message **Pull request title
  and description**
- **Allow rebase merging**: off
- **Automatically delete head branches**: on

### Step 5 — Verify

Re-run `repo-facts.sh` on each changed repo and check every applied item now
matches its template. Report anything that didn't take.

## Called from personal-new-project

A new repo has no `.claude/settings.json`, so the merge writes the template as
is, and it goes into the first commit (on `main`, when Gary asks). The GitHub
item waits until the repo exists on GitHub: say so, and offer to run it after
the first push. On a runner, hand Gary the command instead (Step 4).

## Safety invariants (always enforce)

1. **Audit-first** — Step 2 runs before any write; dry-run is the default.
2. **Fail closed** — without an explicit yes, write nothing, locally or on
   GitHub.
3. **Never drop a key** — the merge only adds, or replaces with `--take`;
   anything else is a hand edit after a yes.
4. **Remote changes ask in-session** — GitHub settings change only after Gary
   confirms in this session, repo by repo.
5. **Only what the plugin can't carry** — the standards reach sessions through
   the plugin; don't copy them into repos.
6. **Standards precedence** — a project or org rule (another merge policy, an
   org-managed `attribution`) wins; note it in the report and skip that item.

## Files in this skill

| File | Purpose |
|------|---------|
| `SKILL.md` | This file — baseline, workflow, and invariants |
| `templates/claude-settings.json` | The baseline keys for a repo's `.claude/settings.json` |
| `templates/github-merge-settings.json` | Target GitHub merge settings; also the PATCH body |
| `scripts/repo-facts.sh` | Read-only facts per repo (facts only, no verdicts) |
| `scripts/merge_settings.py` | Mechanical, key-preserving merge of a template into a JSON file |
| `tests/test-repo-baseline.sh` | Fixture tests for both scripts, with a stub `gh`; `make -C agents test` runs it |
