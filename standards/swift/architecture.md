# Architecture — Swift

Follows [architecture.md](../architecture.md).

## Module Structure — SPM Library

```
PackageName/
├── Package.swift
├── Sources/ModuleName/
│   ├── Module.swift             (Protocol)
│   ├── ModuleImpl.swift
│   ├── ModuleHelpers.swift
│   └── Type+ModuleName.swift
└── Tests/ModuleName/
```

## Module Structure — iOS App

```
AppName/
├── Application/              # App lifecycle, constants, routing
│   ├── MainApp.swift, MainView.swift, MainRouter.swift, K.swift
├── Managers/                 # Business logic (Protocol + Impl pairs)
│   ├── Manager.swift, ManagerFactory.swift
│   ├── Account/ (AccountManager.swift, Account.swift)
│   ├── Network/ (NetworkManager.swift, NetworkError.swift)
│   └── Shared/               # Shared models (Money, Interval, etc.)
├── Error Handling/            # Error protocols and filters
├── UI/                        # SwiftUI views grouped by feature
│   ├── Inventory/ (TicketsView.swift, TicketsViewModel.swift)
│   ├── Navigation/ (Core/, FeatureRouters/)
│   └── Shared/                # Reusable components and styling
├── Services/                  # Cross-cutting (analytics, tracing)
└── Utils/                     # Extensions and helpers
```

## Manager Pattern

Business logic in Manager classes. Protocol + `Impl` class. Dependencies via constructor injection:

```swift
protocol AccountManager: Manager {
    func getSummary(accountId: String, context: TraceContext) async throws -> AccountSummary
}

class AccountManagerImpl: AccountManager {
    private static let log = Logger.logForType(AccountManagerImpl.self)
    private let storeManager: StoreManager
    private let networkManager: NetworkManager

    init(storeManager: StoreManager, networkManager: NetworkManager) {
        self.storeManager = storeManager
        self.networkManager = networkManager
    }

    func getSummary(accountId: String, context: TraceContext) async throws -> AccountSummary {
        Self.log.debug("\(#function): enter accountId=\(accountId, privacy: .public)")
        context.startTrace(type: AccountManagerImpl.self, functionName: "\(#function)")
        defer { context.finishTrace() }

        guard let client = self.networkManager.accountClient else { throw NetworkError.nilClient }
        let options = try await self.networkManager.callOptions(context: context)
        do {
            let remote = try await client.getSummary(request, callOptions: options)
            return AccountSummary(remote: remote)
        } catch {
            throw self.networkManager.mapError(error)
        }
    }
}
```

Domain models that belong to a specific manager live in that manager's subfolder. Use the plain domain name — no `Model` suffix.

## Delegate Pattern

Use when an object needs to notify another without tight coupling. `weak` protocol reference:

```swift
@MainActor
public protocol ErrorManagerDelegate: AnyObject {
    func errorManager(_ manager: ErrorManager, shouldPresent error: Error) -> Bool
    func errorManager(_ manager: ErrorManager, titleFor error: Error) -> String
}
```

## Base Class with No-Op Defaults + Composite

When a protocol has many methods, provide a `BaseTracker` with no-op implementations. Subclasses override what they need. A `CompositeTracker` broadcasts to multiple implementations:

```swift
public class CompositeTracker: BaseTracker {
    private let trackers: [Tracker]
    public init(_ trackers: Tracker...) { self.trackers = trackers }
    override public func logEvent(_ name: String) {
        for tracker in trackers { tracker.logEvent(name) }
    }
}
```

## MVVM Pattern (SwiftUI)

ViewModels are `@MainActor` + `ObservableObject` with `@Published`. Views own ViewModel via `@StateObject`. Static `make()` factory for production wiring, `init` for test injection:

