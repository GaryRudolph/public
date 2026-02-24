# Testing Standards

## Coverage Requirements

- **Unit Tests**: 80% code coverage for business logic
- **Integration Tests**: all critical user paths
- **E2E Tests**: core user flows and happy paths

### What to Test

**Always**: business logic, data transformations, edge cases, public APIs, security-critical code

**Skip**: third-party library internals, simple getters/setters without logic, framework boilerplate

## Test Structure

- **Colocated tests** (preferred for libraries) — test files alongside source
- **Separate test directory** (common for apps) — mirrored in a parallel tree
- Mirror source directory structure so finding tests is obvious

### Naming

Descriptive names that read as sentences: "creates user with valid data", "throws when email already exists". Avoid `test_1` or `test_works`.

### Conventions

- Always annotate test functions with void/`None` return type
- Include a one-line description of what the test verifies

## Mocking Rules

### When to Mock

External APIs, slow operations, non-deterministic behavior (dates, random)

### When Not to Mock

Simple pure functions, the code under test, internal business logic

### Preferences

- **Fakes** (in-memory implementations) over mock objects — more realistic, don't couple to call sequences
- **Dependency injection** over patching/monkey-patching — explicit setup, no hidden coupling
- Never mock what you don't own — wrap third-party APIs and mock the wrapper

## Anti-Patterns

- **Testing implementation** — assert on observable behavior, not internal state
- **Brittle assertions** — assert only fields that matter; avoid comparing full objects with timestamps
- **Test interdependence** — each test sets up its own data; no execution order reliance
- **Over-mocking** — more mocks than real objects means you should use fakes or rethink the design
- **Sleeping** — use async wait/polling or test-controlled time instead of `sleep()`

## Cross-Language Testing Parallels

| Concept | Python | Swift | Kotlin |
|---|---|---|---|
| Framework | pytest | Swift Testing / XCTest | JUnit 5 / Kotest |
| Mocking | unittest.mock, fakes | Protocol-based fakes | MockK, fakes |
| Async | pytest-asyncio | `async throws` | kotlinx-coroutines-test |
| UI testing | Playwright | XCUITest | Compose UI Testing |
| Coverage | pytest-cov | Xcode coverage | JaCoCo / Kover |

## Language-Specific Testing

- **[Python](python/testing.md)**
- **[Swift](swift/testing.md)**
- **[Kotlin](kotlin/testing.md)**
