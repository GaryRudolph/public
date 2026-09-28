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

- **Firestore**: `cloud.google.com/go/firestore/apiv1/firestorepb` with the Firestore emulator (`FIRESTORE_EMULATOR_HOST`)
- **BigQuery**: BigQuery emulator or test project with `-short` skip

Mark integration tests with build tags or `testing.Short()`:

```go
//go:build integration

package user_test
```

Run with: `go test -tags=integration ./...`

## Coverage

```bash
go test -race -cover -coverprofile=coverage.out ./...
go tool cover -func=coverage.out
```

| Threshold | When to Use |
|---|---|
| **80%** | Industry-standard minimum; most projects |
| **90%** | Libraries and shared packages |
| **95%+** | Critical infrastructure, security-sensitive code |

## Race Detection

Always run with `-race` in CI:

```bash
go test -race ./...
```

## Fuzzing

Use Go's built-in fuzzing (Go 1.18+) for functions with broad input spaces:

```go
func FuzzValidateEmail(f *testing.F) {
    f.Add("alice@example.com")
    f.Add("")
    f.Fuzz(func(t *testing.T, email string) {
        _ = ValidateEmail(email) // should not panic
    })
}
```

Run with: `go test -fuzz=FuzzValidateEmail -fuzztime=30s`

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
    ctx := context.Background()
    for b.Loop() {
        _, _ = svc.GetUser(ctx, "1")
    }
}
```