```swift
@MainActor
class TicketsViewModel: ObservableObject {
    @Published var ticketSections: [TicketSection] = []
    private let inventoryManager: InventoryManager

    init(inventoryManager: InventoryManager, stateManager: StateManager) { ... }
    static func make() -> TicketsViewModel { ... }
    func load() async { ... }
}

struct TicketsView: View {
    @StateObject var model: TicketsViewModel = .make()
    var body: some View {
        List { }
            .task { await model.load() }
            .refreshable { await model.load() }
    }
}
```

### Dependency injection rules

- **ViewModels and Managers use constructor injection only.** They must not read `EnvironmentValues`. A ViewModel should be constructible and fully functional outside of any view hierarchy so unit tests can exercise it without SwiftUI.
- **Views use `EnvironmentValues` for cross-cutting view concerns** (presenters, theming, routers, system actions like `dismiss` and `openURL`). Constructor injection is reserved for the view's own ViewModel.
- **The composition root (`AppFactory` / `ManagerFactory`) is the only place that wires values into the environment**, once, at the app root: `.environment(\.myPresenter, factory.myPresenter)`.

| Layer       | Gets its dependencies via                                                                    |
|-------------|----------------------------------------------------------------------------------------------|
| Managers    | Constructor injection                                                                        |
| ViewModels  | Constructor injection                                                                        |
| Views       | `EnvironmentValues` for cross-cutting concerns; constructor argument for their own ViewModel |

## Router Pattern

Navigation driven by router objects, not inline view state:

```swift
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
```

## ManagerFactory / DI Container

Protocol-based factory lazily creates and wires all managers:

```swift
protocol ManagerFactory {
    var storeManager: StoreManager { get set }
    var authManager: AuthManager { get set }
    var networkManager: NetworkManager { get }
    var accountManager: AccountManager { get set }
}

class ManagerFactoryImpl: ManagerFactory {
    lazy var networkManager: NetworkManager = {
        NetworkManagerImpl(host: self.build.apiHost, authManager: self.authManager)
    }()
    lazy var accountManager: AccountManager = {
        AccountManagerImpl(storeManager: self.storeManager, networkManager: self.networkManager)
    }()
}
```

## Environment Values (SwiftUI)

`EnvironmentValues` is the idiomatic mechanism for injecting view-level cross-cutting dependencies. Use it for values that many unrelated views will consume and that the composition root constructs once.

**Do use for:** notice/toast presenters, error presenters, routers, theming, feature flags that views read directly, and anything SwiftUI ships in the environment itself (`dismiss`, `openURL`, `colorScheme`, etc.).

**Do not use for:** Managers, ViewModels, or anything a ViewModel or Manager needs. Those use constructor injection.

### Defining a custom key

```swift
private struct NoticePresenterKey: EnvironmentKey {
    @MainActor static var defaultValue: AnyNoticePresenter {
        AnyNoticePresenter(NoOpNoticePresenter())
    }
}

extension EnvironmentValues {
    var noticePresenter: AnyNoticePresenter {
        get { self[NoticePresenterKey.self] }
        set { self[NoticePresenterKey.self] = newValue }
    }
}
```

- The `defaultValue` must always be safe to use. Prefer a no-op or a sensible production default so a missing injection degrades gracefully.
- Inject from the composition root at the app root: `WindowGroup { ContentView().environment(\.noticePresenter, factory.noticePresenter) }`.
- Read from a view with `@Environment(\.noticePresenter) private var presenter`.
- Never read `@Environment` in a ViewModel (it won't compile in a plain class, and workarounds couple the VM to a view hierarchy).

### Preview and test overrides

```swift
#Preview {
    ContentView()
        .environment(\.noticePresenter, AnyNoticePresenter(FakeNoticePresenter()))
}
```

## Concurrency Architecture

- Swift Concurrency (`async`/`await`, `Actor`) for all new code
- `@MainActor` for UI-bound types
- Custom `actor` types for shared mutable state
- `Sendable` for compile-time thread safety (Swift 6)
