# Architecture Standards

## Core Principles

- **Solve the current problem** — don't build for hypothetical futures; only abstract when it's low effort or you have 3+ concrete examples
- **Prefer boring technology** — established patterns and libraries over novel approaches
- **Separation of concerns** — business logic separate from presentation; data access separate from business logic; configuration separate from code
- **Keep things consistent** - it's better to be consistent, even if it's less than ideal, than have 5 different variants

## Starting New Projects

When scaffolding a new project, repo, package, or service, start on current versions — not whatever your training data or muscle memory suggests.

- **Check current versions before pinning** — for every language, runtime, framework, SDK, API, build tool, and library, look up the latest stable release. Use WebSearch, official release notes, and registry tools (`npm view <pkg> version`, `pip index versions <pkg>`, `gem outdated`, `cargo search`, GitHub releases, vendor changelogs). Agent training data is routinely 6–24 months stale; verify, don't guess.
- **Pin to the latest stable** — not pre-release, beta, RC, or nightly. Use a pre-release only with a documented reason (e.g., a required feature, framework lifecycle, ecosystem maturity).
- **"Boring" applies to the choice, not the version** — "prefer boring technology" means picking proven *stacks* (React, Django, FastAPI, Spring, Postgres, Rails), not stale *versions*. Pick the boring stack, then start it on its latest stable release.
- **Record the version baseline** — capture the chosen versions in the obvious place (`package.json`, `pyproject.toml`, `Gemfile`, `go.mod`, `.tool-versions`, `Dockerfile` base image, `README` "Requirements" section). Future upgrades need a clear starting point.
- **Re-check on every new repo** — versions move fast. Don't copy a stack snapshot from a six-month-old sibling project; re-verify each time.
- **Check end-of-life dates** — avoid pinning to a runtime or framework version that's within ~6 months of EOL (e.g., Node LTS schedule, Python's status page, framework support matrices).

Does not apply to existing repos — established projects follow their own upgrade cadence and version policy (see [versioning.md](versioning.md)).

## Layered Architecture

```
┌─────────────────────────────────────┐
│     Presentation Layer              │  UI, Controllers, APIs
├─────────────────────────────────────┤
│     Business Logic Layer            │  Services, Domain Logic
├─────────────────────────────────────┤
│     Data Access Layer               │  Repositories, DAOs
├─────────────────────────────────────┤
│     Infrastructure Layer            │  Database, External APIs
└─────────────────────────────────────┘
```

Each layer only depends on layers below it. Never skip layers.

## Dependency Management

### Constructor Injection + Factory Builder

All dependencies via constructor. A single factory builder (composition root) wires everything. Classes never create their own collaborators.

- Classes are **testable** — call the constructor with mocks, no framework needed
- The **factory is the only place** that knows about concrete types
- Swapping an implementation requires changing one line in the factory

### Dependency Direction

High-level modules depend on abstractions (interfaces/protocols), not concrete implementations.

## Error Handling Layers

1. **Service Layer** — throws domain-specific errors
2. **Controller Layer** — catches and transforms to HTTP responses (or UI dialogs)
3. **Global Handler** — catches unexpected errors, logs, returns safe responses

## API Design

- Use HTTP verbs correctly; plural nouns for resources (`/users`, not `/user`)
- Version in URL: `/api/v1/users`
- Consistent response format:

```json
{ "data": { }, "meta": { } }

{ "error": { "code": "VALIDATION_ERROR", "message": "...", "details": [] } }
```

## State Management

- Keep state as local as possible
- Immutable data by default
- Single source of truth
- Predictable state updates

## Language-Specific Guidelines

- **[Python](python/architecture.md)**
- **[Swift](swift/architecture.md)**
- **[Kotlin](kotlin/architecture.md)**
