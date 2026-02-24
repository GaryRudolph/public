# Architecture Standards

## Core Principles

### SOLID Principles
- **Single Responsibility** - Each module/class has one reason to change
- **Open/Closed** - Open for extension, closed for modification
- **Liskov Substitution** - Subtypes must be substitutable for base types
- **Interface Segregation** - Many specific interfaces > one general interface
- **Dependency Inversion** - Depend on abstractions, not concretions

### Keep It Simple
- Solve the current problem, not future hypothetical problems
- Prefer boring technology and established patterns
- Only abstract when you have 3+ concrete examples
- Avoid premature optimization

### Separation of Concerns
- Business logic separate from presentation
- Data access separate from business logic
- Configuration separate from code

## Architectural Patterns

### Layered Architecture

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

**Rules:**
- Each layer only depends on layers below it
- Never skip layers (presentation → data access)
- Keep layers thin and focused

### Module Structure

**Python:**

```
feature/
├── __init__.py          # Public API
├── types.py             # Type definitions
├── service.py           # Business logic
├── repository.py        # Data access
├── validators.py        # Input validation
└── tests/
    ├── test_service.py
    └── test_repository.py
```

**Swift (SPM Library):**

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

**Swift (iOS App):**

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

### Repository Pattern
Encapsulate data access logic behind an abstraction. Best for complex domains with multiple data sources or when testability through interface substitution is critical.

**Python:**

```python
from typing import Protocol

class UserRepository(Protocol):
    async def find_by_id(self, id: str) -> User | None: ...
    async def find_by_email(self, email: str) -> User | None: ...
    async def save(self, user: User) -> User: ...
    async def delete(self, id: str) -> None: ...

class DatabaseUserRepository:
    async def find_by_id(self, id: str) -> User | None:
        # Database-specific implementation
        pass
    # ... other methods
```

### ActiveRecord Pattern
Models handle their own persistence via class methods. Best for simpler domains, single-table designs, or when zero-ceremony usage is valued.

```python
class Order(Model):
    class State(StrEnum):
        PENDING = auto()
        SHIPPED = auto()
        DELIVERED = auto()

    order_id = UnicodeAttribute(hash_key=True)
    state = UnicodeAttribute()
    total = NumberAttribute()

    @classmethod
    def create(cls, order_id: UUID, items: list[Item]) -> "Order":
        total = sum(item.price * item.quantity for item in items)
        return cls(order_id=order_id, state=cls.State.PENDING, total=total)

    @classmethod
    def get(cls, order_id: UUID) -> "Order":
        try:
            return super().get(str(order_id))
        except cls.DoesNotExist as e:
            raise OrderNotFoundError(order_id) from e

    @classmethod
    def update_state(cls, order_id: UUID, new_state: "Order.State") -> "Order":
        order = cls.get(order_id)
        order.state = new_state
        order.save()
        return order
```

### Manager Pattern (Swift)

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

### Service Layer Pattern
Encapsulate business logic

```python
class UserService:
    def __init__(self, user_repository: UserRepository, email_service: EmailService):
        self._user_repository = user_repository
        self._email_service = email_service

    async def create_user(self, data: CreateUserData) -> User:
        # 1. Validate
        self._validate_user_data(data)

        # 2. Business logic
        user = User(data)

        # 3. Persist
        await self._user_repository.save(user)

        # 4. Side effects
        await self._email_service.send_welcome(user)

        return user
```

### Factory Pattern
When object creation is complex

**Separate factory class** — for cross-cutting creation logic or mapping between types:

```python
class UserFactory:
    def create_from_api_response(self, data: ApiUser) -> User:
        return User(
            id=data.user_id,
            email=data.email_address,
            created_at=datetime.fromtimestamp(data.created_timestamp),
        )
```

**Classmethod factory** — when defaults or computed values are involved and creation belongs on the model itself:

```python
class Order(Model):
    @classmethod
    def create(
        cls, order_id: UUID, items: list[Item], ttl_days: int = 30,
    ) -> "Order":
        timestamp = datetime.now(timezone.utc)
        expires_at = int(timestamp.timestamp()) + (ttl_days * 86400)
        return cls(
            order_id=order_id,
            total=sum(i.price for i in items),
            created_at=timestamp,
            expires_at=expires_at,
        )
```

### Strategy Pattern
When you have multiple algorithms for the same task

```python
from typing import Protocol

class PaymentStrategy(Protocol):
    async def process_payment(self, amount: float) -> PaymentResult: ...

class CreditCardPayment:
    async def process_payment(self, amount: float) -> PaymentResult:
        # Credit card specific logic
        pass

class PayPalPayment:
    async def process_payment(self, amount: float) -> PaymentResult:
        # PayPal specific logic
        pass

class PaymentService:
    def __init__(self, strategy: PaymentStrategy):
        self._strategy = strategy

    async def pay(self, amount: float) -> PaymentResult:
        return await self._strategy.process_payment(amount)
```

