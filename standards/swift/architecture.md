# Architecture — Swift

Follows general principles in [architecture.md](../architecture.md).

## Module Structure

### SPM Library

```
PackageName/
├── Package.swift                    # Package manifest (platforms, dependencies, targets)
├── Sources/
│   └── ModuleName/
│       ├── ModuleProtocol.swift     # Public protocols
│       ├── ModuleImpl.swift         # Implementations
│       ├── ModuleHelpers.swift      # Internal helpers
│       └── Type+ModuleName.swift    # Extensions on system types
└── Tests/
    └── ModuleNameTests/
        ├── ModuleProtocolTests.swift
        ├── ModuleImplTests.swift
        └── Localizable.strings      # Test resources (via .process in Package.swift)
```

### iOS App

```
AppName/
├── Application/              # App lifecycle, constants, routing
│   ├── AppDelegate.swift
│   ├── MainApp.swift
│   ├── MainView.swift
│   ├── MainRouter.swift
│   └── K.swift               # Constants namespace
├── Managers/                  # Business logic (Protocol + Impl pairs)
│   ├── Manager.swift          # Base protocol
│   ├── ManagerFactory.swift   # DI container
│   ├── Account/
│   │   ├── AccountManager.swift
│   │   └── Account.swift
│   ├── Network/
│   │   ├── NetworkManager.swift
│   │   └── NetworkError.swift
│   └── Shared/                # Shared models (Money, Interval, etc.)
├── Error Handling/            # Error protocols and filters
├── Model/                     # Domain models and resolvers
├── UI/                        # SwiftUI views grouped by feature
│   ├── Inventory/
│   │   ├── TicketsView.swift
│   │   └── TicketsViewModel.swift
│   ├── Navigation/
│   │   ├── Core/              # Router protocols and base classes
│   │   └── FeatureRouters/    # Concrete routers per feature
│   └── Shared/                # Reusable components and styling
├── Services/                  # Cross-cutting services (analytics, tracing)
└── Utils/                     # Extensions and helpers
AppNameTests/
├── BaseTests.swift            # Base XCTestCase
├── BaseManagerTests.swift     # Base for manager tests
├── Managers/                  # Manager unit/integration tests
├── Models/                    # ViewModel tests
├── Mocks/
│   ├── Managers/BaseMocks/    # fatalError stubs per protocol
│   └── MockManagerFactoryImpl.swift
└── Support/                   # Noop implementations for testing
```

## Design Patterns

### Manager Pattern

Business logic lives in **Manager** classes. Each manager is defined as a protocol and implemented by a class with an `Impl` suffix. Managers receive dependencies via constructor injection:

```swift
protocol AccountManager: Manager {
    func getAccountSummary(accountId: String, context: TraceContext) async throws -> AccountSummary
    func getUserAccountSummaries(userId: String, context: TraceContext) async throws -> [AccountSummary]
}

class AccountManagerImpl: AccountManager {
    private static let log = Logger.logForType(AccountManagerImpl.self)
    private let storeManager: StoreManager
    private let networkManager: NetworkManager

    init(storeManager: StoreManager, networkManager: NetworkManager) {
        self.storeManager = storeManager
        self.networkManager = networkManager
    }

    func getAccountSummary(accountId: String, context: TraceContext) async throws -> AccountSummary {
        Self.log.debug("\(#function): enter accountId=\(accountId, privacy: .public)")
        context.startTrace(type: AccountManagerImpl.self, functionName: "\(#function)")
        defer { context.finishTrace() }

        guard let client = self.networkManager.accountClient else { throw NetworkError.nilClient }
        let options = try await self.networkManager.callOptions(context: context)

        do {
            let remote = try await client.getAccountSummary(request, callOptions: options)
            return AccountSummary(remote: remote)
        } catch {
            throw self.networkManager.mapError(error)
        }
    }
}
```

Domain models that belong to a specific manager live in that manager's subfolder inside `Managers/` and use the plain domain name — no `Model` suffix. For example, `AccountManager` owns `Account` (not `AccountModel`). The separate top-level `Model/` folder is for domain models and resolvers that are not owned by a single manager.

### Delegate Pattern

Use the delegate pattern when an object needs to notify or ask another object for decisions without a tight coupling. The delegate is a `weak` protocol reference, avoiding retain cycles:

