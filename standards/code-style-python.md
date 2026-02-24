# Code Style — Python

Follows general principles in [code-style.md](code-style.md) and [PEP 8](https://peps.python.org/pep-0008/).

## Naming Conventions

- Use **snake_case** for variables, functions, and file names: `user_service.py`
- Use **PascalCase** for classes: `UserRepository`
- Use **SCREAMING_SNAKE_CASE** for constants: `MAX_RETRY_ATTEMPTS`

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

```python
# Good
def calculate_total_price(items: list[Item]) -> float:
    """Calculate the total price of items."""
    return sum(item.price for item in items)

class UserRepository:
    def find_by_id(self, user_id: int) -> User | None:
        pass
```

## Imports

```python
# Standard library
import os
import sys

# Third-party
import requests
import flask

# Local
from services.user import UserService
from config import config
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
