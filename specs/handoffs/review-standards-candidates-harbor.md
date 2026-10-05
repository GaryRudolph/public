# Review: standards candidates from nowline-api m5 (harbor)

Evaluation of the 13 candidates in the harbor brief against `personal-standards` at
`c2b7c97`. Each candidate was read against the current files, fact-checked against
primary sources (RFCs, google.aip.dev, aep.dev, Firestore/Cloud Run/Firebase docs,
go.dev, OWASP ASVS), then challenged by an independent reviewer. A separate pass
looked for conflicts between candidates and for problems already in the standards.

Nothing here has been applied. This file is research, not a change.

## Headline

The brief is stale. It quotes the standards at `01139a9`, before #7 (`277eb93`)
rebuilt API Design and error responses on RFC 9457, and before #9 to #11 changed
plan execution and the runner rules. C1 is already done, and better, at HEAD. Most
of the rest is sound in intent but over-claims its sources: C2 and C3 cite Google
AIPs that say the opposite of the rule on several points, and C4's main rationale
about Firestore query locks is false. After trimming, the yield is roughly a dozen
one-line additions plus a handful of real decisions.

## Verdicts

| # | Candidate | Verdict | One line |
|---|---|---|---|
| C1 | RFC 9457 errors | Already done | #7 landed it. Every remaining difference (`code`, `requestId`, `instance` = path, 400 for validation, `/title` pointers) contradicts #7 and RFC 9457 §3.1.1/§3.1.5. Keep only "router 404/405 are problems too". |
| C2 | Resource conventions | Split | Take 201 + `Location`, `readOnly` in OpenAPI, strict unknown-field rejection as **422**. Decide casing, request-id header, 404-vs-403, `/me`. Reject slug aliases. |
| C3 | Resource state and lifecycle | Split | Take `state` not `status`, always an enum (decided). Rewrite soft delete (AIP-164 contradicts it twice). Event log mandate is your call. |
| C4 | Firestore modeling | Adopt with fixes | Five of seven rules hold. ULID conflicts with the UUID rule and hotspots; the query-lock rationale is false; 1500-byte values are truncated, not unindexed. |
| C5 | Admin bootstrap | Defer mechanism | Pull out the standards-backed parts now (no default admin, identity by `iss`+`sub`, never zero admins). The email-allowlist mechanism is n=1. |
| C6 | API hardening | Adopt parts | Take the JSON-API CSP and a logging line. Error-boundary rewrite is already covered. Vuln scan placement is a decision. |
| C7 | Go testing | Adopt with changes | Conformance suite (generic, in testing.md too), fuzz hand-written parsers of untrusted input. Per-package coverage needs exemptions and a decision. |
| C8 | Makefile | Adopt the principle | "`lint` fails on drift in what `format` rewrites" goes in makefile.md; the Go commands go in the personal-makefile Go row. Drop `docker-smoke` from makefile.md. |
| C9 | Build string on health | Adopt core | Backend services report own `<release>+<sha>` and build code. Drop HTML negotiation, the HTML parity test, bundled-tool versions. |
| C10 | Claude Code orchestrate | Decision | Rename `Task` to `Agent` now. The port is a skill change. Reject the fixed "approve, commit, push?" wording. |
| C11 | Project trailers precedence | Don't adopt | Precedence already settles it. The real issue is that the `Co-Authored-By` ban is dead letter in this repo. |
| C12 | `/health`, no `z` paths | Adopt with changes | House convention. Ban `z`-ending fixed path segments generally (Google's advice), not just health names. Liveness checks the process only. |
| C13 | `Vary: Authorization` | Adopt with changes | Set `no-store` as the API default first; make the cacheable case the exception. Cover cookie sessions too. Drop the curl runbook and the Firebase claim. |

## Decisions made

- **JSON keys are lowerCamel on the wire** (2026-10-05), under your rule that camel wins if it's less code; see `research-json-key-casing.md`.
- **C3, state is always an enum** (2026-10-05): every lifecycle state is an enum, never a boolean, so future states can be added without breaking the contract.

## Incorporate (no decision needed)

- **architecture.md, Error Responses.** One clause: errors the app or router generates (404, 405) are problems too; a 405 keeps `Allow` (RFC 9110 §15.5.6). Errors the server or CDN emits before the app runs can't be; clients treat a non-problem error body as `about:blank` with that status.
- **go/architecture.md.** Note that `net/http` ServeMux and chi send `text/plain` 404/405 by default. A custom chi 405 handler replaces the one that sets `Allow`, so wrap rather than replace.
- **architecture.md, API Design table.** `201 Created` with `Location` for a create (RFC 9110 §9.3.3, §15.3.2). `readOnly` for output-only fields in OpenAPI.
- **architecture.md, house conventions.** Request bodies are decoded strictly; an unknown or output-only member is a `422` validation problem with a `pointer`, not ignored. Label it a house convention: AIP-203 says the opposite ("must clear out any value ... must not throw an error"); ProtoJSON and Azure reject.
- **architecture.md, new Resource State.** `state`, never `status` (AIP-216; also avoids colliding with RFC 9457's `status`). State is an output-only enum; clients change it only through DELETE, a transition method, or the system. A lifecycle state is always an enum, never a boolean, even when it has two values today, so a later state (`suspended`, `archived`) is a new value and not a contract break (decided; AIP-126 backs enums over booleans). A plain binary attribute that isn't a lifecycle (`isPublic`) stays a boolean. Lowercase values are a house convention (AIP-126 says `UPPER_SNAKE_CASE`); clients must tolerate unknown values. Open: ProtoJSON emits enum values verbatim as `UPPER_SNAKE`, so lowercase values diverge from any protobuf-backed endpoint.
- **go/architecture.md, Firestore.** Document ids are opaque and never a business key (a rename can't move a document). Uniqueness is a ledger document whose id is the (encoded or hashed) key, created in the same transaction. Subcollections don't cascade on delete; purge is recursive. Index definitions live in the repo and deploy from it. Link Google's best-practices and quotas pages for the numbers instead of restating them.
- **security.md, Security Headers.** A JSON-only API sends `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` (`frame-ancestors` does not fall back to `default-src`). Keep `X-Frame-Options: DENY` as the legacy fallback. Add the same to the Go middleware, scoped to API routes if the service also serves HTML (Swagger UI).
- **security.md, logging.** Logs carry the user id and request id, never tokens, credentials or user content. Error strings and subprocess output can quote user input; treat them as user content.
- **go/security.md, Error Boundaries.** Make `writeProblem` force the generic `detail` on any 5xx, so a handler returning `&Problem{Status: 500, Detail: err.Error()}` can't leak. The prose rule already exists.
- **security.md, API Security.** API responses default to `Cache-Control: no-store`. A response a shared cache may store, at a URL that also accepts credentials, sends `Vary` on that credential (`Authorization`, or `Cookie` for cookie sessions per security.md:10), so a CDN keys anonymous and authenticated requests apart (RFC 9111 §3.5, §4.1). If the CDN won't key on it, put the credential in the CDN's cache key or don't cache that URL. Test caching through the CDN, not just the origin.
- **testing.md + go/testing.md.** One conformance suite, written once against the interface, runs on the fake in every test run and on the real adapter (emulator or container) in CI. Go idiom: `nettest.TestConn`-style `Run(t, newStore)`. Use "conformance suite" in both files ("contract test" means Pact to most people).
- **go/testing.md, Fuzzing.** Fuzz hand-written parsers and decoders of untrusted input (cursors, path segments, subprocess output); the property is at least "never panics", plus a round trip where one exists. Note that plain `go test` replays the seed corpus only.
- **makefile.md.** `lint` fails on drift in anything `format` rewrites. Put `go mod tidy -diff` (Go 1.23+) and `go mod tidy` in the personal-makefile Go row, which also needs golangci-lint (it currently says `go vet` + gofmt). Note that Swift and Node rows don't satisfy the drift rule yet.
- **versioning.md.** New "Backend service" subsection: the service reports its own `<build-version>` and build code on its health endpoint, baked in at build time (link the existing bake-in table). Only the service's own build goes on an unauthenticated endpoint; third-party and bundled-tool versions go in logs or behind auth (ASVS 5.0 13.4.6). Health responses are `no-store` so post-deploy polling sees the live build.
- **architecture.md, house conventions.** Health check at `GET /health`, outside `/api/vN` and outside auth. It answers from process state only, no dependency calls. No fixed path segment ends in `z`; Cloud Run and App Engine reserve "some paths ending with z" and Google recommends avoiding all of them. Health is exempt from the `{data, meta}` envelope.
- **plan-execution.md:613 and personal-plan-orchestrate/SKILL.md:142.** Claude Code's `Task` tool is now `Agent` (renamed in 2.1.63; `Task` is an alias).

## Needs your decision

Ranked by how much they shape the rest.

1. **Do Google AIPs count as a "widely adopted spec" (architecture.md:7)?** C2 and C3 cite them and then contradict them: AIP-203 (ignore output-only fields, don't reject), AIP-164 (`Get` returns a soft-deleted resource; `delete_time` + `purge_time`), AIP-211 (403 after authz, "or it might not exist"), AIP-122 (`users/me` aliases allowed), AIP-126 (UPPER enums). Either follow them, or strip the citations and label the rules house conventions. Recommendation: the latter, citing an AIP or AEP only where the rule matches. AEP is HTTP-native and multi-vendor, so it fits better where you do cite.
2. **JSON key casing.** Resolved under your rule (camel if it's less code): lowerCamel on the wire, acronyms as words (`photoUrl`), regardless of server language. Camel is free in Swift, Kotlin and TypeScript, equal in Go, and one base-model config in Python; snake is free only in Python. ProtoJSON and every current Connect/gateway default emit camel from `snake_case` `.proto` fields. Follow-ups: the Python example (`order_id`) switches to an `alias_generator=to_camel` base model; core.md's "snake_case or camelCase per language convention" gets "wire keys are lowerCamel". Evidence in `research-json-key-casing.md`.
3. **Request id header.** C2 mandates `X-Request-Id`; architecture.md:75 bans new `X-` headers. RFC 6648 doesn't ban existing ones, and there's no registered `Request-Id`. Recommendation: allow `X-Request-Id` as a named de facto exception; `instance` stays the body carrier. A cached response replays the origin's id, so it identifies the origin request only.
4. **Hidden resources: 404, never 403?** RFC 9110 §15.5.4 allows it, GitHub does it; AIP-211 says 403, Azure says 403 unless it leaks existence. Recommendation: adopt 404, with one central `can()` deny-by-default policy called from the service layer. Authorization must run before preconditions (412), conflicts (409) and resource-dependent validation (422), or those leak existence. Credential-dependent 404s get the C13 `Vary`/`no-store` treatment, since 404 is heuristically cacheable.
5. **Soft delete semantics.** C3 says deleted is 404 and bans `deletedAt`; AIP-164 returns the resource and wants `delete_time`. RFC 9110 §9.3.5 backs 404 after DELETE. Open holes either way: what `:undelete` restores (if `archived` and `deleted` share one enum), and whether a create can reuse a soft-deleted id. Recommendation: 404 by default, `showDeleted=true` to see them, keep `deleteTime` and `purgeTime`, single `updateTime` otherwise. With the always-enum decision, `deleted` is a `state` value and `deleteTime` only records when, which sets aside AIP-216's two-state `delete_time`-as-flag alternative.
6. **Mandatory event log from first release (C3).** Real point: history can't be backfilled. But a mandate for every service fails "solve the current problem", and per-field `{from, to}` copies PII and secrets into an immutable store that purge never reaches. Recommendation: "If a resource will need history, write it from the first release; it can't be backfilled. Keep secrets and personal data out of it."
7. **Field names `*At` vs `*Time`.** C3 uses `updatedAt`/`purgeAt` (Rails); AIP/AEP-148 use `updateTime`/`deleteTime`/`purgeTime`. The only stored timestamp in the standards uses `event_time`. Recommendation: `*Time`.
8. **Vulnerability scan placement (C6, C8).** go/security.md:250 already requires govulncheck on every PR. govulncheck fails only on called vulnerabilities, and gosec already runs inside `lint`. Against: it needs the network, results change with no code change, and findings can't be silenced. Recommendation: per-PR blocking check plus a scheduled run (both, not either); don't legislate which make target. `npm audit` has no reachability and no per-advisory ignore, so don't make it blocking on the same terms.
9. **Per-package coverage gate (C7).** Right instinct; one `total:` hides an untested package. As written it flags conformance-suite packages, `cmd/*`, generated code and integration-only packages at 0%, and your review beat would then block every wave. Recommendation: report per package as a review signal with written exemptions; not a CI gate.
10. **Firestore denormalization (C4).** "No denormalized fan-out" is a design trade-off, not a Firestore fact, and mainstream Firestore guidance leans toward selective denormalization. Recommendation: drop it; "single source of truth" already covers the principle.
11. **Ids in Firestore.** architecture.md:71 recommends UUIDv7 when time ordering matters; Firestore warns that monotonically increasing ids (and indexed sequential fields) hotspot at about 500 writes/s. Recommendation: in Firestore, auto-ids or UUIDv4 even when order matters, noted in the Go Firestore section, not in the API table.
12. **Unauthenticated build string (C9, C12).** The web standard already publishes `<release>+<sha>` in the footer and `X-Version`, but backend services publish nothing today, so C9 does widen exposure. Recommendation: accept it for the service's own build (deploy verification needs it), never third-party versions.
13. **Admin bootstrap (C5).** Recommendation: adopt now, as one-liners under a new `## Authorization`: no default admin accounts (ASVS 5.0 6.3.2); link accounts to external identity by `iss` + `sub`, never by email (OIDC Core §5.7, the nOAuth incident); never zero admins across every path that removes admin power; admin accounts require MFA via IdP policy. Defer the email-allowlist mechanism itself until a second service needs it. The brief already keeps `ADMIN_EMAILS` project-local. Note lockout recovery: an IdP-suspended last admin needs an operator break-glass.
14. **`/me` (C2).** Recommendation: reject the ban. AIP-122, GitHub, Gmail and Graph all use caller aliases.
15. **Custom methods.** Colon syntax is shared by AIP-136 and Azure, but "only for state transitions" is narrower than both (it would rule out `:cancel`, `:batchGet`). Go 1.22+ ServeMux can't route `/things/{id}:archive` (wildcards must be whole segments); one `POST /things/{id}` handler that splits on the last `:` works. Recommendation: adopt colon custom methods for anything that isn't CRUD, with the Go note.
16. **Claude Code orchestrate port (C10).** The skill says `model` is ignored per anthropics/claude-code#43869 (still open); the docs and one reviewer's test on 2.1.289 say per-call `model` works. Effort can't be set per call, so `[xdeep]` needs a plugin agent definition (`effort: max`) or stays on model-tiers. Recommendation: port it as a separate skill change with a canary that checks the subagent's `message.model`. Reject the fixed "approve, commit, push?" gate wording: on a runner the push happens before the question, and orchestrate deliberately has no per-wave human gate. "Subagents never commit" also needs a carve-out in the runner rule, since subagents load core.md and see `CLAUDE_CODE_REMOTE=true`.
17. **The `Co-Authored-By` ban (C11).** Don't apply C11; Standards Precedence already settles it. The real problem: git.md:53 bans the trailer, yet this repo's history has 31 `Co-authored-by: Claude` lines, including commits you made directly on `main` (4787426, 45af4d1) and every squash merge since #2. Options: drop the ban; keep it and enforce it (a one-clause pointer in core.md:37 reaches every harness; Claude Code's `attribution` setting doesn't reach cloud sessions, and plugins can't carry it); or replace it with a disclosure trailer such as `Assisted-by:`, which is honest on workstations where you are the author. Recommendation: decide between drop and disclosure; enforcement by prose has already failed.

## Already in the repo and contested

Found while checking the candidates. None of these were caused by them.

- **`X-` headers despite architecture.md:75.** versioning.md:28 (`X-Schema-Version`), :277 and :285 (`X-Version`); python/architecture.md:275 (`X-Token-Id`, which should be `Authorization: Bearer`, RFC 6750). The Go rate limiter (`httprate`) emits `X-RateLimit-*` instead of the `RateLimit` draft headers architecture.md:78 points to.
- **Passwords contradict NIST.** security.md:5 says "minimum 12 chars with complexity"; SP 800-63B-4 says verifiers SHALL NOT impose composition rules and single-factor passwords need 15. Same 12 in go/security.md and python/security.md.
- **"argon2id preferred" but every example uses bcrypt**; the Python example uses passlib, unreleased since 2020-10.
- **Money as a float.** go/architecture.md:188 `Total float64` against architecture.md:69 (exact decimals as strings).
- **`instance` is never populated.** No Go example sets it; Python's `ProblemError` has no field for it; go/security.md:230 logs without the request id that :240 says to log.
- **Go 429 and router errors aren't problems.** httprate's default handler and ServeMux 404/405 write `text/plain`.
- **Go decode errors.** go/security.md:129-137 maps every decode error, including type mismatches that parsed fine, to 400 "not valid JSON"; :108 says that's 422 with a pointer. Pointers are built from `fe.Field()` (leaf name only, no escaping), wrong for nested fields.
- **RFC 9110 MUSTs.** python/architecture.md returns 201 without `Location` and 401 without `WWW-Authenticate`.
- **Per-field errors can't be localized.** Clients must localize from `type` (:110) but every `errors[]` item shares one type and has only English `detail`. A per-item reason member is already allowed by :105; the Go example puts the validator tag in `detail` instead.
- **Commit practice vs git.md.** Beyond the trailer: git.md wants lowercase imperative, no type prefix; history has `docs(...):`, `fix(...):`, capitalized "Add ...".
- **Stale pins.** plan-execution.md:613 says Claude Code `Task`. go/architecture.md:5 targets Go 1.26 while the "pin latest stable" rule would say 1.27.
- **Broken link.** makefile.md:129 links `Makefile.md` to `../documentation.md`, which doesn't exist from there.
- **personal-makefile Go row** omits golangci-lint and govulncheck, contradicting go/code-style.md and go/security.md.

## Process notes on the brief

- Its adopt/adapt/discuss labels were set against `01139a9`. Following them as written would revert four #7 decisions (C1) and collide with the runner rules (C10).
- The source project now diverges from your new RFC 9457 standard in five places (`code`, `requestId`, `instance` = path, 400 validation, `/`-form pointers). Either migrate nowline-api's `internal/httpx/problem.go` or update its ADR-001 to record the deviation from the new standard.
- One PR for 13 candidates conflicts with git.md's one-feature-per-PR and gets squashed anyway. Suggested split: API and errors (C1-C3, after decision 1); security (C5, C6, C13); Go, Firestore, testing, Makefile (C4, C7, C8); versioning and health (C9, C12); process (C10, C11).
- Any `core.md` edit needs `make -C agents cursor-core-rule` before `make -C agents validate test`; the brief's gate omits it and `validate` would fail.
- C10's evidence lives in a gitignored `.scratch/` plan and can't be reviewed from here.
