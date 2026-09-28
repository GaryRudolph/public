# Architecture — Go

Follows [architecture.md](../architecture.md).

Target **Go 1.26** for new projects.

## Technology Stack

| Concern | Library |
|---|---|
| HTTP routing | `net/http` (Go 1.22+ `ServeMux`); `go-chi/chi` when route groups/middleware are needed |
| ORM — PostgreSQL | GORM (`gorm.io/gorm`) with `gorm.io/driver/postgres` (pgx driver) |
| Document store — Firestore | `cloud.google.com/go/firestore` |
| Data warehouse — BigQuery | `cloud.google.com/go/bigquery` |
| Validation | `github.com/go-playground/validator/v10` |
| Configuration | `github.com/caarlos0/env/v11` |
| Structured logging | `log/slog` |
| JWT | `github.com/golang-jwt/jwt/v5` |

## Project Layout

Start flat. Add structure when pain appears — not before.

```
myapp/
├── go.mod
├── main.go                 # composition root (wiring + server start)
├── internal/
│   ├── config/
│   │   └── config.go       # env-based Config struct
│   ├── user/
│   │   ├── handler.go      # HTTP handlers
│   │   ├── service.go      # business logic
│   │   ├── store.go        # Store interface
│   │   └── postgres.go     # GORM implementation
│   └── order/
│       ├── handler.go
│       ├── service.go
│       ├── store.go
│       └── firestore.go    # Firestore implementation
└── docker/
    ├── Dockerfile
    └── docker-compose.yml
```

**Rules:**

- **`internal/`** — compiler-enforced privacy; all implementation packages live here
- **`cmd/`** — only when the repo has **multiple binaries**; otherwise `main.go` at root
- **No `pkg/`** — the Go team does not recommend it; import paths stay short
- Domain packages group by feature (`user/`, `order/`), not by layer (`handlers/`, `services/`)

## Configuration

App configuration lives in `internal/config/config.go`. All env vars are declared here and parsed at startup:

```go
// internal/config/config.go
package config

import "github.com/caarlos0/env/v11"

type Config struct {
    Port        int    `env:"PORT" envDefault:"8080"`
    DatabaseURL string `env:"DATABASE_URL,required"`
    GCPProject  string `env:"GCP_PROJECT,required"`
    JWTSecret   string `env:"JWT_SECRET,required"`
    Environment string `env:"ENVIRONMENT" envDefault:"development"`
}

func Load() (Config, error) {
    var cfg Config
    return cfg, env.Parse(&cfg)
}
```

Missing `required` fields fail at startup. Secrets come from env vars or GCP Secret Manager — never from source code.

## HTTP Routing

Prefer stdlib `net/http` with Go 1.22+ method and path patterns:

```go
mux := http.NewServeMux()
mux.HandleFunc("GET /api/v1/users/{id}", userHandler.Get)
mux.HandleFunc("POST /api/v1/users", userHandler.Create)
```

Reach for **chi** when you need route groups, middleware stacks, or URL parameters with less boilerplate — chi stays 100% compatible with `net/http` handler types:

```go
r := chi.NewRouter()
r.Route("/api/v1", func(r chi.Router) {
    r.Use(authMiddleware)
    r.Get("/users/{id}", userHandler.Get)
    r.Post("/users", userHandler.Create)
})
```

## Manual Constructor Injection

All dependencies via constructor. A single **composition root** (`main.go`) wires everything. Packages never create their own collaborators.

```go
// internal/user/service.go
type Store interface {
    FindByID(ctx context.Context, id string) (*User, error)
    Save(ctx context.Context, user *User) error
}

type Service struct {
    store Store
}

func NewService(store Store) *Service {
    return &Service{store: store}
}
```

```go
// main.go — composition root
func main() {
    cfg, err := config.Load()
    if err != nil { log.Fatal(err) }

    db, err := gorm.Open(postgres.Open(cfg.DatabaseURL), &gorm.Config{})
    if err != nil { log.Fatal(err) }

    userStore := user.NewPostgresStore(db)
    userService := user.NewService(userStore)
    userHandler := user.NewHandler(userService)

    mux := http.NewServeMux()
    mux.HandleFunc("GET /api/v1/users/{id}", userHandler.Get)

    srv := &http.Server{Addr: fmt.Sprintf(":%d", cfg.Port), Handler: mux}
    // graceful shutdown (see below)
}
```

**When to graduate to `google/wire`:** manual wiring exceeds ~30 lines and the dependency graph is static. Avoid runtime DI frameworks (`uber/fx`) unless you need plugin-style lifecycle management.

