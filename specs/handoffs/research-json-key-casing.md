# Research: JSON key casing (snake_case vs lowerCamel)

Question: use `order_id` or `orderId` on the wire? Your rule: if camelCase means less code across Swift, Kotlin, Go, Python (and web TypeScript), use it; if every stack converts cheaply, snake_case is fine. Also: what does protobuf do to the choice if an API serves both JSON and protobuf?

Method: the industry survey counted keys in each vendor's official OpenAPI or discovery spec. The language behavior is from programs run on current releases (Go 1.27.1, Swift 6.4 on Linux, Pydantic 2.13.5 + FastAPI 0.142.2, kotlinx.serialization 1.11.0, Moshi 1.15.2, Jackson 2.22.3/3.2.3, Gson 2.14.0, TS 5.9, protobuf-go 1.36.12, Python protobuf 7.36.2, protoc 36.2). An independent pass then re-ran each program and re-checked each source.

## Answer

Use lowerCamel on the wire (`orderId`, `photoUrl`), acronyms written as words. By your own test it's less code: it's free in Swift, Kotlin and TypeScript, costs the same as snake in Go, and costs one base-model config in Python. Protobuf strengthens the case. Every current ProtoJSON encoder and gateway emits lowerCamel by default, while `.proto` field names must stay `snake_case`. So you keep writing `order_id` in `.proto` files, Python models and SQL, and `orderId` is only what goes over the wire. That split is exactly how Google does it.

## Industry: split, with a pattern

No RFC or W3C standard picks a casing. OpenAPI 3.2 is silent, and the IETF's own JSON formats go both ways: OAuth/OIDC use snake (`access_token`, `email_verified`), while ACME, JMAP and SCIM use camel.

- **Style guides lean camel:** Google JSON Style Guide ("Property names must be camel-cased"), Microsoft Graph and Azure ("DO use camel case for all JSON field names. Do not upper-case acronyms"), JSON:API recommendations, Kubernetes, Smithy (AWS), TypeSpec, Apollo GraphQL.
- **Snake style guides:** Zalando ("MUST property names must be snake_case"), Heroku, and **AEP since 2025-07-30** (commit `4f8a958`, "make snake_case ubiquitous": "Case transformation was going to continue to be a pain point"). AEP is the strongest published argument for snake, and it's recent.
- **Popular developer REST APIs lean snake:** Stripe (1570/0), GitHub REST, Slack, X v2, Square, PayPal, Plaid, Spotify, DigitalOcean, Cloudflare (mostly), OpenAI, Anthropic, Auth0.
- **Platform and enterprise APIs lean camel:** Google Cloud, Gemini, the new Google Places (Legacy Places was snake), Microsoft Graph, Azure ARM, Kubernetes, Jira, Okta, Apple's App Store Server API (`bundleId`, `transactionId`), and almost every GraphQL API (GitHub, Shopify). Shopify's current API is GraphQL-only for new apps, so it's camel now.
- **AWS** is inconsistent: older JSON services use PascalCase, newer REST services use camel.

The pattern: snake follows Rails, Django and Python dicts serialized straight to JSON; camel follows Java, C#, JS and protobuf. The snake vendors absorb the cost by generating SDKs. In typed languages the generated code maps names, and JS callers simply write `max_tokens`.

## Cost per stack

