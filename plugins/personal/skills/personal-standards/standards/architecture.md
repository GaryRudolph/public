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
| Optimistic concurrency | `ETag` on reads, `If-Match` on writes, `412` on mismatch; a resource with history uses its `revision` ([Resource History](#resource-history)) | [RFC 9110] §13 |
| Errors | `application/problem+json` — see [Error Responses](#error-responses-rfc-9457) | [RFC 9457] |
| JSON | UTF-8, no duplicate keys; integers beyond ±2^53 and exact decimals (money) sent as strings | [RFC 8259], [RFC 7493] (I-JSON) |
| Timestamps | UTC with `Z`: `2026-09-30T17:04:00Z` | [RFC 3339] |
| IDs | UUIDv4 (random), never time-ordered | [RFC 9562] |
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
  "detail": "Order d221cf76-2e34-4dc2-b6b0-99a61522eaef has already shipped",
  "instance": "urn:uuid:180de92f-24c9-4f35-8c8f-372da5353e24",
  "state": "SHIPPED"
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
  "instance": "urn:uuid:df6c8512-3986-4bab-a568-91e65e6c62a4",
  "errors": [
    { "detail": "must be at least 1", "pointer": "#/items/0/quantity" },
    { "detail": "must be an ISO 4217 currency code", "pointer": "#/currency" },
    { "detail": "must be true or false", "parameter": "preview" }
  ]
}
```

## Resource History

Opt in per resource type; most resources don't keep history. If a resource will need history, write revisions from its first release, because they can't be backfilled.

A resource with history is a **head** record plus append-only, full-snapshot **revisions**, written in the same transaction as the change. It isn't event sourcing: a revision records a state, not an intent. [AIP-162], still a draft, has the same shape (a `snapshot` plus its create time, listed newest first). AIPs aren't authoritative and are cited only where they match; everything else here is house convention.

- **Named "revisions"** — never "versions", which [versioning.md](versioning.md) uses for contracts and builds; AIP-162 avoids the word for the same reason
- **Head** — the current state, plus `revision`, `state`, `createdAt` and `updatedAt`. `createdAt` stays on the head: with random ids it's the default sort key, and retention may purge revision 1
- **Revision** — keyed `(id, revision)` and insert-only. It holds the full snapshot plus `revision`, `createdAt` (that commit's time), `actor`, `requestId` and `schemaVersion`; never per-field `{from, to}` pairs. `actor` is `{type, sub}`, the same shape as in the [activity log](#activity-log), never an email. Each `type` has one issuer per deployment, so `type` plus `sub` stands for `iss` plus `sub` ([security.md](security.md#authorization)), and a revision ops wrote can't be mistaken for one a tenant user wrote. The current state is a revision too, so `GET …/revisions/{n}` works the same for every `n`
- **Counter** — an integer per resource: 1 on create, plus one per committed change, never reused. It lives on the head, so it survives purges, and it's allocated inside the head's transaction, so it doesn't conflict with random ids
- **No-op writes** — a write that changes nothing creates no revision and keeps the ETag
- **ETag** — the revision is the ETag (`ETag: "7"`, strong), and `revision` is also a `readOnly` body field. `If-Match` uses strong comparison, so a weak tag (`W/"7"`) never matches, and a mismatch is `412` ([RFC 9110] §8.8.1, §13.1.1). Each representation gets its own tag (`"7"` for JSON, `"7-pb"` for protobuf, likewise for in-app gzip; §8.8.3.3). House leniency over §13.1.1: servers match `If-Match` on the leading integer, so a tag from one representation is accepted for a write through another. Keep anything that weakens ETags, such as CDN dynamic compression, off write paths
- **Delete** — `DELETE` writes a revision with `state` `DELETED`. Its `createdAt` is the delete time, so there's no `deleteTime`. A deleted resource is `404` unless the request sets `showDeleted=true`
- **Undelete and restore** — undelete is a new `ACTIVE` revision; restore is a new revision that copies snapshot `n`. History is never rewound or edited
- **Retention** — set per resource type. A purge job deletes revisions past it and never deletes the current revision. Old snapshots keep their `schemaVersion` and are upcast on read; old rows are never rewritten
- **Encryption and erasure** — revisions are encrypted exactly like the head, and unchanged fields carry their ciphertext forward. Erasure is crypto-shredding, and its window is the longest backup retention of any copy ([security.md](security.md#encryption-and-erasure))
- **Large fields** — immutable blob objects, referenced from the revision and carried forward when unchanged
- **Cross-resource history** (as-of queries, everything one actor changed) runs in the warehouse. Change-data-capture and export streams feed analytics only, never the history API: they're asynchronous and carry no actor

The API sits under the resource's own path:

| Request | Result |
|---|---|
| `GET …/books/{id}/revisions` | Revisions, newest first, paginated in `meta` |
| `GET …/books/{id}/revisions/{n}` | `{revision, createdAt, actor, snapshot}` |
| `POST …/books/{id}/revisions/{n}:restore` | Requires `If-Match` on the head; returns the head with its new `ETag` (AIP-162's `:rollback` returns the revision instead) |

- **Deleted parent** — every revisions route is `404` unless `showDeleted=true`
- **Permission** — reading history needs at least read permission on the parent. Consider a separate permission, since history shows values that were later removed
- **No diff endpoint** until a client needs one; clients compare snapshots. If one is added, choose deliberately between [RFC 7396] (the house `PATCH` format, so a diff can be replayed) and [RFC 6902] (precise for arrays and explicit nulls)

Store specifics: [Go and Firestore](go/architecture.md#resource-history--firestore), [Python and PostgreSQL](python/architecture.md#resource-history--postgresql).

## Activity Log

Optional. Add one only when an application needs that kind of logging; most won't at first. Revisions already record who changed what, so an activity log mainly covers reads, exports and actions that create no revision. It's required for the [ops plane](#tenant-admin-and-ops). No standard defines the entry, so its shape is a house convention.

- **Entry** — `time`; `actor` as `{type, sub}`, where `type` is `USER`, `OPS` or `SERVICE`; `organization`; `method` and `resource` (the operation and its target); `revision` when the write produced one; `requestId`; and `outcome` (`status`, plus the problem `type` on failure)
- **Metadata only** — no field values, request or response bodies, tokens or credentials, so the log needs no field-level encryption. No IP addresses unless there's a concrete use for them
- **Append-only sink** — the app's identity can only emit entries. A log router delivers them to append-only storage that identity can't modify, such as a retention-locked log store or a warehouse dataset it has no role on. The app never writes that storage directly: many stores can't grant insert without also granting delete, and a router keeps the app's identity out of the store entirely. GCP setup: [gcp.md](gcp.md#activity-log)
- **Retention is a policy** — actor ids are pseudonymous personal data ([GDPR] Recital 26), so the log has a written retention period, restricted read access and a stated reason to keep it

## Tenant Admin and Ops

"Admin" means the customer's admin, as it does at Google Workspace, Slack, Atlassian and Shopify. The vendor's own staff work in a separate **ops** plane. Words that name customer roles elsewhere ("super admin", "staff", "system") are never used to name an ops role, API or UI. The term "ops" is a house convention: vendors call this plane different things, and no standard names it.

- **Tenant admin is a role** — tenant roles (`owner`, `admin`, `editor`, `viewer`) apply to org-scoped resources in the product API (`/organizations/{org}/…`), and tenant settings live in the product app. There's no separate admin API
- **Ops is its own service** — its own console and API at `ops.<product domain>` (`ops.nowline.io`, with `ops.nowline.dev` for dev), behind IAP
- **One origin** — the console at `/`, the API at `/api/v1/…`. IAP authenticates with a session cookie, so a second host would add a second IAP session, CORS preflights that IAP blocks by default, and `fetch` calls that fail on IAP's sign-in redirect. The product splits `api.` from its app hosts only because its bearer tokens cross origins cleanly
- **The host names the plane** — ops paths follow the product's convention without repeating the plane (`/api/v1/organizations/{org}`, not `/api/v1/ops/…`). The ops `v1` versions independently of the product API
- **Roles** — a single `ops` role to start, split later when needed. An ops role never shares a name with a tenant role
- **Audited** — every ops action writes an [activity log](#activity-log) entry with the actor's `sub` and the target organization, and ops reads of tenant data are logged too. Time-limited support sessions come later
- **Same registrable domain** — ops cookies are host-only `__Host-` cookies, and state-changing ops requests must be same-origin, because sibling subdomains are same-site ([security.md](security.md#shared-domain-cookies))

Identity, bootstrap, revocation and break-glass: [security.md](security.md#authorization). IAP, Terraform and load-balancer setup: [gcp.md](gcp.md#ops-plane-on-iap).

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
[RFC 6902]: https://www.rfc-editor.org/rfc/rfc6902
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
[AIP-162]: https://google.aip.dev/162
[GDPR]: https://eur-lex.europa.eu/eli/reg/2016/679/oj
[draft-ietf-httpapi-idempotency-key-header]: https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/
[draft-ietf-httpapi-ratelimit-headers]: https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/
