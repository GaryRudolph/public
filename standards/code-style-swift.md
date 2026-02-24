# Code Style — Swift

Follows general principles in [code-style.md](code-style.md).

## Naming Conventions

- Use **camelCase** for variables and functions: `userAccountBalance`, `calculateTotalPrice`
- Use **PascalCase** for classes, structs, enums, and protocols: `UserRepository`
- Use **PascalCase** for file names: `UserService.swift`
- Use **SCREAMING_SNAKE_CASE** for static constants inside a constants namespace
- Instance-level constants use `let` with camelCase

```swift
// Good
let userAccountBalance = 1000
func calculateTotalPrice(items: [Item]) { }
class UserRepository { }
let maxRetryAttempts = 3

// Avoid
let uab = 1000
func calc(i: [Any]) { }
```

## Protocol + Implementation Naming

Define interfaces as protocols and implementations as classes with an `Impl` suffix. This enables testability via protocol substitution:

```swift
protocol AccountManager: Manager {
    func getAccount(accountId: String, context: TraceContext) async throws -> Account
    func removeAccount(accountId: String, context: TraceContext) async throws
}

class AccountManagerImpl: AccountManager {
    private let networkManager: NetworkManager

    init(networkManager: NetworkManager) {
        self.networkManager = networkManager
    }

    func getAccount(accountId: String, context: TraceContext) async throws -> Account {
        // Implementation
    }

    func removeAccount(accountId: String, context: TraceContext) async throws {
        // Implementation
    }
}
```

## Extension File Naming

Name extension files as `Type+ModuleName.swift` when extending system or third-party types. This groups all extensions from a module together and avoids collisions across packages:

```swift
// File: Logger+LolayFundamenta.swift
public extension Logger {
    static func logForType<T>(_ type: T.Type, bundle: Bundle = Bundle.main) -> Logger {
        let subsystem = bundle.bundleIdentifier ?? bundle.bundlePath
        return Logger(subsystem: subsystem, category: String(describing: type))
    }
}

// File: String+LolayFundamenta.swift
public extension String {
    static func randomString(length: Int = 16) -> String { /* ... */ }
    var isEmail: Bool { /* ... */ }
}

// File: URL+LolayFundamenta.swift
public extension URL {
    var queryParameters: [String: String]? { /* ... */ }
}
```

For app-internal extensions that don't belong to a reusable module, use `Type+Feature.swift` or `Type+Helpers.swift`.

## File Organization with MARK Comments

Use `// MARK: -` to organize files into logical sections:

```swift
class AccountManagerImpl: AccountManager {

    // MARK: - Properties

    private static let log = Logger.logForType(AccountManagerImpl.self)
    private let networkManager: NetworkManager

    // MARK: - Init

    init(networkManager: NetworkManager) {
        self.networkManager = networkManager
    }

    // MARK: - AccountManager

    func getAccount(accountId: String, context: TraceContext) async throws -> Account {
        // ...
    }

    // MARK: - Helpers

    private func mapResponse(_ remote: AccountRemoteEntity) -> Account {
        // ...
    }
}

// MARK: - Factory Method for Production & Previews

extension AccountManagerImpl {
    static func make() -> AccountManagerImpl {
        // ...
    }
}
```

## Constants Namespace

Use a top-level struct with nested structs and `SCREAMING_SNAKE_CASE` for app-wide constants:

```swift
struct K {
    struct APP {
        static let DEFAULT_BUNDLE_IDENTIFIER = "com.example.MyApp"
    }

    struct URL {
        static let FAQ: Foundation.URL = {
            Foundation.URL(string: "https://example.com/faq") ?? { preconditionFailure("Invalid URL string.") }()
        }()
    }

    struct STYLE {
        struct COLOR {
            struct TEXT {
                static let PRIMARY = Color("text:text-primary")
            }
        }
        struct TYPOGRAPHY {
            static let HEADLINE1 = Font.custom("Inter-Regular", fixedSize: 40.0).weight(.semibold)
        }
    }

    struct NOTIFICATION {
        static let AUTH_DID_CHANGE = Notification.Name("auth_did_change")
    }
}
```

## Module Structure

