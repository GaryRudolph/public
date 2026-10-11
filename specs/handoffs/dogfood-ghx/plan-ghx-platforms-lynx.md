# Plan: ghx on macOS, Linux and Windows, with CI (lynx)

Run B of the orchestrate phase 1 dogfood (`GaryRudolph/public` `specs/handoffs/dogfood-orchestrate-native.md`): Mac CLI, unattended. Second of three plans that bring `lolay/ghx` to the shape of `lolay/triage`. Starts from `main` after plan A (`plan-ghx-baseline-heron`) merged; plan C (`plan-ghx-release-finch`) starts after this plan's PR merges.

## Context

- **After plan A:** module `github.com/lolay/ghx`, binary `ghx` from `cmd/ghx/`, a standard `Makefile` (`make ci` = build, lint, test), `.go-version`, `.golangci.yml`, `.gitattributes`, `specs/testing.md`, and unit tests for `config`, `ghapi` (filter), `manifest` and `ui`. Read `specs/testing.md` and `Makefile.md` first.
- **The token in HTTPS clones:** ghx puts the token in the clone URL, so it lands in every clone's `.git/config` and in `git`'s arguments; m1.s5 hands it to `git` through the environment instead.
- **Not tested yet:** `internal/cloner` (shells out to `git`: clone, `pull --ff-only`, `status --porcelain`, `config user.*`; moves and deletes repo directories), `internal/ghapi` (go-github client built inside each function, so there's no seam for a test server), and `internal/cli`'s run flow (removed and archived repos moved to `DELETED/` and `ARCHIVED/`, or deleted).
- **The model, triage** (`lolay/triage`; on the Mac at `~/Projects/lolay/triage/triage/`): `.github/workflows/ci.yml` runs `make ci` and `make vuln` on Ubuntu and `go build ./...` plus `go test ./...` on `windows-latest`; golangci-lint is installed in CI at the version pinned in the Makefile. ghx goes one further and runs a macOS job too.

## Rules for every step

- Read Gary's standards first: `testing.md`, `go/testing.md`, `go/code-style.md`, `platform-parity.md`, `git.md`, `makefile.md`, `security.md`.
- Commit each finished step on the task branch as `m{N}.s{K} <imperative subject>` (72 characters at most, no period), a blank line, a body if useful, then `Assisted-by: Claude Code` as the last paragraph. Never `Co-authored-by`. Don't push; the orchestrator does after each wave.
- `make ci` passes at the end of every step, and so does `GOOS=windows GOARCH=amd64 go vet ./...` (it type-checks the tests for Windows too).
- Tests are hermetic: no network, no real home directory, no real GitHub. `git` on `PATH` is allowed (every CI runner has it); repos under test are local bare repos made in `t.TempDir()` and cloned by path.
- **No outward actions:** no tags, releases, PRs, GitHub settings, workflow dispatches or re-runs, or writes to any other repo. Reading CI results with `gh run list`, `gh run view` and `gh run watch` is fine. Anything else stops with `needs_info`.

## m1 - Cross-platform correctness

#### s1 - [exec] Hermetic tests for the cloner against local git repos

- A test helper that makes a bare repo with one commit on a named default branch (`git init --bare`, a seed clone, a commit, a push) under `t.TempDir()`, using `filepath` throughout and setting `user.name`, `user.email` and `init.defaultBranch` per command (`-c`), so a runner's global git config doesn't matter.
- `RepoInfo.CloneURL` set to the bare repo's path passes through `resolveURL` unchanged (only `https://` URLs get the token), so `CloneRepos` runs for real: clone, a second run that pulls a new upstream commit, a dirty working tree skipped, a wiki that doesn't exist reported as skipped, `--git-author` / `--git-email` written to the clone's config, concurrency above 1, and a cancelled context.
- `MoveRepo` and `DeleteRepo` on a real clone (its `.git/objects` hold read-only files on Windows), including a destination that already exists.
- Table tests for `resolveURL`, `resolveWikiURL` and `authenticatedHTTPS` (SSH, HTTPS, a URL without `.git`).
- **Accept when:** `go test -race ./internal/cloner/...` passes on the Mac; `cloner` is at or above 80% statement coverage; `GOOS=windows go vet ./...` passes.

#### s2 - [exec] A seam for the GitHub API and its tests

- Give `ghapi` an unexported way to point the go-github client at a base URL (one constructor both `ValidateToken` and `ListOrgRepos` use; tests set it through an `export_test.go` or an option), with no behaviour change for users.
- `httptest` tests: token validation (ok, 401, a network error), listing with pagination across two pages, the repo type filter passed through, `toRepoInfo`'s nil-safe fields, and `formatAPIError`'s messages.
- **Accept when:** `ghapi` is at or above 80% statement coverage; no test reaches `api.github.com` (run them with the network off, or check the base URL in each test).

#### s3 - [exec] End-to-end tests for the run flow

- Drive the cobra root command in-process (`newRootCmd`, args, a buffer for `ui.Out`, `t.Setenv` for `HOME`, `USERPROFILE` and `GITHUB_TOKEN`) against the `httptest` server from m1.s2 and bare repos from m1.s1: a first sync, a second sync that pulls, a repo removed upstream moved to `DELETED/`, an archived one moved to `ARCHIVED/`, `--delete` removing both, `--dry-run` changing nothing on disk, and `--include` / `--exclude`.
- Assert on the directory tree and the `.ghx.json` manifest, not on the progress bar's frames.
- **Accept when:** `internal/cli` is at or above 70% statement coverage (the rest listed in `specs/testing.md` with a reason); `make ci` passes.

#### s4 - [deep] Make every OS touchpoint correct on Windows

- Audit each place ghx meets the OS and decide, with a test where one can show it: paths (`filepath` everywhere, `filepath.Base` on user input, the manifest's names); repo names Windows can't hold as directories (`CON`, `AUX`, `NUL`, `COM1`, a trailing `.`), which today would fail mid-sync, so skip them with a clear message or document the limit; `os.Rename` of a directory onto a path just removed, and anything holding a handle open; `os.RemoveAll` on read-only git objects; finding `git` (`exec.LookPath` once, a clear error when it's missing, `git.exe` on Windows); `git status --porcelain` with CRLF output; the home directory (`USERPROFILE`); ANSI colour and the progress bar on a Windows console (enable virtual terminal processing, or turn colour off when it can't be); `os.Interrupt` and `SIGTERM`; file modes; long paths (`core.longpaths`, or document the limit).
- Fix what's wrong, behind build tags only where the standard library can't do it portably (`_windows.go` / `_unix.go` files, each with a test).
- Leave the token in the HTTPS clone URL alone: m1.s5 takes it out. Record in the step's artifact anything the audit finds that m1.s5 should know (for example how `git` is found on Windows).
- **Accept when:** each touchpoint above is fixed with a test, or recorded as correct or as a documented limit in `specs/testing.md` or the README; `GOOS=windows`, `GOOS=linux` and `GOOS=darwin` `go vet ./...` and `go build ./...` pass for amd64 and arm64; `make ci` passes.

#### s5 - [deep] Keep the token out of clone URLs and .git/config

Hardening. With the default `https` protocol, `resolveURL` and `resolveWikiURL` call `authenticatedHTTPS`, which puts the token in the URL that `processRepo` and `processWiki` hand to `runGit(…, "clone", …)`. So the token is in `git`'s arguments while the clone runs (the process list), and `git` stores it as `remote.origin.url` in every clone's and wiki's `.git/config`, where it outlives a rotated token. `--protocol ssh` clones aren't affected.

- **Hand git the token through its environment.** Clone with the plain `RepoInfo.CloneURL` (and the plain wiki URL), and give `runGit` the credential as environment config: `GIT_CONFIG_COUNT=1`, `GIT_CONFIG_KEY_0=http.<scheme>://<host>/.extraheader` (scheme and host taken from the clone URL, so the header goes to that host only), `GIT_CONFIG_VALUE_0=AUTHORIZATION: basic <base64 of x-access-token:<token>>`, appended to `os.Environ()` for the clone, pull and wiki commands only. Use this rather than `GIT_ASKPASS`: it behaves the same on macOS, Linux and Windows with no helper program (an askpass helper has to be an executable, so Windows would need a `.exe` or `.bat`, or ghx re-running itself as one), and the header is sent up front, so a user's credential helper (`osxkeychain`, Git Credential Manager on Windows) is never asked, can't prompt, and can't store the token; askpass is consulted only after those helpers. A process's environment, unlike its arguments, is readable only by its own user. `GIT_CONFIG_COUNT` needs git 2.31 or later: check the version once, next to m1.s4's `git` lookup, and fail with a clear message below it. Remove `authenticatedHTTPS` and the token parameter of `resolveURL` / `resolveWikiURL`, and update m1.s1's table tests to match.
- **Clean existing clones.** Before `pull --ff-only` in `processRepo` and `processWiki`, read `git remote get-url origin`; if it's an `https` URL with user info, `git remote set-url origin` to the same URL without it. Do the same for the clones already under `DELETED/` and `ARCHIVED/`, which no later sync touches (one pass in the run flow, skipped with `--dry-run`, which returns before cloning). Leave SSH and local-path remotes alone.
- **Failure messages.** `gitResult.Message()` becomes a `RepoResult.Detail` that `ui.PrintSummary` prints under "Failed repos". With the token gone from the URL, check whether any git output can still carry it (a user's `GIT_TRACE_CURL` with `GIT_TRACE_REDACT=0`, a `fatal:` line echoing an old origin URL during a pull), and redact the token and its base64 header value from `Message()` regardless. Check `ghapi`'s `formatAPIError` messages for the token the same way.
- **Tests** (hermetic, on m1.s1's bare repos and m1.s3's end-to-end harness): a seam on `runGit` (the command it builds, or a package-level runner) so a test can see each git invocation's arguments and environment; assert that no argument holds the token and that the header is scoped to the clone URL's host. An `https://github.com/<org>/<repo>.git` clone URL made to resolve to a local bare repo through `url.<bare path>.insteadOf` in the test's git environment, so a real clone and a real pull run; then assert that no `.git/config` under the output directory (repos, wikis, `DELETED/`, `ARCHIVED/`) contains the token, and that a clone seeded with `https://<token>@github.com/…` as its origin is rewritten to the plain URL on the next run. A failed clone whose stderr holds the token yields a `Detail` without it. A Windows-specific part goes in a `_windows_test.go` file only if the behaviour differs there.
- **Docs.** `SECURITY.md`, "How ghx handles your token": replace the "HTTPS clones embed the token" bullet with generic wording: ghx never writes credentials to disk; it gives `git` the token through `git`'s environment for the length of each command, so clone URLs and `.git/config` hold none; a run cleans the origin URLs of clones made by older versions. Adjust the SSH bullet to match. A `CHANGELOG.md` Unreleased entry in the same terms, and the README's minimum git version.
- **Accept when:** `git grep -n authenticatedHTTPS` finds nothing; the tests above pass under `go test -race ./...` and show no token in any git argument, `.git/config` or `Detail`, and an old token-bearing origin rewritten; `cloner` stays at or above 80% statement coverage; `SECURITY.md` and the CHANGELOG describe the change as hardening; `make ci` and the three `GOOS` vets pass.

## m2 - CI on three operating systems

#### s1 - [exec] CI workflow for macOS, Linux and Windows

- `.github/workflows/ci.yml` modelled on triage's: on `push` (every branch, so a task branch is checked before its PR) and `pull_request`, with a `concurrency` group per ref that cancels superseded runs; `permissions: contents: read`; `actions/checkout` and `actions/setup-go` (`go-version-file: .go-version`, module cache) at their current major versions, looked up now.
- Jobs: Linux `go mod verify`, golangci-lint installed at the Makefile's pinned version, `make ci`, `make vuln`; macOS `make ci` (same lint install); Windows `go build ./...`, `go vet ./...`, `go test ./...` (no `-race`: it needs cgo there), under `shell: bash`. Each job shows its OS in its name.
- Lint the workflow with `actionlint` (installed, or `go run github.com/rhysd/actionlint/cmd/actionlint@latest`).
- **Accept when:** `actionlint` reports nothing; the golangci-lint version in `ci.yml` equals `GOLANGCI_LINT_VERSION` in the Makefile; `make ci` passes locally.

#### s2 - [fast] Document the CI map

- `Makefile.md`: fill the "CI map" (each workflow job and the make target or command it runs). README: a CI badge for `ci.yml` on `main`. `CONTRIBUTING.md`: CI runs on macOS, Linux and Windows; Windows runs without `-race`.
- **Accept when:** the CI map names every job in `ci.yml`; the badge URL points at `lolay/ghx`'s `ci.yml`.

#### s3 - [deep] Read this branch's CI run and fix what fails

- The orchestrator pushed this branch after m2.s1-m2.s2. Find the `ci` run for this branch's head (`gh run list --branch <branch> --workflow ci.yml`), wait for it (`gh run watch <id>`), and read each failed job's log (`gh run view <id> --log-failed`).
- Fix each failure at its cause (most likely Windows: path separators, CRLF in fixtures, file locking, `bash` vs `pwsh`), with the fix tested locally where it can be and cross-compiled where it can't. If every job passed, make an empty commit for this step whose body records the run URL and each job's result.
- If the run never starts (Actions disabled, workflow rejected) or `gh` can't read it, stop with `needs_info` and say what you saw. Don't dispatch or re-run workflows.
- **Accept when:** every failed job in that run is fixed or explained in the step's artifact with its log line; the artifact names the run URL and each job's result; `make ci` and the three `GOOS` vets pass. The next run, on the orchestrator's push, is the check of record; Gary sees it on the PR.
