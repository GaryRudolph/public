# Code Style — Kotlin

Follows general principles in [code-style.md](code-style.md) and [Kotlin Official Coding Conventions](https://kotlinlang.org/docs/coding-conventions.html).

## Naming Conventions

- Use **camelCase** for functions, properties, local variables, and parameters: `userName`, `calculateTotal()`
- Use **PascalCase** for classes, interfaces, objects, type aliases, and enum entries: `UserRepository`, `sealed class UiState`
- Use **SCREAMING_SNAKE_CASE** for `const val` and top-level/object `val` constants: `const val MAX_RETRY_ATTEMPTS = 3`
- Use **PascalCase** for file names matching the top-level class: `UserService.kt`
- Backing properties use underscore prefix: `private val _state` / `val state`
- Test functions may use backtick names: `` fun `should return user when ID exists`() ``
- Avoid meaningless names like `Util`, `Helper`, `Manager`

```kotlin
// Good
val userAccountBalance = 1000
fun calculateTotalPrice(items: List<Item>): Double { }
class UserRepository { }
const val MAX_RETRY_ATTEMPTS = 3

// Avoid
val uab = 1000
fun calc(i: List<Any>): Double { }
```

## Formatting

- **4-space indentation**, no tabs
- **100-character line limit**
- Braces follow K&R style (opening brace on same line)
- Single blank line between top-level declarations
- No semicolons
- UTF-8 encoding required

```kotlin
// Good
class UserService(
    private val repo: UserRepository,
    private val emailService: EmailService,
) {
    fun createUser(data: CreateUserData): User {
        val validated = validate(data)
        return repo.save(validated)
    }
}
```

## Module Structure

```kotlin
// 1. Package declaration
package com.example.user

// 2. Imports (no wildcard imports)
import kotlinx.coroutines.flow.StateFlow
import com.example.data.UserRepository

// 3. Constants
const val DEFAULT_TIMEOUT = 5000L

// 4. Type definitions
data class User(val id: String, val name: String)

// 5. Main implementation
class UserService { }

// 6. Extension functions
fun User.displayName(): String = "$name ($id)"
```

## Kotlin Idioms

### Prefer `val` over `var`

```kotlin
// Good — immutable by default
val users = listOf("Alice", "Bob")

// Only use var when mutation is required
var retryCount = 0
```

### Prefer Expression Bodies for Single-Expression Functions

```kotlin
// Good
fun double(x: Int) = x * 2
fun User.isAdmin() = role == Role.ADMIN

// Use block body for multi-statement functions
fun processUser(user: User): Result {
    val validated = validate(user)
    return repository.save(validated)
}
```

### Prefer `when` over Cascading `if-else`

```kotlin
// Good
when (status) {
    Status.LOADING -> showSpinner()
    Status.SUCCESS -> showContent(data)
    Status.ERROR -> showError(message)
}

// Avoid
if (status == Status.LOADING) {
    showSpinner()
} else if (status == Status.SUCCESS) {
    showContent(data)
} else if (status == Status.ERROR) {
    showError(message)
}
```

### Use `require()`, `check()`, and `error()` for Preconditions

```kotlin
fun withdraw(amount: Double) {
    require(amount > 0) { "Amount must be positive: $amount" }
    check(balance >= amount) { "Insufficient balance: $balance < $amount" }
}
```

### Use Scope Functions Appropriately

```kotlin
// let — transform nullable or scoped value
user?.let { sendWelcomeEmail(it) }

// apply — configure an object
val request = Request().apply {
    url = "https://api.example.com"
    timeout = 5000
}

// also — side effects without changing the value
val user = createUser(data).also { logger.info("Created user: ${it.id}") }
```

### Use String Templates over Concatenation

```kotlin
// Good
val message = "Hello, $name! You have ${items.size} items."

// Avoid
val message = "Hello, " + name + "! You have " + items.size + " items."
```

### Use Destructuring Where It Improves Clarity

```kotlin
val (name, email) = user
for ((key, value) in map) { }
```

## Type System

### Use `data class` for DTOs and Value Objects

```kotlin
data class User(
    val id: String,
    val name: String,
    val email: String,
)
```

### Use `sealed class` / `sealed interface` for Finite State Sets

```kotlin
sealed interface UiState {
    data object Loading : UiState
    data class Success(val data: List<Item>) : UiState
    data class Error(val message: String) : UiState
}

// Prefer sealed interface when a type needs multiple hierarchies
sealed interface Loadable
sealed interface Refreshable
data class Content(val items: List<Item>) : Loadable, Refreshable
```

### Use `enum class` Only for Simple Singleton Variants

```kotlin
enum class Direction { NORTH, SOUTH, EAST, WEST }
```

### Use `object` for Singletons and Namespaces

```kotlin
// Prefer object over classes with only static members
object Analytics {
    fun track(event: String) { }
}
```

## Collections

```kotlin
// Use factory functions
val items = listOf("a", "b", "c")
val lookup = mapOf("key" to "value")

// Use buildList / buildMap for conditional construction
val items = buildList {
    add("always")
    if (condition) add("sometimes")
}

// Prefer collection operations over manual loops
val activeUsers = users.filter { it.isActive }.map { it.name }
```

## Coroutines

```kotlin
// Use structured concurrency — never use GlobalScope
class UserService(private val scope: CoroutineScope) {
    fun refresh() {
        scope.launch {
            val user = repository.fetchUser()
            _state.value = UiState.Success(user)
        }
    }
}

// Expose reactive data as Flow / StateFlow
class UserViewModel : ViewModel() {
    private val _state = MutableStateFlow<UiState>(UiState.Loading)
    val state: StateFlow<UiState> = _state.asStateFlow()
}
```

## Error Handling

```kotlin
// Use sealed types for expected errors
sealed interface Result<out T> {
    data class Success<T>(val data: T) : Result<T>
    data class Failure(val error: AppError) : Result<Nothing>
}

// Use specific exception types
class UserNotFoundError(id: String) : Exception("User not found: $id")

// Avoid catching generic Exception unless at a top-level boundary
try {
    processPayment(order)
} catch (e: InsufficientFundsError) {
    showError(e.message)
} catch (e: NetworkError) {
    retry(order)
}
```

## Anti-Patterns

### Magic Numbers

```kotlin
// Avoid
if (user.age > 18) { }

// Good
const val MINIMUM_AGE = 18
if (user.age > MINIMUM_AGE) { }
```

### Deep Nesting

```kotlin
// Avoid
fun processUser(user: User?) {
    if (user != null) {
        if (user.isActive) {
            if (user.hasPermission) {
                // ...
            }
        }
    }
}

// Good — early returns
fun processUser(user: User?) {
    val activeUser = user ?: return
    if (!activeUser.isActive) return
    if (!activeUser.hasPermission) return
    // ...
}
```

## Complexity Thresholds (detekt defaults)

| Metric | Warning |
|---|---|
| Cyclomatic complexity | 15 |
| Cognitive complexity | 15 |
| Long method | 60 lines |
| Large class | 600 lines |
| Functions per file | 11 |
| Complex condition | 3 conditions |
| Max return count | 2 |

## Tools

- **ktlint** — Formatting enforcement (auto-correctable)
- **detekt** — Static analysis (integrate via Gradle plugin)
- Run both in CI and as pre-commit hooks
- Configure in `build.gradle.kts`:

```kotlin
// detekt
plugins {
    id("io.gitlab.arturbosch.detekt") version "1.23+"
}

detekt {
    config.setFrom("$rootDir/config/detekt.yml")
    buildUponDefaultConfig = true
}
```

## Language-Specific Links

- [Kotlin Official Coding Conventions](https://kotlinlang.org/docs/coding-conventions.html)
- [Android Kotlin Style Guide](https://developer.android.com/kotlin/style-guide)
- [detekt Rule Sets](https://detekt.dev/docs/rules/)
- [ktlint Rules](https://pinterest.github.io/ktlint/latest/rules/standard/)
