# Code Style — Swift

Follows general principles in [code-style.md](code-style.md).

## Naming Conventions

- Use **camelCase** for variables and functions: `userAccountBalance`, `calculateTotalPrice`
- Use **PascalCase** for classes, structs, and protocols: `UserRepository`
- Use **PascalCase** for file names: `UserService.swift`
- Constants use `let` with camelCase

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

## Module Structure

```swift
// 1. Imports
import Foundation
import API

// 2. Constants
let defaultTimeout = 5000

// 3. Type definitions
protocol User { }

// 4. Main implementation
public class UserService { }

// 5. Helper functions (private)
private func validateInput() { }
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

## Imports

```swift
// Standard library
import Foundation
import os

// Third-party
import Alamofire
import SwiftyJSON

// Local
import UserService
import Config
```

## Error Handling

```swift
// Good
enum ValidationError: Error {
    case fieldRequired(field: String, message: String)
}

func validateUser(_ user: User) throws {
    guard user.email != nil else {
        throw ValidationError.fieldRequired(field: "email", message: "Email is required")
    }
}

// Avoid
func validateUser(_ user: User) throws {
    if user.email == nil {
        throw NSError()  // Too vague
    }
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
