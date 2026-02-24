# Documentation — Python

Follows general principles in [documentation.md](documentation.md).

## Code Comments

### When to Comment

**Good reasons:**
```python
# Cache results for 5 minutes to reduce API calls to rate-limited service
CACHE_TTL = 5 * 60

# HACK: Temporary workaround for bug in library v2.3.1
# Remove when upgrading to v2.4.0
# See: https://github.com/library/issues/123
if version == '2.3.1':
    apply_workaround()

# Using binary search for O(log n) performance on sorted array
index = binary_search(sorted_array, target)
```

**Bad reasons:**
```python
# Avoid - restates the code
# Set x to 5
x = 5

# Avoid - explains obvious code
# Loop through users
for user in users:
    process_user(user)
```

### Comment Style

```python
# Single-line comments for brief explanations
timeout = 30000  # 30 second timeout

# Multi-line comments for longer explanations.
# Use this format for complex logic that needs more context
# spanning multiple lines.
def complex_function():
    pass
```

### TODO Comments
```python
# TODO: Add input validation
# TODO(username): Refactor to use new API
# TODO: [TICKET-123] Implement caching layer
# FIXME: This breaks when input is negative
# HACK: Workaround for upstream bug
# NOTE: This must run before init_database()
```

## Function Documentation

Use Google-style docstrings:

```python
def calculate_total(items: list[Item], tax_rate: float, discount_code: str = None) -> float:
    """
    Calculate the total price including tax and discount.

    Args:
        items: List of items with price and quantity
        tax_rate: Tax rate as decimal (e.g., 0.08 for 8%)
        discount_code: Optional discount code to apply

    Returns:
        The total price after tax and discount

    Raises:
        ValidationError: If items list is empty
        InvalidDiscountError: If discount code is invalid

    Example:
        >>> total = calculate_total([Item(price=10, quantity=2)], 0.08, 'SAVE10')
        >>> print(total)
        19.44
    """
    pass
```

## Class Documentation

```python
class UserService:
    """
    Service for managing user accounts.

    Handles user creation, authentication, and profile management.
    Uses UserRepository for data persistence and EmailService for notifications.

    Example:
        >>> service = UserService(user_repo, email_service)
        >>> user = service.create_user(email='user@example.com')
    """

    def create_user(self, data: CreateUserData) -> User:
        """
        Create a new user account.

        Validates the user data, creates the account, and sends a welcome email.

        Args:
            data: User creation data

        Returns:
            The created user

        Raises:
            ValidationError: If user data is invalid
            DuplicateEmailError: If email already exists
        """
        pass
```

## Inline Documentation

### Complex Algorithms
```python
def find_path(start: Node, goal: Node) -> list[Node]:
    """
    Implements the A* pathfinding algorithm.

    Time complexity: O(b^d) where b is branching factor and d is depth
    Space complexity: O(b^d)

    Algorithm:
    1. Add start node to open set
    2. While open set not empty:
       a. Get node with lowest f-score
       b. If node is goal, reconstruct path
       c. Add node to closed set
       d. For each neighbor:
          - Calculate tentative g-score
          - If better than recorded, update and add to open set
    """
    pass
```

### Magic Numbers
```python
# Avoid
result = value * 1.08

# Good - explain the number
TAX_RATE = 1.08  # 8% sales tax
result = value * TAX_RATE
```

## README Files

### Project README — Quick Start
```markdown
## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from project import Feature

feature = Feature()
feature.do_something()
```
```

### Module README — Structure
```markdown
## Structure

```
module/
├── __init__.py       # Public API
├── service.py        # Main service logic
├── repository.py     # Data access
└── types.py          # Type definitions
```

## Usage

```python
from module import ModuleService

service = ModuleService()
result = service.do_something()
```
```

## Documentation Tools

- **Sphinx** - Generate HTML docs from docstrings

```bash
sphinx-build -b html docs/ docs/_build
```

## Best Practices

### Be Concise
```python
# Verbose
def validate_user(user):
    """
    This function takes a user object as a parameter and then
    validates all of the fields in the user object to make sure
    they meet the requirements and then returns a boolean value
    indicating whether the user object is valid or not.
    """

# Concise
def validate_user(user):
    """Validates user data against requirements. Returns True if valid."""
```

### Use Examples
```python
def format_date(date: str, style: str = 'long') -> str:
    """
    Formats a date string.

    Example:
        >>> format_date('2024-01-01')          # "January 1, 2024"
        >>> format_date('2024-01-01', 'short') # "Jan 1, 2024"
    """
```

### Link to Resources
```python
def authorize(code: str) -> Token:
    """
    Implements OAuth 2.0 authorization code flow.

    See: https://tools.ietf.org/html/rfc6749#section-4.1
    """
```
