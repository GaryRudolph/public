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

Build on the published HTTP and JSON standards; house conventions only fill the gaps they leave. Google's AIPs aren't authoritative: one is cited only where a rule matches it, and a rule that departs from them is a labeled house convention.

| Concern | Rule | Spec |
|---|---|---|
| Methods and status codes | Use methods as defined (safe, idempotent); return the most specific status code | [RFC 9110] |
| Creates | `201 Created`, a `Location` header naming the new resource, and the resource in the body | [RFC 9110] §9.3.3, §15.3.2 |
| Hidden resources | `404` when the caller may not read the resource; `403` only when it can read it but may not do this — see [Hidden Resources](#hidden-resources) | [RFC 9110] §15.5.4 |
| Optimistic concurrency | `ETag` on reads, `If-Match` on writes, `412` on mismatch; a resource with history uses its `revision` ([Resource History](#resource-history)) | [RFC 9110] §13 |
| Errors | `application/problem+json` for every error the app generates, the router's `404` and `405` included — see [Error Responses](#error-responses-rfc-9457) | [RFC 9457] |
| JSON | UTF-8, no duplicate keys; integer fields that can exceed ±2^53 (any int64) and exact decimals (money) are strings, whatever the value | [RFC 8259], [RFC 7493] (I-JSON) |
| Timestamps | UTC with `Z` (`2026-09-30T17:04:00Z`) in JSON bodies and query parameters — see [Timestamps](#timestamps) | [RFC 3339], [RFC 9557] |
| IDs | UUIDv4 (random), never time-ordered | [RFC 9562] |
| Partial updates | `PATCH` with `application/merge-patch+json` | [RFC 7396] |
| Field locations | JSON Pointer (`#/items/0/quantity`) | [RFC 6901] |
| Retiring a contract version | `Deprecation` and `Sunset` headers on every response from the old version | [RFC 9745], [RFC 8594] |
| Custom headers | A standard header if one fits; otherwise `{Product}-Name` (`Acme-Request-Id`), never `X-` — see [Custom Headers](#custom-headers) | [RFC 9110] §16.3.2.1, [RFC 6648] §3 |
| Contract description | OpenAPI document for every public API; output-only fields (`id`, `state`, `createdAt`) are `readOnly` | [OpenAPI] 3.1 or later |
| Second payload format | Protobuf, interoperating with JSON through ProtoJSON — see [Protobuf](#protobuf) | [ProtoJSON] |

Two IETF drafts cover common gaps. Follow them when you need the feature, and move to the RFC once it publishes: `Idempotency-Key` for safely retried `POST`s ([draft-ietf-httpapi-idempotency-key-header]) and the `RateLimit` / `RateLimit-Policy` response headers ([draft-ietf-httpapi-ratelimit-headers]).

**House conventions** — no standard covers these; keep them consistent:

- **Plural collections** — `/users`, not `/user`
- **Major version in the URL** — `/api/v1/users` (see [versioning.md](versioning.md))
- **lowerCamel member names** — every JSON key is lowerCamel, acronyms written as words (`photoUrl`, `accountId`; never `photoURL` or `account_id`), whatever the server language. It's ProtoJSON's default too
  - **Snake input** — a server may also accept the snake spelling (`account_id`): ProtoJSON parsers must, and Pydantic's `validate_by_name` does. Neither servers nor clients send it
  - **Only the wire is camel** — Go fields, Python attributes, SQL columns and `.proto` fields keep their own case. Swift, Kotlin and TypeScript need nothing for names without acronyms (Swift's `userID` needs a `CodingKeys` entry, [swift/code-style.md](swift/code-style.md#json-codable)); Go needs a tag per field, as it would for snake; Python needs one shared Pydantic base model (`alias_generator=to_camel`, `serialize_by_alias=True`, `validate_by_name=True`)
  - **Inside strings too** — sort and filter parameters name fields by their wire name, and an unknown name is a `422`
  - **Exceptions** — members another spec defines keep its spelling (OAuth's `access_token`, RFC 9457's members), and map keys that hold user data stay as sent
- **Enum values** — unprefixed `UPPER_SNAKE` strings (`"ACTIVE"`), case-sensitive, never integers ([Resource State](#resource-state))
- **Strict decoding** — an unknown request member, or one that's output-only, is a `422` validation problem with a `pointer` to it, never silently dropped. [AIP-203] differs: it clears output-only input without an error. ProtoJSON parsers reject unknown fields by default
- **Custom methods** — an operation that isn't create, get, list, update or delete is a colon method: `POST /books/{id}:archive`, with a lowerCamel verb, and `GET` for one that only reads ([AIP-136] matches). Go's `ServeMux` wildcards must be whole segments, so `/books/{id}:archive` doesn't parse: route `POST /books/{id}` and split the segment on its last `:`
- **`/me` is a lookup** — `GET /api/v1/me` is read-only and returns the caller's ids for that user context (`{ "data": { "accountId": "…" } }`). Every other read and write goes through `/accounts/{id}`, and nothing nests under `/me`
- **Health** — `GET /health`, outside `/api/vN` and outside auth. It answers from the process alone, never calling a dependency, and reports only the service's own build ([versioning.md](versioning.md#backend-service))
- **No fixed path segment ends in `z`** — no `/healthz` or `/readyz`: Cloud Run reserves some paths ending in `z` and recommends avoiding them all ([Cloud Run reserved paths])
- **Success envelope** — every success response except `/health`, with pagination state in `meta`:

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
| `instance` | The request id as a URN (`urn:uuid:…`): the same id as the `{Product}-Request-Id` header ([Custom Headers](#custom-headers)) and the log |

- **Every error the app generates** — the router's `404` for an unknown path and `405` for a wrong method are problems too, and a `405` keeps its `Allow` header ([RFC 9110] §15.5.6). Framework defaults aren't problems: Go's `ServeMux` writes `text/plain`, and chi writes a `text/plain` `404` and an empty `405`. Wrap the router rather than replace its handlers, which set `Allow` ([go/architecture.md](go/architecture.md#router-errors))
- **Errors from before the app** — a load balancer, CDN or proxy that fails before the app runs can't send a problem. Clients treat an error response whose body isn't `application/problem+json` as `about:blank` with that status
- **No `code` member** — `type` is the identifier; a second one drifts
- **Extension members for machine-readable data** — values a client acts on go in members the problem type defines (names of three or more letters, digits, or `_`), never in `detail`
- **Multiple errors of one type** — validation failures return one problem with an `errors` array. Each item has `detail` plus exactly one locator: `pointer` (JSON Pointer into the request body), `parameter` (query or path parameter name), or `header` (request header name). The locator names match JSON:API's
- **Different types, one problem** — when unrelated problems occur together, return the most relevant or urgent one (RFC 9457 §3). No generic "batch" type
- **`400` vs `422`** — `400` when the body can't be parsed; `422` when it parses but fails validation, including an unknown or output-only member ([strict decoding](#api-design))
- **`5xx` is opaque** — `about:blank` with a generic `detail`; never stack traces, SQL, or upstream messages. Log the full error under the `instance` id
- **Clients** (Swift, Kotlin) map `type` to a domain error and localize from `type`, not `detail`

A single problem, with an extension member:

```http
HTTP/1.1 409 Conflict
Content-Type: application/problem+json
Acme-Request-Id: 180de92f-24c9-4f35-8c8f-372da5353e24

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
Acme-Request-Id: df6c8512-3986-4bab-a568-91e65e6c62a4

{
  "type": "https://api.example.com/problems/validation-error",
  "title": "Request validation failed",
  "status": 422,
  "detail": "One or more fields are invalid",
  "instance": "urn:uuid:df6c8512-3986-4bab-a568-91e65e6c62a4",
  "errors": [
    { "detail": "must be at least 1", "pointer": "#/items/0/quantity" },
    { "detail": "must be an ISO 4217 currency code", "pointer": "#/currency" },
    { "detail": "is output-only", "pointer": "#/state" },
    { "detail": "must be true or false", "parameter": "preview" }
  ]
}
```

## Hidden Resources

A caller who may not read a resource gets `404`, the same answer as for one that doesn't exist, so its existence doesn't leak. [RFC 9110] §15.5.4 allows exactly this.

- **`401` first** — a request without valid credentials is `401` with `WWW-Authenticate` ([RFC 9110] §15.5.2), whatever it targets
- **`403` only for visible resources** — the caller can read the resource but may not do this to it
- **Authorization before other checks** — it runs first, in the service layer ([security.md](security.md#authorization)), before preconditions (`412`), conflicts (`409`) and validation that depends on the stored resource (`422`), whose answers would otherwise confirm the resource exists
- **Not shared-cacheable** — `404` is heuristically cacheable ([RFC 9110] §15.1), so a `404` that depends on the credential keeps the API's `no-store` default, or sends `Vary` on that credential ([security.md](security.md#api-security))

## Custom Headers

Use a standard header when one fits (`Authorization`, `traceparent`, `Idempotency-Key`, `RateLimit`, `Deprecation`). Otherwise [RFC 9110] §16.3.2.1 says to prefix a limited-use field with the application's name ("Foo-Desc") and never with `X-`, and [RFC 6648] §3 suggests the organization's name. Which name is a house convention:

- **Namespace** — the product name users see, shared by every service in the product (`Acme-`, not `AcmeApi-`). Use the company name only for a header that spans products
- **Spelling** — letters, digits and hyphens, Title-Case, acronyms as words (`Acme-Request-Id`). Read names case-insensitively: HTTP/2 sends them lowercase ([RFC 9113] §8.2)
- **Permanent** — a shipped header name never changes
- **Existing `X-` headers** — registered and platform headers (`X-Content-Type-Options`, `X-Forwarded-For`) are used as they are; the rule covers new names
- **Request id** — `{Product}-Request-Id: <uuid>` on every response the service generates, minted by the service and never read from the request. The problem `instance` is the same id as `urn:uuid:…`, and every log line carries it. A cached response carries the id of the request that filled the cache. Off-the-shelf middleware (chi `RequestID`, Envoy, asgi-correlation-id) uses `X-Request-Id` and trusts the inbound value, so write a small one instead
- **Correlation across services** — `traceparent` ([Trace Context]): accept it, propagate it and log its trace id. Don't echo it in responses, and don't honor a public client's sampled flag (§7.2)
- **CORS** — a browser client can read a custom response header only if `Access-Control-Expose-Headers` lists it, and send a custom request header only if the preflight's `Access-Control-Allow-Headers` lists it ([Fetch])

## Timestamps

The format is [RFC 3339]. No standard names the fields; the names are a house convention, the most common one across public APIs. Google (`createTime`), Kubernetes and Microsoft each go their own way.

- **Names** — `createdAt` and `updatedAt`, and `<verb>At` for every other instant (`expiresAt`, `lastLoginAt`, `archivedAt`)
- **UTC with `Z`** — `2026-09-30T17:04:00Z`, a string, never a local offset or an epoch number. Since [RFC 9557], `Z` means the time in UTC is known and the local offset isn't
- **JSON only** — in bodies and query parameters. Headers keep their own formats: HTTP-date for `Last-Modified`, `Retry-After` and `Sunset` ([RFC 9110] §5.6.7, [RFC 8594]), and `@<epoch seconds>` for `Deprecation` ([RFC 9745])
- **Microseconds** — truncate to microseconds on write, the precision Firestore, PostgreSQL and BigQuery store, so a value reads back as written
- **Server-set** — `createdAt` and `updatedAt` are set by the server and `readOnly`. If offline creation needs the client's time, that's a separate field (`clientCreatedAt`)
- **Sort key** — ids are random, so lists sort on `(createdAt, id)`, which keeps pagination stable when two resources share a `createdAt`
- **No `deletedAt`** — a deleted resource's `updatedAt` is the delete time ([Resource State](#resource-state)). A purge time, if shown, is `expiresAt`
- **Library defaults are wrong** — Pydantic writes naive datetimes without an offset and keeps local offsets: use `AwareDatetime` with a UTC serializer, and `timestamptz` columns. Go's `encoding/json` keeps local offsets, and `omitempty` doesn't drop a zero `time.Time`: call `.UTC().Truncate(time.Microsecond)` and use `omitzero`

## Resource State

A resource with a lifecycle exposes it as one `state` field. [AIP-216] has the same rules for the name, output-only behavior, transition methods, nesting, unprefixed values and the zero value. The spelling of the values follows ProtoJSON, so hand-written JSON and protobuf servers send the same strings.

- **`state`, never `status`** — `status` already means the HTTP status, and it's an RFC 9457 member
- **Always an enum** — a lifecycle is an enum even when it has two values today, never a boolean (`isActive`), so a later state (`SUSPENDED`, `ARCHIVED`) is a new value and not a contract break. A binary attribute that isn't a lifecycle (`isPublic`) stays a boolean
- **Output-only** — `readOnly` in OpenAPI. State changes only through `DELETE`, a transition method (`POST …/books/{id}:archive`), or the system; a `state` in a `PATCH` is a `422` ([strict decoding](#api-design))

These rules cover every enum on the wire, not only `state`:

- **Unprefixed `UPPER_SNAKE` strings** — `"ACTIVE"`, never `"active"`, `"BOOK_STATE_ACTIVE"` or `1`; [AIP-126] sets the case and [AIP-216] drops the prefix. Values are case-sensitive and never integers. No `_<digit>` segment (`TIER1`, not `TIER_1`): protobuf's 2024 naming style rejects it
- **Clients tolerate unknown values** — a value the client doesn't know decodes to a fallback (an `unknown` case), so adding a value doesn't break it. Swift needs an `unknown` case with its own `init(from:)`, or a `RawRepresentable` struct, since `Codable` throws on an unknown raw value; kotlinx needs `coerceInputValues` and a default, Moshi `EnumJsonAdapter.withUnknownFallback`, Python `_missing_`, TypeScript `| (string & {})`
- **Servers reject `*_UNSPECIFIED`** — it's never sent, and it's a `422` on input
- **Never renamed** — the value string is the contract
- **In code** — Go and TypeScript use the strings as they are. Swift needs a raw value per case (`case active = "ACTIVE"`), Kotlin names the entries `ACTIVE` or adds `@SerialName`, and Python spells the values out (`ACTIVE = "ACTIVE"`), since `StrEnum` with `auto()` yields lowercase
- **In protobuf** — the enum nests in its message, with `STATE_UNSPECIFIED = 0` as the zero the server never sets (with edition 2024's explicit presence, a zero that's set is still sent). Value names are siblings of the enum type, so they're unique across every enum nested in one message. On edition 2024, `export enum` makes it usable from other files, and buf lint needs `except: [ENUM_VALUE_PREFIX]`

```proto
edition = "2024";

message Book {
  export enum State {
    STATE_UNSPECIFIED = 0;
    ACTIVE = 1;
    ARCHIVED = 2;
    DELETED = 3;
  }

  string id = 1;
  State state = 2;
}
```

**Soft delete**, for a resource that can be restored after `DELETE`:

- **`DELETED` is a state** — `DELETE` sets `state` to `DELETED`. There's one `updatedAt` and no `deletedAt`: while the state is `DELETED`, `updatedAt` is the delete time
- **Hidden unless asked for** — a `DELETED` resource is `404`, and lists leave it out, unless the request sets `showDeleted=true`. Only an undelete method (`POST …/books/{id}:undelete`, back to `ACTIVE`) acts on it without that flag
- **`404`, not `410`** — `410 Gone` is for a condition the server knows is permanent, and while the resource can be restored it isn't ([RFC 9110] §15.5.11)
- **With history** — the delete and the undelete are both revisions ([Resource History](#resource-history))

## Protobuf

Protobuf is a supported second payload format. A resource's JSON and protobuf forms interoperate through [ProtoJSON], protobuf's own JSON mapping, and the JSON rules above match its casing, enum and int64 rules. They differ on empty values: by default ProtoJSON leaves out a field that isn't set and an empty list or map, where a hand-written server sends whatever its encoder emits: `[]`, `{}` or the zero value, unless a field is tagged to omit it (Go `omitempty` / `omitzero`). So a client reading a response treats a missing field as its empty value: `[]`, `{}`, `0` (`"0"` for an int64 or decimal), `false` or `""`. Each representation gets its own ETag ([Resource History](#resource-history)).

- **Field names** — `.proto` fields are `lower_snake_case` (edition 2024 makes anything else an error), and ProtoJSON maps them to lowerCamel, the house wire casing. Never set `json_name` or a keep-proto-names option (Go `UseProtoNames`, Python `preserving_proto_field_name`)
- **Enums** — ProtoJSON writes the value name verbatim, so a nested unprefixed enum gives `"state": "ACTIVE"` ([Resource State](#resource-state)). An encoder on an older schema writes a value it doesn't know as an integer, so the service that renders JSON always runs the newest schema
- **64-bit integers** — ProtoJSON writes `int64` and `uint64` as strings, which is the JSON row's rule already
- **Instants** — `google.protobuf.Timestamp`, which ProtoJSON writes as RFC 3339 with `Z`
- **Dates and durations** — a date is a `string` (`"2026-09-30"`) and a duration is an `int64` named `…Seconds` (`timeoutSeconds`, a string in JSON like every int64), because ProtoJSON writes `google.type.Date` as an object and `google.protobuf.Duration` as `"5400s"`
- **Unknown fields** — Connect and grpc-gateway discard unknown JSON fields by default (`DiscardUnknown`); turn that off, or strict decoding doesn't hold
- **Field names in strings** — resolve sort and filter fields through the descriptor's JSON names (Go `Fields().ByJSONName`), and give CEL filters `cel.JSONFieldNames(true)`. Updates use merge patch, so `FieldMask` paths, snake in binary and camel in JSON, stay off the JSON API

## Resource History

Opt in per resource type; most resources don't keep history. If a resource will need history, write revisions from its first release, because they can't be backfilled.

A resource with history is a **head** record plus append-only, full-snapshot **revisions**, written in the same transaction as the change. It isn't event sourcing: a revision records a state, not an intent. [AIP-162], still a draft, has the same shape (a `snapshot` plus its create time, listed newest first); everything else here is house convention.

- **Named "revisions"** — never "versions", which [versioning.md](versioning.md) uses for contracts and builds; AIP-162 avoids the word for the same reason
- **Head** — the current state, plus `revision`, `state`, `createdAt` and `updatedAt`. `createdAt` stays on the head: with random ids it's the default sort key, and retention may purge revision 1
- **Revision** — keyed `(id, revision)` and insert-only. It holds the full snapshot plus `revision`, `createdAt` (that commit's time), `actor`, `requestId` and `schemaVersion`; never per-field `{from, to}` pairs. `actor` is `{type, sub}`, the same shape as in the [activity log](#activity-log), never an email. Each `type` has one issuer per deployment, so `type` plus `sub` stands for `iss` plus `sub` ([security.md](security.md#authorization)), and a revision ops wrote can't be mistaken for one a tenant user wrote. The current state is a revision too, so `GET …/revisions/{n}` works the same for every `n`
- **Counter** — an integer per resource: 1 on create, plus one per committed change, never reused. It lives on the head, so it survives purges, and it's allocated inside the head's transaction, so it doesn't conflict with random ids. It's 32-bit (`int32` in protobuf and Go, `int` in PostgreSQL), so `revision` is a JSON number, never int64's string form
- **No-op writes** — a write that changes nothing creates no revision and keeps the ETag
- **ETag** — the revision is the ETag (`ETag: "7"`, strong), and `revision` is also a `readOnly` body field. `If-Match` uses strong comparison, so a weak tag (`W/"7"`) never matches, and a mismatch is `412` ([RFC 9110] §8.8.1, §13.1.1). Each representation gets its own tag (`"7"` for JSON, `"7-pb"` for protobuf, likewise for in-app gzip; §8.8.3.3). House leniency over §13.1.1: servers match `If-Match` on the leading integer, so a tag from one representation is accepted for a write through another. Keep anything that weakens ETags, such as CDN dynamic compression, off write paths
- **Delete** — the [soft delete](#resource-state) writes a revision with `state` `DELETED`. Its `createdAt` is the delete time and equals the head's `updatedAt`, so there's no `deletedAt`
- **Undelete and restore** — undelete (`:undelete`) is a new `ACTIVE` revision; restore is a new revision that copies snapshot `n`. History is never rewound or edited
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

- **Entry** — `occurredAt`; `actor` as `{type, sub}`, where `type` is `USER`, `OPS` or `SERVICE`; `organization`; `method` and `resource` (the operation and its target); `revision` when the write produced one; `requestId`; and `outcome` (`status`, plus the problem `type` on failure)
- **Metadata only** — no field values, request or response bodies, tokens or credentials, so the log needs no field-level encryption. No IP addresses unless there's a concrete use for them
- **Append-only sink** — the app's identity can only emit entries. A log router delivers them to append-only storage that identity can't modify, such as a retention-locked log store or a warehouse dataset it has no role on. The app never writes that storage directly: many stores can't grant insert without also granting delete, and a router keeps the app's identity out of the store entirely. GCP setup: [gcp.md](gcp.md#activity-log)
- **Retention is a policy** — actor ids are pseudonymous personal data ([GDPR] Recital 26), so the log has a written retention period, restricted read access and a stated reason to keep it

## Tenant Admin and Ops

"Admin" means the customer's admin, as it does at Google Workspace, Slack, Atlassian and Shopify. The vendor's own staff work in a separate **ops** plane. Words that name customer roles elsewhere ("super admin", "staff", "system") are never used to name an ops role, API or UI. The term "ops" is a house convention: vendors call this plane different things, and no standard names it.

- **Tenant admin is a role** — tenant roles (`OWNER`, `ADMIN`, `EDITOR`, `VIEWER`, wire enums like any other: [Resource State](#resource-state)) apply to org-scoped resources in the product API (`/organizations/{org}/…`), and tenant settings live in the product app. There's no separate admin API
- **Ops is its own service** — its own console and API at `ops.<product domain>` (`ops.example.com`, with `ops.example.net` for dev), behind IAP
- **One origin** — the console at `/`, the API at `/api/v1/…`. IAP authenticates with a session cookie, so a second host would add a second IAP session, CORS preflights that IAP blocks by default, and `fetch` calls that fail on IAP's sign-in redirect. The product splits `api.` from its app hosts only because its bearer tokens cross origins cleanly
- **The host names the plane** — ops paths follow the product's convention without repeating the plane (`/api/v1/organizations/{org}`, not `/api/v1/ops/…`). The ops `v1` versions independently of the product API
- **Roles** — one `OPS` role; split it only when a need appears. An ops role never shares a name with a tenant role
- **Audited** — every ops action writes an [activity log](#activity-log) entry with the actor's `sub` and the target organization, and ops reads of tenant data are logged too. Time-limited support sessions are optional
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
[RFC 9113]: https://www.rfc-editor.org/rfc/rfc9113
[RFC 9457]: https://www.rfc-editor.org/rfc/rfc9457
[RFC 9557]: https://www.rfc-editor.org/rfc/rfc9557
[RFC 9562]: https://www.rfc-editor.org/rfc/rfc9562
[RFC 9745]: https://www.rfc-editor.org/rfc/rfc9745
[OpenAPI]: https://spec.openapis.org/oas/
[ProtoJSON]: https://protobuf.dev/programming-guides/json/
[Trace Context]: https://www.w3.org/TR/trace-context/
[Fetch]: https://fetch.spec.whatwg.org/#http-cors-protocol
[JSON:API]: https://jsonapi.org/format/
[AIP-126]: https://google.aip.dev/126
[AIP-136]: https://google.aip.dev/136
[AIP-162]: https://google.aip.dev/162
[AIP-203]: https://google.aip.dev/203
[AIP-216]: https://google.aip.dev/216
[Cloud Run reserved paths]: https://docs.cloud.google.com/run/docs/known-issues#reserved-url-paths
[GDPR]: https://eur-lex.europa.eu/eli/reg/2016/679/oj
[draft-ietf-httpapi-idempotency-key-header]: https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/
[draft-ietf-httpapi-ratelimit-headers]: https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/
