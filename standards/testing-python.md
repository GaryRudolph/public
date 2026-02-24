# Testing — Python

Follows general principles in [testing.md](testing.md).

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

## Coverage Thresholds

| Threshold | When to Use |
|---|---|
| **80%** | Industry-standard minimum; pragmatic for most projects |
| **90%** | Recommended for libraries and shared packages |
| **95%+** | Critical infrastructure, security-sensitive code |

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

## References

- [pytest Documentation](https://docs.pytest.org/en/stable/)
- [pytest-cov](https://pytest-cov.readthedocs.io/en/stable/)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/en/latest/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/en/latest/)
