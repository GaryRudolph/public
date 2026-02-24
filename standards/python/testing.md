# Testing — Python

Follows general principles in [testing.md](../testing.md).

## pytest Configuration

### pyproject.toml Setup

```toml
[tool.pytest.ini_options]
testpaths = ["tests", "src"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-ra --strict-markers"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks integration tests",
]
asyncio_mode = "auto"
```

### Coverage Configuration

```toml
[tool.coverage.run]
source = ["src"]
relative_files = true
omit = ["*/tests/*", "*/__pycache__/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.",
    "@overload",
    "raise NotImplementedError",
]
```

Run with: `pytest --cov=src --cov-report=term-missing`

### Coverage Thresholds

| Threshold | When to Use |
|---|---|
| **80%** | Industry-standard minimum; pragmatic for most projects |
| **90%** | Recommended for libraries and shared packages |
| **95%+** | Critical infrastructure, security-sensitive code |

## Test Organization

**Colocated tests** (preferred for libraries) — test files live alongside source with a `_test.py` suffix:

```
src/mypackage/
├── __init__.py
├── conftest.py              # Shared fixtures
├── models.py
├── models_test.py           # Tests for models
├── service.py
└── service_test.py          # Tests for service
```

**Separate test directory** (common for applications):

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

## Test Naming

Use descriptive names that explain the scenario:

```python
# Good - flat functions with docstrings (preferred for smaller modules)
def test_creates_user_with_valid_data(sample_user: dict) -> None:
    """Test that valid data produces a saved user."""
    ...

def test_raises_validation_error_when_email_is_invalid() -> None:
    """Test that invalid email raises ValidationError."""
    ...

# Good - class-based grouping (useful when a module has many tests)
class TestUserService:
    class TestCreateUser:
        def test_creates_user_with_valid_data(self) -> None: ...
        def test_raises_validation_error_when_email_is_invalid(self) -> None: ...
        def test_sends_welcome_email_after_user_creation(self) -> None: ...

# Avoid - vague names
class TestUserService:
    def test_1(self): ...
    def test_works(self): ...
```

### Test Function Conventions

- Always annotate test functions with `-> None` return type
- Always include a one-line docstring describing what the test verifies

## Fixtures

### Best Practices

```python
import pytest

@pytest.fixture
def user_repo():
    return FakeUserRepository()

@pytest.fixture
def user_service(user_repo):
    return UserService(repo=user_repo)
```

- Use `conftest.py` for shared fixtures across test modules
- Prefer **function scope** (default) for maximum test isolation
- Use **session scope** only for expensive resources (DB connections, Docker containers)
- Use `yield` fixtures for setup + teardown:

```python
@pytest.fixture
def db_session():
    session = create_test_session()
    yield session
    session.rollback()
    session.close()
```

- Use `Generator[YieldType, None, None]` as the return type for yield-based fixtures

### conftest.py Patterns

Use `conftest.py` for shared fixtures, colocated with the test files. Choose fixture scope based on cost:

```python
# conftest.py
import uuid
from typing import Generator

import pytest
from moto import mock_aws

@pytest.fixture(scope="session")
def aws_credentials() -> None:
    """Set mock AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

@pytest.fixture
def dynamodb_table(aws_credentials: None) -> Generator[None, None, None]:
    """Create and tear down a mock DynamoDB table."""
    mock = mock_aws()
    mock.start()
    try:
        MyModel.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        yield
    finally:
        mock.stop()

@pytest.fixture
def sample_id() -> uuid.UUID:
    """Generate a UUID for testing."""
    return uuid.uuid4()
```

### monkeypatch

Prefer `monkeypatch` for simple attribute/env var patching — it auto-reverts:

```python
def test_uses_custom_timeout(monkeypatch):
    monkeypatch.setenv("REQUEST_TIMEOUT", "5")
    service = create_service()
    assert service.timeout == 5

def test_overrides_default(monkeypatch):
    monkeypatch.setattr("app.config.DEFAULT_RETRIES", 1)
    assert get_retry_count() == 1
```

