# Plan: ghx release pipeline to the lolay tap and Scoop bucket (finch)

Run C of the orchestrate phase 1 dogfood (`GaryRudolph/public` `specs/handoffs/dogfood-orchestrate-native.md`): Claude Code on the web, unattended, switched to gated mid-run. Third of three plans that bring `lolay/ghx` to the shape of `lolay/triage`. Starts from `main` after plans A (`plan-ghx-baseline-heron`) and B (`plan-ghx-platforms-lynx`) merged. It ends with everything a release needs in the repo and nothing released: no tag, no workflow run, no secret, no commit to the tap or the bucket.

## Context

- **After plans A and B:** module `github.com/lolay/ghx`, binary `ghx` from `cmd/ghx/`, a standard `Makefile` (no `##@ Release` or `##@ Danger` section yet), `Makefile.md` with a CI map, `.go-version`, tests on every package, `.github/workflows/ci.yml` on macOS, Linux and Windows, `CHANGELOG.md` with `## [Unreleased]`. No version number anywhere yet, no `--version`, no tags on the remote.
- **The model, triage** (`lolay/triage`, public; shallow-clone `https://github.com/lolay/triage.git` into a temp directory outside this repo and only read it): `.goreleaser.yaml` (darwin, linux, windows × amd64, arm64; tar.gz, zip on Windows; checksums), `scripts/publish-formula.sh` + `scripts/triage.rb.tmpl` (renders `Formula/triage.rb` from `dist/checksums.txt` and commits it to `lolay/homebrew-tap` with `HOMEBREW_TAP_TOKEN`; `DRY_RUN=1` prints it), `scripts/publish-scoop.sh` + `scripts/triage.json.tmpl` (the same for `bucket/triage.json` in `lolay/scoop-bucket` with `SCOOP_BUCKET_TOKEN`), `.github/workflows/release.yml`, `specs/releasing.md` ("remote pushes happen last", in a fixed order), and the Makefile's `##@ Release` and `##@ Danger` targets behind `CONFIRM_*`.
- **Where ghx follows Gary's standard instead of triage:** triage's version comes from `git describe` and its workflow bumps only the CHANGELOG. Gary's `versioning.md` and the `personal-release` skill say `version.txt` holds the last released version, `scripts/bump_version.py` and the Release workflow template bump it at tag time, dev builds read `<release>+<sha> (<buildCode>)`, and there are no pre-release suffixes, snapshots included. Copy the two templates from the `personal-release` skill (`templates/bump_version.py`, `templates/release.yml`): the loaded `personal` plugin's copy, or `https://raw.githubusercontent.com/GaryRudolph/public/main/plugins/personal/skills/personal-release/templates/`.
- **Tools on the runner:** if `goreleaser` or `actionlint` isn't installed, run them as `go run github.com/goreleaser/goreleaser/v2@<latest v2>` and `go run github.com/rhysd/actionlint/cmd/actionlint@<latest>`, versions looked up now.

## Rules for every step

- Read Gary's standards first: `versioning.md`, `security.md`, `secrets/` (what may live in a repo), `makefile.md`, `git.md`, `go/security.md`; and the `personal-release` skill.
- Commit each finished step on the task branch as `m{N}.s{K} <imperative subject>` (72 characters at most, no period), a blank line, a body if useful, then the session's trailers as the last paragraph (`Assisted-by: Claude Code`, plus the runner's `Claude-Session:` line). Never `Co-authored-by`. Don't push; the orchestrator does after each wave.
- `make ci` passes at the end of every step.
- **No outward actions, and nothing that could release:** no tags, no `gh release`, no workflow dispatch, no secrets created or read, no PRs, no clone-and-push to `lolay/homebrew-tap` or `lolay/scoop-bucket`. The publish scripts are tested only with `DRY_RUN=1`. No token or secret value in any file; workflows read secrets only through `secrets.<NAME>` into a step's `env`.

