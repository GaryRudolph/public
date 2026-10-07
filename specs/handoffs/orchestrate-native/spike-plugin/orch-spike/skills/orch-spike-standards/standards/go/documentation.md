# Documentation — Go

Follows [documentation.md](../documentation.md).

## Doc Comments

Every exported identifier must have a doc comment. Comments begin with the name of the thing being documented:

```go
// UserService manages user accounts.
type UserService struct { ... }

// GetUser returns the user with the given ID, or ErrNotFound.
func (s *UserService) GetUser(ctx context.Context, id string) (*User, error) { ... }
```

- Complete sentences; no "This function..." or "GetUser gets..."
- Document concurrency behavior, side effects, and error returns
- Don't document the obvious — focus on non-obvious behavior and constraints

## Package Comments

Package-level documentation lives in `doc.go`:

```go
// Package user provides user account management including
// creation, authentication, and profile updates.
package user
```

One `doc.go` per package is sufficient. For simple packages, a comment on the first file works.

## Testable Examples

Use `Example` functions for documentation that stays verified by `go test`:

```go
func ExampleUserService_GetUser() {
    svc := NewService(fakeStore{user: &User{ID: "1", Name: "Alice"}})
    user, err := svc.GetUser(context.Background(), "1")
    if err != nil {
        fmt.Println("error:", err)
        return
    }
    fmt.Println(user.Name)
    // Output: Alice
}
```

Run with: `go test -run Example`

## Viewing Documentation

```bash
go doc example.com/myapp/internal/user.UserService
go doc -all example.com/myapp/internal/user
```

Published packages appear on [pkg.go.dev](https://pkg.go.dev) automatically.

## README Structure

```markdown
# Package Name
## Overview
## Requirements
## Installation
## Quick Start
## Configuration
## Development
### Running Tests
### Linting
## API Reference
## Architecture
## Design Decisions
```

## Test Documentation

Each test function gets a descriptive name (no separate doc comment needed unless the test logic is non-obvious):

```go
func TestGetUser_ReturnsErrorWhenNotFound(t *testing.T) {
    svc := NewService(emptyStore{})
    _, err := svc.GetUser(t.Context(), "missing")
    require.ErrorIs(t, err, ErrNotFound)
}
```

## ADRs and Specs

Architecture decisions and product specs follow the conventions in [documentation.md](../documentation.md) — live in `{project-root}/specs/`, not in Go source comments.
