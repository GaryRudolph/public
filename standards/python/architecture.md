# Architecture — Python

Follows [architecture.md](../architecture.md).

## Technology Stack

| Concern | Library |
|---|---|
| REST framework | FastAPI |
| Validation / schemas | Pydantic v2 |
| ORM — PostgreSQL | SQLAlchemy 2.x (async) |
| ORM — DynamoDB | PynamoDB |

## Module Structure

FastAPI routes, Pydantic schemas, and service logic live together under `services/{domain}/`. SQLAlchemy ORM models and database setup live under `models/`.

**Standard layout:**
```
services/
└── orders/
    ├── router.py        # FastAPI routes
    ├── schemas.py       # Pydantic request/response models
    └── service.py       # Business logic
models/
├── database.py          # SQLAlchemy engine and session factory
└── orders.py            # SQLAlchemy ORM models for the orders domain
```

## Data Access — Models

### PostgreSQL — SQLAlchemy

ORM table definitions live in `models/{domain}.py`. Database session setup lives in `models/database.py`:

```python
# models/database.py
engine = create_async_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

# models/orders.py
class OrderRow(Base):
    __tablename__ = "orders"
    order_id: Mapped[UUID] = mapped_column(primary_key=True)
    state: Mapped[str]
    total: Mapped[Decimal]
```

### DynamoDB — PynamoDB

PynamoDB model definitions also live in `models/{domain}.py`:

```python
# models/orders.py
class OrderModel(Model):
    class Meta:
        table_name = "orders"

    order_id = UnicodeAttribute(hash_key=True)
    state = UnicodeAttribute()
    total = NumberAttribute()
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

## Request / Response Schemas — Pydantic

Pydantic models for request bodies and response shapes live in `services/{domain}/schemas.py` alongside the router and service that use them:

```python
# services/orders/schemas.py
class CreateOrderRequest(BaseModel):
    total: Decimal
    items: list[OrderItemRequest]

class OrderResponse(BaseModel):
    order_id: UUID
    state: str
    total: Decimal

    model_config = ConfigDict(from_attributes=True)
```

## Base API / Handler Pattern

Extract shared request handling into a base class. FastAPI dependency injection handles auth and sessions:

```python
# services/base.py
class BaseService:
    def __init__(self, token_store: TokenStore) -> None:
        self._token_store = token_store

    def _get_and_verify_token(self, request: Request) -> Token:
        header_token = request.headers.get("X-Token-Id")
        token = self._token_store.get_by_key(header_token)
        if not token:
            Errors.bad_token()
        return token

# services/users/service.py
class UserService(BaseService):
    def __init__(self, token_store: TokenStore, queue_service: QueueService) -> None:
        super().__init__(token_store)
        self._queue_service = queue_service

    async def update_user(self, user_id: str, body: UpdateUserRequest, request: Request) -> UserResponse:
        token = self._get_and_verify_token(request)
        user = self._get_and_verify_self(token, user_id)
        return UserResponse.model_validate(user)
```

## Centralized Route Registration

Register all routers in a single function for discoverability. Each `services/{domain}/router.py` exports a `router`:

```python
# main.py
def setup_routing(app: FastAPI) -> None:
    app.include_router(users_router, prefix="/api/v1/users")
    app.include_router(orders_router, prefix="/api/v1/orders")

# services/orders/router.py
from services.orders.schemas import CreateOrderRequest, OrderResponse
from services.orders.service import OrderService

router = APIRouter()

@router.post("/", response_model=OrderResponse, status_code=201)
async def create_order(body: CreateOrderRequest, service: OrderService = Depends()) -> OrderResponse: ...

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: UUID, service: OrderService = Depends()) -> OrderResponse: ...
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
