# Allowlist Scout — Reference

Taxonomy, harness token formats, and safety caveats for the allowlist scout
skill and its supporting scripts (`scan.py`, `render.py`). This file is the
single source of truth for classification rules. Both the agerpoint and personal
copies are byte-identical.

Contents:

1. Access / Intent Classification (propose, never-propose, unclassified)
2. Stack Detection Rules
3. Harness Token Formats
4. Prefix-Matching Safety Caveats
5. Project Tool-Use Preference Is Informational
6. Coverage Model

---

## 1. Access / Intent Classification

Every detected command is classified by **what it accesses or does** — the
class name is the meaning. Classification is judged on the command's own access
merits, regardless of any project style preference for one build tool over
another (see § Project tool-use preference below).

### Propose classes (safe to auto-run)

| Class | Meaning | Examples |
|---|---|---|
| **Inspect** | Reads state only, no side effects — **including read-only remote access** | `git status`, `git fetch`, `git remote -v`, `make help`, `swift package describe`, `xcodebuild -list`, `gh pr view`, `kubectl get`, `databricks … list`, `terraform plan`, `terraform fmt -check`, `cargo fmt --check`, `go vet ./…`, `dotnet format --verify-no-changes` |
| **Build & test** | Compiles, tests, lints, formats (check mode), or produces a **local** artifact — no remote distribution | `make build`, `make test`, `make lint`, `swift build`, `swift test`, `xcodebuild build`, `xcodebuild test`, `go build ./…`, `go test ./…`, `cargo build`, `cargo test`, `cargo clippy`, `pytest`, `ruff check`, `mypy`, `dotnet build`, `dotnet test`, `./gradlew test`, **`make archive`**, **`make sign`** |

**Read-only remote access is Inspect, not Remote Write.** Fetching refs,
listing resources, reading a pipeline status, or pulling metadata from a remote
API are all read-only. Only *writing to or mutating* a remote is Remote Write.

**Local artifact production is Build & test.** `make archive` and `make sign`
produce local `.xcarchive` / signed binary artifacts with no distribution
step — they are Build & test. The boundary is distribution: `make notarize`
round-trips to Apple's notary service; `make testflight` / `make appstore`
push a release — those are Remote Write.

### Never-propose classes

| Class | Meaning | Examples |
|---|---|---|
| **Remote Write** | Writes to or mutates a remote / external service: pushes, deploys, publishes, distributes, or applies remote changes | `git push`, `make testflight`, `make appstore`, `make notarize`, `make deploy`, `make release`, `make publish-*`, `npm publish`, `pnpm publish`, `firebase deploy`, `terraform apply`, `kubectl apply`, `helm install/upgrade`, `docker push`, `twine upload`, `cargo publish`, `rsync`/`scp` to a server, `gh release create`, `aws s3 cp/sync`, `gcloud … deploy`, `xcrun notarytool`, `fastlane pilot/deliver`, `curl` sending data (`-G`/`--get`, `-d`, `--data*`, `-F`, `-T`), `wget --method`/`--post-*`/`--body-*` |
| **Sensitive** | Touches secrets, credentials, or security material: decrypts/exposes keys or tokens, reads a keychain/keystore | `*decrypt*`, `sops -d`, `gpg -d`, `ansible-vault decrypt`, `security find-*`, `vault kv get`, `print-secret`, `unseal`, `.env.enc` access, `op read`, `op run`, `op inject` |
| **Destructive** | Irreversible or privileged: removes files unconditionally, formats storage, requires root, performs a global install, or passes a flag that writes any path or runs any program (below) | `rm -rf`, `dd if=`, `mkfs`, `sudo *`, `git reset --hard`, `git clean -fd`, `make init` (clones or installs), `make setup`, `make bootstrap`, `git log --output=<path>`, `rg --pre <cmd>`, `git fetch --upload-pack=<cmd>` |
| **Long-running** | Interactive or never-returns: would block or hang an agent indefinitely | `make dev`, `make serve`, `make watch`, `make start`, `next dev`, `ng serve`, `nodemon`, `webpack-dev-server`, `vite` (dev mode), `jekyll serve`, `mkdocs serve`, `tail -f` |
| **Unclassified** | `scan.py`'s heuristics could not confidently assign a class | *(see § Unclassified below)* |

