# Documentation — Swift

Follows general principles in [documentation.md](documentation.md).

## Code Comments

### When to Comment

**Good reasons:**
```swift
// Cache results for 5 minutes to reduce API calls to rate-limited service
let cacheTTL = 5 * 60

// HACK: Temporary workaround for bug in library v2.3.1
// Remove when upgrading to v2.4.0
// See: https://github.com/library/issues/123
if version == "2.3.1" {
    applyWorkaround()
}

// Using binary search for O(log n) performance on sorted array
let index = binarySearch(sortedArray, target)
```

**Bad reasons:**
```swift
// Avoid - restates the code
// Set x to 5
let x = 5

// Avoid - explains obvious code
// Loop through users
for user in users {
    processUser(user)
}
```

### Comment Style

```swift
// Single-line comments for brief explanations
let timeout = 30000  // 30 second timeout

// Multi-line comments for longer explanations.
// Use this format for complex logic that needs more context
// spanning multiple lines.
func complexFunction() { }
```

### TODO Comments
```swift
// TODO: Add input validation
// TODO(username): Refactor to use new API
// TODO: [TICKET-123] Implement caching layer
// FIXME: This breaks when input is negative
// HACK: Workaround for upstream bug
// NOTE: This must run before initDatabase()
```

## Documentation Rules

- **Write a `///` or `/** */` doc comment for every `public` and `open` declaration** — no exceptions
- **Start with a single-sentence summary** as a sentence fragment, not "This method..." or "This property is..." — it's redundant
- Document the **complexity** of any computed property that is not O(1): `/// - Complexity: O(n)`
- Use `///` for single-line and member documentation; `/** */` is acceptable for longer type-level docs

## Protocol Documentation

Use `/** */` block comments for protocol and major type-level documentation. Use `///` for individual members:

```swift
/**
 A factory to manage all the other managers. This is effectively a lightweight dependency
 injector where all the managers use constructor injection.
 */
protocol ManagerFactory {
    /// Manager for reading & writing data to persistent stores
    var storeManager: StoreManager { get set }
    /// Configuration manager that can be refreshed remotely
    var configManager: ConfigManager { get }
    /// Authentication manager for requesting access tokens
    var authManager: AuthManager { get set }
}
```

```swift
/**
 Retrieves and saves information about an account.
 */
protocol AccountManager: Manager {

    /**
     Retrieves a summary for a specific accountId.
     - parameter accountId: The accountId of which to get the account.
     - parameter context: Trace context used for tracing a request (i.e. Datadog)
     - returns: The found account summary
     */
    func getAccountSummary(accountId: String, context: TraceContext) async throws -> AccountSummary
}
```

## Function Documentation

Use `///` doc comments with Swift's documentation markup:

```swift
/// Calculates the total price including tax and discount.
///
/// - Parameters:
///   - items: Array of items with price and quantity
///   - taxRate: Tax rate as decimal (e.g., 0.08 for 8%)
///   - discountCode: Optional discount code to apply
/// - Returns: The total price after tax and discount
/// - Throws: `ValidationError` if items array is empty
///
/// Example:
/// ```swift
/// let total = try calculateTotal(items: [...], taxRate: 0.08, discountCode: "SAVE10")
/// ```
func calculateTotal(items: [Item], taxRate: Double, discountCode: String? = nil) throws -> Double {
    // Implementation
}
```

## Class Documentation

```swift
/// Service for managing user accounts.
///
/// Handles user creation, authentication, and profile management.
/// Uses `UserRepository` for data persistence and `EmailService` for notifications.
class UserService {

    /// Creates a new user account.
    ///
    /// Validates the user data, creates the account, and sends a welcome email.
    ///
    /// - Parameter data: User creation data
    /// - Returns: The created user
    /// - Throws: `ValidationError` if user data is invalid, `DuplicateEmailError` if email exists
    func createUser(data: CreateUserData) async throws -> User {
        // Implementation
    }
}
```

## Callout Markers

Use DocC callout markers to highlight important information in doc comments:

```swift
/// Factory method to construct an instance using the app's standard manager instances.
///
/// - Important: This method is intended for production and SwiftUI preview code only.
///   Tests should call the primary `init(...)` directly with mock dependencies.
///
/// - Note: This pattern prepares the codebase for an eventual shift to dependency
///   injection via Resolver (or similar).
///
/// - Tip: Once `make()` is backed by Resolver, even views that call it directly
///   become testable, since registrations can be overridden at test time.
///
/// Example usage:
/// ```swift
/// @StateObject var viewModel: TicketsViewModel = .make()
/// ```
static func make() -> TicketsViewModel {
    TicketsViewModel(
        connectionManager: AppShared.shared.managers.connectionManager,
        inventoryManager: AppShared.shared.managers.inventoryManager
    )
}
```

## Enum Documentation

Document enum types and individual cases with `///`:

