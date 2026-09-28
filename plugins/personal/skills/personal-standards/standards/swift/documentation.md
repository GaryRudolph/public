# Documentation — Swift

Follows [documentation.md](../documentation.md).

## Rules

- **`///` or `/** */` doc comment for every `public` and `open` declaration** — no exceptions
- Start with a single-sentence summary as a sentence fragment, not "This method..."
- Document **complexity** of any computed property that is not O(1): `/// - Complexity: O(n)`
- Use `///` for single-line docs; `/** */` for multi-line docs (types, functions with parameters, etc.)

## Protocol Documentation

```swift
/**
 A factory to manage all the other managers. Lightweight dependency
 injector where all managers use constructor injection.
 */
protocol ManagerFactory {
    /// Manager for reading & writing data to persistent stores
    var storeManager: StoreManager { get set }
    /// Authentication manager for requesting access tokens
    var authManager: AuthManager { get set }
}
```

## Function Documentation

```swift
/**
 Calculates the total price including tax and discount.

 - Parameters:
   - items: Array of items with price and quantity
   - taxRate: Tax rate as decimal (e.g., 0.08 for 8%)
 - Returns: The total price after tax and discount
 - Throws: `ValidationError` if items array is empty
 */
func calculateTotal(items: [Item], taxRate: Double) throws -> Double { }
```

## Callout Markers

```swift
/**
 Factory method to construct an instance using the app's standard managers.

 - Important: Intended for production and SwiftUI preview code only.
   Tests should call `init(...)` directly with mock dependencies.

 - Note: Prepares for eventual shift to DI via Resolver.
 */
static func make() -> TicketsViewModel { }
```

## Enum Documentation

```swift
/**
 Errors for `NetworkManager` that can occur in preparing or handling requests.
 */
enum NetworkError: Error {
    /// Token is nil, effectively already logged out
    case nilClient
    /// Request didn't validate properly according to GRPC
    case invalidMessage
    case server(Error)
    case unknown(Error)
}
```

## DocC Catalogs

For frameworks/packages: add a `.docc` bundle with articles, topic groups, and `@Tutorial` for step-by-step guides.

```
Sources/MyFramework/
├── MyFramework.docc/
│   ├── MyFramework.md
│   ├── GettingStarted.md
│   └── Resources/
├── MyService.swift
```

## iOS App README Structure

```markdown
# AppName
## Prerequisites
## Targets (table: target, environment, notes)
## Architecture (MVVM, Managers, ManagerFactory, Router)
## Build & Run
```
