# Research: AEP's snake_case switch, AEP's authority, and enum values for JSON/protobuf interop

Follow-up to `research-json-key-casing.md`, now that protobuf is planned as a second payload format and JSON/protobuf interop is a goal. Four research tracks, each re-checked by an independent verifier. The verifiers re-ran the code (protoc 35.1 and 36.2, protobuf-go 1.36.12, Python protobuf 7.36.2, protobuf-es 2.16.0, buf 1.73.0, cel-go 0.32.0, connect-go 1.21.0, grpc-gateway 2.31.0) and re-read the threads in aep-dev.

## Why AEP switched to snake_case

**The trigger.** Issue aep-dev/aeps#259 (2025-01-09, Yusuke Tsutsumi): CEL filter strings name fields by their proto (snake) names, but ProtoJSON hands JSON clients camel names. So "the filter syntax will be different, depending on whether you are using protobuf or JSON", which breaks a JSON frontend passing a filter straight to a proto backend.

**The state before.** AEP-140 said proto fields are snake and "Field definitions in OAS schemas **must** use `camelCase` names". That rule was added in 2024-07 by Roblox's maintainer and is not in Google's AIP-140. AEP's own tools disagreed with each other: aepc's generated OpenAPI used snake, the same build's grpc-gateway swagger used camel, and the running gateway answered in camel.

**The change.** Dan Hudlow's draft PR #297 (2025-05) was superseded by Tsutsumi's #309, merged 2025-07-30 with one approval after an offline discussion. A promised blog post was never written. The whole rationale is: "Case transformation was going to continue to be a pain point, and snake_case was never clearly non-idiomatic for JSON. Better to consolidate behind a single case convention." Supporting comments from Discussion #320:
- "all languages generally support snake_case variables"
- Google's Alex Stephen: "It's enough of a convention that libraries like Pydantic rely on snake_case"

Nobody objected to snake JSON. The only dissent was about URL paths, which stayed kebab-case.

**What followed:**
- The editions mechanism (AEP-300) merged 17 minutes later, so snake_case is frozen in the aep-2026 edition until 2028 at the earliest.
- AEP-127 now says to put a snake `json_name` on every field. That reverses Google's AIP-127 ("should not use `json_name`").
- aep-lib-go adds `json_name` everywhere, and aepc's gateway sets `UseProtoNames`.

**The cleanup is unfinished:**
- At least eight AEPs still contain camel names. AEP-132 says "The `string nextPageToken` field **must** be included".
- aep-lib-ts still generates `nextPageToken`.
- AEP-140's "tools may support lowerCamelCase" sentence is cut off mid-clause.
- There is no changelog entry.

**The strongest version of their argument.** A field name appears in many places besides JSON keys: filter and `order_by` strings, field-mask values, query parameters, path variables, error paths, Terraform attributes. Protobuf already requires snake, and JSON has no standard. So one spelling removes every translation step.

**Why it's weaker for this stack:**
1. **CEL, the original reason, is now solved.** cel-go `cel.JSONFieldNames(true)` shipped in v0.28.0 (2026-04), eight months after the switch, so CEL can use camel names. cel-cpp and cel-java have equivalent options, though each accepts only one spelling.
2. **"Snake everywhere" isn't achievable on stock ProtoJSON.** A `FieldMask` in JSON is always camel, even with `UseProtoNames` or a snake `json_name`, and snake mask strings are rejected (`invalid path: "display_name"`). AEP sidesteps this by using JSON Merge Patch for updates.
3. **Forcing snake with `json_name` removes ProtoJSON's tolerance.** Normally parsers accept both spellings. With `json_name` they don't, and under Connect and grpc-gateway (`DiscardUnknown: true`) camel input is silently dropped: `{"displayName":"Dune"}` is stored as `{"display_name":""}`.
4. **The clients pay.** Swift needs a key strategy, Kotlin/Moshi needs per-field annotations, TypeScript needs snake in code or a conversion layer.
5. **AEP's only listed adopter doesn't follow the rule.** Roblox publishes camelCase JSON with camel CEL filters ("Field names in filters use camelCase") on its Open Cloud v2 API, which is exactly the combination chosen here.

