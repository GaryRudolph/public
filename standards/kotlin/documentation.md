# Documentation — Kotlin

Follows general principles in [documentation.md](../documentation.md).

## Code Comments

### When to Comment

**Good reasons:**
```kotlin
// Cache results for 5 minutes to reduce API calls to rate-limited service
const val CACHE_TTL = 5 * 60

// HACK: Temporary workaround for bug in library v2.3.1
// Remove when upgrading to v2.4.0
// See: https://github.com/library/issues/123
if (version == "2.3.1") {
    applyWorkaround()
}

// Using binary search for O(log n) performance on sorted array
val index = sortedArray.binarySearch(target)
```

**Bad reasons:**
```kotlin
// Avoid — restates the code
// Set x to 5
val x = 5

// Avoid — explains obvious code
// Loop through users
for (user in users) {
    processUser(user)
}
```

### TODO Comments
```kotlin
// TODO: Add input validation
// TODO(username): Refactor to use new API
// TODO: [TICKET-123] Implement caching layer
// FIXME: This breaks when input is negative
// HACK: Workaround for upstream bug
// NOTE: This must run before initDatabase()
```

## KDoc Format

Use `/** ... */` comments with [KDoc syntax](https://kotlinlang.org/docs/kotlin-doc.html). The first paragraph is the summary; subsequent paragraphs are the detailed description. Block tags come last.

### Function Documentation

```kotlin
/**
 * Calculates the total price including tax and discount.
 *
 * Applies the discount code first, then adds tax on the discounted subtotal.
 * Invalid discount codes are silently ignored.
 *
 * @param items list of items with price and quantity
 * @param taxRate tax rate as decimal (e.g., 0.08 for 8%)
 * @param discountCode optional discount code to apply
 * @return the total price after tax and discount
 * @throws ValidationException if items list is empty
 * @throws InvalidDiscountException if discount code format is malformed
 * @sample com.example.samples.calculateTotalSample
 */
fun calculateTotal(
    items: List<Item>,
    taxRate: Double,
    discountCode: String? = null,
): Double {
    // Implementation
}
```

### Class Documentation

```kotlin
/**
 * Service for managing user accounts.
 *
 * Handles user creation, authentication, and profile management.
 * Uses [UserRepository] for data persistence and [EmailService] for notifications.
 *
 * This class is safe to use from multiple coroutines concurrently.
 *
 * @property repo the backing user repository
 * @sample com.example.samples.userServiceSample
 */
class UserService(private val repo: UserRepository) {

    /**
     * Creates a new user account.
     *
     * Validates the data, persists the user, and sends a welcome email.
     *
     * @param data user creation data
     * @return the created user
     * @throws ValidationException if user data is invalid
     * @throws DuplicateEmailException if email already exists
     */
    suspend fun createUser(data: CreateUserData): User {
        // Implementation
    }
}
```

### Property Documentation

```kotlin
/**
 * The current authentication state as a [StateFlow].
 *
 * Emits [AuthState.Unauthenticated] initially, then updates on login/logout events.
 */
val authState: StateFlow<AuthState>
```

## Required Block Tags

| Tag | Usage |
|---|---|
| `@param name` | Every function/constructor parameter |
| `@return` | Every non-`Unit` return |
| `@throws ExType` | Every documented exception |
| `@property name` | Class-level property documentation |
| `@sample` | Link to runnable usage examples in test/sample source sets |
| `@see` | Cross-references to related APIs |
| `@suppress` | Exclude internal elements from generated docs |

## What to Document

### Always Document
- All `public` and `protected` APIs — classes, functions, properties
- Non-obvious `internal` APIs used across modules
- Thread safety and concurrency guarantees
- Nullability contracts and side effects

### Don't Document
- `private` members unless the logic is genuinely complex
- Self-explanatory `enum` entries without associated data
- Overrides that don't change behavior — don't copy-paste the base documentation

## Inline Formatting

- Use **Markdown** for inline formatting in KDoc
- Use `[ClassName]` for cross-references to other declarations (KDoc link syntax)
- Do not mix KDoc link syntax `[Foo]` with Markdown link syntax `[Foo](url)` in the same doc block
- Use backticks for inline code: `` `null` ``, `` `StateFlow` ``

```kotlin
/**
 * Converts this [User] to a [UserDto] suitable for API responses.
 *
 * Returns `null` if the user has been soft-deleted.
 *
 * @see UserDto
 */
fun User.toDto(): UserDto? { }
```

## Deprecation

Use the `@Deprecated` annotation instead of KDoc deprecation tags:

```kotlin
@Deprecated(
    message = "Use fetchUser(id) instead",
    replaceWith = ReplaceWith("fetchUser(id)"),
    level = DeprecationLevel.WARNING,
)
fun getUser(id: String): User { }
```

## Complex Algorithms

```kotlin
/**
 * Implements the A* pathfinding algorithm.
 *
 * Time complexity: O(b^d) where b is branching factor and d is depth.
 * Space complexity: O(b^d).
 *
 * Algorithm:
 * 1. Add start node to open set
 * 2. While open set is not empty:
 *    a. Get node with lowest f-score
 *    b. If node is goal, reconstruct path
 *    c. Add node to closed set
 *    d. For each neighbor, calculate tentative g-score and update if better
 *
 * @param start the starting node
 * @param goal the target node
 * @return the shortest path as a list of nodes, or empty list if unreachable
 */
fun findPath(start: Node, goal: Node): List<Node> {
    // Implementation
}
```

## Best Practices

### Be Concise

```kotlin
// Verbose
/**
 * This function takes a user object as a parameter and then
 * validates all of the fields in the user object to make sure
 * they meet the requirements and then returns a boolean value
 * indicating whether the user object is valid or not.
 */
fun validateUser(user: User): Boolean { }

// Concise
/** Validates user data against requirements. */
fun validateUser(user: User): Boolean { }
```

### Link to Resources

```kotlin
/**
 * Implements OAuth 2.0 authorization code flow with PKCE.
 *
 * @see <a href="https://tools.ietf.org/html/rfc6749#section-4.1">RFC 6749 Section 4.1</a>
 */
suspend fun authorize(code: String): Token { }
```

## Documentation Tools

- **Dokka** — The official Kotlin documentation engine (generates HTML, Javadoc, and Markdown)

```bash
./gradlew dokkaHtml
```

## References

- [Kotlin KDoc Reference](https://kotlinlang.org/docs/kotlin-doc.html)
- [AndroidX KDoc Guidelines](https://android.googlesource.com/platform/frameworks/support/+/refs/heads/androidx-main/docs/kdoc_guidelines.md)
- [Dokka Documentation](https://kotlinlang.org/docs/dokka-introduction.html)
