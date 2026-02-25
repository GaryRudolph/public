# Code Style — Python

Follows [code-style.md](../code-style.md) and [PEP 8](https://peps.python.org/pep-0008/).

## Formatting

- **4 spaces**, no tabs; **88-char** line length (Black/Ruff); **double quotes**
- **Trailing comma** on last element of multi-line collections, arguments, and parameters

## Naming

- **snake_case** for variables, functions, files: `user_service.py`
- **PascalCase** for classes: `UserStore`
- **SCREAMING_SNAKE_CASE** for constants: `MAX_RETRY_ATTEMPTS`
- **`_leading_underscore`** for private/internal: `_internal_cache`, `_validate_input()`

## Module Structure

```python
# 1. Imports (standard library, third-party, then local)
from typing import Protocol
from api import API

# 2. Constants
DEFAULT_TIMEOUT = 5000

# 3. Type definitions
# 4. Main implementation
# 5. Helper functions (module-private)
```

Use `__all__` in `__init__.py` to define the public API explicitly. Use relative imports for intra-package, absolute for inter-package.

## Type Hints

- Prefer `X | Y` over `Optional[X]` and `Union[X, Y]` (3.10+)
- Always annotate return types, including `-> None`
- Lowercase builtins: `list[int]`, `dict[str, Any]`, `tuple[int, ...]` (3.9+)
- Use `Protocol` for structural subtyping instead of ABCs where possible
- All **public functions** must have full type annotations

```python
def calculate_total_price(items: list[Item]) -> float:
    return sum(item.price for item in items)

class UserStore:
    def find_by_id(self, user_id: int) -> User | None:
        pass
```

## Enumerations

Use `StrEnum` with `auto()` for string-valued enums. Nest enums inside the class they belong to when tightly coupled:

```python
class Order(Model):
    class State(StrEnum):
        PENDING = auto()
        APPROVED = auto()
        SHIPPED = auto()

    state: State = State.PENDING
```

## File Headers

For open-source packages: copyright and license header before imports. Private projects: shorter preferred or none — be consistent.

## Debug Logging

Use entry/exit logging in service and API methods:

```python
log = logging.getLogger(__name__)

class OrderService:
    def create_order(self, user_id: str, items: list[Item]) -> Order:
        log.debug("enter user_id=%s, items=%d", user_id, len(items))
        order = Order.create(user_id=user_id, items=items)
        log.debug("exit order_id=%s", order.order_id)
        return order
```

## Model Self-Serialization

Models serialize via `to_dict()` calling `super()` and extending:

```python
class User(BaseModel):
    name: str
    email: str

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result.update({"name": self.name, "email": self.email})
        return result
```

## Error Handling

Use domain-specific exceptions with context:

```python
class ValidationError(Exception):
    def __init__(self, field: str, message: str):
        super().__init__(f"Validation failed for {field}: {message}")
        self.field = field
```

## Tools

### Ruff (linting + formatting)

```toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = ["E", "W", "F", "UP", "B", "SIM", "I", "C4", "RUF"]
fixable = ["ALL"]

[tool.ruff.lint.isort]
known-first-party = ["my_package"]
```

For strict projects add: `"S"` (bandit), `"D"` (docstrings), `"ANN"` (annotations), `"PTH"` (pathlib), `"T20"` (no print).

### mypy (strict mode)

```toml
[tool.mypy]
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
```

### Package Management

Use **uv** + **pyproject.toml** with hatchling:

```toml
[project]
name = "my-package"
version = "0.1.0"
requires-python = ">=3.12"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```
