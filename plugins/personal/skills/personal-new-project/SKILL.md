---
name: personal-new-project
description: >-
  Start a new project, repo, package, or service Gary's way: choose a boring
  stack, look up the current latest stable version of every language,
  runtime, framework, SDK, build tool, and library from its registry (never
  from training data), check end-of-life dates, record the version baseline,
  and lay the project out per his architecture, testing, documentation,
  Makefile, and git standards. Use when asked to "start a new project",
  "scaffold", "bootstrap", "set up a new repo/service/package", or "create
  a new app". Not for upgrading an existing repo.
---

# personal-new-project

Run this before pinning anything. Model training data is routinely 6 to 24
months behind, so every version comes from a registry lookup made during
this session.

The canonical rules are in
[`../personal-standards/standards/architecture.md`](../personal-standards/standards/architecture.md)
under "Starting New Projects". This skill is the procedure for applying them.

## 1. Confirm it's new

Check the target directory: `git log --oneline -1`, and whether manifests
already exist (`package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`,
`Gemfile`, `build.gradle*`, `Package.swift`). If the project already has
history or pinned dependencies, stop. Existing repos follow their own
upgrade cadence (`standards/versioning.md`); say so and ask how to proceed.

## 2. Settle the stack

Prefer boring, proven *stacks* (React, Django, FastAPI, Spring, Rails, Go's
standard library, Postgres). "Boring" is about the choice, not the version.
If the request doesn't name the stack, propose one with a sentence of
reasoning each, and wait for Gary to confirm.

Then list every component that will get pinned: language and runtime,
framework, test framework, linter and formatter, build tool, key libraries,
container base image, and CI actions.

## 3. Look up current versions

```bash
python3 scripts/latest_versions.py \
    eol:python pypi:fastapi pypi:pydantic pypi:pytest pypi:ruff \
    eol:nodejs npm:react npm:vite npm:typescript \
    go:github.com/gin-gonic/gin crates:serde gem:rails \
    maven:org.springframework.boot:spring-boot github:astral-sh/uv brew:node
```

| Spec | Registry |
| --- | --- |
| `npm:<pkg>` | npm `latest` dist-tag |
| `pypi:<pkg>` | PyPI current release |
| `go:<module>` | Go module proxy `@latest` |
| `crates:<crate>` | crates.io `max_stable_version` |
| `gem:<gem>` | RubyGems latest |
| `maven:<group>:<artifact>` | Highest non-pre-release version in `maven-metadata.xml` |
| `github:<owner>/<repo>` | Latest GitHub release (excludes pre-releases) |
| `brew:<formula>` | Homebrew stable |
| `eol:<product>` | endoflife.date: recent release cycles, LTS flag, and EOL dates |

The script reports what each registry says and the URL it asked. It makes
no recommendation. For anything it can't cover, or when it prints
`error:`, use WebSearch and the vendor's release notes. Never fill the gap
from memory.

## 4. Choose and justify each pin

Using those facts:

- Pin the latest **stable** release, never a pre-release, beta, RC, or
  nightly, unless there's a documented reason (a required feature,
  framework lifecycle, ecosystem maturity). Write the reason down.
- For runtimes and frameworks, avoid a release cycle within about six
  months of its EOL date. Prefer the current LTS where the product has one.
- Check that the picks are compatible with each other (framework versus
  runtime, plugin versus build tool). Where a registry lists several
  flavors (for example `-jre` and `-android`), pick the one that fits the
  target.

Present the table of component, version, source, and any reason for
deviating, and wait for approval before scaffolding.

## 5. Scaffold to the standards

Load only what the stack needs from `../personal-standards/standards/`:

- `architecture.md` plus `<language>/architecture.md`: layering, constructor
  injection with a single composition root, error handling
- `code-style.md` plus `<language>/code-style.md`: linter and formatter
  config at the pinned versions
- `testing.md` plus `<language>/testing.md`: test layout and the first test
- `documentation.md`: `README.md` with a "Requirements" section listing the
  version baseline; specs go in `specs/`
- `makefile.md`: a self-documenting `Makefile` with the standard target
  vocabulary (the `personal-makefile` skill can audit it afterwards)
- `git.md`: `.gitignore` essentials, including `.scratch/`
- `secrets/README.md`, only if the project needs secrets

## 6. Record the baseline

Pin versions where the ecosystem expects them (`package.json`,
`pyproject.toml`, `go.mod`, `Cargo.toml`, `Gemfile`, `.tool-versions`,
the `Dockerfile` base image, CI workflow versions) and repeat the list in
the README's "Requirements" section, so future upgrades have a clear
starting point.

Don't copy a stack snapshot from an older sibling project. Re-run step 3
for every new repo.

Follow the core working agreements throughout: pause after each step,
and don't commit unless asked.
