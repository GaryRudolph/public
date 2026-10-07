# Code Style — Swift

Follows [code-style.md](../code-style.md) and [Apple Swift API Design Guidelines](https://swift.org/documentation/api-design-guidelines).

## Formatting

- **4 spaces** (Xcode default); **120-char** line length; no semicolons
- No parentheses around `if`/`guard`/`while`/`switch` conditions
- Every file ends with exactly one trailing newline
- Compile with **zero warnings**

## Naming

- **camelCase** for variables/functions; **PascalCase** for types and file names
- **SCREAMING_SNAKE_CASE** for static constants in a constants namespace; `let` with camelCase for instance constants
- Booleans read as assertions: `isEmpty`, `isEnabled`, `hasContent`
- Factory methods begin with `make`: `makeIterator()`
- Mutating/nonmutating pairs: `sort()` / `sorted()`, `append()` / `appending()`
- Protocols: nouns for "what something is", `-able`/`-ible` for capabilities
- Omit needless words: `allViews.remove(cancelButton)` not `removeElement`

## Protocol + Implementation

Define interfaces as protocols, implementations with `Impl` suffix:

```swift
protocol AccountManager: Manager {
    func getAccount(accountId: String, context: TraceContext) async throws -> Account
}

class AccountManagerImpl: AccountManager {
    private let networkManager: NetworkManager
    init(networkManager: NetworkManager) { self.networkManager = networkManager }
    // ...
}
```

## Extension File Naming

`Type+ModuleName.swift` for extensions on system/third-party types. `Type+Feature.swift` for app-internal extensions.

## File Organization with MARK

```swift
class AccountManagerImpl: AccountManager {
    // MARK: - Properties
    // MARK: - Init
    // MARK: - AccountManager
    // MARK: - Helpers
}

// MARK: - Factory Method for Production & Previews
extension AccountManagerImpl { static func make() -> AccountManagerImpl { } }
```

## Constants Namespace

```swift
struct K {
    struct APP {
        static let DEFAULT_BUNDLE_IDENTIFIER = "com.example.MyApp"
    }
    struct STYLE {
        struct COLOR {
            struct TEXT {
                static let PRIMARY = Color("text:text-primary")
            }
        }
    }
    struct API {
        static let DEFAULT_TIMEOUT_SECONDS = 30
    }
}
```

## Static Logging

Each manager/service class gets a static logger. Log entry with key parameters and exit with key results:

```swift
class InventoryManagerImpl: InventoryManager {
    private static let log = Logger.logForType(InventoryManagerImpl.self)

    func search(accountId: String, query: String) async throws -> [Item] {
        Self.log.debug("\(#function): enter accountId=\(accountId, privacy: .public)")
        // ...
        Self.log.debug("\(#function): exit items=\(items.count)")
        return items
    }

    func sync(accountId: String) async throws {
        Self.log.debug("\(#function): enter accountId=\(accountId, privacy: .public)")
        defer { Self.log.debug("\(#function): exit") }
        // ... use defer when there's no meaningful result to log
    }
}
```

## Concurrency

- `async`/`await` over completion handlers for all new code
- `@MainActor` for all UI-bound types (ViewModels, UI services)
- Custom `actor` types for shared mutable state
- Prefer value types (`struct`, `enum`) — value semantics prevent shared mutable state
- `Sendable` conformance for compile-time thread safety (Swift 6)

### Parallel async let

```swift
func load() async throws {
    async let inventory = inventoryManager.search(accountId: accountId, context: context)
    async let connections = connectionManager.getConnections(accountId: accountId, context: context)
    let inventoryResult = try await inventory
    let connectionsResult = try await connections
}
```

## Error Handling

### Domain Errors

```swift
enum NetworkError: Error {
    case nilClient
    case server(Error)
    case unknown(Error)
}
```

### AutoLocalizedError

Protocol to derive `LocalizedError` automatically from enum cases and localization keys.

### ErrorFilter

Dedicated type to suppress non-user-facing errors (e.g., cancelled requests) from UI presentation.

### mapError Pattern

Convert low-level errors to domain errors at the boundary:

```swift
func mapError(_ error: Error) -> Error {
    if let status = error as? GRPCStatus {
        if status.code == .unauthenticated { return AuthError.unauthorized(error) }
        return NetworkError.server(error)
    }
    return error
}
```

## JSON (Codable)

- **No key strategy** — Swift properties are already lowerCamel, the wire casing ([API Design](../architecture.md#api-design)). Never `.convertFromSnakeCase`, which is also slower
- **Acronym properties need `CodingKeys`** — `userID`, the API Design Guidelines' and swift-protobuf's spelling, maps to the wire's `userId` with `case userID = "userId"`. `accountId`, as spelled in these examples, needs none
- **Wire enums have explicit raw values** — `case active = "ACTIVE"`, the unprefixed `UPPER_SNAKE` wire value ([Resource State](../architecture.md#resource-state)); the case names stay lowerCamel
- **Unknown values fall back** — synthesized `Codable` throws on an unknown raw value, so a value the server adds would fail the whole response. Give each wire enum an `unknown` case, never sent, and an `init(from:)` that falls back to it; that covers arrays too
- **Unknown members are ignored** — `Codable` already skips keys it doesn't declare
- **Dates are RFC 3339, fractional seconds optional** — servers send `…:00Z` or `…:00.123456Z`. Before Foundation shipped [SF-0021](https://github.com/swiftlang/swift-foundation/blob/main/Proposals/0021-ISO8601ComponentsStyle.md)'s lenient parser, `.iso8601` rejected fractions and `ISO8601FormatStyle` required exactly what `includingFractionalSeconds` said, so decode with a strategy that tries both. `ISO8601DateFormatter` keeps only milliseconds
- **Encoding drops precision** — `.iso8601` writes whole seconds and `ISO8601FormatStyle(includingFractionalSeconds: true)` milliseconds. When an instant must round-trip exactly (a cursor, a filter bound), keep the server's string

```swift
enum OrderState: String, Codable, Sendable {
    case pending = "PENDING"
    case shipped = "SHIPPED"
    case unknown = "UNKNOWN"  // client-only; never sent

    init(from decoder: any Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = OrderState(rawValue: raw) ?? .unknown
    }
}

struct Order: Codable, Sendable {
    let id: String
    let userID: String
    let state: OrderState
    let createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id, state, createdAt
        case userID = "userId"
    }
}

extension JSONDecoder.DateDecodingStrategy {
    /// RFC 3339, with or without fractional seconds
    static let rfc3339 = custom { decoder in
        let text = try decoder.singleValueContainer().decode(String.self)
        let fractional = Date.ISO8601FormatStyle(includingFractionalSeconds: true)
        if let date = try? fractional.parse(text) { return date }
        return try Date.ISO8601FormatStyle().parse(text)
    }
}
```

## Dependency injection

- Managers and ViewModels: constructor injection only.
- Views: `EnvironmentValues` for cross-cutting dependencies; constructor argument for their own ViewModel.

See [architecture.md](./architecture.md) for the full rules and an `EnvironmentKey` example.

## Access Control

Default to `private`, then `fileprivate`, then `internal`. Don't use `public extension` for blanket access — put modifiers on individual members unless providing default protocol implementations.

## Force Unwraps

- `!` and `as!` strongly discouraged in production; require comment explaining invariant
- `try!` forbidden except for compile-time-provable safety (e.g., regex literals)
- Implicitly unwrapped optionals only for `@IBOutlet` and lifecycle-dependent properties

## Complexity Thresholds (SwiftLint)

| Metric | Warning | Error |
|---|---|---|
| Line length | 120 | 200 |
| Function body | 50 lines | 100 lines |
| Type body | 250 lines | 350 lines |
| File length | 400 lines | 1000 lines |
| Cyclomatic complexity | 10 | 20 |
| Parameter count | 5 | 8 |