**Flags that make a command Destructive.** A command that passes one of these
flags is never proposed, as Build & test or Inspect or anything else, whatever
its name or tool says. The flag is caught in the command text and in the
target's own recipe or script body: a `package.json` script named `lint` that
runs `rg --pre x` is caught. What that body calls is not followed: a make
prerequisite, a `$(MAKE)` call, npm's `pre<name>` hook, or a script the recipe
runs (r1.f14), and `scan.py` reads only a script's first 60 lines.

| Flag | Why |
|---|---|
| `--output`, `--output-directory` | writes any path (`git log`, `git diff`, `git format-patch`) |
| `--pre` | runs any program over each file (`rg --pre cat`) |
| `--upload-pack`, `--exec` | runs any program on the remote end (`git fetch`, `git ls-remote`, `git clone`); git's abbreviations `--upload-p`, `--upload-pa` and `--upload-pac` count |

Whole flags only, as `--flag value` or `--flag=value`: `--output-format`,
`--prefix`, `--pre-release` and `--exec-path` do not match, and neither does
`--output` followed by a format word (`--output json`, `--output=jsonpath=...`)
under kubectl, aws, az, gcloud, helm, oc or doctl, which use it for formats.
Under any other command, git included (`--output=json` writes a file named
`json`), `--output` counts. Short forms such
as `git format-patch -o` or `sort -o` are not caught.

**Security-scanning tools are Inspect, not Sensitive.** `bandit`, `pip-audit`,
`trivy`, `semgrep` and similar static analysis / dependency audit tools are
read-only — they report vulnerabilities without exposing secrets — and class
as Inspect.

### Unclassified (fail-closed fallback)

When `scan.py` cannot confidently assign a class it marks the command
**Unclassified** and emits supporting evidence (the Makefile recipe body, the
`package.json` script value, or the first 60 lines of the script file) so the
agent can perform a **deeper evaluation**:

1. Read the command's actual definition (recipe body, script value, file
   contents) and reason about what it accesses.
2. If it resolves to **Inspect** or **Build & test** → treat it as proposable
   (with the usual repo-by-repo confirmation).
3. If it resolves to a never-propose class → omit it with that reason.
4. If it is genuinely indeterminate after the deeper pass → it remains
   Unclassified, is omitted (fail-closed), and is surfaced for the user to
   classify by hand.

Unclassified commands are **never** written to a denylist. They are listed in
the `.scratch` report as "not proposed — needs agent deep-eval".

---

## 2. Stack Detection Rules

`scan.py` scans the following files/markers per repo:

