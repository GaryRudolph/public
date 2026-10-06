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
    id: Mapped[UUID] = mapped_column(primary_key=True)
    state: Mapped[str]
    total: Mapped[Decimal]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    __mapper_args__ = {"eager_defaults": True}

class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[UUID]
    quantity: Mapped[int]
    order: Mapped["Order"] = relationship(back_populates="items")
```

- **Timestamps are `timestamptz`** — `DateTime(timezone=True)`. A plain `DateTime` is `timestamp without time zone`, reads back naive, and fails the response model's `UtcDatetime` ([schemas](#request--response-schemas--pydantic))
- **`eager_defaults`** — reads server-set columns back with `RETURNING`. Without it, `updated_at` is expired after an `UPDATE`, and an async session can't lazy-load it

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

## Resource History — PostgreSQL

How a PostgreSQL table that opts in implements [Resource History](../architecture.md#resource-history):

- **Tables** — the head table plus `<table>_revisions(id, revision, created_at, actor_type, actor_sub, request_id, schema_version, snapshot jsonb)`, keyed `(id, revision)`, with `id` referencing the head `ON DELETE CASCADE`
- **jsonb snapshots, not typed mirror tables** — one generic trigger serves every table, history never needs a migration, and old rows stay truly immutable. Readers upcast by `schema_version`. `bytea` becomes a `"\\x…"` string inside jsonb, so store ciphertext as base64 text
- **One generic trigger pair** — a `BEFORE` trigger stamps the timestamps and enforces the counter; an `AFTER` trigger writes the snapshot. An Alembic migration creates them with `op.execute`
- **Hardening** — without these, the app role can bypass history:
  - The functions set `search_path = pg_catalog, pg_temp` and schema-qualify the revisions table, or a temp table can capture the inserts ([Writing `SECURITY DEFINER` Functions Safely](https://www.postgresql.org/docs/current/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY))
  - A non-login owner role owns the tables and functions, and migrations `SET ROLE` to it. The app role never owns a table, because an owner can disable its triggers
  - `clock_timestamp()`, not `now()`: `now()` is the transaction's start, so concurrent writers can stamp revisions out of order
  - An empty `app.actor_type` or `app.actor_sub` is rejected: on a pooled connection that set it in an earlier transaction, `current_setting` returns `''` instead of raising
  - `REVOKE ALL ON FUNCTION … FROM PUBLIC`: new functions are executable by `PUBLIC`. The triggers still fire for the app role, but it can't attach the `SECURITY DEFINER` function to a table of its own
- **Grants** — the app role gets `SELECT, INSERT, UPDATE` on the head (no `DELETE`; a delete sets `state`) and only `SELECT` on revisions. A separate purger role holds `DELETE` for purge (the foreign key cascades) and retention
- **Actor** — a `Session` `after_begin` hook sets `app.actor_type`, `app.actor_sub` and `app.request_id` for each transaction with `set_config(…, true)`; the revisions response nests the two columns as `actor{type, sub}`. An async auth dependency sets the `ContextVar`: a sync dependency runs in a threadpool, so what it sets never reaches the handler. Sessions without an actor (health checks, jobs) set empty values, and the trigger rejects their writes
- **Optimistic concurrency** — compare `If-Match` with the loaded `revision` (412 on mismatch), then let `version_id_col` guard the race between load and flush: SQLAlchemy writes `UPDATE … WHERE revision = :old` and raises `StaleDataError` when no row matches, also a 412. It emits no `UPDATE` when nothing changed, so a no-op write creates no revision
- **Trigger-set columns** — `FetchedValue()` plus `eager_defaults` so the ORM reads back what the trigger wrote
- **Snapshot keys** are snake_case column names, so the lowerCamel response model reads them with `validate_by_name=True`
- **No native option** — PostgreSQL has no system-versioned tables; [the PostgreSQL 19 docs](https://www.postgresql.org/docs/19/ddl-temporal-tables.html) (in beta) say to emulate them with triggers

```sql
-- One generic pair serves every table with history; history_owner (NOLOGIN) owns everything
CREATE FUNCTION rev_stamp() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  IF NULLIF(current_setting('app.actor_type', true), '') IS NULL
     OR NULLIF(current_setting('app.actor_sub', true), '') IS NULL THEN
    RAISE EXCEPTION 'app.actor_type and app.actor_sub must be set';
  END IF;
  NEW.updated_at := clock_timestamp();
  IF TG_OP = 'INSERT' THEN
    NEW.revision := 1;
    NEW.created_at := NEW.updated_at;
  ELSIF NEW.revision <> OLD.revision + 1 THEN
    RAISE EXCEPTION 'revision must be %', OLD.revision + 1;
  ELSE
    NEW.created_at := OLD.created_at;
  END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION rev_snapshot() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
  EXECUTE format('INSERT INTO %I.%I (id, revision, created_at, actor_type, actor_sub,
                  request_id, schema_version, snapshot) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)',
                 TG_TABLE_SCHEMA, TG_TABLE_NAME || '_revisions')
  USING NEW.id, NEW.revision, NEW.updated_at, current_setting('app.actor_type'),
        current_setting('app.actor_sub'), NULLIF(current_setting('app.request_id', true), ''),
        TG_ARGV[0]::int, to_jsonb(NEW) - 'revision' - 'created_at' - 'updated_at';
  RETURN NULL;
