# Architecture — Python

Follows general principles in [architecture.md](../architecture.md).

## Module Structure

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
Encapsulate data access logic behind an abstraction. Best for complex domains with multiple data sources or when testability through interface substitution is critical.

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

### ActiveRecord Pattern
Models handle their own persistence via class methods. Best for simpler domains, single-table designs, or when zero-ceremony usage is valued.

```python
class Order(Model):
    class State(StrEnum):
        PENDING = auto()
        SHIPPED = auto()
        DELIVERED = auto()

    order_id = UnicodeAttribute(hash_key=True)
    state = UnicodeAttribute()
    total = NumberAttribute()

    @classmethod
    def create(cls, order_id: UUID, items: list[Item]) -> "Order":
        total = sum(item.price * item.quantity for item in items)
        return cls(order_id=order_id, state=cls.State.PENDING, total=total)

    @classmethod
    def get(cls, order_id: UUID) -> "Order":
        try:
            return super().get(str(order_id))
        except cls.DoesNotExist as e:
            raise OrderNotFoundError(order_id) from e

    @classmethod
    def update_state(cls, order_id: UUID, new_state: "Order.State") -> "Order":
        order = cls.get(order_id)
        order.state = new_state
        order.save()
        return order
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

**Separate factory class** — for cross-cutting creation logic or mapping between types:

```python
class UserFactory:
    def create_from_api_response(self, data: ApiUser) -> User:
        return User(
            id=data.user_id,
            email=data.email_address,
            created_at=datetime.fromtimestamp(data.created_timestamp),
        )
```

**Classmethod factory** — when defaults or computed values are involved and creation belongs on the model itself:

```python
class Order(Model):
    @classmethod
    def create(
        cls, order_id: UUID, items: list[Item], ttl_days: int = 30,
    ) -> "Order":
        timestamp = datetime.now(timezone.utc)
        expires_at = int(timestamp.timestamp()) + (ttl_days * 86400)
        return cls(
            order_id=order_id,
            total=sum(i.price for i in items),
            created_at=timestamp,
            expires_at=expires_at,
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

### Error Catalog Pattern
Centralize error definitions as classmethods on a single class. Each method maps a domain error to a status code and error code, providing a single source of truth for all API error responses:

```python
from http import HTTPStatus

class AppError(Exception):
    def __init__(self, status: HTTPStatus, code: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code

class Errors:
    @classmethod
    def user_not_found(cls) -> AppError:
        raise AppError(HTTPStatus.NOT_FOUND, 3, "User not found")

    @classmethod
    def bad_token(cls) -> AppError:
        raise AppError(HTTPStatus.UNAUTHORIZED, 7, "Bad token")

    @classmethod
    def required_field(cls, field: str) -> AppError:
        raise AppError(HTTPStatus.BAD_REQUEST, 10, f"Missing required field: {field}")

    @classmethod
    def not_authorized(cls) -> AppError:
        raise AppError(HTTPStatus.FORBIDDEN, 12, "You don't have access")
```

### Base API / Handler Pattern
Extract shared request handling (auth verification, permission checks) into a base class that API handlers inherit:

```python
class BaseApi:
    def _get_and_verify_token(self, request: Request) -> Token:
        header_token = request.headers.get("X-Token-Id")
        token = Token.get_by_key(header_token)
        if not token:
            Errors.bad_token()
        return token

    def _get_and_verify_self(self, token: Token, user_id: str) -> User:
        if token.user.id == user_id:
            return token.user
        user = User.get(user_id)
        if user is None:
            Errors.user_not_found()
        Errors.not_authorized()

class UserApi(BaseApi):
    def __init__(self, queue_service: QueueService) -> None:
        self._queue_service = queue_service

    def update_user(self, user_id: str) -> dict[str, Any]:
        token = self._get_and_verify_token(request)
        user = self._get_and_verify_self(token, user_id)
        # ... update logic
        return {"user": user.to_dict()}
```

### Centralized Route Registration
Register all routes in a single function for discoverability, rather than scattering decorator-based routes across files:

```python
def setup_routing(app: App) -> None:
    app.route("/api/users", methods=["POST"], handler=users_api.create_user)
    app.route("/api/users/<user_id>", methods=["PUT"], handler=users_api.update_user)
    app.route("/api/users/<user_id>/orders", methods=["GET"], handler=orders_api.get_orders)
    app.route("/api/users/<user_id>/orders", methods=["POST"], handler=orders_api.create_order)
    app.route("/api/queues/order_created", methods=["POST"], handler=queues_api.handle_order_created)
```

## Dependency Management

### Constructor Injection

```python
class OrderService:
    def __init__(
        self,
        order_repository: OrderRepository,
        payment_service: PaymentService,
        notification_service: NotificationService,
    ) -> None:
        self._order_repository = order_repository
        self._payment_service = payment_service
        self._notification_service = notification_service
```

### Factory Builder (Composition Root)

```python
class ServiceFactory:
    def __init__(self, config: Config) -> None:
        self._config = config

    @cached_property
    def notification_service(self) -> NotificationService:
        return NotificationServiceImpl(api_key=self._config.notify_key)

    @cached_property
    def payment_service(self) -> PaymentService:
        return StripePaymentService(secret=self._config.stripe_secret)

    @cached_property
    def order_repository(self) -> OrderRepository:
        return DynamoOrderRepository(table=self._config.table_name)

    @cached_property
    def order_service(self) -> OrderService:
        return OrderService(
            order_repository=self.order_repository,
            payment_service=self.payment_service,
            notification_service=self.notification_service,
        )

# Composition root — one place that builds the entire graph
factory = ServiceFactory(load_config())
order_service = factory.order_service
```

For simple apps, a plain module-level script can serve as the composition root:

```python
# main.py
push_service = PushService()
queue_service = QueueService(push_service)
user_api = UserApi(queue_service)
contact_api = ContactApi(queue_service, sms_service, shorten_service)
```

### Dependency Direction

```python
from typing import Protocol

class EmailSender(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...

class UserService:
    def __init__(self, email_sender: EmailSender) -> None:
        self._email_sender = email_sender

class SendGridEmailSender:
    async def send(self, to: str, subject: str, body: str) -> None:
        # SendGrid specific implementation
        pass
```

### Avoid Hardcoded Dependencies

```python
# Avoid - hardcoded dependencies
class OrderService:
    def __init__(self) -> None:
        self._repository = OrderRepository()       # untestable
        self._payment = StripePaymentService()      # untestable
```

## Error Handling

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

## State Management

### Avoid Global State

```python
# Avoid - global mutable state
current_user: User | None = None

# Good - passed explicitly
def process_order(order: Order, user: User):
    # user is explicit parameter
    pass
```

### Module-Level Initialization

A package `__init__.py` can configure models or services on import for zero-ceremony usage. This is acceptable for configuration wiring that applies once at startup:

```python
# mypackage/__init__.py
from .models import Order, OrderItem
from .exceptions import OrderError, OrderNotFoundError

_config = load_config()
Order.Meta.table_name = _config.table_name
Order.Meta.region = _config.region

__all__ = ["Order", "OrderItem", "OrderError", "OrderNotFoundError"]
```
