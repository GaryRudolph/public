# Documentation — Kotlin

Follows [documentation.md](../documentation.md).

## KDoc Format

`/** ... */` with [KDoc syntax](https://kotlinlang.org/docs/kotlin-doc.html). First paragraph = summary; block tags last.

### Function Documentation

```kotlin
/**
 * Calculates the total price including tax and discount.
 *
 * @param items list of items with price and quantity
 * @param taxRate tax rate as decimal (e.g., 0.08 for 8%)
 * @param discountCode optional discount code to apply
 * @return the total price after tax and discount
 * @throws ValidationException if items list is empty
 */
fun calculateTotal(items: List<Item>, taxRate: Double, discountCode: String? = null): Double { }
```

### Class Documentation

```kotlin
/**
 * Service for managing user accounts.
 *
 * Uses [UserRepository] for persistence and [EmailService] for notifications.
 * Safe to use from multiple coroutines concurrently.
 *
 * @property repo the backing user repository
 */
class UserService(private val repo: UserRepository) { }
```

## Required Block Tags

| Tag | Usage |
|---|---|
| `@param name` | Every function/constructor parameter |
| `@return` | Every non-`Unit` return |
| `@throws ExType` | Every documented exception |
| `@property name` | Class-level property documentation |
| `@sample` | Link to runnable usage examples |
| `@see` | Cross-references to related APIs |

## What to Document

**Always**: all `public`/`protected` APIs, non-obvious `internal` APIs, thread safety, nullability contracts

**Skip**: `private` members (unless complex), self-explanatory enum entries, overrides that don't change behavior

## Formatting

- Markdown for inline formatting; `[ClassName]` for KDoc cross-references
- Don't mix KDoc link syntax with Markdown link syntax in same block
- Backticks for inline code: `` `null` ``, `` `StateFlow` ``

## Deprecation

```kotlin
@Deprecated(
    message = "Use fetchUser(id) instead",
    replaceWith = ReplaceWith("fetchUser(id)"),
    level = DeprecationLevel.WARNING,
)
fun getUser(id: String): User { }
```

## Tools

**Dokka** — official Kotlin documentation engine: `./gradlew dokkaHtml`
