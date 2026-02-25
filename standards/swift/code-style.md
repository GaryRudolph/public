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
    struct NOTIFICATION {
        static let AUTH_DID_CHANGE = Notification.Name("auth_did_change")
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
