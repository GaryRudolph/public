# Testing — Swift

Follows [testing.md](../testing.md).

## Swift Testing (Xcode 16+, preferred for new code)

```swift
import Testing

@Suite("User Service")
struct UserServiceTests {
    @Test("creates user with valid data")
    func createUserValid() async throws {
        let service = UserService(repo: FakeUserRepository())
        let user = try await service.createUser(data: validUserData)
        #expect(user.name == "Alice")
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

- `#expect(condition)` for soft assertions; `#require(condition)` for hard preconditions
- `@Suite` for hierarchical grouping; tags for categorization: `@Test(.tags(.networking))`
- Parameterize tests: `@Test("validates emails", arguments: [...])`
- Tests run in parallel — design for isolation

## XCTest (existing codebases)

- Naming: `test<Method>_<scenario>_<expectedResult>`
- Use `setUpWithError()` / `tearDownWithError()` (throwing variants)
- Never `sleep()` — use `XCTestExpectation` / `fulfillment(of:timeout:)`
- `@testable import` for internal member access

## Test Organization

```
Sources/UserService/
Tests/
├── UserServiceTests/
├── IntegrationTests/
└── UITests/
```

- Mirror source structure; separate unit/integration/UI into distinct targets
- **>80% coverage** on business logic / domain layer
- Don't test private methods — test through public interfaces

## Protocol-Based Mocking

```swift
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

- Define dependencies as protocols; inject via init
- Prefer fakes over mocks; never mock what you don't own
- Use `Actor`-isolated test doubles for concurrency-safe mocking

## Snapshot Testing

Using [swift-snapshot-testing](https://github.com/pointfreeco/swift-snapshot-testing):

```swift
@Test("renders default state")
func defaultState() {
    let view = ProfileView(user: .sample)
    assertSnapshot(of: view, as: .image(layout: .device(config: .iPhone13)))
}
```

Record with `record: .all`; commit reference images. Test on fixed device configs.

## UI Testing

```swift
func testLogin_withValidCredentials_shouldShowDashboard() {
    let emailField = app.textFields["email_input"]
    emailField.tap()
    emailField.typeText("user@example.com")
    app.buttons["login_button"].tap()
    XCTAssertTrue(app.staticTexts["dashboard_title"].waitForExistence(timeout: 5))
}
```

- `accessibilityIdentifier` on all interactive elements
- Page Object pattern: each screen gets a helper struct
- Launch arguments for test configuration: `app.launchArguments = ["--uitesting"]`