## Test Data Management

### Static Test Data

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

## Unit Testing

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

## Parametrized Tests

```python
@pytest.mark.parametrize("input_val,expected", [
    (1, 2),
    (2, 4),
    (-1, -2),
    (0, 0),
])
def test_double(input_val: int, expected: int) -> None:
    assert double(input_val) == expected

@pytest.mark.parametrize("email", [
    "",
    "no-at-sign",
    "@no-local",
    "spaces in@email.com",
])
def test_rejects_invalid_emails(email: str) -> None:
    with pytest.raises(ValidationError):
        validate_email(email)
```

Use parametrized tests instead of copy-pasting near-identical test functions.

## Mocking

### Use `spec=True` to Catch API Drift

```python
from unittest.mock import MagicMock, AsyncMock

mock_repo = MagicMock(spec=UserRepository)
mock_repo.save = AsyncMock(spec=UserRepository.save)
```

`spec=True` (or `spec_set=True`) ensures the mock raises `AttributeError` if you access attributes that don't exist on the real object — catches renames and refactors.

### Prefer Dependency Injection over Patching

```python
# Good — inject the dependency
def test_sends_welcome_email(user_repo, mock_email_service):
    service = UserService(repo=user_repo, email=mock_email_service)
    service.create_user(valid_data)
    mock_email_service.send.assert_called_once()

# Avoid when possible — patching couples tests to implementation
with patch("app.services.user.EmailService") as MockEmail:
    pass
```

### Prefer Fakes over Mocks

When feasible, use in-memory implementations instead of mocks:

```python
class FakeUserRepository:
    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._counter = 0

    async def save(self, user: User) -> User:
        self._counter += 1
        user.id = str(self._counter)
        self._users[user.id] = user
        return user

    async def find_by_id(self, user_id: str) -> User | None:
        return self._users.get(user_id)
```

Fakes are more realistic than mocks and don't couple tests to call sequences.

### Patching Examples

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

## Integration Testing

### Database Tests (SQL)

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

### AWS Service Tests (moto)

Use **moto** to mock AWS services (DynamoDB, S3, SQS, etc.) and **pytest-socket** to prevent accidental network calls:

```python
import os
from typing import Generator

import pytest
from moto import mock_aws

from .models import Order

@pytest.fixture(scope="session")
def aws_credentials() -> None:
    """Set mock AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture
def dynamodb_table(aws_credentials: None) -> Generator[None, None, None]:
    """Create and tear down a mock DynamoDB table."""
    mock = mock_aws()
    mock.start()
    try:
        Order.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        yield
    finally:
        mock.stop()

def test_creates_and_retrieves_order(dynamodb_table: None) -> None:
    """Test round-trip create and get for an Order."""
    order = Order.create(order_id=uuid4(), items=[item])
    order.save()

    retrieved = Order.get(order.order_id)
    assert retrieved.order_id == order.order_id
```

### HTTP Integration Tests

For API tests that hit real endpoints, use a base test class with class-level setup for expensive operations (creating test users, authenticating). Use numbered test names when execution order matters:

```python
import unittest
from http import HTTPStatus

class BaseApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._base_url = "http://localhost:8080/api"

    def _get(self, path: str, token: str) -> dict:
        """Issue an authenticated GET and return the JSON response."""
        response = requests.get(
            f"{self._base_url}{path}",
            headers={"Authorization": f"Bearer {token}"},
        )
        return response.json()

    def _post(self, path: str, token: str, data: dict) -> dict:
        """Issue an authenticated POST and return the JSON response."""
        response = requests.post(
            f"{self._base_url}{path}",
            headers={"Authorization": f"Bearer {token}"},
            json=data,
        )
        return response.json()


class TestUserApi(BaseApiTest):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._user = cls._register(test_token)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._cleanup(cls._user)
        super().tearDownClass()

    def test_01_create_user(self) -> None:
        """Verify user registration returns a valid user and token."""
        response = self._post("/users", token, {"name": "Test"})
        self.assertIsNotNone(response.get("user"))
        self.assertIsNotNone(response.get("token"))

    def test_02_login(self) -> None:
        """Verify login with existing credentials succeeds."""
        response = self._post("/login", token, {})
        self.assertEqual(response["user"]["id"], self._user["id"])
```

