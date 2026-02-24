# Testing — Kotlin

Follows general principles in [testing.md](testing.md).

## Testing Pyramid

| Layer | Coverage Target | Tools |
|---|---|---|
| Unit Tests | 80%+ | JUnit 5, Kotest, MockK, Turbine, kotlinx-coroutines-test |
| Integration Tests | Critical paths | SQLDelight test helpers, Ktor MockEngine, Room in-memory DB |
| UI Tests | Core user flows | Compose UI Testing, Espresso |

## JUnit 5 Patterns

### Test Naming

Use backtick names for readable test descriptions:

```kotlin
class UserServiceTest {

    @Nested
    inner class CreateUser {

        @Test
        fun `should create user with valid data`() {
            // ...
        }

        @Test
        fun `should throw when email already exists`() {
            // ...
        }

        @Test
        fun `should send welcome email after creation`() {
            // ...
        }
    }
}
```

### Parameterized Tests

```kotlin
@ParameterizedTest
@CsvSource(
    "1, 2",
    "2, 4",
    "-1, -2",
)
fun `should double the input`(input: Int, expected: Int) {
    assertEquals(expected, double(input))
}

@ParameterizedTest
@MethodSource("invalidEmails")
fun `should reject invalid email formats`(email: String) {
    assertThrows<ValidationException> { validateEmail(email) }
}

companion object {
    @JvmStatic
    fun invalidEmails() = listOf("", "no-at-sign", "@no-local", "spaces in@email.com")
}
```

### Exception Testing

```kotlin
@Test
fun `should throw when input is negative`() {
    val exception = assertThrows<IllegalArgumentException> {
        withdraw(-100.0)
    }
    assertEquals("Amount must be positive: -100.0", exception.message)
}
```

## Coroutine Testing

Use `kotlinx-coroutines-test` for all coroutine tests:

```kotlin
@Test
fun `should fetch user from repository`() = runTest {
    val repo = mockk<UserRepository>()
    coEvery { repo.findById("123") } returns User("123", "Alice")

    val service = UserService(repo)
    val user = service.getUser("123")

    assertEquals("Alice", user.name)
}
```

`runTest` provides a `TestDispatcher` with virtual time control — never use `delay()` or `Thread.sleep()` to wait in tests.

## MockK

### Basic Mocking

```kotlin
@Test
fun `should process payment before saving order`() = runTest {
    val paymentService = mockk<PaymentService>()
    val orderRepo = mockk<OrderRepository>()

    coEvery { paymentService.charge(any()) } returns PaymentResult.Success
    coEvery { orderRepo.save(any()) } returns Order(id = "order-1")

    val service = OrderService(paymentService, orderRepo)
    service.createOrder(orderData)

    coVerify(ordering = Ordering.ORDERED) {
        paymentService.charge(any())
        orderRepo.save(any())
    }
}
```

### Argument Capture

```kotlin
@Test
fun `should save user with hashed password`() = runTest {
    val repo = mockk<UserRepository>()
    val slot = slot<User>()
    coEvery { repo.save(capture(slot)) } returns Unit

    val service = UserService(repo)
    service.createUser(CreateUserData(email = "a@b.com", password = "secret"))

    assertNotEquals("secret", slot.captured.passwordHash)
}
```

### Best Practices

- Use `mockk<T>()` for strict mocks — avoid `relaxed = true` except for prototyping
- Use `coEvery` / `coVerify` for suspend functions
- Call `clearMocks()` or `unmockkAll()` in `@AfterEach` to prevent test pollution
- Prefer fakes (in-memory repository implementations) over mocks when feasible
- MockK handles final classes, extension functions, and coroutines natively

## Turbine for Flow Testing

```kotlin
@Test
fun `should emit loading then success`() = runTest {
    val viewModel = UserViewModel(fakeRepo)

    viewModel.state.test {
        assertEquals(UiState.Loading, awaitItem())
        assertEquals(UiState.Success(expectedData), awaitItem())
        cancelAndConsumeRemainingEvents()
    }
}

@Test
fun `should not emit after cancellation`() = runTest {
    val flow = flowOf(1, 2, 3)

    flow.test {
        assertEquals(1, awaitItem())
        assertEquals(2, awaitItem())
        assertEquals(3, awaitItem())
        awaitComplete()
    }
}
```

- Always call `cancelAndConsumeRemainingEvents()` or `ensureAllEventsConsumed()` at the end
- Use `awaitItem()` for expected emissions, `expectNoEvents()` for confirming silence
- Use `awaitError()` for expected error terminal events

## Kotest

Use Kotest as an alternative or complement to JUnit 5:

```kotlin
class UserServiceSpec : FunSpec({

    test("should create user with valid data") {
        val service = UserService(FakeUserRepository())
        val user = service.createUser(validData)
        user.name shouldBe "Alice"
        user.id.shouldNotBeNull()
    }

    test("should throw for duplicate email") {
        val repo = FakeUserRepository(existing = listOf(existingUser))
        val service = UserService(repo)
        shouldThrow<DuplicateEmailException> {
            service.createUser(existingUser.toCreateData())
        }
    }
})
```

### Property-Based Testing

```kotlin
class SortSpec : FunSpec({

    test("sort should be idempotent") {
        checkAll(Arb.list(Arb.int())) { xs ->
            xs.sorted().sorted() shouldBe xs.sorted()
        }
    }
})
```

Use property-based testing for functions with broad input spaces (parsers, serializers, algorithms).

## Compose UI Testing

```kotlin
class LoginScreenTest {

    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun `should show error for invalid email`() {
        composeRule.setContent {
            LoginScreen(viewModel = LoginViewModel())
        }

        composeRule.onNodeWithTag("email_input")
            .performTextInput("invalid-email")
        composeRule.onNodeWithTag("login_button")
            .performClick()
        composeRule.onNodeWithText("Invalid email format")
            .assertIsDisplayed()
    }

    @Test
    fun `should navigate to dashboard on success`() {
        composeRule.setContent {
            LoginScreen(viewModel = fakeSuccessViewModel)
        }

        composeRule.onNodeWithTag("email_input")
            .performTextInput("user@example.com")
        composeRule.onNodeWithTag("password_input")
            .performTextInput("validpassword")
        composeRule.onNodeWithTag("login_button")
            .performClick()

        composeRule.waitUntil { /* dashboard visible */ }
        composeRule.onNodeWithTag("dashboard_screen")
            .assertIsDisplayed()
    }
}
```

### Compose Testing Rules

- Apply `Modifier.testTag("tag")` to composables; find with `onNodeWithTag("tag")`
- Also use semantic finders: `onNodeWithText()`, `onNodeWithContentDescription()`
- Actions: `performClick()`, `performTextInput()`, `performScrollTo()`
- Assertions: `assertIsDisplayed()`, `assertTextEquals()`, `assertIsEnabled()`
- Use `waitUntil {}` for async content — never `Thread.sleep()`
- Test state transitions, not implementation details — assert what the user sees

## General Rules

- Every public function in domain/data layers has at least one unit test
- Test both success and failure paths — especially error mapping
- Keep tests independent — no shared mutable state between tests
- Run tests in CI on every PR; fail the build on any test failure
- Use fakes over mocks when feasible (e.g., in-memory repository implementations)

## References

- [JUnit 5 User Guide](https://junit.org/junit5/docs/current/user-guide/)
- [MockK Documentation](https://mockk.io/)
- [Kotest Documentation](https://kotest.io/)
- [Turbine (Cash App)](https://github.com/cashapp/turbine)
- [Compose Testing](https://developer.android.com/jetpack/compose/testing)
- [kotlinx-coroutines-test](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-test/)