Idiomatic property names assumed: Go `UserID`, Swift `accountId` (your standard's style), Kotlin and TS `userId`, Python `user_id`.

| Stack | snake wire | camel wire | Notes |
|---|---|---|---|
| Go (encoding/json v1, and v2, GA in 1.27) | one tag per field | one tag per field | Same either way. Neither version has a naming strategy. v1 silently drops a `user_id` key it can't match. |
| Python (Pydantic v2 + FastAPI) | zero | one shared base model: `alias_generator=to_camel`, `serialize_by_alias=True`, `validate_by_name=True` | pyright rejects `M(userId=...)` and accepts `M(user_id=...)`, which strict alias mode fails at runtime. So in practice you need `validate_by_name`, and FastAPI then accepts both spellings. FastAPI already serializes by alias. |
| Swift (Codable) | key strategy on every encoder and decoder | zero (for names without acronyms) | Snake decoding is about 3x slower and encoding about 2x (Linux microbenchmark; Apple documents "a noticeable performance cost"). `photo_url` decodes to `photoUrl`, never `photoURL`. Acronym properties need `CodingKeys` under either casing. Apple's swift-openapi-generator keeps `user_id` as the Swift name unless you set `idiomatic`. |
| Kotlin (kotlinx, Jackson, Gson, Moshi) | one line in kotlinx (`JsonNamingStrategy.SnakeCase`: experimental in 1.11, stable in 1.12.0-RC), Jackson, Gson; one annotation per field in Moshi (it has no strategy) | zero in all four | Gson writes `userID` as `user_i_d`. Moshi, Gson and Jackson 3 silently ignore keys they don't recognize. |
| TypeScript (web) | snake names in your TS code, or a conversion layer (`camelcase-keys`), which also rewrites map keys inside user data | zero | openapi-typescript keeps wire names; openapi-generator's typescript-fetch generates mappers. |
| OpenAPI codegen | maps automatically for Swift, Kotlin, Go, Python, typescript-fetch | names match | Generated Go and Swift use `UserId`/`userId`, not `UserID`/`userID`. |

Summary: snake is zero-config only in Python. Camel is zero-config in Swift, Kotlin and TS, and a wash in Go. Every stack *can* convert, but the conversions are global settings with real costs: Swift performance, Python type-checker friction, Moshi annotating every field, Gson mangling acronyms, and TS map-key rewriting.

## Protobuf

- **Field names in `.proto` are `lower_snake_case`.** That's the protobuf style guide, buf lint `FIELD_LOWER_SNAKE_CASE`, and AIP-140. Edition 2024 makes it a compiler error: `Field name orderId should be lower_snake_case`.
- **ProtoJSON maps them to lowerCamel:** "Message field names are mapped to lowerCamelCase to be used as JSON object keys." Parsers "are required to accept both the converted lowerCamelCase name and the proto field name." There are opt-outs: Go `UseProtoNames`, Python `preserving_proto_field_name`, Java `preservingProtoFieldNames()`, swift-protobuf `preserveProtoFieldNames`, protobuf-es `useProtoFieldName`, connect-swift `preserveProtobufFieldNames`.
- **Framework defaults are camel:** connect-go, connect-es, connect-swift, connect-kotlin and grpc-gateway v2. Twirp defaults to snake, but its last release was 2022-10.
- **Binary protobuf carries field numbers, not names**, so casing only matters for JSON. The exception is `FieldMask` paths, which are strings: `order_id` in binary, `orderId` in JSON.
- **Generated identifiers come out idiomatic whichever JSON you choose:** Go `OrderId`, Kotlin/Java `orderId`/`getOrderId()`, swift-protobuf `orderID` (it upper-cases id/url/http), Python `order_id`, protobuf-es `orderId`.

What snake JSON costs on a dual-format API:
- Every server and client needs the opt-out flag.
- protobuf-es typed JSON only exists for camel.
- connect-go, connect-es and grpc-gateway set `DiscardUnknown`, so a component left on defaults or a misspelled key is dropped silently rather than rejected.
- Android usually runs the protobuf Lite runtime, which has no ProtoJSON, so an Android JSON client falls back to kotlinx or Moshi without the accept-both-spellings safety net.

Camel JSON costs nothing on any of these.

ProtoJSON also fixes more of the JSON shape than casing:
- int64 values are strings (already your rule in architecture.md).
- Zero values are omitted by default.
- Enum values are emitted verbatim as `UPPER_SNAKE` (`SHIPPED`, or `ORDER_STATUS_SHIPPED` for a top-level enum with the style-guide prefix).

That last point conflicts with C3's lowercase enum values if protobuf is a real prospect.

Google mixes spellings in places, and it costs them. AIP-160 filters and AIP-134 path variables use snake field names, and the Pub/Sub push payload carries both `messageId` and `message_id`.

## Exceptions to keep

Members defined by another spec keep that spec's spelling: OAuth/OIDC claims (`access_token`, `email_verified`) and RFC 9457 members (single words already). Map keys holding user data aren't field names; leave them as sent.

## Sources

protobuf.dev JSON mapping and style guide; google.aip.dev 140, 160, 134; aep.dev/140 and aep-dev/aeps commit 4f8a958; google.github.io/styleguide/jsoncguide.html; microsoft/api-guidelines (Azure, Graph); jsonapi.org/recommendations; Zalando RESTful API Guidelines rule 118; kubernetes api-conventions; smithy.io style guide; go.dev/doc/go1.27 and pkg.go.dev/encoding/json/v2; pydantic v2.13.5 `config.py`; fastapi `routing.py`; swift-foundation JSONDecoder/JSONEncoder; kotlinx.serialization JsonNamingStrategy (v1.11.0, v1.12.0-RC changelog); square/moshi README; gson FieldNamingPolicy; jackson-databind DeserializationFeature; connectrpc codecs; grpc-gateway marshaler registry; twirp server_options.go; swift-protobuf NamingUtils.swift; vendor OpenAPI specs (Stripe, GitHub, X, Slack, Twilio, Square, Plaid, Microsoft Graph, ARM, Kubernetes, OpenAI, Cloudflare, DigitalOcean).
