# Documentation — Python

Follows [documentation.md](../documentation.md).

## Module Docstrings

Every module should have a docstring. One-line for simple modules, multi-line when non-obvious:

```python
"""PynamoDB model for InferenceRequest."""
```

```python
"""
Shared test fixtures for inference store tests.

Provides mock AWS credentials, DynamoDB table setup/teardown,
and sample UUID generators for use across test modules.
"""
```

## Function Documentation

Use Google-style docstrings:

```python
def calculate_total(items: list[Item], tax_rate: float, discount_code: str = None) -> float:
    """Calculate the total price including tax and discount.

    Args:
        items: List of items with price and quantity
        tax_rate: Tax rate as decimal (e.g., 0.08 for 8%)
        discount_code: Optional discount code to apply

    Returns:
        The total price after tax and discount

    Raises:
        ValidationError: If items list is empty
    """
```

## Class Documentation

```python
class UserService:
    """Service for managing user accounts.

    Handles user creation, authentication, and profile management.
    Uses UserStore for data persistence and EmailService for notifications.
    """
```

## Test Documentation

Each test function gets a one-line docstring. Fixtures include docstrings with Args/Returns when they take parameters or yield:

```python
def test_format_pk(sample_request_id: UUID) -> None:
    """Test PK formatting with UUID."""
    pk = InferenceRequest.format_pk(sample_request_id)
    assert pk == f"R#{str(sample_request_id)}"

@pytest.fixture
def dynamodb_table(aws_credentials: None) -> Generator[None, None, None]:
    """Create and tear down a mock DynamoDB table.

    Args:
        aws_credentials: Ensures mock credentials are set before table creation
    """
```

## Library README Structure

```markdown
# Package Name
## Overview
## Installation
## Building
## Testing
## Quick Start
## How It Works
### Architecture
### Data Models
### Configuration
### Error Handling
## API Reference
## Development
## Design Decisions
```
