# Testing — Python

Follows [testing.md](../testing.md).

## pytest Configuration

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

## Coverage Configuration

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

| Threshold | When to Use |
|---|---|
| **80%** | Industry-standard minimum; most projects |
| **90%** | Libraries and shared packages |
| **95%+** | Critical infrastructure, security-sensitive code |

## Test Organization

**Colocated** (preferred for libraries): `models.py` alongside `models_test.py`

**Separate directory** (common for apps): `src/feature/tests/test_service.py`

## Test Naming and Conventions

- Always annotate with `-> None`; always include a one-line docstring
- Flat functions with docstrings for smaller modules; class-based grouping when a module has many tests

```python
def test_creates_user_with_valid_data(sample_user: dict) -> None:
    """Test that valid data produces a saved user."""

class TestUserService:
    class TestCreateUser:
        def test_creates_user_with_valid_data(self) -> None: ...
        def test_raises_validation_error_when_email_is_invalid(self) -> None: ...
```

## Fixtures

- Use `conftest.py` for shared fixtures; prefer **function scope** for isolation
- Use **session scope** only for expensive resources (DB connections, Docker)
- Use `yield` fixtures for setup + teardown; type as `Generator[YieldType, None, None]`

```python
@pytest.fixture
def user_service(user_repo):
    return UserService(repo=user_repo)

@pytest.fixture
def db_session():
    session = create_test_session()
    yield session
    session.rollback()
    session.close()
```

### monkeypatch

Prefer `monkeypatch` for simple attribute/env var patching:

```python
def test_uses_custom_timeout(monkeypatch):
    monkeypatch.setenv("REQUEST_TIMEOUT", "5")
    service = create_service()
    assert service.timeout == 5
```

## Mocking Preferences

- Use `spec=True` on mocks to catch API drift
- Prefer **DI** over patching; prefer **fakes** over mocks

```python
class FakeUserRepository:
    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    async def save(self, user: User) -> User:
        self._users[user.id] = user
        return user

    async def find_by_id(self, user_id: str) -> User | None:
        return self._users.get(user_id)
```

## Parametrized Tests

```python
@pytest.mark.parametrize("email", [
    "", "no-at-sign", "@no-local", "spaces in@email.com",
])
def test_rejects_invalid_emails(email: str) -> None:
    """Test that invalid emails raise ValidationError."""
    with pytest.raises(ValidationError):
        validate_email(email)
```

## AWS Integration Tests (moto)

```python
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
```

## HTTP Integration Tests

Use a base test class with class-level setup for expensive operations:

```python
class BaseApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._base_url = "http://localhost:8080/api"

    def _get(self, path: str, token: str) -> dict:
        response = requests.get(f"{self._base_url}{path}",
                                headers={"Authorization": f"Bearer {token}"})
        return response.json()
```

Use numbered test names when execution order matters. Use `pytest.mark.skip(reason="...")` when tests cannot run in a mock environment.

## Property-Based Testing (Hypothesis)

Use for functions with broad input spaces, round-trip invariants, mathematical properties:

```python
@given(st.lists(st.integers()))
def test_sort_is_idempotent(xs: list[int]) -> None:
    assert sorted(sorted(xs)) == sorted(xs)
```

## Async Testing

With `asyncio_mode = "auto"`, async test functions are recognized automatically:

```python
async def test_fetches_user_data(user_service: UserService) -> None:
    """Test fetching user data by ID."""
    user = await user_service.get_user("123")
    assert user.name == "Alice"
```