END $$;

CREATE TABLE books_revisions (
  id             uuid NOT NULL REFERENCES books ON DELETE CASCADE,
  revision       int NOT NULL,
  created_at     timestamptz NOT NULL,
  actor_type     text NOT NULL CHECK (actor_type IN ('USER', 'OPS', 'SERVICE')),
  actor_sub      text NOT NULL,
  request_id     text,
  schema_version int NOT NULL,
  snapshot       jsonb NOT NULL,
  PRIMARY KEY (id, revision)
);
CREATE TRIGGER stamp BEFORE INSERT OR UPDATE ON books
  FOR EACH ROW EXECUTE FUNCTION rev_stamp();
CREATE TRIGGER snapshot AFTER INSERT OR UPDATE ON books
  FOR EACH ROW EXECUTE FUNCTION rev_snapshot('1');  -- the snapshot's schema_version

REVOKE ALL ON FUNCTION rev_stamp(), rev_snapshot() FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON books TO app;
GRANT SELECT ON books_revisions TO app;
GRANT SELECT, DELETE ON books, books_revisions TO purger;
```

```python
# app/models/books.py
class Book(Base):
    __tablename__ = "books"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column()
    state: Mapped[str]
    title: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=FetchedValue()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=FetchedValue(), server_onupdate=FetchedValue()
    )
    __mapper_args__ = {"version_id_col": revision, "eager_defaults": True}

# app/models/database.py
from app.core.request_id import request_id  # set by RequestIdMiddleware

# (type, sub), set by the async auth dependency; empty outside a request
actor: ContextVar[tuple[str, str]] = ContextVar("actor", default=("", ""))

@event.listens_for(Session, "after_begin")
def _set_actor(session: Session, tx: SessionTransaction, conn: Connection) -> None:
    actor_type, actor_sub = actor.get()
    conn.execute(
        text(
            "SELECT set_config('app.actor_type', :t, true), set_config('app.actor_sub', :s, true),"
            " set_config('app.request_id', :r, true)"
        ),
        {"t": actor_type, "s": actor_sub, "r": request_id.get()},
    )

# app/api/books/services.py
async def rename_book(session: AsyncSession, book_id: UUID, if_match: int, title: str) -> Book:
    async with session.begin():
        book = await session.get(Book, book_id)
        if book is None or book.state == "DELETED":
            raise ProblemError(HTTPStatus.NOT_FOUND, "Book not found")
        if book.revision != if_match:
            raise ProblemError(HTTPStatus.PRECONDITION_FAILED, "Book has changed")
        book.title = title
        try:
            await session.flush()
        except StaleDataError:  # another write committed after the load
            raise ProblemError(HTTPStatus.PRECONDITION_FAILED, "Book has changed") from None
    return book
```

## Request Id

Every response carries `{Product}-Request-Id`, and every problem's `instance` is the same id ([Custom Headers](../architecture.md#custom-headers)). A small ASGI middleware mints it; asgi-correlation-id and similar packages use `X-Request-Id` and trust the inbound value:

```python
# app/core/request_id.py
from contextvars import ContextVar
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "Example-Request-Id"  # {Product}-Request-Id

request_id: ContextVar[str] = ContextVar("request_id", default="")