```swift
@MainActor
public protocol ErrorManagerDelegate: AnyObject {
    func errorManager(_ manager: ErrorManager, shouldPresent error: Error) -> Bool
    func errorManager(_ manager: ErrorManager, didPresent error: Error)
    func errorManager(_ manager: ErrorManager, titleFor error: Error) -> String
    func errorManager(_ manager: ErrorManager, messageFor error: Error) -> String?
}

@MainActor
public class ErrorManager {
    public weak var delegate: ErrorManagerDelegate?
    private let bundle: Bundle?

    public init(bundle: Bundle? = nil) {
        self.bundle = bundle
    }

    public func present(_ error: Error) {
        if let delegate, !delegate.errorManager(self, shouldPresent: error) { return }

        let title = delegate?.errorManager(self, titleFor: error)
            ?? localizedTitle(for: error)
            ?? "Error"
        let message = delegate?.errorManager(self, messageFor: error)
            ?? error.localizedDescription

        // present alert with title and message
    }
}
```

The delegate protocol should be `AnyObject`-constrained so the delegate property can be `weak`. The manager provides default behavior when no delegate is set.

### Base Class with No-Op Defaults

When a protocol has many methods but most implementations only need a subset, provide a base class with empty (no-op) implementations. Subclasses override only the methods they care about:

```swift
public protocol Tracker {
    func setIdentifier(_ identifier: String)
    func logEvent(_ name: String)
    func logEvent(_ name: String, parameters: [String: String])
    func logPage(_ name: String)
    func logError(_ error: Error)
}

public class BaseTracker: Tracker {
    public func setIdentifier(_ identifier: String) { }
    public func logEvent(_ name: String) { }
    public func logEvent(_ name: String, parameters: [String: String]) { }
    public func logPage(_ name: String) { }
    public func logError(_ error: Error) { }
}

public class OSLogTracker: BaseTracker {
    private let log: OSLog

    public init(bundleIdentifier: String) {
        self.log = OSLog(subsystem: bundleIdentifier, category: String(describing: type(of: self)))
    }

    override public func logEvent(_ name: String) {
        os_log(.info, log: log, "event=%{PUBLIC}@", name)
    }

    override public func logError(_ error: Error) {
        os_log(.error, log: log, "error=%{PUBLIC}@", error.localizedDescription)
    }
}
```

A `NoopTracker` subclass that overrides nothing is useful as a test double or a placeholder when tracking is disabled.

### Composite / Multiplexer Pattern

When you need to broadcast to multiple implementations of the same protocol, wrap them in a composite that iterates over a collection of delegates:

```swift
public class CompositeTracker: BaseTracker {
    private let trackers: [Tracker]

    public init(_ trackers: Tracker...) {
        self.trackers = trackers
    }

    override public func setIdentifier(_ identifier: String) {
        for tracker in trackers { tracker.setIdentifier(identifier) }
    }

    override public func logEvent(_ name: String) {
        for tracker in trackers { tracker.logEvent(name) }
    }

    override public func logEvent(_ name: String, parameters: [String: String]) {
        for tracker in trackers { tracker.logEvent(name, parameters: parameters) }
    }

    override public func logPage(_ name: String) {
        for tracker in trackers { tracker.logPage(name) }
    }

    override public func logError(_ error: Error) {
        for tracker in trackers { tracker.logError(error) }
    }
}
```

Usage at the composition root:

```swift
let tracker = CompositeTracker(
    OSLogTracker(bundleIdentifier: Bundle.main.bundleIdentifier!),
    FirebaseTracker(),
    CrashlyticsTracker()
)
```

This keeps callers unaware of how many (or which) backends are active.

### MVVM Pattern (SwiftUI)

ViewModels are `@MainActor` classes conforming to `ObservableObject` with `@Published` properties. Views are structs that own their ViewModel via `@StateObject`. The ViewModel receives dependencies through `init` and exposes a static `make()` factory for production wiring:

```swift
@MainActor
class TicketsViewModel: ObservableObject {
    @Published var error: Error?
    @Published var ticketSections: [TicketSection] = []
    @Published var syncStatus: InventorySyncStatus? = .none

    private let inventoryManager: InventoryManager
    private let stateManager: StateManager

    init(inventoryManager: InventoryManager, stateManager: StateManager) {
        self.inventoryManager = inventoryManager
        self.stateManager = stateManager
    }

    func load() async {
        // async business logic, updates @Published properties
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

struct TicketsView: View {
    @StateObject var model: TicketsViewModel = .make()

    var body: some View {
        List { /* ... */ }
            .task { await model.load() }
            .refreshable { await model.load() }
    }
}
```