```swift
// 1. Imports (grouped: system, third-party, local)
import Foundation
import os.log

import GRPC
import DatadogTrace

// 2. Protocol definition
protocol UserManager: Manager {
    func getUser(id: String, context: TraceContext) async throws -> User
}

// 3. Implementation
class UserManagerImpl: UserManager {
    private static let log = Logger.logForType(UserManagerImpl.self)
    // ...
}
```

## Static Logging

Use a `private static let log` pattern with a type-specific logger:

```swift
class InventoryManager {
    private static let log = Logger.logForType(InventoryManager.self)

    func syncInventory(accountId: String) async throws {
        Self.log.debug("\(#function): enter accountId=\(accountId, privacy: .public)")
        defer { Self.log.debug("\(#function): exit") }

        // ...
    }
}
```

## Spacing

```swift
// Good spacing
func calculate(a: Int, b: Int) -> Int {
    let result = a + b
    return result
}

let config = [
    "timeout": 5000,
    "retry": true,
]

// Use blank lines to separate logical sections
func processUser(user: User) {
    // Validation
    guard user.id != nil else {
        fatalError("Invalid user")
    }

    // Processing
    let normalized = normalizeUser(user)

    // Storage
    return saveUser(normalized)
}
```

## Comments

```swift
// Good - explains why
// Cache results to avoid repeated API calls
let cachedResults = [String: Any]()

// Avoid - explains what (obvious from code)
// Set x to 5
let x = 5
```

## Language-Specific Guidelines

- Use `let` by default, `var` only when mutation needed
- Prefer `async/await` for asynchronous code
- Use string interpolation for combining strings
- Use `guard` statements for early exits
- Leverage optionals and optional chaining
- Annotate ViewModels and UI-bound classes with `@MainActor`
- Use `lazy var` for expensive initializations that may not always be needed

```swift
// Good
let firstName = user.firstName
let message = "Hello, \(firstName)!"

func fetchUser(id: String) async throws -> User {
    let response = try await api.get("/users/\(id)")
    return response.data
}

// Avoid
var firstName = user.firstName  // Use let if not mutating
let message = "Hello, " + firstName + "!"

func fetchUser(id: String, completion: @escaping (User) -> Void) {
    api.get("/users/" + id) { response in
        completion(response.data)
    }
}
```

## Concurrency Patterns

### async/await

Prefer `async/await` over completion handlers. Use `defer` for cleanup:

```swift
func getAccount(accountId: String, context: TraceContext) async throws -> Account {
    Self.log.debug("\(#function): enter accountId=\(accountId, privacy: .public)")
    context.startTrace(type: AccountManagerImpl.self, functionName: "\(#function)")
    defer { context.finishTrace() }

    guard let client = self.networkManager.accountClient else { throw NetworkError.nilClient }
    let options = try await self.networkManager.callOptions(context: context)

    do {
        let remote = try await client.getAccount(request, callOptions: options)
        return Account(remote: remote)
    } catch {
        throw self.networkManager.mapError(error)
    }
}
```

### Parallel async let

Use `async let` to run independent operations concurrently:

```swift
func load() async throws {
    async let inventory = inventoryManager.search(accountId: accountId, context: context)
    async let connections = connectionManager.getConnections(accountId: accountId, context: context)
    async let profile: Void = stateManager.refresh(.profile, context: context)

    let inventoryResult = try await inventory
    let connectionsResult = try await connections
    _ = try await profile
}
```

### @MainActor

Annotate ViewModels and other UI-bound types:

```swift
@MainActor
class TicketsViewModel: ObservableObject {
    @Published var error: Error?
    @Published var submit = AsyncStatus.none

    // ...
}
```

## Extensions

### Protocol Conformance Extensions

Use extensions to organize protocol conformances separately:

```swift
struct Money: Codable, Equatable, Comparable {
    let currencyCode: String
    let amount: Decimal
}

extension Money: Hashable {
    func hash(into hasher: inout Hasher) {
        hasher.combine(amount)
    }
}

extension Money: CustomStringConvertible {
    var description: String { /* ... */ }
}
```

### Protocol Extensions for Default Implementations

Use `public extension` on a protocol to provide default behavior that conforming types can rely on or override:

