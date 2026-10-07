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

Use `StrEnum` for string-valued enums. Nest enums inside the class they belong to when tightly coupled.

- **Wire enums spell out their values** — an enum whose values reach an API, a protobuf or another service uses explicit unprefixed `UPPER_SNAKE` values ([Resource State](../architecture.md#resource-state)). `auto()` would give lowercase (`"pending"`)
- **`auto()` only for internal enums** — values that never leave the process
- **No `*_UNSPECIFIED` member** — then that value is a 422 on input, like any unknown one
- **A client's copy of another service's enum falls back** — an `UNKNOWN` member and `_missing_`, so a value added later doesn't break decoding. A server's own request enums never do, so an unknown value stays a 422

```python
class Order(Base):
    __tablename__ = "orders"

    class State(StrEnum):
        PENDING = "PENDING"
        APPROVED = "APPROVED"
        SHIPPED = "SHIPPED"

    state: Mapped[str] = mapped_column(default=State.PENDING)


class PartnerShipment(ApiModel):  # decoded from a partner's API
    class State(StrEnum):
        IN_TRANSIT = "IN_TRANSIT"
        DELIVERED = "DELIVERED"
        UNKNOWN = "UNKNOWN"  # never sent

        @classmethod
        def _missing_(cls, value: object) -> "PartnerShipment.State":
            return cls.UNKNOWN

    state: State
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
        log.debug("exit order_id=%s", order.id)
        return order
```

## Model Serialization

API models inherit the shared `ApiModel` ([architecture.md](architecture.md#request--response-schemas--pydantic)), so `model_dump()` and FastAPI both write lowerCamel keys. Use `model_validate()` to construct from ORM objects:

```python
class UserResponse(ApiModel):
    display_name: str
    photo_url: str | None

    model_config = ConfigDict(from_attributes=True)

# Serialize with wire keys: {"displayName": ..., "photoUrl": ...}
data = user_response.model_dump(mode="json")

# Construct from SQLAlchemy model
response = UserResponse.model_validate(user_row)
```

Construct and read models by field name (`UserResponse(display_name=…)`). pyright knows only field names, and `validate_by_name=True` makes them valid at runtime.

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
version = "1"
requires-python = ">=3.12"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```
