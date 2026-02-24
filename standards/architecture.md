# Architecture Standards

## Core Principles

### SOLID Principles
- **Single Responsibility** - Each module/class has one reason to change
- **Open/Closed** - Open for extension, closed for modification
- **Liskov Substitution** - Subtypes must be substitutable for base types
- **Interface Segregation** - Many specific interfaces > one general interface
- **Dependency Inversion** - Depend on abstractions, not concretions

### Keep It Simple
- Solve the current problem, not future hypothetical problems
- Prefer boring technology and established patterns
- Only abstract when you have 3+ concrete examples
- Avoid premature optimization

### Separation of Concerns
- Business logic separate from presentation
- Data access separate from business logic
- Configuration separate from code

## Architectural Patterns

### Layered Architecture

```
┌─────────────────────────────────────┐
│     Presentation Layer              │  UI, Controllers, APIs
├─────────────────────────────────────┤
│     Business Logic Layer            │  Services, Domain Logic
├─────────────────────────────────────┤
│     Data Access Layer               │  Repositories, DAOs
├─────────────────────────────────────┤
│     Infrastructure Layer            │  Database, External APIs
└─────────────────────────────────────┘
```

**Rules:**
- Each layer only depends on layers below it
- Never skip layers (presentation → data access)
- Keep layers thin and focused

### Module Structure

```
feature/
├── __init__.py          # Public API
├── types.py             # Type definitions
├── service.py           # Business logic
├── repository.py        # Data access
├── validators.py        # Input validation
└── tests/
    ├── test_service.py
    └── test_repository.py
```

## Design Patterns

### Repository Pattern
Encapsulate data access logic

```python
from typing import Protocol

class UserRepository(Protocol):
    async def find_by_id(self, id: str) -> User | None: ...
    async def find_by_email(self, email: str) -> User | None: ...
    async def save(self, user: User) -> User: ...
    async def delete(self, id: str) -> None: ...

class DatabaseUserRepository:
    async def find_by_id(self, id: str) -> User | None:
        # Database-specific implementation
        pass
    # ... other methods
```

### Service Layer Pattern
Encapsulate business logic

```python
class UserService:
    def __init__(self, user_repository: UserRepository, email_service: EmailService):
        self._user_repository = user_repository
        self._email_service = email_service

    async def create_user(self, data: CreateUserData) -> User:
        # 1. Validate
        self._validate_user_data(data)

        # 2. Business logic
        user = User(data)

        # 3. Persist
        await self._user_repository.save(user)

        # 4. Side effects
        await self._email_service.send_welcome(user)

        return user
```

### Factory Pattern
When object creation is complex

```python
class UserFactory:
    def create_from_api_response(self, data: ApiUser) -> User:
        return User(
            id=data.user_id,
            email=data.email_address,
            created_at=datetime.fromtimestamp(data.created_timestamp),
        )
```

### Strategy Pattern
When you have multiple algorithms for the same task

```python
from typing import Protocol

class PaymentStrategy(Protocol):
    async def process_payment(self, amount: float) -> PaymentResult: ...

class CreditCardPayment:
    async def process_payment(self, amount: float) -> PaymentResult:
        # Credit card specific logic
        pass

class PayPalPayment:
    async def process_payment(self, amount: float) -> PaymentResult:
        # PayPal specific logic
        pass

class PaymentService:
    def __init__(self, strategy: PaymentStrategy):
        self._strategy = strategy

    async def pay(self, amount: float) -> PaymentResult:
        return await self._strategy.process_payment(amount)
```

## Dependency Management

### Dependency Injection
- Pass dependencies through constructors
- Makes code testable and flexible
- Avoid global state and singletons

```python
# Good - dependencies injected
class OrderService:
    def __init__(
        self,
        order_repository: OrderRepository,
        payment_service: PaymentService,
        logger: Logger,
    ):
        self._order_repository = order_repository
        self._payment_service = payment_service
        self._logger = logger

# Avoid - hardcoded dependencies
class OrderService:
    def __init__(self):
        self._order_repository = OrderRepository()
        self._payment_service = PaymentService()
```