class RequestIdMiddleware:
    """Mints the id; never reads one from the request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        rid = str(uuid4())
        request_id.set(rid)  # not reset: the 500 handler runs after this returns

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = rid
            await send(message)

        await self.app(scope, receive, send_with_id)
```

- **Register it** in `main.py` with `app.add_middleware(RequestIdMiddleware)`
- **The 500 handler sets the header itself** — Starlette runs it in `ServerErrorMiddleware`, outside every app middleware, so `send_with_id` never sees that response
- **Logs** — a `logging.Filter` that copies `request_id.get()` and, once auth has run, the actor's `sub` onto each record puts both on every log line ([security.md](../security.md#logging))

## Error Catalog Pattern

Every error is an RFC 9457 problem (see [Error Responses](../architecture.md#error-responses-rfc-9457)). `ProblemError` carries one, with the request id as its `instance`; catalog classmethods raise it:

```python
# app/core/problems.py
import logging
from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Any, NoReturn, Self
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match

from app.core.request_id import REQUEST_ID_HEADER, request_id

PROBLEM_BASE = "https://api.example.com/problems/"


class ProblemError(Exception):
    def __init__(
        self,
        status: HTTPStatus,
        detail: str,
        type_: str = "about:blank",
        title: str | None = None,
        errors: list[dict[str, str]] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.type = type_
        self.title = title or status.phrase
        self.errors = errors
        self.headers = dict(headers or {})
        rid = request_id.get()
        self.instance = f"urn:uuid:{rid}" if rid else None

    @classmethod
    def validation(cls, errors: list[dict[str, str]]) -> Self:
        return cls(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "One or more fields are invalid",
            type_=PROBLEM_BASE + "validation-error",
            title="Request validation failed",
            errors=errors,
        )

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": self.type,
            "title": self.title,
            "status": int(self.status),
            "detail": self.detail,
        }
        if self.instance:
            body["instance"] = self.instance
        if self.errors:
            body["errors"] = self.errors
        return body


class Errors:
    @classmethod
    def user_not_found(cls) -> NoReturn:
        raise ProblemError(HTTPStatus.NOT_FOUND, "User not found")

    @classmethod
    def bad_token(cls) -> NoReturn:
        raise ProblemError(  # RFC 9110 §15.5.2 challenge; RFC 6750 §3.1 error
            HTTPStatus.UNAUTHORIZED,
            "Bad token",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )

    @classmethod
    def required_field(cls, field: str) -> NoReturn:
        raise ProblemError.validation(
            [{"detail": "is required", "pointer": f"#/{field}"}]
        )
```

Register the handlers in `main.py` with `register_problem_handlers(app)`. They render `ProblemError`, turn FastAPI's own validation and HTTP errors into problems (the router's 404 and 405 included), and make anything else an opaque 500 (Starlette still logs the traceback):

```python
# app/core/problems.py (continued)
PROBLEM_JSON = "application/problem+json"
INTERNAL_ERROR = "an internal error occurred"
METHODS = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")

logger = logging.getLogger(__name__)


def _render(
    problem: ProblemError, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    if problem.status >= 500 and problem.detail != INTERNAL_ERROR:
        # 5xx is opaque: the log keeps what was said, the client gets the generic detail
        logger.error("server error %d: %s", problem.status, problem.detail)
        problem = ProblemError(problem.status, INTERNAL_ERROR, headers=problem.headers)
    return JSONResponse(
        problem.to_dict(),
        status_code=problem.status,
        headers={**problem.headers, **(headers or {})},
        media_type=PROBLEM_JSON,
    )


def http_problem(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Renders an HTTPException, the router's 404 and 405 included, as a problem."""
    headers = dict(exc.headers or {})
    if exc.status_code == HTTPStatus.METHOD_NOT_ALLOWED:
        headers["Allow"] = _allow(request)
    return _render(ProblemError(HTTPStatus(exc.status_code), str(exc.detail)), headers)


def _allow(request: Request) -> str:
    """Every method the path accepts. Starlette's own Allow names only the first
    route whose path matched, and RFC 9110 §15.5.6 wants them all."""
    routes = request.app.router.routes  # included routers too
    return ", ".join(
        method
        for method in METHODS
        if any(
            r.matches({**request.scope, "method": method})[0] is Match.FULL
            for r in routes
        )
    )


def _token(part: str | int) -> str:
    """RFC 6901 §3 escaping, then §6 percent-encoding, as Go's url.PathEscape."""
    return quote(str(part).replace("~", "~0").replace("/", "~1"), safe="$&+:=@")


