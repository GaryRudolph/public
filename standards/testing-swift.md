# Testing — Swift

Follows general principles in [testing.md](testing.md).

## Testing Frameworks

### Swift Testing (Xcode 16+, preferred for new code)

```swift
import Testing

@Suite("User Service")
struct UserServiceTests {

    @Test("creates user with valid data")
    func createUserValid() async throws {
        let service = UserService(repo: FakeUserRepository())
        let user = try await service.createUser(data: validUserData)

        #expect(user.name == "Alice")
        #expect(user.id != nil)
    }

    @Test("throws for duplicate email")
    func createUserDuplicate() async {
        let repo = FakeUserRepository(existing: [existingUser])
        let service = UserService(repo: repo)

        await #expect(throws: DuplicateEmailError.self) {
            try await service.createUser(data: existingUser.toCreateData())
        }
    }
}
```

**Key features:**
- Use `@Test` functions instead of `XCTestCase` subclasses
- Use `#expect(condition)` for soft assertions (test continues on failure)
- Use `#require(condition)` for hard preconditions (test aborts on failure)
- Organize with `@Suite` types for hierarchical grouping
- Use **tags** to categorize tests: `@Test(.tags(.networking))`
- Parameterize tests instead of copy-pasting:

```swift
@Test("validates email formats", arguments: [
    "user@example.com",
    "name+tag@domain.co",
    "user@subdomain.domain.com",
])
func validEmails(email: String) throws {
    #expect(isValidEmail(email))
}
```

Tests run in parallel by default — design for isolation from the start.

### XCTest (existing codebases)

```swift
import XCTest
@testable import MyModule

final class UserServiceTests: XCTestCase {

    private var sut: UserService!
    private var mockRepo: MockUserRepository!

    override func setUpWithError() throws {
        mockRepo = MockUserRepository()
        sut = UserService(repo: mockRepo)
    }

    override func tearDownWithError() throws {
        sut = nil
        mockRepo = nil
    }

    func testCreateUser_withValidData_shouldReturnUser() async throws {
        // Arrange
        let data = CreateUserData(name: "Alice", email: "alice@example.com")

        // Act
        let user = try await sut.createUser(data: data)

        // Assert
        XCTAssertEqual(user.name, "Alice")
        XCTAssertNotNil(user.id)
    }

    func testCreateUser_withDuplicateEmail_shouldThrow() async {
        // Arrange
        mockRepo.existingEmails = ["alice@example.com"]
        let data = CreateUserData(name: "Alice", email: "alice@example.com")

        // Act & Assert
        do {
            _ = try await sut.createUser(data: data)
            XCTFail("Expected DuplicateEmailError")
        } catch is DuplicateEmailError {
            // Expected
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }
}
```

**XCTest naming convention:** `test<MethodName>_<scenario>_<expectedResult>`

**Rules:**
- Use `setUpWithError()` and `tearDownWithError()` (the throwing variants)
- Never use `sleep()` — use `XCTestExpectation` / `fulfillment(of:timeout:)` for async
- Tests must be independent — no ordering dependencies, no shared mutable state
- Use `@testable import` to access internal members

## Test Organization

```
Sources/
├── UserService/
│   ├── UserService.swift
│   └── UserRepository.swift
Tests/
├── UserServiceTests/
│   ├── UserServiceTests.swift
│   └── UserRepositoryTests.swift
├── IntegrationTests/
│   └── UserFlowIntegrationTests.swift
└── UITests/
    └── LoginUITests.swift
```

- Mirror the source directory structure in test targets
- Separate unit tests, integration tests, and UI tests into distinct targets
- Aim for **>80% code coverage** on business logic / domain layer
- Don't test private methods directly — test through public interfaces
- Use test plans in Xcode to define test configurations (devices, locales, sanitizers)

## Mocking and Dependency Injection

### Protocol-Based Mocking

```swift
protocol UserRepository: Sendable {
    func findById(_ id: String) async throws -> User?
    func save(_ user: User) async throws -> User
}

// Production implementation
struct DatabaseUserRepository: UserRepository {
    func findById(_ id: String) async throws -> User? { /* ... */ }
    func save(_ user: User) async throws -> User { /* ... */ }
}

// Test fake
struct FakeUserRepository: UserRepository {
    var users: [User] = []

    func findById(_ id: String) async throws -> User? {
        users.first { $0.id == id }
    }

    func save(_ user: User) async throws -> User {
        var copy = user
        copy.id = UUID().uuidString
        return copy
    }
}
```