**What remains true under camel:** field names inside string values (filters, `order_by`, mask values, error paths) need server-side mapping. Google's own front end leaks `page_size` in errors, and some Google endpoints silently ignore an `order_by` they can't resolve. The fix is server-owned and small:
- Every string reference to a field uses the JSON (camel) name.
- The server resolves it through the descriptor (`Fields().ByJSONName`).
- An unknown name is a `400`/`422`, never ignored.
- CEL environments use `JSONFieldNames(true)`.

Updates stay on merge-patch, so field masks stay off the JSON surface.

Verdict: the camelCase decision stands.

## How authoritative AEP is

| Signal | Finding |
|---|---|
| Origin | Started at Google as aip.dev (2020) for organization-agnostic AIPs. A CNCF Sandbox application in 2023 was declined. Forked and renamed AEP in 2023-10. The CNCF aspiration was removed from the charter in 2025-10 ("long-term home… still TBD"). No foundation. |
| Governance | Steering committee of at least five people from at least five organizations, membership by invitation. Nine maintainers: GM, Google, Rubrik, Microsoft, Roblox, Buf, Algoric, two unaffiliated. In practice two people (Tsutsumi at GM, Stephen at Google) wrote 34 of the 49 commits in the last 12 months; four maintainers had none. Meetings and minutes may be private. |
| Maturity | First stable edition aep-2026 (tag 2025-11-20), frozen, with a two-year cadence. 55 of 58 AEPs approved, 3 reviewing. Activity is falling: 102 commits in 2024, 96 in 2025, 11 so far in 2026. Tooling is v0.x and mostly one author. |
| Adoption | ADOPTERS.md lists one adopter, Roblox, as a private fork (unchanged since 2023), and Roblox's public API doesn't follow AEP-140. One small independent conforming project (DCM) was found. About 81 GitHub stars, against about 1.7k for Google's AIPs. Google's AIP repo never mentions AEP. |
| Internal consistency | AEP-126's proto and OAS samples would put different enum strings on the wire. AEP-132 contradicts AEP-140. Process rules are loosely applied: only 14 of 58 AEPs have the changelog AEP-1 requires. |

On your ladder (RFC, then a mature draft or widely adopted spec, then house convention), AEP is a **house convention from a small, well-intentioned group**. It is not a widely adopted spec. It is still worth citing as prior art, because it is the only guide that treats protobuf and OpenAPI as equal peers, which fits your plan. For comparison:
- Google's AIPs carry far more practical weight, since every Google API follows them, but they are still one company's house convention.
- For the interop question itself, the governing spec is ProtoJSON (protobuf.dev).

## Enum values for interop

**What ProtoJSON does.** "The name of the enum value as specified in proto is used. Parsers accept both enum names and integer values." The JSON string *is* the proto value name, case-sensitive. Lowercase can't be had cleanly: STYLE2024 naming enforcement and buf both require UPPER_SNAKE value names. Edition 2026 adds a real per-value JSON name, `[(pb.enumvalue.json).string = "..."]`, supported in Python, Java, C#, C++ and protobuf-es 2.16, but **not in Go**: protobuf-go 1.36.12 says "use of edition EDITION_2026 not yet supported", and main still tops out at 2024. Released swift-protobuf can't generate Edition 2026 either. So it isn't usable for a Go or Connect stack today.

**Recommendation: unprefixed UPPER_SNAKE strings on the wire, `"state": "ACTIVE"`.** The rules, by layer:

- **Wire contract**
  - JSON enum values are unprefixed `UPPER_SNAKE_CASE` strings, case-sensitive, never integers.
  - Label it a house convention, citing ProtoJSON, AIP-126 and AIP-216/AEP-216 ("State enum values **should not** be prefixed with the enum name, except for the default value `STATE_UNSPECIFIED`").
  - No `_<digit>` segments (`TIER1`, not `TIER_1`; STYLE2024 rejects the latter).