def _locate(loc: Sequence[str | int]) -> dict[str, str]:
    where, *rest = loc
    if where == "body":
        return {"pointer": "#" + "".join(f"/{_token(p)}" for p in rest)}
    return {"header" if where == "header" else "parameter": str(rest[0])}


def _unparsable(error: Mapping[str, Any]) -> bool:
    """Malformed JSON, no body, or a literal null body: a 400.

    Go matches on the first two; it decodes null into a zero struct and
    validates it (422). null is never a valid resource, so 400 here is fine.
    """
    return error["type"] == "json_invalid" or (
        error["type"] == "missing" and tuple(error["loc"]) == ("body",)
    )


def register_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def problem(request: Request, exc: ProblemError) -> JSONResponse:
        return _render(exc)

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        if any(_unparsable(e) for e in exc.errors()):
            return _render(
                ProblemError(HTTPStatus.BAD_REQUEST, "request body is not valid JSON")
            )
        errors = [{"detail": e["msg"], **_locate(e["loc"])} for e in exc.errors()]
        return _render(ProblemError.validation(errors))

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return http_problem(request, exc)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        problem = ProblemError(HTTPStatus.INTERNAL_SERVER_ERROR, INTERNAL_ERROR)
        return _render(problem, {REQUEST_ID_HEADER: request_id.get()})
```

- **5xx is opaque** — `_render` sends the generic detail for any `5xx`, so `ProblemError(HTTPStatus.SERVICE_UNAVAILABLE, str(err))` can't leak, and logs what was said; the log filter adds the request id
- **`Allow` is rebuilt** — Starlette's `405` lists only the first route that matched the path, so `DELETE /orders` beside separate `GET` and `POST` routes says `Allow: GET`. `http_problem` asks every route which methods it would take for the path
- **Decoding is more lenient than Go** — Python's `json` keeps the last of duplicate keys instead of rejecting them, and `validate_by_name` accepts snake keys in bodies ([API Design](../architecture.md#api-design))

## Request / Response Schemas — Pydantic

Every API model inherits one shared base in `app/api/schemas.py`, so attributes stay snake_case and JSON keys are lowerCamel ([API Design](../architecture.md#api-design)):

```python
# app/api/schemas.py
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, PlainSerializer
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,  # photo_url <-> "photoUrl"
        serialize_by_alias=True,  # model_dump() writes camel too, not only FastAPI
        validate_by_name=True,  # Model(photo_url=...) type-checks and runs
    )


class ApiRequest(ApiModel):
    model_config = ConfigDict(extra="forbid")  # an unknown member is a 422


# A naive datetime is a validation error; output is UTC with Z
UtcDatetime = Annotated[
    AwareDatetime, PlainSerializer(lambda v: v.astimezone(UTC), return_type=datetime)
]


class Data[T](ApiModel):
    data: T
    meta: dict[str, Any] = Field(default_factory=dict)
```

Domain models live in `app/api/{domain}/schemas.py` alongside the router and service that use them:

```python
# app/api/orders/schemas.py
class OrderState(StrEnum):
    PENDING = "PENDING"
    SHIPPED = "SHIPPED"
    CANCELLED = "CANCELLED"


class OrderItemRequest(ApiRequest):
    product_id: UUID
    quantity: int = Field(ge=1)


class CreateOrderRequest(ApiRequest):
    total: Decimal
    items: list[OrderItemRequest]


class OrderResponse(ApiModel):
    id: UUID
    state: OrderState
    total: Decimal
    created_at: UtcDatetime
    updated_at: UtcDatetime

    model_config = ConfigDict(from_attributes=True)


class ListOrdersParams(ApiRequest):
    show_deleted: bool = False
