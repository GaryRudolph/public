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
```
src/
├── feature/
│   ├── service.py
│   └── tests/
│       ├── test_service.py
│       └── test_service_integration.py
└── tests/
    ├── unit/           # Additional unit tests
    ├── integration/    # Integration tests
    └── e2e/            # End-to-end tests
```

### Test Naming
Use descriptive names that explain the scenario:

```python
# Good - describes behavior
class TestUserService:
    class TestCreateUser:
        def test_creates_user_with_valid_data(self): ...
        def test_raises_validation_error_when_email_is_invalid(self): ...
        def test_sends_welcome_email_after_user_creation(self): ...

# Avoid - vague names
class TestUserService:
    def test_1(self): ...
    def test_works(self): ...
```

### AAA Pattern (Arrange, Act, Assert)
```python
def test_calculates_total_with_discount():
    # Arrange - setup test data
    items = [
        {"price": 10, "quantity": 2},
        {"price": 5, "quantity": 1},
    ]
    discount = 0.1

    # Act - execute the code under test
    total = calculate_total(items, discount)

    # Assert - verify the result
    assert total == 22.5  # (10*2 + 5*1) * 0.9
```

## Unit Testing

### Principles
- Test one thing at a time
- Mock external dependencies
- Fast execution (< 100ms per test)
- No network or file system access

### Example
```python
from unittest.mock import MagicMock, AsyncMock
import pytest

@pytest.fixture
def mock_order_repository():
    repo = MagicMock()
    repo.save = AsyncMock()
    repo.find_by_id = AsyncMock()
    return repo

@pytest.fixture
def mock_payment_service():
    svc = MagicMock()
    svc.process_payment = AsyncMock()
    return svc

@pytest.fixture
def order_service(mock_order_repository, mock_payment_service):
    return OrderService(mock_order_repository, mock_payment_service)

class TestOrderService:
    class TestCreateOrder:
        async def test_creates_order_and_processes_payment(
            self, order_service, mock_order_repository, mock_payment_service
        ):
            # Arrange
            order_data = {"items": [{"id": "1", "quantity": 2}]}
            mock_payment_service.process_payment.return_value = {"success": True}
            mock_order_repository.save.return_value = {"id": "order-1", **order_data}

            # Act
            result = await order_service.create_order(order_data)

            # Assert
            mock_payment_service.process_payment.assert_called_once()
            mock_order_repository.save.assert_called_once()
            assert result["id"] == "order-1"

        async def test_does_not_save_order_if_payment_fails(
            self, order_service, mock_order_repository, mock_payment_service
        ):
            # Arrange
            order_data = {"items": [{"id": "1", "quantity": 2}]}
            mock_payment_service.process_payment.side_effect = Exception("Payment failed")

            # Act & Assert
            with pytest.raises(Exception, match="Payment failed"):
                await order_service.create_order(order_data)
            mock_order_repository.save.assert_not_called()
```

## Integration Testing

### Purpose
- Test interaction between modules
- Use real dependencies where practical
- Test database operations, API calls

### Database Tests
```python
import pytest

@pytest.fixture(scope="session")
def db():
    database = create_test_database()
    yield database
    database.close()

@pytest.fixture(autouse=True)
def clean_db(db):
    yield
    db.execute("TRUNCATE users CASCADE")

class TestUserRepositoryIntegration:
    async def test_saves_and_retrieves_user(self, db):
        # Arrange
        user_repo = UserRepository(db)
        user = {"email": "test@example.com", "name": "Test User"}

        # Act
        saved = await user_repo.save(user)
        retrieved = await user_repo.find_by_id(saved["id"])

        # Assert
        assert retrieved["email"] == user["email"]
        assert retrieved["name"] == user["name"]

    async def test_raises_error_when_saving_duplicate_email(self, db):
        # Arrange
        user_repo = UserRepository(db)
        user = {"email": "test@example.com", "name": "Test User"}
        await user_repo.save(user)

        # Act & Assert
        with pytest.raises(Exception, match="Email already exists"):
            await user_repo.save(user)
```

## End-to-End Testing

### Purpose
- Test complete user workflows
- Use real environment (or close to it)
- Fewer tests, higher confidence

### Example
```python
import pytest
from playwright.sync_api import Page, expect

@pytest.fixture(scope="session")
def browser(playwright):
    browser = playwright.chromium.launch()
    yield browser
    browser.close()

@pytest.fixture
def page(browser):
    page = browser.new_page()
    page.goto("http://localhost:8000/register")
    yield page
    page.close()

class TestUserRegistrationFlow:
    def test_registers_new_user_successfully(self, page: Page):
        # Arrange & Act
        page.fill("#email", "newuser@example.com")
        page.fill("#password", "SecurePass123!")
        page.fill("#confirm-password", "SecurePass123!")
        page.click("button[type='submit']")
        page.wait_for_url("**/dashboard")

        # Assert
        expect(page).to_have_url(re.compile(r"/dashboard"))
        expect(page.locator(".welcome")).to_contain_text("Welcome")

    def test_shows_error_for_invalid_email(self, page: Page):
        # Act
        page.fill("#email", "invalid-email")
        page.fill("#password", "SecurePass123!")
        page.click("button[type='submit']")

        # Assert
        expect(page.locator(".error")).to_contain_text("Invalid email")
```

