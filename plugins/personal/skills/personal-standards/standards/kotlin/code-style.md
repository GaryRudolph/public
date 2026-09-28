# Code Style — Kotlin

Follows [code-style.md](../code-style.md) and [Kotlin Official Coding Conventions](https://kotlinlang.org/docs/coding-conventions.html).

## Naming

- **camelCase** for functions, properties, locals: `userName`, `calculateTotal()`
- **PascalCase** for classes, interfaces, objects, enum entries: `UserRepository`, `sealed class UiState`
- **SCREAMING_SNAKE_CASE** for `const val` and top-level constants: `const val MAX_RETRY_ATTEMPTS = 3`
- **PascalCase** for file names matching top-level class: `UserService.kt`
- Backing properties: `private val _state` / `val state`
- Test functions may use backtick names: `` fun `should return user when ID exists`() ``

## Formatting

- **4-space indentation**, no tabs; **100-char** line limit
- K&R braces; single blank line between top-level declarations; no semicolons

## File Headers

Open-source: copyright + license before package declaration. Private: shorter or none — be consistent.

## Module Structure

```kotlin
package com.example.user

import kotlinx.coroutines.flow.StateFlow
import com.example.data.UserRepository

const val DEFAULT_TIMEOUT = 5000L

data class User(val id: String, val name: String)

class UserService { }

fun User.displayName(): String = "$name ($id)"
```

No wildcard imports.

## Key Idioms

- Prefer `val` over `var`; expression bodies for single-expression functions
- `when` over cascading `if-else`
- `require()` / `check()` for preconditions
- Scope functions: `let` for nullable transforms, `apply` for configuration, `also` for side effects
- Destructuring where it improves clarity: `val (name, email) = user`

## Type System

- `data class` for DTOs and value objects
- `sealed interface` / `sealed class` for finite state sets
- `enum class` only for simple singleton variants
- `object` for singletons and namespaces

```kotlin
sealed interface UiState {
    data object Loading : UiState
    data class Success(val data: List<Item>) : UiState
    data class Error(val message: String) : UiState
}
```

## Collections

```kotlin
val items = buildList {
    add("always")
    if (condition) add("sometimes")
}

val activeUsers = users.filter { it.isActive }.map { it.name }
```

## Coroutines

- Structured concurrency — never `GlobalScope`
- Expose reactive data as `Flow` / `StateFlow`

```kotlin
class UserViewModel : ViewModel() {
    private val _state = MutableStateFlow<UiState>(UiState.Loading)
    val state: StateFlow<UiState> = _state.asStateFlow()
}
```

## Error Handling

```kotlin
sealed interface Result<out T> {
    data class Success<T>(val data: T) : Result<T>
    data class Failure(val error: AppError) : Result<Nothing>
}
```

Catch specific exceptions; avoid catching generic `Exception` unless at a top-level boundary.

## Complexity Thresholds (detekt)

| Metric | Warning |
|---|---|
| Cyclomatic complexity | 15 |
| Cognitive complexity | 15 |
| Long method | 60 lines |
| Large class | 600 lines |
| Complex condition | 3 conditions |

## Tools

- **ktlint** — formatting; **detekt** — static analysis
- Run both in CI and as pre-commit hooks

```kotlin
plugins { id("io.gitlab.arturbosch.detekt") version "1.23+" }
detekt {
    config.setFrom("$rootDir/config/detekt.yml")
    buildUponDefaultConfig = true
}
```