## m1 - Version and release artifacts

#### m1.s1 - [deep] Version source of truth and `ghx --version`

- `version.txt` per the `personal-release` skill's set-up section (`0.1.0`, since nothing has shipped), `scripts/bump_version.py` copied from the template unchanged, and an `internal/buildinfo` package with `Version`, `Sha` and `BuildCode` set by `-ldflags -X` (defaults for an unstamped `go build`/`go run`, such as `dev`).
- `ghx --version` prints `ghx <release>+<sha> (<buildCode>)`, with `.dirty` on the metadata for a dirty tree, per the standard's "Reading a build version" (not triage's format). Wire it through cobra's `Version` with a template.
- Makefile: `build` stamps `RELEASE` from `version.txt`, `SHA` from `git rev-parse --short HEAD` (plus `.dirty`), `BUILD_CODE` from `git rev-list --count HEAD`; a `bump` target (`LEVEL=patch|minor|major`, `##@ Release`) that runs `scripts/bump_version.py`. Decide and write down (a comment in the Makefile and in the step's artifact) how goreleaser will get the same three values in m1.s2, so a local build and a release build of one commit print the same string.
- Tests for the version string (stamped, unstamped, dirty), and a `make build && bin/ghx --version` check in the step's artifact.
- **Accept when:** `bin/ghx --version` prints `ghx 0.1.0+<sha> (<count>)` on a clean tree; `python3 scripts/bump_version.py patch --dry-run` reports `0.1.1` and changes nothing; `make ci` passes.

#### m1.s2 - [exec] goreleaser configuration and a local snapshot

- `.goreleaser.yaml` (v2 schema) from triage's: `main: ./cmd/ghx`, binary `ghx`, `CGO_ENABLED=0`, `-trimpath`, ldflags into `github.com/lolay/ghx/internal/buildinfo` as m1.s1 decided (`BUILD_CODE` from the environment, `{{ .ShortCommit }}`), darwin, linux and windows × amd64 and arm64, archives `ghx_<version>_<os>_<arch>` (tar.gz, zip on Windows) carrying `README.md`, `LICENSE` and `CHANGELOG.md`, `checksums.txt`, `release.github` `lolay/ghx`. Snapshot naming without a pre-release suffix (`<release>+<sha>`), per the standard.
- Makefile `##@ Release`: `snapshot` (`goreleaser release --snapshot --clean`) and `release-check` (`goreleaser check`), with `GORELEASER ?= goreleaser` so the runner can pass the `go run` form.
- **Accept when:** `goreleaser check` passes; `make snapshot` builds all six archives and `checksums.txt` under `dist/`; the darwin or linux binary for this machine prints the same `--version` string as `make build` for this commit, apart from `.dirty`; `dist/` stays ignored.

#### m1.s3 - [exec] Homebrew formula and Scoop manifest publishers

- `scripts/publish-formula.sh` + `scripts/ghx.rb.tmpl` and `scripts/publish-scoop.sh` + `scripts/ghx.json.tmpl`, ported from triage's: `class Ghx`, the description from the GitHub repo ("Clones and refreshes all repos for a GitHub organization"), homepage `https://github.com/lolay/ghx`, license `Apache-2.0`, `bin.install "ghx"` (no man pages), a `test do` that matches the version in `ghx --version`, Scoop `"bin": "ghx.exe"` with `checkver` and `autoupdate`. Same flow as triage: render from `dist/checksums.txt`, `DRY_RUN=1` prints and exits, otherwise clone the target repo with its token, commit `ghx <version>` as a bot identity, push.
- **Accept when:** after `make snapshot`, `DRY_RUN=1 scripts/publish-formula.sh <snapshot version> dist` and `DRY_RUN=1 scripts/publish-scoop.sh <snapshot version> dist` print a formula and a manifest whose every sha256 matches `dist/checksums.txt`; `ruby -c` on the rendered formula and `python3 -m json.tool` on the manifest pass (skip either tool if missing and say so); `shellcheck` on both scripts is clean if installed; neither script ran without `DRY_RUN=1`.

#### m1.s4 - [fast] Danger targets for the publish steps

- Makefile `##@ Danger`, copied from triage's shape with the standard's `confirm` macro: `publish-formula` (`CONFIRM_PUBLISH_FORMULA=1`, `VERSION=x.y.z`), `publish-scoop` (`CONFIRM_PUBLISH_SCOOP=1`), `release` (`CONFIRM_RELEASE=1`, `goreleaser release --clean` for the current tag). No `tag` target: tags come from the Release workflow.
- **Accept when:** each Danger target refuses without its `CONFIRM_*` variable (run each bare and see the refusal; never set the variable); `make help` lists them under Danger.

## m2 - Release workflows and docs

#### m2.s1 - [deep] Release and publish workflows

- `.github/workflows/release.yml` from the `personal-release` template (dispatch with `level`, from `main` or a `release/vX[.Y]` line branch, bump with `bump_version.py`, commit `release vX.Y.Z`, tag, push with `RELEASE_TOKEN`) and `.github/workflows/publish.yml` on `push` of `v[0-9]+.[0-9]+.[0-9]+` tags: checkout with `fetch-depth: 0`, `setup-go` from `.go-version`, `BUILD_CODE` computed, `goreleaser release --clean` with `GITHUB_TOKEN`, then `scripts/publish-formula.sh`, then `scripts/publish-scoop.sh`, in that order so the formula and manifest only point at assets that exist (triage's `specs/releasing.md` "remote pushes happen LAST"). A `workflow_dispatch` on `publish.yml` re-runs a failed publish for an existing tag, as triage's does.
- Decide, and record in the step's artifact with a reason each: floating `vX.Y` / `vX` tags (triage has them for its GitHub Action consumers; a CLI likely doesn't need them); least-privilege `permissions` per job; `concurrency`; pinning third-party actions to a major or a SHA (`go/security.md`); what happens when the tap push succeeds and the bucket push fails.
- Add a `release-check` job (`goreleaser check`) to `ci.yml`.
- Secrets the workflows name, and nothing else: `RELEASE_TOKEN` (contents write on `lolay/ghx`, so its tag push starts `publish.yml`), `HOMEBREW_TAP_TOKEN` (contents write on `lolay/homebrew-tap`), `SCOOP_BUCKET_TOKEN` (contents write on `lolay/scoop-bucket`). Gary creates them; the step only lists them.
- **Accept when:** `actionlint` reports nothing on all workflows; no workflow references a secret outside that list or echoes one; the publish job's order is goreleaser, formula, Scoop; `make ci` passes.

#### m2.s2 - [exec] Release docs

- `specs/releasing.md` modelled on triage's, for this repo's flow: the core rule (remote pushes last, in order), versioning (`version.txt`, lazy bump, `<release>+<sha> (<buildCode>)`), pre-flight, cutting a release (Actions, Release, Run workflow, level), re-running a failed publish, the emergency local path with the Danger targets, the three secrets with the scope each needs, and a first-release checklist: create the secrets, add a `ghx` row to the tap's and the bucket's README tables, confirm `brew install lolay/tap/ghx` and `scoop install lolay/ghx` afterwards.
- README "Install": `brew trust lolay/tap`, `brew install lolay/tap/ghx`; `scoop bucket add lolay https://github.com/lolay/scoop-bucket`, `scoop install lolay/ghx`; GitHub Releases; from source. Marked as available from the first release.
- `Makefile.md`: the Release and Danger sections and the `publish.yml` / `release.yml` rows in the CI map. `CHANGELOG.md` Unreleased: `--version`, the release pipeline.
- **Accept when:** every target, script, workflow and secret named in the docs exists under that name; `make ci` passes.
