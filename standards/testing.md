# Testing Standards

## Testing Philosophy

- **Write tests first** - Consider TDD for complex logic
- **Test behavior, not implementation** - Tests should survive refactoring
- **Fast feedback** - Tests should run quickly
- **Independent tests** - Tests should not depend on each other
- **Clear failures** - When tests fail, it should be obvious why

## Test Coverage

### Minimum Requirements
- **Unit Tests**: 80% code coverage for business logic
- **Integration Tests**: All critical user paths
- **E2E Tests**: Core user flows and happy paths

### What to Test
**Always test:**
- Business logic and calculations
- Data transformations
- Edge cases and error conditions
- Public APIs and interfaces
- Security-critical code

**Don't test:**
- Third-party library internals
- Simple getters/setters without logic
- Framework boilerplate

## Test Structure

### Test Organization

Choose a layout that fits the project type:

- **Colocated tests** (preferred for libraries) — test files live alongside source files
- **Separate test directory** (common for applications) — tests mirrored in a parallel directory tree, optionally split by unit / integration / e2e

Mirror the source directory structure in the test directory so that finding the tests for a given module is obvious.

### Test Naming

Use descriptive names that explain the scenario being tested. A good test name reads as a sentence: "creates user with valid data", "throws when email already exists". Avoid vague names like `test_1` or `test_works`.

### Test Function Conventions

- Always annotate test functions with a void/`None` return type
- Include a one-line description of what the test verifies (docstring, display name, or backtick name depending on language)

### AAA Pattern (Arrange, Act, Assert)

Structure each test in three phases:

1. **Arrange** — set up test data and dependencies
2. **Act** — execute the code under test
3. **Assert** — verify the result

Keep each phase short. If Arrange is long, extract shared setup into fixtures or helper functions.

## Unit Testing

### Principles
- Test one thing at a time
- Mock external dependencies
- Fast execution (< 100ms per test)
- No network or file system access

## Integration Testing

### Purpose
- Test interaction between modules
- Use real dependencies where practical
- Test database operations, API calls, message queues

### Principles
- Use test-scoped resources (in-memory databases, mock servers, service emulators)
- Clean up state between tests to maintain independence
- Use skip markers with a reason when tests cannot run in a mock environment

## End-to-End Testing

### Purpose
- Test complete user workflows
- Use real environment (or close to it)
- Fewer tests, higher confidence

### Principles
- Focus on critical user flows (login, purchase, onboarding)
- E2E tests are slow — keep the suite small and targeted
- Use accessibility identifiers or semantic selectors, not position-based queries

## Test Data Management

### Principles
- Use **fixtures** for shared test setup; scope them appropriately (per-test for mutable state, per-session for expensive resources)
- Use **static test data** (constants or dictionaries) for simple, reusable values
- Use **factory functions** when tests need many similar-but-unique objects
- Prefer generating unique data (UUIDs, incrementing IDs) to avoid cross-test collisions

## Mocking Best Practices

### When to Mock
- External APIs and third-party services
- Slow operations (database, file system, network)
- Non-deterministic behavior (dates, random numbers)

### When Not to Mock
- Simple pure functions
- The code under test itself
- Internal business logic

### Principles
- Prefer **fakes** (in-memory implementations) over mock objects when feasible — fakes are more realistic and don't couple tests to call sequences
- Prefer **dependency injection** over patching/monkey-patching — injection makes test setup explicit and avoids hidden coupling to module paths
- Never mock what you don't own — wrap third-party APIs in your own abstractions and mock those

## Testing Anti-Patterns

- **Testing implementation details** — assert on observable behavior (return values, side effects), not internal state or private fields
- **Brittle assertions** — assert only the fields that matter for the scenario; avoid comparing entire objects with timestamps or auto-generated IDs
- **Test interdependence** — each test must set up its own data; never rely on execution order or shared mutable state
- **Over-mocking** — if a test has more mocks than real objects, consider using fakes or rethinking the design
- **Sleeping in tests** — use async wait/polling or test-controlled time instead of `sleep()`

## Performance Testing

- Use dedicated load-testing tools (Locust, k6, Artillery) for performance benchmarks
- For unit-level performance assertions, measure wall-clock time and assert an upper bound
- Test realistic scenarios under expected and peak load

## Continuous Testing

- Run the full test suite in CI on every pull request
- Fail the build on any test failure — no merging with red tests
- Run linting and type checking alongside tests in CI
- Use pre-commit hooks to catch issues before push
- Gate deployments on passing tests

## Test Documentation

Document:
- Complex test setup and environment requirements
- Non-obvious test scenarios and why they exist
- Reasons for skipped tests
- How to run specific test suites

## Cross-Language Testing Parallels

| Concept | Python | Swift | Kotlin |
|---|---|---|---|
| Framework | pytest | Swift Testing / XCTest | JUnit 5 / Kotest |
| Mocking | unittest.mock, fakes | Protocol-based fakes | MockK, fakes |
| Async testing | pytest-asyncio | `async throws` | kotlinx-coroutines-test |
| UI testing | Playwright | XCUITest | Compose UI Testing |
| Snapshot testing | — | swift-snapshot-testing | — |
| Property-based | Hypothesis | — | Kotest property |
| Flow/state testing | — | — | Turbine |
| Coverage | pytest-cov | Xcode coverage | JaCoCo / Kover |

## Language-Specific Testing

- **[Python](python/testing.md)** - pytest config, Hypothesis, coverage, fixtures, monkeypatch, moto/AWS, integration patterns
- **[Swift](swift/testing.md)** - Swift Testing, XCTest, snapshot testing, UI testing
- **[Kotlin](kotlin/testing.md)** - JUnit 5, MockK, Kotest, Turbine, Compose UI testing