**Rules:**
- Define dependencies as protocols; inject via initializer
- Prefer fakes over mocks where feasible (in-memory implementations)
- Never mock what you don't own — wrap third-party APIs in your own protocols
- Use `Actor`-isolated test doubles for concurrency-safe mocking

## Snapshot Testing

Using [swift-snapshot-testing](https://github.com/pointfreeco/swift-snapshot-testing):

```swift
import SnapshotTesting
import Testing

@Suite("Profile View Snapshots")
struct ProfileViewSnapshotTests {

    @Test("renders default state")
    func defaultState() {
        let view = ProfileView(user: .sample)
        assertSnapshot(of: view, as: .image(layout: .device(config: .iPhone13)))
    }

    @Test("renders loading state")
    func loadingState() {
        let view = ProfileView(user: nil, isLoading: true)
        assertSnapshot(of: view, as: .image(layout: .device(config: .iPhone13)))
    }
}
```

**Rules:**
- Record snapshots explicitly with `record: .all`; commit reference images to git
- Test on **fixed device configurations** to avoid flaky diffs
- Use `.dump` or `.recursiveDescription` strategies for non-visual structural assertions
- Supports both XCTest and Swift Testing as of v1.17.0+

## UI Testing

```swift
import XCTest

final class LoginUITests: XCTestCase {

    private var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["--uitesting"]
        app.launch()
    }

    func testLogin_withValidCredentials_shouldShowDashboard() {
        let emailField = app.textFields["email_input"]
        let passwordField = app.secureTextFields["password_input"]
        let loginButton = app.buttons["login_button"]

        emailField.tap()
        emailField.typeText("user@example.com")
        passwordField.tap()
        passwordField.typeText("validpassword")
        loginButton.tap()

        let dashboard = app.staticTexts["dashboard_title"]
        XCTAssertTrue(dashboard.waitForExistence(timeout: 5))
    }

    func testLogin_withInvalidEmail_shouldShowError() {
        let emailField = app.textFields["email_input"]
        emailField.tap()
        emailField.typeText("invalid-email")
        app.buttons["login_button"].tap()

        let error = app.staticTexts["error_message"]
        XCTAssertTrue(error.waitForExistence(timeout: 2))
    }
}
```

**Rules:**
- Set `accessibilityIdentifier` on all interactive elements — never query by frame position or label text
- Use Page Object pattern: each screen gets a helper struct that encapsulates element queries
- Keep UI tests focused on critical user flows (login, purchase, onboarding) — they're slow
- Use launch arguments/environment to configure app state: `app.launchArguments = ["--uitesting"]`

## Async Testing Patterns

### Swift Testing

```swift
@Test("fetches user from network")
func fetchUser() async throws {
    let service = UserService(client: MockHTTPClient())
    let user = try await service.fetchUser(id: "123")
    #expect(user.name == "Alice")
}
```

### XCTest with Expectations

```swift
func testNotificationReceived() {
    let expectation = expectation(description: "notification received")

    NotificationCenter.default.addObserver(
        forName: .userLoggedIn,
        object: nil,
        queue: .main
    ) { _ in
        expectation.fulfill()
    }

    sut.login(credentials: validCredentials)

    wait(for: [expectation], timeout: 2.0)
}
```

## TDD Workflow

1. **Red** — Write a failing test that describes the desired behavior
2. **Green** — Write the minimum code to make the test pass
3. **Refactor** — Clean up while keeping tests green

Run tests on every save (Xcode continuous testing or `swift test` in CI). Gate all PRs on passing tests — no merging with red tests.

## General Rules

- One logical assertion per test (related assertions may be grouped, but test one behavior)
- Test both success and failure paths
- Keep tests independent — no shared mutable state between tests
- Run tests in CI on every PR; fail the build on any test failure

## References

- [Apple Swift Testing](https://developer.apple.com/documentation/testing/)
- [XCTest Documentation](https://developer.apple.com/documentation/xctest)
- [swift-snapshot-testing](https://github.com/pointfreeco/swift-snapshot-testing)
- [Swift Testing Migration Guide](https://developer.apple.com/documentation/testing/migratingfromanxctestbasedtesttoaswifttestingtest)