### Delegate Pattern (Swift)

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

### Error Catalog Pattern
Centralize error definitions as classmethods on a single class. Each method maps a domain error to a status code and error code, providing a single source of truth for all API error responses:

```python
from http import HTTPStatus

class AppError(Exception):
    def __init__(self, status: HTTPStatus, code: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code

class Errors:
    @classmethod
    def user_not_found(cls) -> AppError:
        raise AppError(HTTPStatus.NOT_FOUND, 3, "User not found")

    @classmethod
    def bad_token(cls) -> AppError:
        raise AppError(HTTPStatus.UNAUTHORIZED, 7, "Bad token")

    @classmethod
    def required_field(cls, field: str) -> AppError:
        raise AppError(HTTPStatus.BAD_REQUEST, 10, f"Missing required field: {field}")

    @classmethod
    def not_authorized(cls) -> AppError:
        raise AppError(HTTPStatus.FORBIDDEN, 12, "You don't have access")
```

### Base API / Handler Pattern
Extract shared request handling (auth verification, permission checks) into a base class that API handlers inherit:

```python
class BaseApi:
    def _get_and_verify_token(self, request: Request) -> Token:
        header_token = request.headers.get("X-Token-Id")
        token = Token.get_by_key(header_token)
        if not token:
            Errors.bad_token()
        return token

    def _get_and_verify_self(self, token: Token, user_id: str) -> User:
        if token.user.id == user_id:
            return token.user
        user = User.get(user_id)
        if user is None:
            Errors.user_not_found()
        Errors.not_authorized()

class UserApi(BaseApi):
    def __init__(self, queue_service: QueueService) -> None:
        self._queue_service = queue_service

    def update_user(self, user_id: str) -> dict[str, Any]:
        token = self._get_and_verify_token(request)
        user = self._get_and_verify_self(token, user_id)
        # ... update logic
        return {"user": user.to_dict()}
```

### Centralized Route Registration
Register all routes in a single function for discoverability, rather than scattering decorator-based routes across files:

```python
def setup_routing(app: App) -> None:
    app.route("/api/users", methods=["POST"], handler=users_api.create_user)
    app.route("/api/users/<user_id>", methods=["PUT"], handler=users_api.update_user)
    app.route("/api/users/<user_id>/orders", methods=["GET"], handler=orders_api.get_orders)
    app.route("/api/users/<user_id>/orders", methods=["POST"], handler=orders_api.create_order)
    app.route("/api/queues/order_created", methods=["POST"], handler=queues_api.handle_order_created)
```

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

### ManagerFactory / DI Container (Swift)

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

### Constructor Injection + Factory Builder

Favor **constructor injection** for all dependencies. Each class declares what it needs in `__init__` / `init` and never creates its own collaborators. A single **factory builder** (or composition root) is responsible for wiring everything together. This keeps classes testable in isolation — tests call the constructor directly with mocks — while production code uses the factory.

**Python — constructor injection:**

```python
class OrderService:
    def __init__(
        self,
        order_repository: OrderRepository,
        payment_service: PaymentService,
        notification_service: NotificationService,
    ) -> None:
        self._order_repository = order_repository
        self._payment_service = payment_service
        self._notification_service = notification_service
```

**Python — factory builder (composition root):**

```python
class ServiceFactory:
    def __init__(self, config: Config) -> None:
        self._config = config

    @cached_property
    def notification_service(self) -> NotificationService:
        return NotificationServiceImpl(api_key=self._config.notify_key)

    @cached_property
    def payment_service(self) -> PaymentService:
        return StripePaymentService(secret=self._config.stripe_secret)

    @cached_property
    def order_repository(self) -> OrderRepository:
        return DynamoOrderRepository(table=self._config.table_name)

    @cached_property
    def order_service(self) -> OrderService:
        return OrderService(
            order_repository=self.order_repository,
            payment_service=self.payment_service,
            notification_service=self.notification_service,
        )

# Composition root — one place that builds the entire graph
factory = ServiceFactory(load_config())
order_service = factory.order_service
```

For simple apps, a plain module-level script can serve as the composition root:

```python
# main.py
push_service = PushService()
queue_service = QueueService(push_service)
user_api = UserApi(queue_service)
contact_api = ContactApi(queue_service, sms_service, shorten_service)
```

**Swift — constructor injection + lazy factory:**

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