| Stack | Detection file(s) | Commands extracted |
|---|---|---|
| **make** | `Makefile` / `makefile` | All plain-word non-pattern targets (`make <target>`) with recipe body |
| **node** | `package.json` (root + `packages/*`, `apps/*`) | `scripts` keys; package manager inferred from lock file (`pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, else npm) |
| **python** | `pyproject.toml`, `requirements*.txt`, `setup.cfg`, `tests/`, `test/` | `pytest`, `ruff check`, `mypy`, `pyright`, `black --check`, `isort --check`, `uv lock --check`; `[project.scripts]` entrypoints → Unclassified |
| **go** | `go.mod` | `go build ./…`, `go test ./…`, `go vet ./…` |
| **rust** | `Cargo.toml` | `cargo build`, `cargo test`, `cargo clippy`, `cargo fmt --check` |
| **dotnet** | `*.sln`, `*.csproj` | `dotnet build`, `dotnet test`, `dotnet format --verify-no-changes` |
| **swift** | `Package.swift` | `swift build`, `swift test`, `swift package describe` |
| **swift** | `*.xcodeproj` / `*.xcworkspace` | `xcodebuild -list`, `xcodebuild build`, `xcodebuild test` |
| **gradle** | `build.gradle*`, `settings.gradle*` | `./gradlew tasks/test/build/check` (uses `gradle` if no `gradlew`) |
| **terraform** | `*.tf` (any depth) | `terraform validate`, `terraform plan`, `terraform fmt -check` |
| **scripts** | `scripts/`, `bin/`, `tools/` — `.mjs/.cjs/.js/.ts/.py/.sh/.bash/.rb` files | `<runner> <rel-path>`; body from first 60 lines for classification |

Directories always skipped during enumeration and scanning:
`node_modules`, `.build`, `build`, `checkouts`, `vendor`, `external`, `Pods`,
`DerivedData`, `dist`, `target`, `out`, `.git`, `.venv`, `venv`,
`__pycache__`, `.gradle`, `.idea`, `.tox`, `coverage`.

---

## 3. Harness Token Formats

The four first-class harness targets and the token format each uses:

| Harness | File | Array / key | Token format |
|---|---|---|---|
| **Cursor IDE** | `<repo>/.cursor/permissions.json` | `terminalAllowlist` | Raw prefix string: `"make test"` |
| **Cursor CLI** | `<repo>/.cursor/cli.json` | `permissions.allow` | `"Shell(<base>:<args>)"` for a multi-word segment, args literal (`Shell(make:test)`); no token for a one-word segment, or one containing `*` or `?` or a colon in its first word |
| **Claude Code** | `<repo>/.claude/settings.json` | `permissions.allow` | `"Bash(<cmd>)"`, the exact command; no token for a segment containing `*` |
| **Gemini** | `<repo>/.gemini/policies/<name>.toml` | additive `[[rule]]` blocks | `toolName = "run_shell_command"`, `commandPrefix = "<segment>"`, `decision = "allow"`, `priority = 100` |

**Cursor CLI rule.** Cursor's permissions docs define `Shell(commandBase)`
(the command's first token, any arguments: `Shell(git)` allows every `git`
subcommand) and the `command:args` form, whose args part is a glob
(`Shell(curl:*)` is `curl` with anything). A `command:args` rule with no glob
character in args names one command line, so `render.py` writes
`Shell(make:test)` for `make test` and never `Shell(make:*)`, which would
also grant `make release`. The docs state the glob rule but never show an
exact `command:args` example, so this relies on a glob without a wildcard
matching only itself. A segment containing `*` or `?`, or whose first word
contains a colon, can't be written exactly, so the Cursor CLI gets no rule
for it and `render.py` says so. A one-word segment gets no rule either:
Cursor reads `Shell(<word>)` as the command with any arguments, so
`Shell(rg)` would also allow `rg --pre <prog>`.

**Claude Code rule.** `render.py` writes `Bash(<cmd>)`, which Claude Code
matches as that exact command, never the prefix `Bash(<cmd>:*)`: `Bash(git
log:*)` would also allow `git log --output=<path>`, and `Bash(make test:*)`
would allow `make test x --eval=...`. A segment holding a `*` gets no rule.
The agent allowlist installer renders allows the same way in both tools
(r1.f1, the Owner's call of 2026-11-23).
`scan.py` reads `Shell(cmd:args)` back as covering only `cmd args`, and
`Shell(cmd:*)`, `Bash(cmd:*)` or `Bash(cmd *)` as the prefix `cmd`, and
`Bash(cmd)` with no wildcard as covering only `cmd`, as Claude Code reads it. This keeps § 4 rule 2:
no entry subsumes a command the scout would never propose.

**A bare entry covers nothing.** Neither Cursor CLI nor Claude Code reads an
unwrapped string such as `"make test"` in `permissions.allow`; the agent
allowlist installer wrote them that way before r1.f1. `scan.py` reads one in
either file as covering no command, so the scout proposes the wrapped rule
for it. Cursor IDE's `terminalAllowlist` and Gemini's `commandPrefix` are raw
strings by design and still count.

All writes are **union-only**: `render.py` adds missing allow entries and never
removes anything, never writes a `deny` / `ask_user` / `confirmationRequired`
rule.

**Gemini caveats:**
- Target is the **latest Policy Engine** (`[[rule]]` blocks in project-tier
  `.toml` files). The older `tools.allowed` / `run_shell_command(<prefix>)`
  auto-accept mechanism is deprecated and is not a write target.
- `render.py` **never sets `policyPaths`** in `.gemini/settings.json`. Setting
  `policyPaths` *replaces* the user's global `~/.gemini/policies/` directory
  (a destructive side-effect). We only append additive project-tier `.toml`
  allow rules.
- Project-tier policies require a *trusted folder*; on builds without
  project-policy support the file is ignored harmlessly.

---

## 4. Prefix-Matching Safety Caveats

Most harness entries are prefix rules: an entry `X` covers any command whose
full string starts with `X` (followed by a space, or exact match). The Cursor
CLI's `Shell(<base>:<args>)` with literal args is the exception: it names one
command line (§ 3), so it covers nothing longer.

For a prefix entry, **a short prefix subsumes longer commands**. For example:
- Allowlisting `make` (as `Bash(make:*)`, a Cursor IDE `make` entry, or
  `Shell(make:*)`) also grants `make release` and `make deploy` (Remote
  Write). Allowlisting `make test` as a prefix also grants `make test` with any
  arguments and, where a harness matches raw string prefixes, `make testflight`
  (Remote Write).
- Allowlisting `swift` covers `swift package generate-xcodeproj`, but also
  `swift run` (Long-running in some contexts).

**Rules for safe entries:**
1. Use the **most specific segment** that covers only safe variants. Prefer
   `make test` over `make` when only `make test` is needed.
2. Never propose a prefix that subsumes a Remote Write / Sensitive /
   Destructive / Long-running command. `scan.py` and the agent deep-eval step
   flag these.
3. When a **broad existing entry** already covers a candidate (e.g. a global
   `make` entry covers a proposed `make test`), the candidate is treated as
   *covered* for that harness and is **not proposed** — but the report records
   `"suppressed by broad prefix '<entry>' in <harness>"` so you can see why
   and tighten the broad entry if desired.

---

## 5. Project Tool-Use Preference Is Informational

If a repo's `AGENTS.md` or `.cursor/rules` says "use `make`, not `xcodebuild`",
that is a **style preference** for the agent's default workflow — it does not
gate the access classification. The scout still evaluates the raw-tool command
(`xcodebuild -list`, `xcodebuild build`) on its own access merits and proposes
it if it is Inspect / Build & test. The proposal may annotate the repo's
preferred interface, but a safe command is never suppressed on style grounds.

---

## 6. Coverage Model

The existing harness allowlist files (global + per-repo, all supported
harnesses) are the **single source of truth**. No new metadata file is ever
created.

**Global files** (paths overridable via env vars):

| Harness | Global file |
|---|---|
| Cursor IDE | `$CURSOR_DATA_HOME/permissions.json` (default `~/.cursor/permissions.json`) |
| Cursor CLI | `$CURSOR_DATA_HOME/cli-config.json` (default `~/.cursor/cli-config.json`) |
| Claude Code | `<dir>/settings.json` for each existing dir in `$CLAUDE_CONFIG_DIRS`, plus the session's `$CLAUDE_CONFIG_DIR` (else `~/.claude`) (see below) |
| Gemini | `$GEMINI_DATA_HOME/policies/*.toml` (default `~/.gemini/policies/*.toml`) |

**Claude Code config dirs.** Claude Code sessions can run from several config
dirs (`CLAUDE_CONFIG_DIR` set by a shell function or launcher). The scout
checks every dir in `CLAUDE_CONFIG_DIRS` (colon-separated absolute paths, the
same list the installer manages; export it in the shell) that exists on this
machine, plus the running session's own dir (`CLAUDE_CONFIG_DIR`, else
`~/.claude`), so a session outside the list still has its own allowlist
counted. A command counts as covered globally only when **every** one of those
dirs' `permissions.allow` covers it (intersection): a per-repo
`.claude/settings.json` applies whichever dir a session runs under, so
proposing what one dir lacks is safe, while counting it covered would leave
sessions under that dir prompting. A coverage note says "broad" only when
every dir matched broadly. The JSON's `global_allowlists.claude` gives
`source` (`CLAUDE_CONFIG_DIRS` or `session`), `session_dir`, per dir `path`,
`exists` and `count`, and `missing_dirs` (listed, not on this machine, not
counted). `CLAUDE_DATA_HOME` is no longer read.

**Per-repo files** (relative to the repo root):

| Harness | Per-repo file |
|---|---|
| Cursor IDE | `.cursor/permissions.json` |
| Cursor CLI | `.cursor/cli.json` |
| Claude Code | `.claude/settings.json` |
| Gemini | `.gemini/policies/*.toml` |

**Grouping:**
- **Group 1** — missing from every harness: propose adding to all harnesses'
  per-repo files.
- **Group 2** — partial coverage (drift): already present in some harnesses but
  not others; propose adding only to the harnesses that lack it, and show which
  harnesses already have it.
- Fully covered everywhere → not shown.

**Global-promotion candidates:** commands recurring across ≥ 2 repos (or
universally safe) are flagged separately and offered for global promotion (a
copy-paste bullet list for a bok agent to add to the meta-source, never written
by the scout itself) or for per-repo addition instead.
