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

## Resource History — Firestore

How a Firestore resource type that opts in implements [Resource History](../architecture.md#resource-history):

```
books/{id}                 head: fields, revision, state, createdAt, updatedAt
books/{id}/revisions/{n}   revision, createdAt, actor{type, sub}, requestId, schemaVersion, snapshot{…}
```

- **One `RunTransaction` per write** — `tx.Get` the head: missing or `DELETED` is `ErrNotFound` (404), and a `revision` that doesn't match `If-Match` is `ErrPreconditionFailed` (412). Then `tx.Set` the head and `tx.Create` the revision. `Create` fails if the document exists, so a revision is never overwritten. Skip both writes when nothing changed: `Book` is comparable, so `==` against a copy taken before the change works; a struct with slices or maps needs a field-by-field compare
- **Commit time** — a zero `serverTimestamp` field resolves to the commit time, the same in both documents, so the head's `updatedAt` equals the revision's `createdAt`
- **Order by the `revision` field**, never the document id, since string ids sort `"10"` before `"9"`: `OrderBy("revision", firestore.Desc)`
- **Exempt `snapshot` from indexing** — a `fieldOverrides` entry in `firestore.indexes.json` with `"collectionGroup": "revisions"`, `"fieldPath": "snapshot"`, `"indexes": []`; a map's subfields inherit the exemption. Cross-resource history runs in BigQuery
- **Immutability is enforced by code only** — IAM applies per database and server SDKs bypass Security Rules, so any identity that can write the database can rewrite history. The repository is the only writer and only ever calls `Create` on revisions
- **Retention is a purge job, not TTL** — a revision's TTL field is fixed when it's written, so TTL would also expire the current revision's copy. The job deletes revisions past the type's cutoff and skips the head's current `revision`
- **Purge** — deleting a document doesn't delete its subcollections, and Go has no recursive delete. Delete the revisions first with `BulkWriter`, check every job's result, list again until none are left, and only then delete the head. `BulkWriter` applies writes neither atomically nor in order, so an unchecked failure leaves orphaned revisions that still hold data

Audit logs: [gcp.md](../gcp.md#resource-history-stores). The BigQuery export and backups: [gcp.md](../gcp.md#encryption-and-erasure).

```go
// internal/book/firestore.go
var ErrPreconditionFailed = errors.New("precondition failed") // 412

// Book holds the resource fields; a revision's snapshot is exactly this.
type Book struct {
    Title string `firestore:"title"`
    State string `firestore:"state"`
}

type head struct {
    Book                // embedded: its fields sit at the top level
    Revision  int64     `firestore:"revision"`
    CreatedAt time.Time `firestore:"createdAt"`
    UpdatedAt time.Time `firestore:"updatedAt,serverTimestamp"` // zero = commit time
}

// Actor is who made the change; Type is USER, OPS or SERVICE.
type Actor struct {
    Type string `firestore:"type"`
    Sub  string `firestore:"sub"`
}

type revision struct {
    Revision      int64     `firestore:"revision"`
    CreatedAt     time.Time `firestore:"createdAt,serverTimestamp"`
    Actor         Actor     `firestore:"actor"`
    RequestID     string    `firestore:"requestId"`
    SchemaVersion int       `firestore:"schemaVersion"`
    Snapshot      Book      `firestore:"snapshot"`
}

func (s *FirestoreStore) Update(ctx context.Context, id string, ifMatch int64,
    actor Actor, requestID string, fn func(*Book)) (int64, error) {
    ref := s.client.Collection("books").Doc(id)
    var rev int64
    err := s.client.RunTransaction(ctx, func(ctx context.Context, tx *firestore.Transaction) error {
        snap, err := tx.Get(ref)
        if status.Code(err) == codes.NotFound {
            return ErrNotFound
        } else if err != nil {
            return err
        }
        var h head
        if err := snap.DataTo(&h); err != nil {
            return err
        }
        if h.State == "DELETED" {
            return ErrNotFound
        }
        if h.Revision != ifMatch {
            return ErrPreconditionFailed
        }
        before := h.Book
        fn(&h.Book)
        if h.Book == before { // no-op: no revision, same ETag
            rev = h.Revision
            return nil
        }
        h.Revision++
        h.UpdatedAt = time.Time{}
        rev = h.Revision
        if err := tx.Set(ref, h); err != nil {
            return err
        }
        return tx.Create(ref.Collection("revisions").Doc(strconv.FormatInt(rev, 10)), revision{
            Revision: rev, Actor: actor, RequestID: requestID, SchemaVersion: 1, Snapshot: h.Book,
        })
    })
    return rev, err
}

// Purge hard-deletes a book: every revision first, then the head.
func (s *FirestoreStore) Purge(ctx context.Context, id string) error {
    ref := s.client.Collection("books").Doc(id)
    for {
        refs, err := ref.Collection("revisions").DocumentRefs(ctx).GetAll()
        if err != nil {
            return err
        }
        if len(refs) == 0 {
            break
        }
        bw := s.client.BulkWriter(ctx) // writes each document at most once
        jobs := make([]*firestore.BulkWriterJob, 0, len(refs))
        for _, r := range refs {
            j, err := bw.Delete(r)
            if err != nil {
                return err
            }
            jobs = append(jobs, j)
        }
        bw.End()
        for _, j := range jobs {
            if _, err := j.Results(); err != nil {
                return fmt.Errorf("purge revision: %w", err)
            }
        }
    }
    _, err := ref.Delete(ctx)
    return err
}
```

## Error Catalog

Centralize domain errors. Handlers map them to RFC 9457 problem responses (see [Error Responses](../architecture.md#error-responses-rfc-9457)):

```go
var (
    ErrNotFound     = errors.New("not found")
    ErrUnauthorized = errors.New("unauthorized")
)

const problemBase = "https://api.example.com/problems/"

// Problem is an RFC 9457 problem details object.
type Problem struct {
    Type     string       `json:"type"`
    Title    string       `json:"title"`
    Status   int          `json:"status"`
    Detail   string       `json:"detail,omitempty"`
    Instance string       `json:"instance,omitempty"`
    Errors   []FieldError `json:"errors,omitempty"`
}

// FieldError is one item of the "errors" extension. Set exactly one locator.
type FieldError struct {
    Detail    string `json:"detail"`
    Pointer   string `json:"pointer,omitempty"`
    Parameter string `json:"parameter,omitempty"`
    Header    string `json:"header,omitempty"`
}

func (p *Problem) Error() string { return p.Title + ": " + p.Detail }

func NotFound(resource string) *Problem {
    return &Problem{
        Type:   "about:blank",
        Title:  http.StatusText(http.StatusNotFound),
        Status: http.StatusNotFound,
        Detail: resource + " not found",
    }
}

func Validation(errs ...FieldError) *Problem {
    return &Problem{
        Type:   problemBase + "validation-error",
        Title:  "Request validation failed",
        Status: http.StatusUnprocessableEntity,
        Detail: "One or more fields are invalid",
        Errors: errs,
    }
}
```

**Layers:**

1. **Service** — returns domain errors (`ErrNotFound`, `*Problem`)
2. **Handler** — maps errors to a `*Problem` and writes `application/problem+json` (see [security.md](security.md#error-boundaries))
3. **Middleware** — catches unexpected panics/errors, logs, returns an `about:blank` 500 problem

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
