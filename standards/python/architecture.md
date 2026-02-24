# Architecture — Python

Follows [architecture.md](../architecture.md).

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

## Data Access Patterns

### Repository Pattern

Use when testability through interface substitution is critical:

```python
class UserRepository(Protocol):
    async def find_by_id(self, id: str) -> User | None: ...
    async def save(self, user: User) -> User: ...

class DatabaseUserRepository:
    async def find_by_id(self, id: str) -> User | None: ...
```

### ActiveRecord Pattern

Models handle their own persistence. Use for simpler domains or single-table designs:

```python
class Order(Model):
    class State(StrEnum):
        PENDING = auto()
        SHIPPED = auto()

    @classmethod
    def create(cls, order_id: UUID, items: list[Item]) -> "Order":
        return cls(order_id=order_id, state=cls.State.PENDING,
                   total=sum(i.price * i.quantity for i in items))

    @classmethod
    def get(cls, order_id: UUID) -> "Order":
        try:
            return super().get(str(order_id))
        except cls.DoesNotExist as e:
            raise OrderNotFoundError(order_id) from e
```

## Error Catalog Pattern

Centralize error definitions as classmethods on a single class:

```python
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
```

## Base API / Handler Pattern

Extract shared request handling into a base class:

```python
class BaseApi:
    def _get_and_verify_token(self, request: Request) -> Token:
        header_token = request.headers.get("X-Token-Id")
        token = Token.get_by_key(header_token)
        if not token:
            Errors.bad_token()
        return token

class UserApi(BaseApi):
    def __init__(self, queue_service: QueueService) -> None:
        self._queue_service = queue_service

    def update_user(self, user_id: str) -> dict[str, Any]:
        token = self._get_and_verify_token(request)
        user = self._get_and_verify_self(token, user_id)
        return {"user": user.to_dict()}
```

## Centralized Route Registration

Register all routes in a single function for discoverability:

```python
def setup_routing(app: App) -> None:
    app.route("/api/users", methods=["POST"], handler=users_api.create_user)
    app.route("/api/users/<user_id>", methods=["PUT"], handler=users_api.update_user)
    app.route("/api/users/<user_id>/orders", methods=["GET"], handler=orders_api.get_orders)
```

## Constructor Injection + Factory Builder

```python
class ServiceFactory:
    def __init__(self, config: Config) -> None:
        self._config = config

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

factory = ServiceFactory(load_config())
```

For simple apps, a plain module-level script can serve as the composition root:

```python
push_service = PushService()
queue_service = QueueService(push_service)
user_api = UserApi(queue_service)
```