### Dependency Direction
- High-level modules should not depend on low-level modules
- Both should depend on abstractions (interfaces)

```python
from typing import Protocol

# Business logic defines the interface it needs
class EmailSender(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...

# Business logic depends on abstraction
class UserService:
    def __init__(self, email_sender: EmailSender):
        self._email_sender = email_sender

# Infrastructure implements the interface
class SendGridEmailSender:
    async def send(self, to: str, subject: str, body: str) -> None:
        # SendGrid specific implementation
        pass
```

## Error Handling Architecture

### Error Hierarchy
```python
# Base error class
class AppError(Exception):
    def __init__(self, message: str, status_code: int, is_operational: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.is_operational = is_operational

# Specific error types
class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(message, 400)

class NotFoundError(AppError):
    def __init__(self, resource: str):
        super().__init__(f"{resource} not found", 404)

class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, 401)
```

### Error Handling Layers
1. **Service Layer** - Throws domain-specific errors
2. **Controller Layer** - Catches and transforms to HTTP responses
3. **Global Handler** - Catches unexpected errors, logs, returns safe responses

## Data Flow

### Request Flow
```
HTTP Request
    ↓
Controller (validate, parse)
    ↓
Service (business logic)
    ↓
Repository (data access)
    ↓
Database
```

### Response Flow
```
Database
    ↓
Repository (domain models)
    ↓
Service (business logic)
    ↓
Controller (DTOs/serialization)
    ↓
HTTP Response
```

## State Management

### Principles
- Keep state as local as possible
- Immutable data by default
- Single source of truth
- Predictable state updates

### Avoid Global State
```python
# Avoid - global mutable state
current_user: User | None = None

# Good - passed explicitly
def process_order(order: Order, user: User):
    # user is explicit parameter
    pass
```

## API Design

### RESTful Principles
- Use HTTP verbs correctly (GET, POST, PUT, DELETE)
- Use plural nouns for resources (`/users`, not `/user`)
- Use path parameters for IDs (`/users/123`)
- Use query parameters for filtering (`/users?status=active`)

### Versioning
- Include version in URL: `/api/v1/users`
- Maintain backward compatibility within a version
- Document breaking changes

### Response Format
```json
// Success response
{
  "data": { },
  "meta": { }
}

// Error response
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": [
      { "field": "email", "message": "Invalid email format" }
    ]
  }
}
```

## Performance Considerations

### When to Optimize
1. Measure first - don't guess
2. Focus on algorithmic complexity
3. Optimize hot paths only
4. Don't sacrifice readability for minor gains

### Caching Strategy
- Cache at appropriate layers
- Use cache invalidation strategies
- Consider cache consistency requirements

### Database Access
- Use connection pooling
- Avoid N+1 queries
- Use indexes on frequently queried fields
- Paginate large result sets

## Security Architecture

### Defense in Depth
- Multiple layers of security
- Validate at every boundary
- Never trust client input
- Use principle of least privilege

### Authentication & Authorization
- Separate authentication (who are you?) from authorization (what can you do?)
- Use established libraries for authentication
- Store permissions in central location
- Check permissions at service layer, not just UI

## Testing Architecture

### Test Pyramid
```
        /\
       /  \      E2E Tests (few)
      /────\
     /      \    Integration Tests (some)
    /────────\
   /          \  Unit Tests (many)
  /____________\
```

### Test Boundaries
- **Unit Tests** - Single function/class, mocked dependencies
- **Integration Tests** - Multiple modules, real dependencies
- **E2E Tests** - Full system, real environment

## Documentation Requirements

Document:
- Public APIs
- Complex business logic
- Architectural decisions (ADRs)
- Non-obvious behavior

Don't document:
- Self-explanatory code
- Implementation details that may change
- What the code does (code should be self-documenting)