```swift
/**
 Status to categorize an async operation. Typically used to display loading
 information or disable a button to prevent multiple clicks.
 */
enum AsyncStatus: String {
    case none
    case started
    case finished
}
```

```swift
/**
 Errors for `NetworkManager` that can occur in preparing or handling the request.
 */
enum NetworkError: Error {
    /// Token is nil, effectively already logged out
    case nilClient
    /// The request didn't validate properly according to GRPC
    case invalidMessage
    case server(Error)
    case unknown(Error)
}
```

## Inline Documentation

### Complex Algorithms
```swift
/// Implements the A* pathfinding algorithm.
///
/// - Complexity: Time O(b^d), Space O(b^d) where b is branching factor and d is depth
///
/// Algorithm:
/// 1. Add start node to open set
/// 2. While open set not empty:
///    a. Get node with lowest f-score
///    b. If node is goal, reconstruct path
///    c. Add node to closed set
///    d. For each neighbor, calculate tentative g-score and update if better
func findPath(start: Node, goal: Node) -> [Node] {
    // Implementation
}
```

### Magic Numbers
```swift
// Avoid
let result = value * 1.08

// Good - explain the number
let taxRate = 1.08  // 8% sales tax
let result = value * taxRate
```

## README Files

### Module/Library README — Structure
```markdown
## Structure

```
Sources/Module/
├── Module.swift          # Public API
├── ModuleService.swift   # Main service logic
├── ModuleRepository.swift # Data access
└── ModuleTypes.swift     # Type definitions
```

## Usage

```swift
import Module

let service = ModuleService()
let result = try await service.doSomething()
```
```

### iOS App README — Structure

An iOS app README should cover build prerequisites, target configurations, and architecture:

```markdown
# AppName

## Prerequisites
- Xcode 15+
- Ruby & Bundler (for Fastlane)
- CocoaPods or SPM dependencies

## Targets
| Target | Environment | Notes |
|--------|-------------|-------|
| AppDebug | Development | Mock auth available |
| AppBeta | Staging | TestFlight builds |
| AppProduction | Production | App Store release |

## Architecture
- **MVVM** with SwiftUI
- **Managers** for business logic (protocol + implementation)
- **ManagerFactory** for dependency injection
- **Router pattern** for navigation

## Build & Run
```bash
bundle install
bundle exec fastlane build
```
```

## DocC Documentation Catalogs

For frameworks and packages, add a documentation catalog (`.docc` bundle):

- Write long-form **articles** in Markdown for conceptual guides
- Organize with **Topics** groups in your documentation catalog
- Include code examples — runnable where possible
- Use `@Tutorial` for step-by-step guides with associated images

```
Sources/
└── MyFramework/
    ├── MyFramework.docc/
    │   ├── MyFramework.md          # Landing page
    │   ├── GettingStarted.md       # Article
    │   └── Resources/              # Images, sample code
    ├── MyService.swift
    └── ...
```

## Documentation Tools

- **DocC** - Apple's documentation compiler, integrated with Xcode

```bash
xcodebuild docbuild -scheme MyScheme -destination 'platform=macOS'
```

## Best Practices

### Be Concise
```swift
// Verbose
/// This function takes a user object as a parameter and then
/// validates all of the fields in the user object to make sure
/// they meet the requirements and then returns a boolean value
/// indicating whether the user object is valid or not.
func validateUser(_ user: User) -> Bool { }

// Concise
/// Validates user data against requirements.
func validateUser(_ user: User) -> Bool { }
```

### Use Examples
```swift
/// Formats a date string.
///
/// Example:
/// ```swift
/// formatDate("2024-01-01")          // "January 1, 2024"
/// formatDate("2024-01-01", style: .short) // "Jan 1, 2024"
/// ```
func formatDate(_ date: String, style: DateStyle = .long) -> String { }
```

### Link to Resources
```swift
/// Implements OAuth 2.0 authorization code flow.
///
/// See: https://tools.ietf.org/html/rfc6749#section-4.1
func authorize(code: String) async throws -> Token { }
```
