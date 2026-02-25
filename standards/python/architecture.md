# Architecture — Python

Follows [architecture.md](../architecture.md).

## Module Structure

```
feature/
├── __init__.py          # Public API
├── types.py             # Type definitions
├── service.py           # Business logic
├── store.py             # Data access
├── validators.py        # Input validation
└── tests/
    ├── test_service.py
    └── test_store.py
```

## Data Access — Store Pattern

Models are plain data classes. A separate store class owns all persistence logic:

```python
@dataclass
class Order:
    class State(StrEnum):
        PENDING = auto()
        SHIPPED = auto()

    order_id: UUID
    state: State
    total: Decimal

class OrderStore(Protocol):
    async def get(self, order_id: UUID) -> Order | None: ...
    async def save(self, order: Order) -> Order: ...

class DynamoOrderStore:
    def __init__(self, table: Table) -> None:
        self._table = table

    async def get(self, order_id: UUID) -> Order | None: ...
    async def save(self, order: Order) -> Order: ...
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
    def __init__(self, token_store: TokenStore) -> None:
        self._token_store = token_store

    def _get_and_verify_token(self, request: Request) -> Token:
        header_token = request.headers.get("X-Token-Id")
        token = self._token_store.get_by_key(header_token)
        if not token:
            Errors.bad_token()
        return token

class UserApi(BaseApi):
    def __init__(self, token_store: TokenStore, queue_service: QueueService) -> None:
        super().__init__(token_store)
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
    def order_store(self) -> OrderStore:
        return DynamoOrderStore(table=self._config.table_name)

    @cached_property
    def order_service(self) -> OrderService:
        return OrderService(
            order_store=self.order_store,
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
