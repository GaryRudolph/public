# Code Style — Go

Follows [code-style.md](../code-style.md), [Effective Go](https://go.dev/doc/effective_go), [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments), and the [Google Go Style Guide](https://google.github.io/styleguide/go/).

Target **Go 1.26** for new projects. Run `go fix ./...` after upgrading to mechanically adopt modern idioms.

## Formatting

- **Tabs** for indentation (enforced by `gofmt`); no line-length cap — let `gofmt`/`gofumpt` decide
- **One statement per line**; opening brace on same line (K&R style)
- Run `gofmt` / `gofumpt` on every save; CI must reject unformatted code

## Imports

Group in three blocks separated by blank lines:

1. Standard library
2. Third-party
3. Local (`internal/` or module path)

Use `goimports` or `gci` to enforce grouping. No dot imports except in tests when unavoidable.

```go
import (
    "context"
    "net/http"

    "github.com/go-chi/chi/v5"
    "gorm.io/gorm"

    "example.com/myapp/internal/user"
)
```

## Naming

- **MixedCaps** / **mixedCaps** — no underscores in identifiers (`userID`, not `user_id`)
- **Short receiver names** — one or two letters matching the type: `func (s *Server)`, `func (u *User)`
- **Lowercase package names** — short, no underscores, no `util`/`common`/`helpers`
- **Consistent acronym casing** — `ID`, `URL`, `HTTP`, `JSON` (not `Id`, `Url`)
- **Sentinel errors** — `Err` prefix: `ErrNotFound`, `ErrInvalidInput`
- **Interfaces** — single-method interfaces named with `-er` suffix: `Reader`, `UserStore`
- **File names** — lowercase, underscores allowed for test files: `user_service.go`, `user_service_test.go`

## File Structure

```go
// Package user provides user account management.
package user

import (...)

const defaultPageSize = 20

type Service struct { ... }

func NewService(store Store) *Service { ... }

func (s *Service) GetUser(ctx context.Context, id string) (*User, error) { ... }

func parseEmail(raw string) (string, error) { ... } // unexported helper
```

Order: package comment → imports → constants → types → constructors → exported methods → unexported helpers.

## Error Handling

- Always check errors — never `_ = err` unless documented
- Wrap with context: `fmt.Errorf("load user %s: %w", id, err)`
- Inspect with `errors.Is` / `errors.As` / `errors.AsType` — never `err == ErrXxx` on wrapped errors
- Return errors; don't log and return (pick one layer)

```go
if err != nil {
    return nil, fmt.Errorf("fetch order %s: %w", id, err)
}

if errors.Is(err, ErrNotFound) { ... }

if appErr, ok := errors.AsType[*AppError](err); ok { ... }
```

## Logging

Use **`log/slog`** (stdlib, Go 1.21+) — not logrus or zap for new code:

```go
slog.Info("order created", "order_id", order.ID, "user_id", userID)
slog.Error("payment failed", "err", err, "order_id", order.ID)
```

## Modern Go (Invalidates Past Idioms)

Patterns below are **deprecated** on Go 1.22+. Run `go fix ./...` to migrate mechanically.

| Old pattern | Modern replacement | Since |
|---|---|---|
| `interface{}` | `any` | 1.18 |
| `v := v` inside loops | remove it — each iteration has its own variable | 1.22 |
| `for i := 0; i < n; i++` | `for i := range n` | 1.22 |
| Custom `min`/`max` helpers | `min(a, b)` / `max(a, b)` builtins | 1.21 |
| `for k := range m { delete(m, k) }` | `clear(m)` | 1.21 |
| `sort.Slice(s, func(i,j int) bool{…})` | `slices.SortFunc(s, cmpFn)` | 1.21 |
| Manual contains/index loops | `slices.Contains`, `slices.Index`, `slices.IndexFunc` | 1.21 |
| Manual map copy/clone | `maps.Clone`, `maps.Copy`, `maps.DeleteFunc` | 1.21 |
| Loop collecting map keys | `slices.Sorted(maps.Keys(m))` | 1.23 |
| `io/ioutil` | `io`, `os` packages | 1.16 |
| `github.com/pkg/errors` | stdlib `errors` + `fmt.Errorf %w` | 1.13 |
| `errors.As` with pointer boilerplate | `errors.AsType[*T](err)` | 1.26 |
| `logrus` / `zap` as default | `log/slog` | 1.21 |
| `strings.Split` + loop | `for part := range strings.SplitSeq(s, sep)` | 1.23 |

## Generics

Use generics only when you have **3+ concrete duplications** or a clear type-safe abstraction. Prefer small interfaces over generic constraints when either works.

```go
func Map[T, U any](items []T, fn func(T) U) []U {
    out := make([]U, len(items))
    for i, item := range items {
        out[i] = fn(item)
    }
    return out
}
```

## Tools

### golangci-lint v2

Pin via `go.mod` tool directive:

```bash
go get -tool github.com/golangci/golangci-lint/v2/cmd/golangci-lint@latest
go tool golangci-lint run
```

```yaml
# .golangci.yml
version: "2"
run:
  timeout: 5m
linters:
  default: standard
  enable:
    - errcheck
    - govet
    - staticcheck
    - revive
    - gosec
    - errorlint
    - bodyclose
    - modernize
  settings:
    govet:
      enable-all: true
formatters:
  enable:
    - gofmt
    - goimports
```

### Tool dependencies (Go 1.24+)

```bash
go get -tool github.com/golangci/golangci-lint/v2/cmd/golangci-lint@latest
go tool golangci-lint run
```

### Modernization

After upgrading Go, run:

```bash
go fix ./...
go test ./...
```

Review the diff — fixers should not change behavior, but always verify.