### Skipping Environment-Dependent Tests

Use `pytest.mark.skip` with a reason when tests cannot run in a mock environment:

```python
@pytest.mark.skip(reason="moto doesn't support LSI queries - test against real DynamoDB")
def test_query_by_index(dynamodb_table: None) -> None:
    """Test querying via local secondary index."""
    ...
```

## End-to-End Testing

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

## Property-Based Testing (Hypothesis)

```python
from hypothesis import given, settings, example
from hypothesis import strategies as st

@given(st.lists(st.integers()))
def test_sort_is_idempotent(xs: list[int]) -> None:
    assert sorted(sorted(xs)) == sorted(xs)

@given(st.text(min_size=1))
def test_roundtrip_encode_decode(s: str) -> None:
    assert decode(encode(s)) == s

@given(st.integers(min_value=0, max_value=1000))
@example(0)
@example(999)
def test_fibonacci_is_non_negative(n: int) -> None:
    assert fibonacci(n) >= 0
```

**When to use:**
- Functions with broad input spaces (parsers, serializers, algorithms)
- Round-trip invariants (encode/decode, serialize/deserialize)
- Mathematical properties (commutativity, idempotency, monotonicity)

**Configuration:**
- Use `@settings(max_examples=1000)` for critical paths
- Use `@example()` decorator for known regression cases
- Hypothesis auto-generates edge cases you wouldn't think to write

## Async Testing

```python
import pytest

async def test_fetches_user_data(user_service: UserService) -> None:
    user = await user_service.get_user("123")
    assert user is not None
    assert user.name == "Alice"

async def test_raises_for_missing_user(user_service: UserService) -> None:
    with pytest.raises(UserNotFoundError, match="not found"):
        await user_service.get_user("nonexistent")
```

With `asyncio_mode = "auto"` in `pyproject.toml`, async test functions are automatically recognized — no need for `@pytest.mark.asyncio`.

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

## Performance Testing

```python
import time

def test_processes_large_dataset_efficiently():
    start = time.monotonic()
    result = process_large_dataset(data)
    duration = time.monotonic() - start

    assert duration < 1.0  # Should complete in < 1s
```

For load testing, use dedicated tools (Locust, k6, Artillery).

## Test Anti-Patterns

### Don't Mock Everything

```python
# Avoid — over-mocking hides real bugs
def test_creates_user(mock_repo, mock_email, mock_logger, mock_metrics, mock_cache):
    service = UserService(mock_repo, mock_email, mock_logger, mock_metrics, mock_cache)
    # Testing mock interactions, not actual behavior

# Better — use fakes for data, mocks only at boundaries
def test_creates_user(fake_repo, mock_email):
    service = UserService(repo=fake_repo, email=mock_email)
    user = service.create_user(valid_data)
    assert user.id is not None
    mock_email.send.assert_called_once()
```

### Don't Use `sleep()` in Tests

```python
# Avoid
import time
time.sleep(2)
assert result.is_ready

# Good — use asyncio or polling
import asyncio
await asyncio.wait_for(result.wait(), timeout=2.0)
```

## CI/CD Pipeline

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
- Complex test setup and environment requirements
- Non-obvious test scenarios
- Reasons for skipped tests

```python
class TestAuthenticationIntegration:
    """
    Tests user authentication flow.

    Note: These tests require a test database to be running.
    Run `make test-db-setup` before executing.
    """
    # tests...
```

## References

- [pytest Documentation](https://docs.pytest.org/en/stable/)
- [pytest-cov](https://pytest-cov.readthedocs.io/en/stable/)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/en/latest/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/en/latest/)
