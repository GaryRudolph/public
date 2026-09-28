---
name: personal-release
description: >-
  Cut releases Gary's way: pick patch/minor/major from what changed since the
  last v-tag, bump version.txt and every package version in lock-step, move
  the CHANGELOG's Unreleased entries, tag vMAJOR.MINOR.PATCH (no pre-release
  suffixes), run the hotfix flow from a release/vX.Y branch, compute a build's
  <release>+<sha> (<buildCode>) string, and set up a repo's versioning and
  Release workflow. Also decides when an API/file-format contract gets a new
  integer major (v1 to v2). Use for "cut a release", "release this", "bump
  the version", "tag v…", "ship a hotfix", "what version is this build", or
  "set up versioning".
---

# personal-release

The canonical rules are in
[`../personal-standards/standards/versioning.md`](../personal-standards/standards/versioning.md).
The essentials, for quick reference:

- **Two regimes.** Artifacts (binaries, packages, apps, images) use SemVer
  `MAJOR.MINOR.PATCH`, tagged `vX.Y.Z`. Contracts (URL paths, wire and file
  formats) use an integer major, `v1` or `v2`, bumped only when they break,
  and never git-tagged on their own.
- **`version.txt` holds the last released version.** Only the release step
  rewrites it, at tag time.
- **No pre-release suffixes.** Every tag is stable. Dev builds are
  `<release>+<sha>`, never `<release>-<sha>`.
- **Build code** is `git rev-list --count HEAD`, so CI needs `fetch-depth: 0`.

## Start with the facts

```bash
python3 scripts/release_facts.py            # add --next patch|minor|major to preview
```

It reports the branch, whether the tree is clean or the clone is shallow,
the build code, the last v-tag and the commits since it, every version field
and whether it matches `version.txt`, pre-release suffixes, the CHANGELOG's
Unreleased entries, release tooling and checkout depth, the platform surfaces
the repo appears to ship, and `/api/vN` contract paths. It makes no
recommendation. Decide from these facts.

## Cut a release

1. **Preconditions.** On `main`, or `release/vX.Y` for a hotfix. Clean tree,
   CI green on HEAD, not already tagged, every version field matching
   `version.txt`. Stop and report anything that isn't met.
2. **Propose the level.** Read the commits and the Unreleased entries since
   the last tag:
   - `major`: a breaking change to the public API, CLI, or schema
   - `minor`: a backward-compatible feature
   - `patch`: bug fixes only

   On `0.x`, a breaking change may be a minor, but call it out in the
   changelog. Give Gary the level and a sentence of evidence. **He picks.**
3. **Check the changelog.** Unreleased should describe what ships. Offer to
   fill gaps from the commits, but don't invent entries.
4. **Release.** With Gary's go-ahead:
   - If the repo has a Release workflow:
     `gh workflow run release.yml -f level=<level>` (add `--ref release/vX.Y`
     for a hotfix), then watch it.
   - Otherwise, locally: `python3 scripts/bump_version.py <level>`, review
     the diff, commit `release vX.Y.Z`, `git tag -a vX.Y.Z -m vX.Y.Z`, and
     push the branch and the tag. Pushing is outward-facing, so confirm first.
5. **After.** The tag push starts the per-platform publish jobs. Check they
   ran. Dev builds now read `X.Y.Z+<sha>`.

Never tag with a suffix (`-rc.1`, `-beta`) or put `+sha` into a published
version field (`package.json`, `pyproject.toml`, `Info.plist`, the Play
`versionName`). The per-platform tables in the standard say which field gets
which form.

## Hotfix

1. `git switch -c release/vX.Y vX.Y.Z` from the tag being patched, and push.
2. PR the fix against `release/vX.Y`, labelled `backport main`. Once it's
   merged, get the same fix onto `main` (the backport workflow, or a
   cherry-pick PR).
3. Release from `release/vX.Y` with `level=patch`. The hotfix tag doesn't
   need to be on `main`.
4. **Android Play:** `versionCode` must beat the current production value,
   so override `BUILD_CODE` for the upload (see the standard's Play
   caveat), and note the override in the release notes. iOS needs nothing.

## Contract versions (Regime 1)

A breaking change to an API path, RPC schema, or file format gets the next
integer (`/api/v2`, `acme v3`). Non-breaking changes don't bump it. Keep the
old version serving until consumers move. Hotfixes to a contract (`v2.1`)
are for security or data-loss fixes only. The artifact that implements the
contract is still released under SemVer as usual.

## What version is this build

`<release>+<sha>[.dirty] (<buildCode>)`: `version.txt`, the short HEAD SHA
(`.dirty` if the tree has uncommitted changes), and
`git rev-list --count HEAD`. `release_facts.py` prints it. A shallow clone
undercounts the build code; fetch the full history first.

## Set up versioning in a repo

1. Create `version.txt` with the last released version, or `0.1.0` if none
   has shipped, and make every package version field match it.
2. Copy [`templates/bump_version.py`](templates/bump_version.py) to
   `scripts/bump_version.py`. It bumps `version.txt`, every `package.json`
   outside `node_modules`, `pyproject.toml` `[project]`, and `Cargo.toml`
   `[package]` in lock-step, moves the changelog entries, and refuses if the
   fields already disagree. Other surfaces (Info.plist, Gradle, Maven,
   Docker tags, Windows resources) should read `version.txt` at build time;
   the standard's per-platform tables give each projection.
3. Copy [`templates/release.yml`](templates/release.yml) to
   `.github/workflows/release.yml`, and add a `RELEASE_TOKEN` secret that can
   push. `GITHUB_TOKEN` pushes don't trigger the tag workflows.
4. Set `fetch-depth: 0` on every checkout that computes a build code.
5. Bake `<release>`, `<sha>`, and `<buildCode>` into the binary or app at
   build time, so `--version` and About screens show the full string. The
   standard's Homebrew section lists the mechanism per language.
6. Add `CHANGELOG.md` with a `## [Unreleased]` section if there isn't one.