- **Protobuf schema**
  - Nest the enum in its resource message. The zero value is `STATE_UNSPECIFIED` and is never set by the server; under edition 2024's explicit presence, an explicitly set zero is emitted.
  - Value names must be unique within the message (protoc treats enum values as siblings of their type). This is why Cloud Run's `Condition.State` ended up as `CONDITION_PENDING`.
  - On edition 2024, mark it `export enum` to use it across files.
  - buf: `except: [ENUM_VALUE_PREFIX]`. Google's api-linter has no prefix rule.
- **Later migration**
  - Once Go and Swift support Edition 2026, the proto side can move to top-level prefixed names (`BOOK_STATE_ACTIVE [(pb.enumvalue.json).string = "ACTIVE"]`), which is where protobuf's style guide and Edition 2026's STRICT visibility point, without changing the wire.

**The competing view, and why not.** protobuf.dev's style guide ("Prefer top-level enums with prefixed values") and buf STANDARD lead to `"BOOK_STATE_ACTIVE"` on the wire. Both conventions interoperate equally. The difference is permanence:
- The wire string is the contract and is very hard to change.
- Proto identifiers can be re-spelled later behind the Edition 2026 JSON name.

Choosing unprefixed now keeps the clean wire and leaves the proto layout free. Choosing prefixed now locks the prefix onto the wire. Unprefixed also matches what Google's APIs actually send: Spanner `READY`, Pub/Sub `ACTIVE`, GKE `RUNNING`.

**Adding a value is breaking for strict JSON clients.**
- Strict ProtoJSON parsers reject an unknown enum string. Connect and grpc-gateway (`DiscardUnknown`) silently turn it into `STATE_UNSPECIFIED`, and drop it from repeated fields.
- A renderer on an older schema emits the integer (`{"state":7}`).
- protobuf.dev: adding values is safe only if "Emit enum values as integers" is set on all clients.

So the always-an-enum rule needs companions:
- Clients decode unknown values to a fallback (Swift: an `unknown` case or a RawRepresentable struct, since `Codable` throws on an unknown raw value; kotlinx: `coerceInputValues` plus a default; Moshi: `EnumJsonAdapter.withUnknownFallback`; Python: `_missing_`; TS: `| (string & {})`).
- Servers reject `*_UNSPECIFIED` on input.
- The service rendering JSON always runs the newest schema.
- Enum value names are never renamed.

**Per-language cost of UPPER_SNAKE values in hand-written models:**
- **Go and TypeScript:** free.
- **Swift:** an explicit raw value per case (`case active = "ACTIVE"`).
- **Kotlin:** name the entries `ACTIVE` (Kotlin's conventions allow UPPER_SNAKE enum constants) or add `@SerialName` per entry. Your kotlin/code-style.md says PascalCase entries, so wire enums need an exception. Android runs the protobuf Lite runtime, which has no ProtoJSON, so Kotlin clients parse with kotlinx or Moshi.
- **Python:** explicit values (`ACTIVE = "ACTIVE"`). python/code-style.md prescribes `StrEnum` with `auto()`, which yields lowercase; wire enums need an exception.

## Sources

aep-dev/aeps issue #259, PRs #195, #297, #309, #311, #331, #332, #366, Discussion #320, commits 4f8a958 and 17b4010, MAINTAINERS.md, ADOPTERS.md, AEP-1, AEP-6, AEP-126, AEP-127, AEP-132, AEP-140, AEP-216, AEP-300; aep.dev blog (history, aep-2026 release) and FAQ; cncf/sandbox#30; aep-lib-go 46c6aa2; aepc 6485221 and 6fa792d; google.aip.dev 126, 127, 140, 160, 216; protobuf.dev JSON mapping, style guide, editions features, symbol visibility, 2026-07-13 news; protocolbuffers/protobuf v36.0 notes; protobuf-go releases; swift-protobuf #2111 and #2128; protobuf-es 2.16.0; cel-go v0.28.0 `JSONFieldNames`; cel-cpp `use_json_field_names`; connect-go `codec.go`; grpc-gateway `marshaler_registry.go` and `query.go`; Roblox Open Cloud patterns; Google discovery docs (Spanner, Compute, Pub/Sub, Cloud Run v2); kotlinlang coding conventions.