```

- **Only the wire is camel** — attributes, columns and revision snapshots stay snake_case
- **Construct by field name** — `OrderResponse(created_at=…)`. pyright knows only field names and rejects `createdAt=`; without `validate_by_name`, field names fail at runtime and `from_attributes` can't read ORM attributes. The cost is that request bodies also accept the snake spelling
- **Strict decoding** — `ApiRequest` forbids extra members, so an unknown or output-only member (`state` in a create) is a 422 with a `pointer` to it
- **Wire enums** — explicit `UPPER_SNAKE` values, not `auto()` ([code-style.md](code-style.md#enumerations)). With no `*_UNSPECIFIED` member, that value is a 422 like any unknown one
- **Timestamps** — `UtcDatetime` everywhere ([Timestamps](../architecture.md#timestamps)). `AwareDatetime` makes a naive input a 422 and a naive column fail loudly; the serializer turns a local offset into UTC, which Pydantic writes with `Z`
- **Money** — Pydantic writes `Decimal` as a JSON string, as the [JSON rule](../architecture.md#api-design) requires
- **Query parameters** — a query model on `ApiRequest` (`params: Annotated[ListOrdersParams, Query()]`) reads `showDeleted` and rejects unknown parameters; a lone parameter needs `Query(alias="showDeleted")`
- **Envelope** — success bodies are `Data[T]`, which renders `{"data": …, "meta": {}}`

## Base API / Handler Pattern

FastAPI dependency injection handles auth and sessions; a base class holds the checks services share. The token travels as `Authorization: Bearer` ([RFC 6750] §2.1), never a custom header:

```python
# app/api/auth.py
# A missing or non-Bearer Authorization header is a 401 with WWW-Authenticate: Bearer
bearer = HTTPBearer()


async def current_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    token_store: Annotated[TokenStore, Depends(get_token_store)],
) -> Token:
    token = await token_store.get_by_key(credentials.credentials)
    if token is None:
        Errors.bad_token()
    actor.set(("USER", token.sub))  # async, so the handler and session see it
    return token


CurrentToken = Annotated[Token, Depends(current_token)]

# app/api/base.py
class BaseService:
    def _verify_self(self, token: Token, user_id: UUID) -> None:
        if token.user_id != user_id:
            Errors.user_not_found()  # hidden, so 404 and not 403

# app/api/users/services.py
class UserService(BaseService):
    def __init__(self, user_store: UserStore, queue_service: QueueService) -> None:
        self._user_store = user_store
        self._queue_service = queue_service

    async def update_user(
        self, token: Token, user_id: UUID, body: UpdateUserRequest
    ) -> UserResponse:
        self._verify_self(token, user_id)
        user = await self._user_store.update(user_id, body)
        return UserResponse.model_validate(user)
```

- **Every 401 carries `WWW-Authenticate`** ([RFC 9110] §15.5.2). `HTTPBearer` sends `Bearer` for missing credentials, and the problem handler keeps its headers; a rejected token adds `error="invalid_token"` ([RFC 6750] §3.1). FastAPI before 0.122 answered missing credentials with 403 and no challenge

## Centralized Route Registration

Register all routers in a single function for discoverability. Each `app/api/{domain}/router.py` exports a `router`:

```python
# main.py
def setup_routing(app: FastAPI) -> None:
    app.include_router(users_router, prefix="/api/v1/users")
    app.include_router(orders_router, prefix="/api/v1/orders")

# app/api/orders/router.py
from app.api.auth import CurrentToken
from app.api.orders.schemas import CreateOrderRequest, ListOrdersParams, OrderResponse
from app.api.orders.services import OrderService, get_order_service
from app.api.schemas import Data

router = APIRouter()
Service = Annotated[OrderService, Depends(get_order_service)]


@router.post("", status_code=HTTPStatus.CREATED)
async def create_order(
    body: CreateOrderRequest,
    token: CurrentToken,
    service: Service,
    request: Request,
    response: Response,
) -> Data[OrderResponse]:
    order = await service.create_order(token, body)
    location = request.app.url_path_for("get_order", order_id=order.id)
    response.headers["Location"] = location  # /api/v1/orders/{id}
    return Data(data=OrderResponse.model_validate(order))


@router.get("/{order_id}")
async def get_order(
    order_id: UUID, token: CurrentToken, service: Service
) -> Data[OrderResponse]: ...


@router.get("")
async def list_orders(
    params: Annotated[ListOrdersParams, Query()], token: CurrentToken, service: Service
) -> Data[list[OrderResponse]]: ...
```

- **A create is `201` with `Location`** ([RFC 9110] §9.3.3, §15.3.2). `request.app.url_path_for` builds the path with the router's prefix; a path is a valid `Location`
- **The return annotation is the response model** — no `response_model=` needed
- **Collection paths have no trailing slash** — `""`, not `"/"`, under the prefix, or `POST /api/v1/orders` redirects

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

[RFC 6750]: https://www.rfc-editor.org/rfc/rfc6750
[RFC 9110]: https://www.rfc-editor.org/rfc/rfc9110
