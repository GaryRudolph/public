# Architecture Standards

## Core Principles

- **Solve the current problem** — don't build for hypothetical futures; only abstract when it's low effort or you have 3+ concrete examples
- **Prefer boring technology** — established patterns and libraries over novel approaches
- **Prefer published standards** — an RFC first; then a mature IETF draft or widely adopted spec (OpenAPI, JSON Schema, OAuth, SemVer); only then a house convention, labeled as one in the standard
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
2. **Controller Layer** — catches and transforms to HTTP problem responses ([Error Responses](#error-responses-rfc-9457)) or UI dialogs
3. **Global Handler** — catches unexpected errors, logs, returns an opaque `500` problem

## API Design

Build on the published HTTP and JSON standards; house conventions only fill the gaps they leave.

| Concern | Rule | Spec |
|---|---|---|
| Methods and status codes | Use methods as defined (safe, idempotent); return the most specific status code | [RFC 9110] |
| Optimistic concurrency | `ETag` on reads, `If-Match` on writes, `412` on mismatch | [RFC 9110] §13 |
| Errors | `application/problem+json` — see [Error Responses](#error-responses-rfc-9457) | [RFC 9457] |
| JSON | UTF-8, no duplicate keys; integers beyond ±2^53 and exact decimals (money) sent as strings | [RFC 8259], [RFC 7493] (I-JSON) |
| Timestamps | UTC with `Z`: `2026-09-30T17:04:00Z` | [RFC 3339] |
| IDs | UUIDs; UUIDv7 when time ordering matters | [RFC 9562] |
| Partial updates | `PATCH` with `application/merge-patch+json` | [RFC 7396] |
| Field locations | JSON Pointer (`#/items/0/quantity`) | [RFC 6901] |
| Retiring a contract version | `Deprecation` and `Sunset` headers on every response from the old version | [RFC 9745], [RFC 8594] |
| New headers | No `X-` prefix | [RFC 6648] |
| Contract description | OpenAPI document for every public API | [OpenAPI] 3.1 or later |

Two IETF drafts cover common gaps. Follow them when you need the feature, and move to the RFC once it publishes: `Idempotency-Key` for safely retried `POST`s ([draft-ietf-httpapi-idempotency-key-header]) and the `RateLimit` / `RateLimit-Policy` response headers ([draft-ietf-httpapi-ratelimit-headers]).

**House conventions** — no standard covers these; keep them consistent:

- Plural nouns for collections: `/users`, not `/user`
- Major version in the URL: `/api/v1/users` (see [versioning.md](versioning.md))
- Success envelope, with pagination state in `meta`:

```json
{ "data": { }, "meta": { } }
```

The closest published envelope is [JSON:API]. We don't adopt it: it wraps every resource in `type` / `id` / `attributes` / `relationships`, and its `errors` format isn't RFC 9457.

## Error Responses (RFC 9457)

Every error response is a Problem Details object ([RFC 9457]) sent with `Content-Type: application/problem+json`.

| Member | Rule |
|---|---|
| `type` | Absolute URI naming the problem: `https://<api-host>/problems/<kebab-slug>`. The only field clients branch on. Use `about:blank` when the status code says everything (plain `404`, `405`, `500`) |
| `title` | Short summary, identical for every occurrence of a `type`; the status phrase (`Not Found`) for `about:blank` |
| `status` | Must equal the HTTP status code |
| `detail` | Human-readable explanation of this occurrence. Clients never parse it |
| `instance` | The request id as a URN (`urn:uuid:…`), also written to the log |

- **No `code` member** — `type` is the identifier; a second one drifts
- **Extension members for machine-readable data** — values a client acts on go in members the problem type defines (names of three or more letters, digits, or `_`), never in `detail`
- **Multiple errors of one type** — validation failures return one problem with an `errors` array. Each item has `detail` plus exactly one locator: `pointer` (JSON Pointer into the request body), `parameter` (query or path parameter name), or `header` (request header name). The locator names match JSON:API's
- **Different types, one problem** — when unrelated problems occur together, return the most relevant or urgent one (RFC 9457 §3). No generic "batch" type
- **`400` vs `422`** — `400` when the body can't be parsed; `422` when it parses but fails validation
- **`5xx` is opaque** — `about:blank` with a generic `detail`; never stack traces, SQL, or upstream messages. Log the full error under the `instance` id
- **Clients** (Swift, Kotlin) map `type` to a domain error and localize from `type`, not `detail`

A single problem, with an extension member:

```http
HTTP/1.1 409 Conflict
Content-Type: application/problem+json

{
  "type": "https://api.example.com/problems/order-not-cancellable",
  "title": "Order can't be cancelled",
  "status": 409,
  "detail": "Order 0192e4c1-7c5b-7d3e-9a41-3f1d2b6c8e10 has already shipped",
  "instance": "urn:uuid:0192e4c1-8a10-7b2f-b3c4-5d6e7f8a9b0c",
  "state": "shipped"
}
```

Several validation errors in one response:

```http
HTTP/1.1 422 Unprocessable Content
Content-Type: application/problem+json

{
  "type": "https://api.example.com/problems/validation-error",
  "title": "Request validation failed",
  "status": 422,
  "detail": "One or more fields are invalid",
  "instance": "urn:uuid:0192e4c1-9b21-7c3a-8d4e-6f7a8b9c0d1e",
  "errors": [
    { "detail": "must be at least 1", "pointer": "#/items/0/quantity" },
    { "detail": "must be an ISO 4217 currency code", "pointer": "#/currency" },
    { "detail": "must be true or false", "parameter": "preview" }
  ]
}
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
- **[Go](go/architecture.md)**

[RFC 3339]: https://www.rfc-editor.org/rfc/rfc3339
[RFC 6648]: https://www.rfc-editor.org/rfc/rfc6648
[RFC 6901]: https://www.rfc-editor.org/rfc/rfc6901
[RFC 7396]: https://www.rfc-editor.org/rfc/rfc7396
[RFC 7493]: https://www.rfc-editor.org/rfc/rfc7493
[RFC 8259]: https://www.rfc-editor.org/rfc/rfc8259
[RFC 8594]: https://www.rfc-editor.org/rfc/rfc8594
[RFC 9110]: https://www.rfc-editor.org/rfc/rfc9110
[RFC 9457]: https://www.rfc-editor.org/rfc/rfc9457
[RFC 9562]: https://www.rfc-editor.org/rfc/rfc9562
[RFC 9745]: https://www.rfc-editor.org/rfc/rfc9745
[OpenAPI]: https://spec.openapis.org/oas/
[JSON:API]: https://jsonapi.org/format/
[draft-ietf-httpapi-idempotency-key-header]: https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/
[draft-ietf-httpapi-ratelimit-headers]: https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/