```swift
public protocol LolayError: Error {
    var errorKey: String { get }
}

public extension LolayError {
    var errorKey: String {
        String(describing: type(of: self))
    }
}
```

Conforming types get `errorKey` for free but can override it when needed:

```swift
enum OrderError: String, Error, LolayError {
    case notFound
    case expired

    var errorKey: String {
        String(describing: type(of: self)) + "." + self.rawValue
    }
}
```

This is preferred over a base class when the protocol may be adopted by structs, enums, or classes that already have a different superclass.

### Private Extensions for File-Local Helpers

Use `private extension` to scope helpers to the file:

```swift
struct TicketsView: View {
    var body: some View {
        NavigationStack(path: $router.path) {
            ticketsListView()
                .setupToolbar(title: "Tickets", router: router)
        }
    }
}

private extension View {
    func setupToolbar(title: String, router: TicketRouter) -> some View {
        self
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.large)
    }
}
```

## Static Factory Methods

Use a static `make()` method on ViewModels for production wiring while keeping `init` clean for test injection:

```swift
@MainActor
class TicketsViewModel: ObservableObject {
    private let inventoryManager: InventoryManager
    private let stateManager: StateManager

    init(inventoryManager: InventoryManager, stateManager: StateManager) {
        self.inventoryManager = inventoryManager
        self.stateManager = stateManager
    }
}

// MARK: - Factory Method for Production & Previews

extension TicketsViewModel {
    static func make() -> TicketsViewModel {
        TicketsViewModel(
            inventoryManager: AppShared.shared.managers.inventoryManager,
            stateManager: AppShared.shared.managers.stateManager
        )
    }
}

// Usage in SwiftUI views
struct TicketsView: View {
    @StateObject var model: TicketsViewModel = .make()
}
```

## Lazy Initialization

Use `lazy var` in factory/container types for on-demand initialization:

```swift
class ManagerFactoryImpl: ManagerFactory {
    lazy var accountManager: AccountManager = {
        AccountManagerImpl(
            storeManager: self.storeManager,
            authManager: self.authManager,
            networkManager: self.networkManager
        )
    }()

    lazy var networkManager: NetworkManager = {
        NetworkManagerImpl(host: self.build.apiHost, port: self.build.apiPort)
    }()
}
```

## Imports

```swift
// Standard library
import Foundation
import os.log

// Third-party
import GRPC
import DatadogTrace

// Local modules
import LolayErred
import LolayInvestigo
```

## Error Handling

### Domain-Specific Error Enums

Use enums with associated values for rich error context:

```swift
enum NetworkError: Error {
    case nilClient
    case invalidMessage
    case server(Error)
    case unknown(Error)

    var underlyingError: Error? {
        switch self {
        case .unknown(let error), .server(let error): return error
        default: return nil
        }
    }
}
```

### LocalizedError Conformance

Extend error types with `LocalizedError` for user-facing messages:

```swift
extension NetworkError: LocalizedError {
    public var errorDescription: String? {
        switch self {
        case .server(let error):
            if let status = error as? GRPCStatus { return status.message }
            return nil
        default:
            return nil
        }
    }
}
```

### AutoLocalizedError Protocol

Use a drop-in protocol to get `LocalizedError` for free via reflection and localization keys:

```swift
protocol AutoLocalizedError: Error, LocalizedError { }

enum SyncError: AutoLocalizedError {
    case backend(String)
    case timeout
}
```

### Error Filtering

Use a dedicated type to decide which errors to suppress from the UI:

```swift
enum ErrorFilter {
    static func shouldSuppress(_ error: Error?) -> Bool {
        guard let error else { return false }
        if let status = error as? GRPCStatus {
            return status.code == .cancelled
        }
        return false
    }
}
```

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

## Anti-Patterns

### Magic Numbers

```swift
// Avoid
if user.age > 18 { }

// Good
let minimumAge = 18
if user.age > minimumAge { }
```

### Deep Nesting

```swift
// Avoid
if let user = user {
    if user.isActive {
        if user.hasPermission {
            // Do something
        }
    }
}

// Good - guard statements
guard let user = user else { return }
guard user.isActive else { return }
guard user.hasPermission else { return }
```
