# Versioning Standards

Pick the regime by **what you're versioning**, not by personal preference. The two regimes regularly coexist in a single project: a backend service might be at SemVer `2.4.1` (the deployable artifact, Regime 2) while exposing `/api/v1/users` (the public HTTP contract, Regime 1) and writing `.acme v3` files (the file format, Regime 1). Bump them independently — the artifact bumps every release; the contract only bumps when it breaks.

| Regime | Use for | Format |
|---|---|---|
| 1. Integer-major | URL API paths, wire/RPC formats, message schemas, file/serialization formats | `v1`, `v2`, `v3` (`vN.x` only for hotfixes) |
| 2. SemVer 2.0 | Service binaries, published packages, libraries, distributed apps | `MAJOR.MINOR.PATCH` |

## Design principles

We lean into existing public standards rather than inventing our own — [SemVer 2.0](https://semver.org/) for artifacts, integer-major URL-style versioning for contracts. Both are widely understood, broadly tooled, and well-documented; reinventing them would force every consumer to learn a private convention.

What follows is **the same practice across every platform; only the mechanics differ**:

- **Practice (constant across platforms).** One source-of-truth marketing version; lazy bump at tag time; dev builds carry `<release>+<sha>`; no pre-release suffixes; build metadata is informational only; commit-count `buildCode` for stores.
- **Mechanics (per-platform).** Each channel has hard format constraints — Apple `Info.plist` rejects `+`/`-`/letters; Google Play caps `versionCode` at 2.1×10⁹; npm strips build metadata on publish; Maven uses `-SNAPSHOT` for dev; PEP 440 has its own pre-release grammar. The per-platform sections below project the shared practice onto each channel's native fields, picking the closest legal expression. We adjust the *projection*, never the *practice*.

Regime 1 (integer-major) is *also* a deliberate non-reinvention: URL paths, wire schemas, and file formats already have universal `v1`/`v2`/`v3` conventions across the industry. Mapping these to SemVer would impose unused `MINOR`/`PATCH` axes — consumers of `/api/v1/users` only care about breaking changes, so `MAJOR` is the only useful one.

## Regime 1: Integer-major (contracts)

For things consumers code against — URL paths, RPC schemas, wire formats, file/serialization formats. Always-incrementing single integer; bumped only when the contract breaks. `MINOR`/`PATCH` exist only for emergency hotfixes to a contract (security vulnerabilities, data-loss bugs); regular non-breaking changes do not bump it.

- **Standard releases**: `v1`, `v2`, `v3`, `v4`, …
- **Hotfixes** (rare): `v2.1`, `v2.2` — next planned contract is still `v3`.

The contract version lives wherever the contract is exposed — typically a URL segment (`/api/v3/...`), a header field (`X-Schema-Version: 3`), or a literal in the file/message itself (`acme v3` declared inside an `.acme` file). It is **not** a git tag in its own right; the service binary that implements it is tagged via Regime 2.

Examples: `/api/v1/users`, the `acme v1` declaration inside an `.acme` file, a gRPC package version (`acme.users.v2`), a JSON Schema `$id` segment.

## Regime 2: SemVer 2.0

Full [Semantic Versioning](https://semver.org/) — `MAJOR.MINOR.PATCH`, tagged `vMAJOR.MINOR.PATCH`. Apply to anything that ships as a deployable or installable artifact: service binaries, Docker images, npm/PyPI/crates packages, Homebrew formulas, App Store / Play Store / VS Code Marketplace apps, libraries.

- **`MAJOR`** — breaking change to the public API/CLI/schema.
- **`MINOR`** — additive, backward-compatible feature.
- **`PATCH`** — bug fix only.
- **`0.x.y`** — minors may break; patches are bug-fix only. Call out breaking changes in the changelog.
- **No pre-release suffixes.** We do not ship `-rc.N`, `-beta.N`, or `-alpha.N` artifacts. Every tag is a stable release. Dev builds iterate on `main` as `<release>+<sha>` (build-metadata only) until the release pipeline cuts a stable tag. If a "next" channel is ever needed for external testers, revisit this rule then; until then, internal testers consume the same lazy-bump dev builds via TestFlight / Firebase / canary deployments.
- **Build metadata (`+sha`)** — informational only, per SemVer §10. Equal precedence to the version without it. Allowed in human-readable surfaces (CLI `--version`, in-app About, GitHub Release asset filenames). **Never** in a published `package.json#version`, `pyproject.toml`, `Info.plist`, an Android `versionName` you upload to Play, or any other registry/store identity field — most registries strip or reject it, and SemVer requires comparators to ignore it for ordering.

### Source of truth: last-released, lazy bump

`version.txt` (or whatever single file you read) holds the **last released** marketing version, **not** the next planned one. The release pipeline is the only thing that rewrites it, at tag time, when the maintainer picks `patch` / `minor` / `major`.

Between releases, every dev build on `main` advertises the previous release's marketing version with `+<sha>` appended (per SemVer §10) to mark it as post-release work:

- ✅ `2.4.0+abc1234` — "something past 2.4.0; bump level TBD."
- ❌ `2.5.0` — guessed at the start of the cycle, breaks if the cycle actually ships as `2.4.1` or `3.0.0`.
- ❌ `2.4.0-abc1234` — sorts *before* `2.4.0` per SemVer §11, which is reversed: our build is *past* 2.4.0, not pre-2.4.0.

This avoids guessing the bump level weeks in advance and being wrong.

### Reading a build version

Every channel — local, internal beta, store, production — shows the same shape in its runtime About display: `<release>+<sha> (<buildCode>)`. The pieces:

| Token | Meaning | Source |
|---|---|---|
| `<MAJOR>.<MINOR>.<PATCH>` (the prefix) | The marketing version this artifact is on. Identifies the v-tag line. | `version.txt`. |
| `+<sha>` | Build metadata: short HEAD SHA, pinning the artifact to a specific commit. SemVer §10 reserves `+build` for informational metadata. | CI compute-time. |
| `(<buildCode>)` | Total commit count reachable from `HEAD`; matches `CFBundleVersion` / `versionCode`. Universal join key across crash reports, store consoles, and analytics. Strictly monotonic on `main`. | `git rev-list --count HEAD`. |
| `.dirty` (trailing on metadata) | Working tree had uncommitted changes when this artifact was built. Matches `git describe --dirty`. | `git status --porcelain`. |

We do **not** repurpose `.dirty` to mean "post-release." That would conflate two genuinely distinct states — committed-but-past-tag vs. uncommitted-tree — and conflict with `git describe`'s established meaning across the wider toolchain.

**Uniform display.** The same format is used for every build, including tagged releases — the SHA is the tag's commit, the buildCode advances by 1 per commit:

```text
2.4.0+abc1234 (1469)          ← dev build past v2.4.0
2.4.1+def5678 (1470)          ← tagged release v2.4.1
└── SemVer ──┘ └buildCode┘
```

We do **not** append human-readable labels (`— dev`, `— internal beta`, `— canary`) to the version display. The `<release>` identifies the v-tag line, the `<sha>` and `<buildCode>` uniquely identify the artifact, and the relationship between consecutive `<buildCode>` values reveals cycle progression. A tester, support engineer, or developer encountering an About screen on any channel reads it the same way.

### Build code

Stores need a single monotonic integer (`CFBundleVersion`, `versionCode`). We use the count of commits in the repository's history as that integer:

```text
buildCode = git rev-list --count HEAD
```

The integer grows by one with every commit that lands on the branch being built. It has no relationship to the marketing version — that lives in the SemVer string alongside it. The pairing `<release>+<sha> (<buildCode>)` carries both: marketing version for humans, monotonic int for stores.

#### Reference encoder

```ts
// scripts/build-code.mjs
import { execFileSync } from "node:child_process";

export function buildCode(): number {
  return Number(
    execFileSync("git", ["rev-list", "--count", "HEAD"]).toString().trim(),
  );
}
```

#### CI requirement: full history

`git rev-list --count` walks the full ancestry of `HEAD`, so CI must check out with full history — not the default shallow clone:

```yaml
# GitHub Actions
- uses: actions/checkout@v4
  with:
    fetch-depth: 0          # required for git rev-list --count
```

```yaml
# GitLab CI
variables:
  GIT_DEPTH: 0
```

CircleCI / Bitbucket / Buildkite / Jenkins: run `git fetch --unshallow` after the default checkout step.

For repos under ~100k commits the cost is in the noise (1–10 seconds) compared to test/build/upload time. Set `fetch-depth: 0` once and forget it.

#### Universal uniqueness

Because `buildCode` derives entirely from git history reachable from `HEAD`:

- **The same SHA always yields the same `buildCode`.** Re-running CI, building locally, or building on another vendor produces an identical integer for any given commit. Content-addressed.
- **Different SHAs yield different `buildCode`s** along a single branch's history. The standard ships from `main`, where the count is strictly monotonic. (Two parallel feature branches at different points may differ in count from each other, but `main` is the only history that produces release builds.)
- **The `buildCode` identifies the artifact, not the channel.** The same compiled artifact promoted from a local build → TestFlight → App Store carries the same `buildCode` at every stage. A web app deployed to staging and then production from the same commit carries the same `buildCode`. A CLI dev build run on a developer's laptop and the same SHA built in CI carry the same `buildCode`. There is no separate "production buildCode" vs "dev buildCode" — there is only "the buildCode for this artifact."

Because of this, the `buildCode` is the right join key across crash reports, analytics, deployment dashboards, and store consoles. Anywhere you need to ask "which exact build is this?", the `buildCode` answers definitively — even when the marketing version, channel, or distribution method differs.

#### Cap

Play caps `versionCode` at **2,100,000,000**. At one increment per commit, that's 2.1 billion commits — effectively unreachable. Linux kernel has ~1.3M; WebKit ~300k. iOS `CFBundleVersion` has no practical cap.

There is no rollover or assertion under this scheme; the integer just grows.

#### Fallback: CI run number

If a project ever genuinely outgrows full-history clones (Linux-kernel scale, hundreds of thousands of commits with stringent CI budgets), the fallback is the CI vendor's monotonic build number:

```yaml
# GitHub Actions
env:
  BUILD_CODE: ${{ github.run_number }}
```

Tradeoffs we accept when we fall back:

- **Vendor-locked.** Migrating CI vendors resets the counter; manual offset needed at the migration point to preserve monotonicity.
- **Loses content-addressing.** Re-running CI on the same SHA produces a different run number; the same artifact ends up with two different `buildCode` values.
- **Doesn't work for local builds.** Developers running `xcodebuild` directly have no run number; substitute `0` or a placeholder.

Use this only when the full-history default is genuinely too expensive. For everything else, `git rev-list --count HEAD` wins on simplicity and idempotence.

## Version string grammars

The forms below are what we **produce**. Per-platform constraints on what each surface will **accept** are in the platform sections below.

```bnf
; Common production rules
<digit>           ::= "0" | "1" | "2" | ... | "9"
<positive-digit> ::= "1" | "2" | ... | "9"
<digits>          ::= <digit> | <digit> <digits>
<numeric-id>      ::= "0" | <positive-digit> | <positive-digit> <digits>
<hex-char>        ::= <digit> | "a" | "b" | "c" | "d" | "e" | "f"
<sha-short>       ::= 7 to 12 <hex-char>

; Marketing version — SemVer release identifier
<release>         ::= <numeric-id> "." <numeric-id> "." <numeric-id>

; Canonical build-version string (uniform across all channels — local, beta, store, production).
; SHA pins the artifact to a specific commit; the paired <build-code> sequences it.
<build-version>   ::= <release> "+" <build-meta>
<build-meta>      ::= <sha-short> [".dirty"]

; Build code (single int; goes in CFBundleVersion, versionCode)
<build-code>      ::= <numeric-id>          ; git rev-list --count HEAD

; Git tag
<release-tag>     ::= "v" <release>

; Integer-major contract version (Regime 1)
<contract-version>::= "v" <numeric-id> ["." <numeric-id>]    ; "v3", "v3.1"
```

Examples:

- `<release>` — `2.4.1`
- `<build-version>` — `2.4.0+abc1234` (dev), `2.4.1+def5678` (tagged release), `2.4.0+abc1234.dirty` (uncommitted tree)
- `<build-code>` — `1469` (total commit count reachable from HEAD)
- `<release-tag>` — `v2.4.1`
- `<contract-version>` — `v3`, `v3.1`

## Per-platform surfaces

Every platform follows the same shape: **local** (developer machine) → **beta channel** (internal testers) → **store/registry** (real users) → **runtime display** (CLI banner / in-app About / HTTP header). Each section gives the platform's BNF for accepted formats, then the values to write at each stage.

### iOS

#### Grammar

```bnf
<cfbundle-short>  ::= <numeric-id> ["." <numeric-id> ["." <numeric-id>]]
                                              ; 1–3 dotted ints; no "+", "-", letters
<cfbundle>        ::= <numeric-id> ["." <numeric-id> ["." <numeric-id>]]
                                              ; same shape; ASC requires uniqueness per <cfbundle-short>
<ios-about>       ::= <build-version> " (" <build-code> ")"
                                              ; uniform across all channels
```

#### Surfaces

| Channel | `CFBundleShortVersionString` | `CFBundleVersion` | About display |
|---|---|---|---|
| Local Xcode build | `2.4.0` | `${buildCode}` | `2.4.0+abc1234 (1469)` |
| TestFlight (internal beta) | `2.4.0` | `${buildCode}` | `2.4.0+abc1234 (1469)` |
| App Store | `2.4.1` | `${buildCode}` | `2.4.1+def5678 (1470)` |

Notes:

- `CFBundleShortVersionString` rejects `-`, `+`, and letters — only dotted ints. Lazy-bump avoids ever needing a non-numeric value here: TestFlight gets clean `2.4.0` builds throughout the cycle; the App Store gets `2.4.1` from the release tag. The `+sha` lives only in the in-app About string.
- ASC enforces strictly increasing `CFBundleVersion` per `CFBundleShortVersionString`. `git rev-list --count HEAD` satisfies this naturally — it grows by one with every commit.
- Use a separate **beta bundle ID** (`com.foo.app.beta`) so internal testers seeing `2.4.0 (...)` for weeks don't conflate it with the production `2.4.0` already shipped.
- About-screen string is generated as `BuildInfo.swift` constants at compile time; use it on the Settings → About screen and in any debug-overlay HUD.

### Android

#### Grammar

```bnf
<version-name-firebase> ::= <build-version>
                                              ; "+sha" allowed, displayed verbatim by Firebase
<version-name-play>     ::= <release>
                                              ; cosmetic-clean; no "+sha"; no pre-release suffix
<version-code>          ::= <numeric-id>      ; 1..2_100_000_000; strictly increasing per upload
<android-about>         ::= <build-version> " (" <build-code> ")"
                                              ; uniform across all channels
```

#### Surfaces

| Channel | `versionName` | `versionCode` | About display |
|---|---|---|---|
| Local debug build | `2.4.0+abc1234` | `${buildCode}` | `2.4.0+abc1234 (1469)` |
| Firebase App Distribution | `2.4.0+abc1234` | `${buildCode}` | `2.4.0+abc1234 (1469)` |
| Play Internal/Closed/Open testing | `2.4.0` | `${buildCode}` | `2.4.0+abc1234 (1469)` |
| Play Production | `2.4.1` | `${buildCode}` | `2.4.1+def5678 (1470)` |

Notes:

- Play **orders by `versionCode`**, not `versionName`. `versionName` is display-only.
- `versionCode` must strictly increase per upload to a given Play track. `git rev-list --count HEAD` satisfies this — every commit lands as a higher integer than the one before.
- Firebase App Distribution sideloads via the tester app and has no Play-imposed constraints, so it accepts the `+sha` form directly.

```kotlin
// app/build.gradle.kts (sketch)
android {
    defaultConfig {
        val release = rootProject.file("version.txt").readText().trim()  // "2.4.0"
        val code = System.getenv("BUILD_CODE")?.toInt() ?: 0             // computed in CI
        val sha = System.getenv("GIT_SHA_SHORT") ?: "local"
        val isFirebase = System.getenv("DISTRIBUTION") == "firebase"

        versionCode = code
        versionName = if (isFirebase) "$release+$sha" else release
    }
}
```

### Web app (Node.js / browser)

#### Grammar

```bnf
<web-display>        ::= <build-version>      ; uniform across local, staging, production
<x-version-header>   ::= <build-version>
<package-json-app>   ::= <release>            ; "private": true; never published to npm
<sentry-release>     ::= "<app-name>@" <release>
                                              ; build metadata stripped; pair with dist=<build-code>
```

#### Surfaces

| Channel | `package.json#version` (private app) | Footer / `/version` endpoint | `X-Version` HTTP header | Sentry release |
|---|---|---|---|---|
| Local dev server | `2.4.0` | `2.4.0+abc1234` | `2.4.0+abc1234` | `app@2.4.0`, dist `1469` |
| Staging deploy (canary) | `2.4.0` | `2.4.0+abc1234` | `2.4.0+abc1234` | `app@2.4.0`, dist `1469` |
| Production deploy | `2.4.1` | `2.4.1+def5678` | `2.4.1+def5678` | `app@2.4.1`, dist `1470` |

Notes:

- Web apps with `"private": true` aren't published to npm, so it's harmless to leave `+sha` in `package.json#version` — but `version.txt` remains the source of truth, with `package.json#version` derived during CI.
- Crash reporters take `release` and `dist` as separate fields. Don't mash them together: `release="app@2.4.1"` (clean), `dist="1470"` (the build code).

### npm (published library)

#### Grammar

```bnf
<npm-publish>     ::= <release>               ; build metadata stripped/rejected on publish
<dist-tag>        ::= "latest"
```

#### Surfaces

| Channel | `package.json#version` | Publish command | `dist-tag` |
|---|---|---|---|
| Local / on `main` | `2.4.0` (last released; `+sha` lives only in CLI `--version` and asset filenames, never in `package.json` on `main`) | — | — |
| Stable | `2.4.1` | `npm publish` | `latest` |

Notes:

- `+sha` build metadata is stripped or rejected on publish; never appears in installable artifact identity.
- For a multi-package monorepo, all packages bump in lock-step. pnpm 10 rewrites `workspace:*` to the resolved version inside each tarball.
- If a project ever needs a `next` channel for external testers, it can opt in to pre-release suffixes locally and publish with `npm publish --tag next` — but doing so deviates from this standard and should be a deliberate per-project decision.

### PyPI (published Python package)

#### Grammar

```bnf
<pypi-version>    ::= <release> ["+" <local-version>]
<local-version>   ::= <alphanum-and-dot>      ; "+local" forbidden on PyPI uploads
```

#### Surfaces

| Channel | `pyproject.toml#project.version` | Notes |
|---|---|---|
| Local install (`pip install -e .`) | `2.4.0+abc1234` | PEP 440 "local version"; works locally but **forbidden** on `twine upload`. |
| PyPI stable | `2.4.1` | |

### Rust (crates.io)

| Channel | `Cargo.toml#package.version` | Notes |
|---|---|---|
| Local / on `main` | `2.4.0` | `+sha` build metadata is parsed but stripped on publish. |
| crates.io stable | `2.4.1` | |

### Java/Kotlin (Maven Central)

| Channel | `<version>` | Notes |
|---|---|---|
| Local snapshot | `2.4.0-SNAPSHOT` | Maven's idiomatic dev marker; comparator-aware. Stays at the last-released marketing version. Not published. |
| Maven Central stable | `2.4.1` | |

### VS Code extension (Marketplace + Open VSX)

```bnf
<vscode-version>  ::= <numeric-id> "." <numeric-id> "." <numeric-id>
                                              ; integers only; no "-", no "+"
```

| Channel | `package.json#version` | Notes |
|---|---|---|
| Local development | `2.4.0` | unconstrained locally |
| Marketplace stable | `2.4.1` | Every tag ships as a stable release. Marketplace's pre-release channel requires either a SemVer pre-release suffix or odd-minor parity — we use neither (see the [no pre-release suffixes](#regime-2-semver-20) rule). Open VSX has no pre-release channel. |

### Homebrew tap + GitHub Releases

```bnf
<release-tag>        ::= "v" <release>
<gh-asset-name>      ::= <name> "-" <release> "-" <platform> "-" <arch> ["+" <build-meta>]
                       | <name> "-" <release> "." <ext>
<homebrew-version>   ::= <release>            ; integers only; formula derives from <release-tag>
```

| Channel | Identifier | Value |
|---|---|---|
| GitHub Release tag | git tag | `v2.4.1` |
| GitHub Release asset name | filename | `tool-2.4.1-darwin-arm64`, `tool-2.4.1.deb`. Optional dev artifacts may include `+abc1234`. |
| Homebrew formula | `Formula/foo.rb` `version` | `2.4.1` |
| `brew list --versions foo` | display | `foo 2.4.1` |
| `brew info foo` | display | `foo: stable 2.4.1` |
| `foo --version` (the installed binary) | display | `foo 2.4.1+def5678 (1470)` |

Notes:

- Homebrew formula `version` field accepts SemVer-shape strings, but our convention is to keep it integers-only (`MAJOR.MINOR.PATCH`) to match what's tagged. Build metadata would confuse `brew outdated` (it'd compare `2.4.1+abc1234` against `2.4.1+def5678` and not know which is newer); upgrade math needs clean SemVer.
- Asset filenames are free-form, so `+sha` is allowed there as informational. Stable Homebrew installs always pull the clean `2.4.1` asset.
- **The binary owns the rich version string.** Homebrew shows the lightweight identifier (`2.4.1`); the installed binary's own `--version` flag shows the full canonical string (`2.4.1+def5678 (1470)`). This is the standard CLI pattern (`go version`, `kubectl version`, `gh --version`, `terraform --version` all do this).
- Bake `<release>`, `<sha>`, and `<buildCode>` into the binary at compile time as constants. Per language:

  | Language | Mechanism |
  |---|---|
  | Go | `go build -ldflags "-X main.Version=$RELEASE -X main.Sha=$SHA -X main.BuildCode=$BUILD_CODE"` |
  | Rust | `build.rs` writes `src/build_info.rs` with `pub const VERSION: &str = "..."`; or use `vergen`. |
  | Node (CLI bundled with esbuild/tsup) | Define-replace at bundle time: `--define:__VERSION__='"2.4.1"' --define:__SHA__='"def5678"' --define:__BUILD_CODE__='"1470"'`. |
  | Python | Generate `_version.py` in `pyproject.toml`'s build hook (`setuptools-scm` style). |
  | Java/Kotlin | Filter resources at build time; read from `META-INF/foo-version.properties` at runtime. |

  At runtime, `foo --version` reads the constants and prints `foo $VERSION+$SHA ($BUILD_CODE)`.

### Docker / OCI image registry

```bnf
<docker-tag>      ::= <release>                              ; "2.4.1" — exact pin
                    | <release-major-minor>                  ; "2.4" — rolling pointer to latest patch
                    | <release-major>                        ; "2" — rolling pointer to latest minor
                    | "latest"                               ; rolling pointer to latest stable
                    | <release> "-" <variant>                ; "2.4.1-amd64", "2.4.1-alpine"
                    | "sha-" <sha-short>                     ; "sha-abc1234" — dev/canary
                    | "dev"                                  ; rolling pointer to latest main build
```

| Channel | Tags applied to a single digest |
|---|---|
| Local build | `sha-abc1234` |
| Canary / `main` push | `sha-abc1234`, `dev` |
| Stable | `2.4.1`, `2.4`, `2`, `latest`, `sha-abc1234` |

### Linux packages (deb / rpm / Snap / Flatpak / AppImage)

| Format | Version field | Dev | Release |
|---|---|---|---|
| deb | `Version:` (`[epoch:]upstream[-revision]`) | `2.4.0+abc1234-1` | `2.4.1-1` |
| rpm | `Version-Release` | `2.4.0-0.dev.abc1234` | `2.4.1-1` |
| Snap | `version:` (≤32 chars) | `2.4.0+abc1234` | `2.4.1` |
| Flatpak | metadata | `2.4.0+abc1234` | `2.4.1` |
| AppImage | filename | `Foo-2.4.0+abc1234-x86_64.AppImage` | `Foo-2.4.1-x86_64.AppImage` |

### Windows installers (MSI / EXE)

```bnf
<win-product>     ::= <numeric-id> "." <numeric-id> "." <numeric-id> "." <numeric-id>
                                              ; 4 dotted uint16; no "-", no "+"
```

| Channel | `FileVersion` / `ProductVersion` | Display version |
|---|---|---|
| Dev | `2.4.0.${buildCode}` | `2.4.0+abc1234` |
| Release | `2.4.1.0` | `2.4.1` |

Notes: Display version (`DisplayVersion` registry key, About dialog) can differ from the resource version. Use display for the SemVer-shape string; use resource for the 4-tuple. Each component of the 4-tuple is `uint16` — for repos with `buildCode > 65535` substitute `${buildCode} & 0xFFFF` (the resource version is for installer ordering, not artifact identity, so truncation is safe).

## Promote-to-release flow

The `cut-release` flow:

1. Maintainer dispatches the **Release** workflow with `level=patch|minor|major`.
2. CI runs `scripts/bump-version.mjs <level>`:
   - Reads `version.txt` (e.g. `2.4.0`).
   - Computes new value (`2.4.1` for patch).
   - Rewrites `version.txt` and every package's version field in lock-step.
   - Moves `## [Unreleased]` entries in `CHANGELOG.md` into `## [v2.4.1] - YYYY-MM-DD`.
3. CI commits as `release v2.4.1`, tags `v2.4.1`, pushes both with a PAT (not `GITHUB_TOKEN`, which doesn't trigger downstream workflows).
4. The tag push triggers the build/publish matrix for every platform that applies (npm, iOS, Android, Homebrew, GitHub Release, Docker, etc.).
5. After release, `version.txt` on `main` is `2.4.1`. All dev builds now advertise `2.4.1+<sha>` until the next release.

## Hotfix flow

When a released line needs a fix without dragging in newer work:

1. `git switch -c release/v2.4 v2.4.1` — branch from the tag you need to patch; push.
2. Open a PR against `release/v2.4` with the fix; label `backport main`.
3. Merge after CI. A backport workflow auto-opens a follow-up PR cherry-picking the fix onto `main`.
4. Dispatch the Release workflow from the `release/v2.4` branch (`Use workflow from: release/v2.4`) with `level=patch`. This produces `v2.4.2` from the hotfix line without pulling in newer `main` work.
5. The hotfix tag does not need to live on `main`; the published artifacts just need the right code at the right SHA.

#### Android Play caveat for hotfixes

Play enforces strictly-increasing `versionCode` **per app**, not per release line. If `main` has already shipped `v2.5.0` (e.g. `versionCode=1505`) and a hotfix branch produces `v2.4.2` whose `git rev-list --count HEAD` is `1471`, Play rejects the hotfix upload as a regression.

iOS is unaffected — ASC scopes `CFBundleVersion` monotonicity per `CFBundleShortVersionString`, so `2.4.2 (1471)` and `2.5.0 (1505)` coexist cleanly.

For Android Play hotfix uploads, override the auto-computed value with one that exceeds the currently-released production `versionCode`:

```yaml
# Hotfix release workflow, Android job
env:
  BUILD_CODE: ${{ vars.PLAY_PRODUCTION_VERSION_CODE + 1 }}
```

This is the one place we deliberately break content-addressing — the artifact built locally from the same SHA will have a different `buildCode` than the Play upload. Document the override in the release notes and move on; hotfixes are rare enough that the cost is small.
