# Code Style Standards

## General Principles

- **Readability over cleverness** - Write code that is easy to understand
- **Consistency** - Follow existing patterns in the codebase
- **Simplicity** - Avoid unnecessary complexity
- **Self-documenting** - Use clear names and structure

## Naming Conventions

### Variables and Functions
- Use **descriptive, pronounceable names**
- Avoid abbreviations unless widely understood
- Use **camelCase** for variables and functions
- Use **PascalCase** for classes and types
- Use **SCREAMING_SNAKE_CASE** for constants

```python
# Good
user_account_balance = 1000
def calculate_total_price(items): pass
class UserRepository: pass
MAX_RETRY_ATTEMPTS = 3

# Avoid
uab = 1000  # unclear abbreviation
def calc(i): pass  # unclear abbreviation
```

```swift
// Good
let userAccountBalance = 1000
func calculateTotalPrice(items: [Item]) { }
class UserRepository { }
let MAX_RETRY_ATTEMPTS = 3

// Avoid
let uab = 1000  // unclear abbreviation
func calc(i: [Any]) { }  // unclear abbreviation
```

### Files and Directories
- Use **snake_case** for Python file names: `user_service.py`
- Use **PascalCase** for Swift file names: `UserService.swift`
- Use **singular names** for single-entity files: `user_model.py`, `UserModel.swift`
- Use **plural names** for collections: `utils/`, `helpers/`
- Match file name to primary export: `UserService` class in `user_service.py` or `UserService.swift`
- Prefer a file and directory structure where files that work together are
  store together. An example is `user_model.py` and `user_service.py` in the
  same directory `src/user`.
- Prefer data logic and business logic stored in the same directory structure with
  nesting (i.e. `src/user/data` and `src/user/service`).
- Prefer separate projects for clean separation between a services and UI.

### Booleans
- Prefix with `is`, `has`, `can`, `should`
- Make the positive case clear

```python
is_active = True
has_permission = False
can_edit = True
should_retry = False
```

```swift
let isActive = true
let hasPermission = false
let canEdit = true
let shouldRetry = false
```

## Code Organization

### Module Structure

**Python:**
```python
# 1. Imports (standard library, third-party, then local)
from typing import Protocol
from api import API

# 2. Constants
DEFAULT_TIMEOUT = 5000

# 3. Type definitions
class User(Protocol):
    pass

# 4. Main implementation
class UserService:
    pass

# 5. Helper functions (module-private)
def _validate_input():
    pass
```

**Swift:**
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

## Formatting

### Indentation
- Use **2 spaces** for indentation (or 4 spaces, but be consistent)
- No tabs

### Line Length
- Maximum **100 characters** per line
- Break long lines at logical boundaries

### Spacing

**Python:**
```python
# Good spacing
def calculate(a, b):
    result = a + b
    return result

config = {
    "timeout": 5000,
    "retry": True,
}

# Use blank lines to separate logical sections
def process_user(user):
    # Validation
    if not user.id:
        raise ValueError("Invalid user")

    # Processing
    normalized = normalize_user(user)

    # Storage
    return save_user(normalized)
```

**Swift:**
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

### Comments
- Use comments to explain **why**, not what
- Place comments above the code they describe
- Keep comments up-to-date with code changes

**Python:**
```python
# Good - explains why
# Cache results to avoid repeated API calls
cached_results = {}

# Avoid - explains what (obvious from code)
# Set x to 5
x = 5
```

**Swift:**
```swift
// Good - explains why
// Cache results to avoid repeated API calls
let cachedResults = [String: Any]()

// Avoid - explains what (obvious from code)
// Set x to 5
let x = 5
```

## Language-Specific Guidelines

### Swift
- Use `let` by default, `var` only when mutation needed
- Prefer `async/await` for asynchronous code
- Use string interpolation for combining strings
- Use guard statements for early exits
- Leverage optionals and optional chaining

```swift
// Good
let firstName = user.firstName
let lastName = user.lastName
let message = "Hello, \(firstName)!"

func fetchUser(id: String) async throws -> User {
    let response = try await api.get("/users/\(id)")
    return response.data
}

// Avoid
var firstName = user.firstName  // Use let if not mutating
var lastName = user.lastName
let message = "Hello, " + firstName + "!"

func fetchUser(id: String, completion: @escaping (User) -> Void) {
    api.get("/users/" + id) { response in
        completion(response.data)
    }
}
```

### Python
- Follow PEP 8
- Use **snake_case** for functions and variables
- Use **PascalCase** for classes
- Use type hints for function signatures

```python
# Good
def calculate_total_price(items: list[Item]) -> float:
    """Calculate the total price of items."""
    return sum(item.price for item in items)

class UserRepository:
    def find_by_id(self, user_id: int) -> User | None:
        pass
```

## Imports

### Ordering
1. Standard library imports
2. Third-party imports
3. Local application imports

**Python:**
```python
# Standard library
import os
import sys

# Third-party
import requests
import flask

# Local
from services.user import UserService
from config import config
```

**Swift:**
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

### Avoid Circular Dependencies
- Keep module dependencies unidirectional
- Extract shared code to separate modules

## Error Handling

- Use specific error types
- Always include error context
- Handle errors at appropriate levels

**Python:**
```python
# Good
class ValidationError(Exception):
    def __init__(self, field: str, message: str):
        super().__init__(f"Validation failed for {field}: {message}")
        self.field = field

def validate_user(user: User):
    if not user.email:
        raise ValidationError("email", "Email is required")

# Avoid
def validate_user(user):
    if not user.email:
        raise Exception("Invalid")  # Too vague
```

**Swift:**
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

## Anti-Patterns to Avoid

### Magic Numbers

**Python:**
```python
# Avoid
if user.age > 18:
    pass

# Good
MINIMUM_AGE = 18
if user.age > MINIMUM_AGE:
    pass
```

**Swift:**
```swift
// Avoid
if user.age > 18 { }

// Good
let minimumAge = 18
if user.age > minimumAge { }
```

### Deep Nesting

**Python:**
```python
# Avoid
if user:
    if user.is_active:
        if user.has_permission:
            # Do something
            pass

# Good - early returns
if not user:
    return
if not user.is_active:
    return
if not user.has_permission:
    return

# Do something
```

**Swift:**
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

// Do something
```

### Large Functions
- Keep functions small and focused
- Extract complex logic into separate functions
- Aim for < 50 lines per function

## Tools

Configure your editor to:
- Format on save
- Show linting errors
- Auto-fix common issues
- Highlight trailing whitespace