### Router Pattern (SwiftUI Navigation)

Navigation is driven by router objects, not inline view state. A `NavigationRouter` protocol defines the contract, and base classes provide stack, sheet, or tab behaviors:

```swift
@MainActor
protocol NavigationRouter: ObservableObject {
    associatedtype Destination: Hashable
    func navigate(to destination: Destination)
}

@MainActor
class StackRouterBase<D: Hashable>: StackRouting {
    @Published var path = NavigationPath()

    func navigate(to destination: D) { path.append(destination) }
    func navigateBack() { guard !path.isEmpty else { return }; path.removeLast() }
    func navigateToRoot() { guard !path.isEmpty else { return }; path.removeLast(path.count) }
}

final class TicketRouter: StackRouterBase<TicketRouter.Destination> {
    enum Destination: Hashable {
        case details(String)
        case paymentDetails(Payment)
    }
}

struct TicketsView: View {
    @StateObject var router: TicketRouter

    var body: some View {
        NavigationStack(path: $router.path) {
            // content
        }
        .navigationDestination(for: TicketRouter.Destination.self) { dest in
            switch dest {
            case .details(let id): TicketDetailView(inventoryId: id)
            case .paymentDetails(let payment): PaymentDetailsView(payment: payment)
            }
        }
    }
}
```

### ManagerFactory / DI Container

A protocol-based factory lazily creates and wires all managers. The factory takes external dependencies in `init` and provides managers on demand. Tests can substitute mock implementations:

```swift
protocol ManagerFactory {
    var storeManager: StoreManager { get set }
    var authManager: AuthManager { get set }
    var networkManager: NetworkManager { get }
    var accountManager: AccountManager { get set }
    var profileManager: ProfileManager { get set }
    // ...
}

class ManagerFactoryImpl: ManagerFactory {
    private let build: Build

    init(build: Build, notificationCenter: NotificationCenter) {
        self.build = build
        // ...
    }

    lazy var networkManager: NetworkManager = {
        NetworkManagerImpl(host: self.build.apiHost, port: self.build.apiPort,
                           authManager: self.authManager, debug: self.build.debug)
    }()

    lazy var accountManager: AccountManager = {
        AccountManagerImpl(storeManager: self.storeManager,
                           authManager: self.authManager,
                           networkManager: self.networkManager)
    }()
    // ...
}
```

## Dependency Management

### Constructor Injection + Lazy Factory

```swift
protocol OrderManager: Manager {
    func createOrder(items: [Item], context: TraceContext) async throws -> Order
}

class OrderManagerImpl: OrderManager {
    private let networkManager: NetworkManager
    private let storeManager: StoreManager

    init(networkManager: NetworkManager, storeManager: StoreManager) {
        self.networkManager = networkManager
        self.storeManager = storeManager
    }
}

class ManagerFactoryImpl: ManagerFactory {
    lazy var networkManager: NetworkManager = {
        NetworkManagerImpl(host: self.build.apiHost, authManager: self.authManager)
    }()

    lazy var orderManager: OrderManager = {
        OrderManagerImpl(networkManager: self.networkManager, storeManager: self.storeManager)
    }()
}
```

## Error Handling

### Error Hierarchy

Use enums with associated values for domain-specific errors. Conform to `LocalizedError` for user-facing messages. Use an `AutoLocalizedError` protocol to derive `LocalizedError` automatically from enum cases and localization keys:

```swift
enum NetworkError: Error {
    case nilClient
    case server(Error)
    case unknown(Error)
}

extension NetworkError: LocalizedError {
    public var errorDescription: String? {
        switch self {
        case .server(let error):
            if let status = error as? GRPCStatus { return status.message }
            return nil
        default: return nil
        }
    }
}

enum AppError: String, Error {
    case alreadyAuthenticated
    case urlNotSupported
}
```

Use an `ErrorFilter` to suppress non-user-facing errors (e.g., cancelled requests) from dialog presentation.

## Concurrency Architecture

- Use Swift Concurrency (`async`/`await`, `Actor`) instead of GCD/completion handlers for all new code
- Use `@MainActor` for all UI-bound types (ViewModels, UI services)
- Isolate shared mutable state in custom `actor` types to prevent data races
- Prefer value types (`struct`, `enum`) over reference types (`class`) unless identity semantics are required — value semantics prevent shared mutable state
- Use `Sendable` conformance to verify thread safety at compile time (Swift 6 strict concurrency)