**Why this matters:**
- Classes are **testable** — call the constructor with mocks, no framework needed
- The **factory builder is the only place** that knows about concrete types
- Swapping an implementation (e.g., a mock payment service) requires changing one line in the factory, not touching business logic
- **Avoid** classes that create their own dependencies internally — this hides coupling and makes testing difficult

```python
# Avoid - hardcoded dependencies
class OrderService:
    def __init__(self) -> None:
        self._repository = OrderRepository()       # untestable
        self._payment = StripePaymentService()      # untestable
```

### Dependency Direction
- High-level modules should not depend on low-level modules
- Both should depend on abstractions (interfaces/protocols)

```python
from typing import Protocol

class EmailSender(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...

class UserService:
    def __init__(self, email_sender: EmailSender) -> None:
        self._email_sender = email_sender

class SendGridEmailSender:
    async def send(self, to: str, subject: str, body: str) -> None:
        # SendGrid specific implementation
        pass
```

## Error Handling Architecture

### Error Hierarchy
```python
# Base error class
class AppError(Exception):
    def __init__(self, message: str, status_code: int, is_operational: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.is_operational = is_operational

# Specific error types
class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, 400)

class NotFoundError(AppError):
    def __init__(self, resource: str):
        super().__init__(f"{resource} not found", 404)

class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, 401)
```

### Error Hierarchy (Swift)

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

### Error Handling Layers
1. **Service Layer** - Throws domain-specific errors
2. **Controller Layer** - Catches and transforms to HTTP responses (or UI error dialogs in mobile)
3. **Global Handler** - Catches unexpected errors, logs, returns safe responses

## Data Flow

### Request Flow
```
HTTP Request
    ↓
Controller (validate, parse)
    ↓
Service (business logic)
    ↓
Repository (data access)
    ↓
Database
```

### Response Flow
```
Database
    ↓
Repository (domain models)
    ↓
Service (business logic)
    ↓
Controller (DTOs/serialization)
    ↓
HTTP Response
```

## State Management

### Principles
- Keep state as local as possible
- Immutable data by default
- Single source of truth
- Predictable state updates

### Avoid Global State
```python
# Avoid - global mutable state
current_user: User | None = None

# Good - passed explicitly
def process_order(order: Order, user: User):
    # user is explicit parameter
    pass
```

### Module-Level Initialization

A package `__init__.py` can configure models or services on import for zero-ceremony usage. This is acceptable for configuration wiring that applies once at startup:

```python
# mypackage/__init__.py
from .models import Order, OrderItem
from .exceptions import OrderError, OrderNotFoundError

_config = load_config()
Order.Meta.table_name = _config.table_name
Order.Meta.region = _config.region

__all__ = ["Order", "OrderItem", "OrderError", "OrderNotFoundError"]
```

## API Design

### RESTful Principles
- Use HTTP verbs correctly (GET, POST, PUT, DELETE)
- Use plural nouns for resources (`/users`, not `/user`)
- Use path parameters for IDs (`/users/123`)
- Use query parameters for filtering (`/users?status=active`)

### Versioning
- Include version in URL: `/api/v1/users`
- Maintain backward compatibility within a version
- Document breaking changes

### Response Format
```json
// Success response
{
  "data": { },
  "meta": { }
}

// Error response
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": [
      { "field": "email", "message": "Invalid email format" }
    ]
  }
}
```

## Performance Considerations

### When to Optimize
1. Measure first - don't guess
2. Focus on algorithmic complexity
3. Optimize hot paths only
4. Don't sacrifice readability for minor gains

### Caching Strategy
- Cache at appropriate layers
- Use cache invalidation strategies
- Consider cache consistency requirements

### Database Access
- Use connection pooling
- Avoid N+1 queries
- Use indexes on frequently queried fields
- Paginate large result sets

## Security Architecture

### Defense in Depth
- Multiple layers of security
- Validate at every boundary
- Never trust client input
- Use principle of least privilege

### Authentication & Authorization
- Separate authentication (who are you?) from authorization (what can you do?)
- Use established libraries for authentication
- Store permissions in central location
- Check permissions at service layer, not just UI

## Testing Architecture

### Test Pyramid
```
        /\
       /  \      E2E Tests (few)
      /────\
     /      \    Integration Tests (some)
    /────────\
   /          \  Unit Tests (many)
  /____________\
```

### Test Boundaries
- **Unit Tests** - Single function/class, mocked dependencies
- **Integration Tests** - Multiple modules, real dependencies
- **E2E Tests** - Full system, real environment

## Documentation Requirements

Document:
- Public APIs
- Complex business logic
- Architectural decisions (ADRs)
- Non-obvious behavior

Don't document:
- Self-explanatory code
- Implementation details that may change
- What the code does (code should be self-documenting)
