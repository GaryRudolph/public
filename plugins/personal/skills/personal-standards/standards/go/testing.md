# Testing — Go

Follows [testing.md](../testing.md).

## testify

Use `github.com/stretchr/testify` for assertions:

- **`require`** — stops the test on failure (setup/preconditions)
- **`assert`** — continues on failure (multiple checks in one test)

```go
func TestGetUser(t *testing.T) {
    svc := NewService(fakeStore{user: &User{ID: "1", Name: "Alice"}})

    user, err := svc.GetUser(t.Context(), "1")
    require.NoError(t, err)
    require.Equal(t, "Alice", user.Name)
}
```

## Table-Driven Tests

The idiomatic pattern for data-heavy tests. Use `t.Run` for subtests:

```go
func TestValidateEmail(t *testing.T) {
    tests := []struct {
        name  string
        email string
        want  bool
    }{
        {"valid", "alice@example.com", true},
        {"missing at", "alice.example.com", false},
        {"empty", "", false},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got := ValidateEmail(tt.email)
            assert.Equal(t, tt.want, got)
        })
    }
}
```

## Test Organization

- **Colocated** (preferred): `user_service.go` alongside `user_service_test.go`
- **Black-box tests**: use `package user_test` to test only the public API
- Mirror source structure so finding tests is obvious

## Test Conventions

- Descriptive test names: `TestGetUser_ReturnsErrorWhenNotFound`
- Use `t.Parallel()` for independent tests; don't parallelize tests sharing mutable state
- Use `t.Cleanup()` for teardown (preferred over defer in loops)
- Use `t.Setenv()` instead of manually setting `os.Setenv`
- Use `t.Context()` (Go 1.24+) instead of `context.Background()` in tests

```go
func TestWithDatabase(t *testing.T) {
    t.Parallel()
    db := setupTestDB(t)
    t.Cleanup(func() { db.Close() })

    t.Setenv("FEATURE_FLAG", "true")
    ctx := t.Context()
    // ...
}
```

## Mocking Preferences

- **Fakes** (in-memory implementations) over mock objects — more realistic, no call-sequence coupling
- **DI** over patching — pass fakes via constructor, not monkey-patching globals
- Use **mockery** only when a fake would be too complex; generate mocks from interfaces

```go
type fakeUserStore struct {
    users map[string]*User
}

func (f *fakeUserStore) FindByID(_ context.Context, id string) (*User, error) {
    u, ok := f.users[id]
    if !ok {
        return nil, ErrNotFound
    }
    return u, nil
}

func TestCreateUser(t *testing.T) {
    store := &fakeUserStore{users: make(map[string]*User)}
    svc := NewService(store)
    // ...
}
```

## Conformance Suites

One suite, written once against the interface, runs on the fake in every test run and on the real adapter (emulator or container) in CI, so the fake can't drift from what it stands in for ([testing.md](../testing.md#conformance-suites)). The Go idiom is [`nettest.TestConn`](https://pkg.go.dev/golang.org/x/net/nettest#TestConn): a `Run(t, newStore)` function in a `…test` package beside the interface, like `httptest` and `fstest`.

```
internal/book/
├── store.go              # Store interface
├── firestore.go          # the real adapter
├── store_test.go         # booktest.Run on the fake
├── firestore_test.go     # //go:build integration: booktest.Run on the emulator
└── booktest/
    ├── conformance.go    # Run(t, newStore)
    └── fake.go           # in-memory Store
```

```go
// internal/book/booktest/conformance.go

// Run checks a Store against the contract. newStore returns an empty store;
// each subtest gets its own.
func Run(t *testing.T, newStore func(t *testing.T) book.Store) {
    t.Run("GetMissing", func(t *testing.T) {
        _, err := newStore(t).Get(t.Context(), uuid.NewV4().String())
        require.ErrorIs(t, err, book.ErrNotFound)
    })
    t.Run("CreateTakenID", func(t *testing.T) {
        s := newStore(t)
        b := &book.Book{ID: uuid.NewV4().String(), Title: "Dune"}
        require.NoError(t, s.Create(t.Context(), b))
        require.ErrorIs(t, s.Create(t.Context(), b), book.ErrConflict)
    })
}
```

```go
// internal/book/store_test.go
func TestFake(t *testing.T) {
    booktest.Run(t, func(*testing.T) book.Store { return booktest.NewFake() })
}

// internal/book/firestore_test.go (//go:build integration)
func TestFirestoreStore(t *testing.T) {
    booktest.Run(t, func(t *testing.T) book.Store {
        return book.NewFirestoreStore(emulatorClient(t)) // a fresh demo- project each call
    })
}
```

- **Behavior, not calls** — the suite asserts what every implementation must do: the sentinel errors, ordering, no-op writes, preconditions. What only the real store can show (indexes, transactions under contention) goes in an adapter-only test
- **An empty store per subtest** — a new fake, or the adapter on its own emulator project (`demo-<random>`), so subtests don't share data
- **"Conformance suite"**, never "contract test", which means Pact-style consumer contracts to most people

