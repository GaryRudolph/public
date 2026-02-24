# Testing — Kotlin

Follows [testing.md](../testing.md).

## Testing Pyramid

| Layer | Coverage | Tools |
|---|---|---|
| Unit | 80%+ | JUnit 5, Kotest, MockK, Turbine, kotlinx-coroutines-test |
| Integration | Critical paths | SQLDelight helpers, Ktor MockEngine, Room in-memory DB |
| UI | Core flows | Compose UI Testing, Espresso |

## JUnit 5

Backtick names for readable descriptions. `@Nested` for grouping:

```kotlin
class UserServiceTest {
    @Nested
    inner class CreateUser {
        @Test
        fun `should create user with valid data`() { }

        @Test
        fun `should throw when email already exists`() { }
    }
}
```

### Parameterized Tests

```kotlin
@ParameterizedTest
@CsvSource("1, 2", "2, 4", "-1, -2")
fun `should double the input`(input: Int, expected: Int) {
    assertEquals(expected, double(input))
}
```

## Coroutine Testing

```kotlin
@Test
fun `should fetch user from repository`() = runTest {
    val repo = mockk<UserRepository>()
    coEvery { repo.findById("123") } returns User("123", "Alice")
    val service = UserService(repo)
    assertEquals("Alice", service.getUser("123").name)
}
```

`runTest` provides virtual time control — never use `delay()` or `Thread.sleep()`.

## MockK

```kotlin
val paymentService = mockk<PaymentService>()
coEvery { paymentService.charge(any()) } returns PaymentResult.Success

// Argument capture
val slot = slot<User>()
coEvery { repo.save(capture(slot)) } returns Unit
```

- `mockk<T>()` for strict mocks; avoid `relaxed = true` except prototyping
- `coEvery` / `coVerify` for suspend functions
- `clearMocks()` in `@AfterEach`
- Prefer fakes over mocks when feasible

## Turbine (Flow Testing)

```kotlin
@Test
fun `should emit loading then success`() = runTest {
    viewModel.state.test {
        assertEquals(UiState.Loading, awaitItem())
        assertEquals(UiState.Success(expectedData), awaitItem())
        cancelAndConsumeRemainingEvents()
    }
}
```

Always call `cancelAndConsumeRemainingEvents()` or `ensureAllEventsConsumed()`.

## Compose UI Testing

```kotlin
@get:Rule
val composeRule = createComposeRule()

@Test
fun `should show error for invalid email`() {
    composeRule.setContent { LoginScreen(viewModel = LoginViewModel()) }
    composeRule.onNodeWithTag("email_input").performTextInput("invalid-email")
    composeRule.onNodeWithTag("login_button").performClick()
    composeRule.onNodeWithText("Invalid email format").assertIsDisplayed()
}
```

- `Modifier.testTag("tag")` on composables; find with `onNodeWithTag`
- Use `waitUntil {}` for async content — never `Thread.sleep()`
- Test what the user sees, not implementation details