## Test Data Management

### Test Fixtures
```python
# tests/fixtures/users.py
valid_user = {
    "email": "user@example.com",
    "name": "Test User",
    "role": "user",
}

admin_user = {
    "email": "admin@example.com",
    "name": "Admin User",
    "role": "admin",
}

# Usage
from tests.fixtures.users import valid_user

async def test_creates_user():
    result = await user_service.create_user(valid_user)
    assert result["email"] == valid_user["email"]
```

### Factory Functions
```python
# tests/factories/user_factory.py
from itertools import count

_counter = count(1)

def create_user(**overrides) -> dict:
    n = next(_counter)
    return {
        "id": f"user-{n}",
        "email": f"user{n}@example.com",
        "name": "Test User",
        **overrides,
    }

# Usage
user1 = create_user(email="specific@example.com")
user2 = create_user()  # Gets auto-generated email
```

## Mocking Best Practices

### When to Mock
- External APIs
- Slow operations (database, file system)
- Non-deterministic behavior (dates, random)
- Third-party services

### When Not to Mock
- Simple pure functions
- Code under test
- Internal business logic

### Mock Examples
```python
from unittest.mock import patch, MagicMock
from datetime import datetime

# Mock external API
with patch("app.api.github.fetch_user") as mock_fetch:
    mock_fetch.return_value = {"id": "123", "name": "Test User"}
    result = fetch_user("123")

# Mock datetime
with patch("app.service.datetime") as mock_dt:
    mock_dt.utcnow.return_value = datetime(2024, 1, 1)
    result = service.create_event()

# Mock module-level config
with patch.dict("os.environ", {"API_KEY": "test-key", "API_URL": "http://test-api.com"}):
    result = service.call_api()
```

## Testing Async Code

### pytest-asyncio
```python
import pytest

@pytest.mark.asyncio
async def test_fetches_user_data():
    user = await user_service.get_user("123")
    assert user is not None
```

### Error Handling
```python
@pytest.mark.asyncio
async def test_raises_error_for_invalid_id():
    with pytest.raises(Exception, match="User not found"):
        await user_service.get_user("invalid")
```

## Test Assertions

### Use Specific Assertions
```python
# Good - specific assertions
assert value == 5
assert len(array) == 3
assert "substring" in string
assert obj["name"] == "John"
mock_fn.assert_called_with(arg1, arg2)

# Avoid - vague assertions
assert value > 0  # OK but prefer assertEqual when possible
assert bool(value)
```

### Custom Assertions
```python
import re

def assert_valid_email(email: str):
    pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    assert re.match(pattern, email), f"Expected {email!r} to be a valid email"

# Usage
assert_valid_email("user@example.com")
```

## Testing Anti-Patterns

### Don't Test Implementation Details
```python
# Avoid - testing internal state
def test_sets_internal_flag():
    service = UserService()
    service.some_method()
    assert service._internal_flag  # Bad!

# Good - test behavior
async def test_sends_notification_after_user_creation():
    await user_service.create_user(user_data)
    mock_notification_service.send.assert_called_once()
```

### Don't Write Brittle Tests
```python
# Avoid - too specific, breaks easily
assert result == {
    "id": "123",
    "name": "John",
    "email": "john@example.com",
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00",
    "version": 1,
}

# Good - test what matters
assert result["name"] == "John"
assert result["email"] == "john@example.com"
assert "id" in result
assert isinstance(result["created_at"], datetime)
```

### Avoid Test Interdependence
```python
# Avoid - tests depend on execution order
user_id = None

def test_creates_user():
    global user_id
    user = create_user()
    user_id = user["id"]  # Shared state!

def test_updates_user():
    update_user(user_id)  # Depends on previous test

# Good - each test is independent
async def test_creates_user():
    user = await create_user()
    assert "id" in user

async def test_updates_user():
    user = await create_user()  # Create own data
    updated = await update_user(user["id"])
    assert updated is not None
```

## Performance Testing

### Test Execution Time
```python
import time

def test_processes_large_dataset_efficiently():
    start = time.monotonic()
    result = process_large_dataset(data)
    duration = time.monotonic() - start

    assert duration < 1.0  # Should complete in < 1s
```

### Load Testing
- Use dedicated tools (Locust, k6, Artillery)
- Test realistic scenarios
- Monitor system resources

## Continuous Testing

### Pre-commit Hooks
```bash
# Run tests before commit
pytest

# Run linting
ruff check .
```

### CI/CD Pipeline
```yaml
# Example: GitHub Actions
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run unit tests
        run: pytest tests/unit
      - name: Run integration tests
        run: pytest tests/integration
      - name: Upload coverage
        uses: codecov/codecov-action@v4
```

## Test Documentation

Document:
- Complex test setup
- Non-obvious test scenarios
- Reasons for skipped tests
- Test environment requirements

```python
class TestAuthenticationIntegration:
    """
    Tests user authentication flow.

    Note: These tests require a test database to be running.
    Run `make test-db-setup` before executing.
    """
    # tests...
```
