# Changelog fragments

Why the standards replace `## [Unreleased]` edits with per-PR fragment files,
where the design departs from HashiCorp's, the evidence from nowline, and
the checklist for moving nowline over. The rules are in
`standards/documentation.md` (Changelog); the tooling and the generic
set-up and migration steps are in the `personal-release` skill.

## Recommendation

Adopt HashiCorp's model: each PR adds `.changelog/<name>.txt` with fenced
`release-note:<kind>` blocks, and the release step assembles the files into
`CHANGELOG.md` and deletes them. PRs stop sharing lines, so they stop
conflicting, with or without a merge queue.

Where it deliberately departs from HashiCorp's `go-changelog`:

- **Kinds are Keep a Changelog's** (`added`, `changed`, `deprecated`,
  `removed`, `fixed`, `security`), not HashiCorp's (`feature`, `bug`,
  `enhancement`, ...). The standard and every existing changelog are KaC.
- **Free file names, branch slug by default**, not `<PR number>.txt`. An agent
  commits before the PR exists (and doesn't open PRs on its own), so
  requiring the number costs a second push per PR.
- **One stdlib Python script** (`personal-release/templates/changelog.py`),
  not a Go toolchain. It sits beside `bump_version.py`, which calls it.
- **No `## [Unreleased]` heading in a migrated file.** An empty one invites
  agents trained on KaC to append there; the CI check fails a PR that adds
  an entry or heading above the latest release, while fixes to released
  entries pass. `changelog.py preview` shows what's pending.
- **The release deletes the fragments it used.** HashiCorp keeps every file
  forever and diffs two git refs to find each release's set
  (terraform-provider-aws carries thousands). Once an entry is in
  `CHANGELOG.md` and git history, keeping its file adds nothing, and an
  empty-but-for-README `.changelog/` means "nothing pending" at a glance.
  Order comes from git (first-parent merge time), not names, so deleting
  loses nothing there either.

Merge queues: needed for none of this. The CI check lists `merge_group:` so a
repo can turn a queue on later without a stalled required check; on Team
plan private repos the trigger never fires.

## Evidence from nowline

- CHANGELOG.md is in 82 of 198 commits since June (41%). Nothing else
  that PRs touch comes close: `cursor-release-history.json` (48) is a bot
  pushing to main, the `package.json` churn is release commits, and
  `hashes.json` and `pnpm-lock.yaml` (13 to 14) are generated.
- Replayed the 29 PRs since v0.8.6 as parallel branches off one base, on a
  scratch clone. Applying each PR's CHANGELOG.md diff: 28 of 29 don't
  3-way-apply to the base, because each was written on top of the previous
  PR's entry. As fragments: 29 branches, 0 conflicts.
- `changelog.py release` on today's tree is byte-identical to
  `release-changelog.mjs` except for the dropped empty `## [Unreleased]`, for
  both changelogs. The fragment replay reproduced all 47 pending entries
  (plus two copies of one entry a later PR had reworded in place; with
  fragments, a reword edits the earlier fragment file).

## nowline migration checklist (one PR, not done yet)

1. `scripts/changelog.py` from the template; `.changelog/README.md` and
   `packages/vscode-extension/.changelog/README.md` from
   `changelog-readme.md`.
2. `Makefile` `release-changelog`: `python3 scripts/changelog.py release
   $(VERSION)`. Delete `.github/scripts/release-changelog.mjs` and
   `packages/integration-tests/test/release-changelog.test.ts`.
3. **`release.yml` "Commit, tag, and push"** adds named paths; add
   `.changelog packages/vscode-extension/.changelog` or the fragment
   deletions never commit and the next release ships them twice.
4. `.github/workflows/changelog.yml` from the template; create the
   `no-changelog` label; add `{ "context": "changelog" }` to the required
   checks in `scripts/apply-branch-policies.sh` and re-run it after the
   workflow has reported once.
5. Text: CHANGELOG.md preamble, CONTRIBUTING.md "Changelog entries" and the
   PR checklist line, AGENTS.md "Changelog", `specs/releasing.md`
   "Changelog workflow" and the cut-release steps,
   `.cursor/skills/optimize-docs/SKILL.md`.
6. Leave the 47 pending Unreleased entries where they are; the next release
   folds them in.
7. Any open PR editing CHANGELOG.md moves its entry to a fragment.

## The strict up-to-date rule

nowline's ruleset sets `strict_required_status_checks_policy: true`, so every
merge still makes each other PR update and re-run the full matrix.
Fragments take the changelog out of that update (the "Update branch"
button stops hitting conflicts there), but they don't remove the CI rerun. nowline
is public, so a merge queue is available on any plan and is the fix for that
cost. On Team plan private repos there's no queue: keep strict where a stale
base could hide a semantic break, and drop it in small repos where the
rerun costs more than it catches.