## Repository Pattern

Define the **interface near the consumer** (service), not the implementation. Each datastore gets its own implementation file.

### PostgreSQL — GORM

```go
// internal/user/postgres.go
type PostgresStore struct {
    db *gorm.DB
}

func NewPostgresStore(db *gorm.DB) *PostgresStore {
    return &PostgresStore{db: db}
}

type User struct {
    ID    uuid.UUID `gorm:"type:uuid;primaryKey"`
    Email string    `gorm:"uniqueIndex;not null"`
    Name  string
}

func (s *PostgresStore) FindByID(ctx context.Context, id string) (*User, error) {
    var u User
    if err := s.db.WithContext(ctx).First(&u, "id = ?", id).Error; err != nil {
        if errors.Is(err, gorm.ErrRecordNotFound) {
            return nil, ErrNotFound
        }
        return nil, fmt.Errorf("find user: %w", err)
    }
    return &u, nil
}
```

### Firestore

```go
// internal/order/firestore.go
type FirestoreStore struct {
    client *firestore.Client
}

type Order struct {
    ID    string    `firestore:"id"`
    State string    `firestore:"state"`
    Total float64   `firestore:"total"`
    Items []Item    `firestore:"items"`
}

func (s *FirestoreStore) FindByID(ctx context.Context, id string) (*Order, error) {
    doc, err := s.client.Collection("orders").Doc(id).Get(ctx)
    if err != nil {
        if status.Code(err) == codes.NotFound {
            return nil, ErrNotFound
        }
        return nil, fmt.Errorf("get order: %w", err)
    }
    var o Order
    if err := doc.DataTo(&o); err != nil {
        return nil, fmt.Errorf("decode order: %w", err)
    }
    return &o, nil
}
```

### BigQuery

Use the official client for analytics/warehouse queries. Keep domain types free of BigQuery-specific types — map in the repository layer.

```go
type Event struct {
    Name string    `bigquery:"name"`
    At   time.Time `bigquery:"event_time"`
}

func (s *BigQueryStore) QueryEvents(ctx context.Context, since time.Time) ([]Event, error) {
    q := s.client.Query("SELECT name, event_time FROM events WHERE event_time > @since")
    q.Parameters = []bigquery.QueryParameter{{Name: "since", Value: since}}
    it, err := q.Read(ctx)
    // iterate rows into []Event
}
```

**Rules:**

- `context.Context` as the **first parameter** on every store/service method
- Domain structs stay storage-agnostic — map Firestore/BigQuery types in the repository
- GORM handles migrations via `AutoMigrate` in dev; use `golang-migrate` or goose for production

## Error Catalog

Centralize domain errors. Handlers map them to HTTP responses:

```go
var (
    ErrNotFound     = errors.New("not found")
    ErrUnauthorized = errors.New("unauthorized")
    ErrValidation   = errors.New("validation failed")
)

type AppError struct {
    Status  int
    Code    string
    Message string
}

func (e *AppError) Error() string { return e.Message }

func NotFound(resource string) *AppError {
    return &AppError{http.StatusNotFound, "NOT_FOUND", resource + " not found"}
}
```

**Layers:**

1. **Service** — returns domain errors (`ErrNotFound`, `*AppError`)
2. **Handler** — catches errors, writes JSON response
3. **Middleware** — catches unexpected panics/errors, logs, returns safe 500

## Graceful Shutdown

```go
ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
defer stop()

go func() {
    if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
        slog.Error("server error", "err", err)
    }
}()

<-ctx.Done()
shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
defer cancel()
if err := srv.Shutdown(shutdownCtx); err != nil {
    slog.Error("shutdown error", "err", err)
}
```

## Constructor Injection + Factory Builder

For larger apps, extract wiring into a factory function — still manual, still explicit:

```go
type App struct {
    UserHandler *user.Handler
    Server      *http.Server
}

func NewApp(cfg config.Config) (*App, error) {
    db, err := gorm.Open(postgres.Open(cfg.DatabaseURL), &gorm.Config{})
    if err != nil { return nil, err }

    userStore := user.NewPostgresStore(db)
    userService := user.NewService(userStore)
    userHandler := user.NewHandler(userService)

    mux := http.NewServeMux()
    mux.HandleFunc("GET /api/v1/users/{id}", userHandler.Get)

    return &App{
        UserHandler: userHandler,
        Server:      &http.Server{Addr: fmt.Sprintf(":%d", cfg.Port), Handler: mux},
    }, nil
}
```