## HTTP Handler Tests

Use `net/http/httptest` — no running server needed:

```go
func TestGetUserHandler(t *testing.T) {
    svc := NewService(&fakeUserStore{users: map[string]*User{"1": {ID: "1", Name: "Alice"}}})
    handler := NewHandler(svc)

    req := httptest.NewRequest(http.MethodGet, "/api/v1/users/1", nil)
    req.SetPathValue("id", "1")
    rec := httptest.NewRecorder()

    handler.Get(rec, req)

    require.Equal(t, http.StatusOK, rec.Code)
    var resp UserResponse
    require.NoError(t, json.NewDecoder(rec.Body).Decode(&resp))
    assert.Equal(t, "Alice", resp.Name)
}
```

## Integration Tests

Use **testcontainers-go** for real database instances in CI:

```go
func TestPostgresStore(t *testing.T) {
    if testing.Short() {
        t.Skip("skipping integration test")
    }
    ctx := t.Context()
    container, db := startPostgresContainer(t, ctx)
    t.Cleanup(func() { container.Terminate(ctx) })

    store := NewPostgresStore(db)
    // ...
}
```

For GCP services, use official emulators:

- **Firestore**: the regular `cloud.google.com/go/firestore` client, which connects to the emulator when `FIRESTORE_EMULATOR_HOST` is set, on a `demo-` project ([gcp.md](../gcp.md#firebase-emulator-guard))
- **BigQuery**: BigQuery emulator or test project with `-short` skip

Mark integration tests with build tags or `testing.Short()`:

```go
//go:build integration

package user_test
```

Run with: `go test -tags=integration ./...`

## Coverage

```bash
go test -race -cover ./...                       # one line per package
go test -race -coverprofile=coverage.out ./...
go tool cover -func=coverage.out                 # per function
```

- **Per package** — read each package's line; one `total:` hides an untested package
- **A review signal, not a CI gate** — a reviewer asks about a package below its target; no build fails on a percentage
- **Written exemptions** — list exempt packages in the repo with a reason each: generated code, `cmd/*`, and conformance-suite packages, which report 0% because coverage counts only a package's own tests (`-coverpkg=./...` counts them from the packages that run them). A package tested only under `-tags=integration` is read from the integration run

| Target | Packages |
|---|---|
| **80%** | Most packages |
| **90%** | Libraries and shared packages |
| **95%+** | Critical infrastructure, security-sensitive code |

## Race Detection

Always run with `-race` in CI:

```bash
go test -race ./...
```

## Fuzzing

Fuzz every hand-written parser or decoder of untrusted input: page cursors, path segments (the [custom method](architecture.md#custom-methods) split), header values, subprocess output.

- **Properties** — at least "never panics", plus a round trip where one exists: decode, encode, decode again, and compare the two decoded values. Comparing against the input fails on spellings the decoder accepts but never writes
- **`go test` replays the seed corpus only** — the `f.Add` seeds and `testdata/fuzz/<Name>/`, with no new inputs. Generating inputs needs `-fuzz`, one target per run, locally or in a scheduled job
- **Keep what it finds** — `-fuzz` writes a failing input to `testdata/fuzz/<Name>/`; commit it with the fix, so every later `go test` replays it

```go
func FuzzDecodeCursor(f *testing.F) {
    f.Add(page.Encode(page.Cursor{
        CreatedAt: time.Date(2026, 9, 30, 17, 4, 0, 0, time.UTC),
        ID:        uuid.MustParse("d221cf76-2e34-4dc2-b6b0-99a61522eaef"),
    }))
    f.Add("")
    f.Add("not a cursor")
    f.Fuzz(func(t *testing.T, s string) {
        c, err := page.Decode(s) // never panics
        if err != nil {
            return
        }
        again, err := page.Decode(page.Encode(c)) // round trip
        require.NoError(t, err)
        require.Equal(t, c, again)
    })
}
```

Run with: `go test -run='^$' -fuzz='^FuzzDecodeCursor$' -fuzztime=30s ./internal/page`

## Concurrent Code Testing

Use **`testing/synctest`** (Go 1.25+) for testing goroutine-heavy code deterministically:

```go
func TestConcurrentAccess(t *testing.T) {
    synctest.Test(t, func(t *testing.T) {
        // goroutines run deterministically within synctest
    })
}
```

## Benchmarks

Use `testing.B.Loop` (Go 1.24+) instead of `for i := 0; i < b.N; i++`:

```go
func BenchmarkGetUser(b *testing.B) {
    svc := NewService(fakeStore{})
    ctx := b.Context()
    for b.Loop() {
        _, _ = svc.GetUser(ctx, "1")
    }
}
```
