# Architecture — Python

Follows [architecture.md](../architecture.md).

## Technology Stack

| Concern | Library |
|---|---|
| REST framework | FastAPI |
| Validation / schemas | Pydantic v2 |
| ORM — PostgreSQL | SQLAlchemy 2.x (async) |
| ORM — DynamoDB | PynamoDB |

## Settings

App configuration lives in `app/core/config.py` using `pydantic-settings`. All env vars are declared here and accessed via a single `settings` instance:

```python
# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
```

## Module Structure

Follows the FastAPI `app/` convention. Routes, Pydantic schemas, and service logic live under `app/api/{domain}/`. SQLAlchemy ORM models and database setup live under `app/models/`.

```
app/
├── main.py              # FastAPI app entry point, route registration
├── core/
│   └── config.py        # Pydantic-settings Settings class
├── api/
│   ├── schemas.py       # Shared/base Pydantic schemas (pagination, errors, etc.)
│   ├── services.py      # Shared/base services, logic (auth, permissions, etc.)
│   └── orders/
│       ├── router.py    # FastAPI routes
│       ├── schemas.py   # Pydantic request/response models
│       └── services.py  # Business logic
└── models/
    ├── base.py          # SQLAlchemy DeclarativeBase
    ├── database.py      # SQLAlchemy engine and session factory
    └── orders.py        # ORM models for the orders domain
alembic/
├── env.py               # Alembic environment config
├── script.py.mako       # Migration template
└── versions/            # Generated migration files
alembic.ini              # Alembic configuration
docker/
├── Dockerfile
└── docker-compose.yml
```

## Data Access — Models

### PostgreSQL — SQLAlchemy

ORM table definitions live in `app/models/{domain}.py`. `DeclarativeBase` lives in `app/models/base.py` and is imported by all model files. Database session setup lives in `app/models/database.py`:

```python
# app/models/base.py
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

# app/models/database.py
engine = create_async_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

# app/models/orders.py
class Order(Base):
    __tablename__ = "orders"
    order_id: Mapped[UUID] = mapped_column(primary_key=True)
    state: Mapped[str]
    total: Mapped[Decimal]
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    item_id: Mapped[UUID] = mapped_column(primary_key=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.order_id"))
    product_id: Mapped[UUID]
    quantity: Mapped[int]
    order: Mapped["Order"] = relationship(back_populates="items")
```

### DynamoDB — PynamoDB

PynamoDB model definitions also live in `app/models/{domain}.py`:

```python
# app/models/orders.py
class OrderItem(MapAttribute):
    item_id = UnicodeAttribute()
    product_id = UnicodeAttribute()
    quantity = NumberAttribute()

class Order(Model):
    class Meta:
        table_name = "orders"

    order_id = UnicodeAttribute(hash_key=True)
    state = UnicodeAttribute()
    total = NumberAttribute()
    items = ListAttribute(of=OrderItem)
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

Pydantic models for request bodies and response shapes live in `app/api/{domain}/schemas.py` alongside the router and service that use them:

```python
# app/api/orders/schemas.py
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
# app/api/base.py
class BaseService:
    def __init__(self, token_store: TokenStore) -> None:
        self._token_store = token_store

    def _get_and_verify_token(self, request: Request) -> Token:
        header_token = request.headers.get("X-Token-Id")
        token = self._token_store.get_by_key(header_token)
        if not token:
            Errors.bad_token()
        return token

# app/api/users/services.py
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

Register all routers in a single function for discoverability. Each `app/api/{domain}/router.py` exports a `router`:

```python
# main.py
def setup_routing(app: FastAPI) -> None:
    app.include_router(users_router, prefix="/api/v1/users")
    app.include_router(orders_router, prefix="/api/v1/orders")

# app/api/orders/router.py
from app.api.orders.schemas import CreateOrderRequest, OrderResponse
from app.api.orders.service import OrderService

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
