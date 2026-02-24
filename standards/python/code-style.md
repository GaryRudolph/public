# Code Style — Python

Follows general principles in [code-style.md](../code-style.md) and [PEP 8](https://peps.python.org/pep-0008/).

## Formatting

- **4 spaces** per indentation level (per PEP 8). No tabs.
- **88-character** line length (Black/Ruff default).
- **Double quotes** by default (Black convention).
- **Trailing comma** on the last element of multi-line collections, arguments, and parameters — forces multi-line formatting and produces cleaner diffs.

## Naming Conventions

- Use **snake_case** for variables, functions, and file names: `user_service.py`
- Use **PascalCase** for classes: `UserRepository`
- Use **SCREAMING_SNAKE_CASE** for constants: `MAX_RETRY_ATTEMPTS`
- Use **`_leading_underscore`** for private/internal attributes and functions: `_internal_cache`, `_validate_input()`

```python
# Good
user_account_balance = 1000
def calculate_total_price(items): pass
class UserRepository: pass
MAX_RETRY_ATTEMPTS = 3

# Avoid
uab = 1000
def calc(i): pass
```

## Module Structure

```python
# 1. Imports (standard library, third-party, then local)
from typing import Protocol
from api import API

# 2. Constants
DEFAULT_TIMEOUT = 5000

# 3. Type definitions
class User(Protocol):
    pass

# 4. Main implementation
class UserService:
    pass

# 5. Helper functions (module-private)
def _validate_input():
    pass
```

### Public API (`__init__.py`)

Use `__all__` to define the public API of a package explicitly:

```python
from .models import User, UserRole
from .exceptions import ValidationError, NotFoundError
from .service import UserService

__all__ = [
    "User",
    "UserRole",
    "UserService",
    "ValidationError",
    "NotFoundError",
]
```

## Spacing

```python
# Good spacing
def calculate(a, b):
    result = a + b
    return result

config = {
    "timeout": 5000,
    "retry": True,
}

# Use blank lines to separate logical sections
def process_user(user):
    # Validation
    if not user.id:
        raise ValueError("Invalid user")

    # Processing
    normalized = normalize_user(user)

    # Storage
    return save_user(normalized)
```

## Comments

```python
# Good - explains why
# Cache results to avoid repeated API calls
cached_results = {}

# Avoid - explains what (obvious from code)
# Set x to 5
x = 5
```

## Language-Specific Guidelines

- Follow PEP 8
- Use type hints for function signatures

### Type Hints

- Prefer `X | Y` over `Optional[X]` and `Union[X, Y]` (Python 3.10+)
- Always annotate return types, including `-> None`
- Use lowercase builtins: `list[int]`, `dict[str, Any]`, `tuple[int, ...]` (Python 3.9+)
- Use `Protocol` for structural subtyping instead of ABCs where possible
- Use `*args: Any, **kwargs: Any` when forwarding arguments
- All **public functions** must have full type annotations (parameters + return type)

```python
# Good
def calculate_total_price(items: list[Item]) -> float:
    """Calculate the total price of items."""
    return sum(item.price for item in items)

class UserRepository:
    def find_by_id(self, user_id: int) -> User | None:
        pass

def save(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
    return super().save(*args, **kwargs)

def process(data: str) -> None:
    print(data)
```

### Enumerations

Use `StrEnum` with `auto()` for state machines and string-valued enums:

```python
from enum import StrEnum, auto

class OrderState(StrEnum):
    PENDING = auto()    # "pending"
    APPROVED = auto()   # "approved"
    SHIPPED = auto()    # "shipped"
    DELIVERED = auto()  # "delivered"
    CANCELLED = auto()  # "cancelled"
```

Nest enums inside the class they belong to when they are tightly coupled:

```python
class Order(Model):
    class State(StrEnum):
        PENDING = auto()
        APPROVED = auto()
        SHIPPED = auto()

    state: State = State.PENDING
```

## File Headers

For open-source packages, include a copyright and license header at the top of every source file, before imports:

```python
# Copyright © 2024 Company, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations
```

For private/internal projects, a shorter header (just copyright) or no header is acceptable. Be consistent within a repository.

## Imports

```python
# Standard library
import os
import sys

# Third-party
import requests
import flask

# Local (absolute for inter-package)
from services.user import UserService
from config import config
```

### Relative Imports

Use relative imports for intra-package references. Use absolute imports for inter-package references.

```python
# Within the same package — use relative
from .exceptions import ValidationError
from .models import User

# From a different package — use absolute
from services.auth import AuthService
```

### Deferred Imports

Import inside a function body to break circular dependencies:

```python
class Order(Model):
    @classmethod
    def create(cls, data: dict) -> "Order":
        from .pricing import calculate_total

        total = calculate_total(data["items"])
        return cls(total=total, **data)
```

## Debug Logging

Use entry/exit logging in service and API methods for traceability:

```python
import logging

log = logging.getLogger(__name__)

class OrderService:
    def create_order(self, user_id: str, items: list[Item]) -> Order:
        log.debug("enter user_id=%s, items=%d", user_id, len(items))

        order = Order.create(user_id=user_id, items=items)

        log.debug("exit order_id=%s", order.order_id)
        return order
```

## Model Self-Serialization

Models should serialize themselves via a `to_dict()` method that calls `super()` and extends:

```python
class BaseModel:
    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id}

class User(BaseModel):
    name: str
    email: str

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result.update({"name": self.name, "email": self.email})
        return result
```

## Error Handling

```python
# Good
class ValidationError(Exception):
    def __init__(self, field: str, message: str):
        super().__init__(f"Validation failed for {field}: {message}")
        self.field = field

def validate_user(user: User):
    if not user.email:
        raise ValidationError("email", "Email is required")

# Avoid
def validate_user(user):
    if not user.email:
        raise Exception("Invalid")  # Too vague
```

## Anti-Patterns

### Magic Numbers

```python
# Avoid
if user.age > 18:
    pass

# Good
MINIMUM_AGE = 18
if user.age > MINIMUM_AGE:
    pass
```

### Deep Nesting

```python
# Avoid
if user:
    if user.is_active:
        if user.has_permission:
            pass

# Good - early returns
if not user:
    return
if not user.is_active:
    return
if not user.has_permission:
    return
```

### Dangerous Functions

```python
# Never use on untrusted input
eval(user_input)              # Arbitrary code execution
exec(user_input)              # Arbitrary code execution
pickle.loads(untrusted_data)  # Arbitrary code execution

# Use subprocess safely — never shell=True with dynamic input
import subprocess
subprocess.run(["ls", "-la", path], shell=False, check=True)  # Good
subprocess.run(f"ls -la {path}", shell=True)                  # Vulnerable to injection
```

## Tools

### Linting and Formatting

Use **ruff** for both linting and formatting (replaces black, isort, flake8):

```bash
ruff check .       # Lint
ruff check --fix . # Lint with auto-fix
ruff format .      # Format
```

### Ruff Configuration

Add to `pyproject.toml`. Start with the recommended tier and expand as the codebase matures:

```toml
[tool.ruff]
target-version = "py312"
line-length = 88

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # Pyflakes (undefined names, unused imports)
    "UP",   # pyupgrade (modernize syntax)
    "B",    # flake8-bugbear (likely bugs)
    "SIM",  # flake8-simplify
    "I",    # isort (import sorting)
    "C4",   # flake8-comprehensions
    "RUF",  # Ruff-specific rules
]
fixable = ["ALL"]

[tool.ruff.lint.isort]
known-first-party = ["my_package"]
```

For strict projects, add: `"S"` (bandit security), `"D"` (docstrings), `"ANN"` (annotations), `"PTH"` (pathlib), `"T20"` (no print), `"N"` (naming), `"ARG"` (unused arguments).

### Type Checking

Use **mypy** in strict mode for static type checking:

```bash
mypy src/
```

Configuration in `pyproject.toml`:

```toml
[tool.mypy]
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
no_implicit_optional = true
```

### Package Management

Use **uv** as the package manager and **pyproject.toml** as the project configuration:

```bash
uv venv               # Create virtual environment
uv sync --extra dev   # Install with dev dependencies
uv build              # Build package
```

### Build Configuration

Use `pyproject.toml` with hatchling as the build backend:

```toml
[project]
name = "my-package"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
dev = [
    "mypy",
    "pytest",
    "ruff",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```
