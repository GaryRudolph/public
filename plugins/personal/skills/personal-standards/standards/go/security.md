# Security — Go

Follows [security.md](../security.md).

## Password Hashing

Use **argon2id** (preferred) or **bcrypt** via `golang.org/x/crypto`:

```go
import "golang.org/x/crypto/bcrypt"

const bcryptCost = 12

func HashPassword(password string) (string, error) {
    hash, err := bcrypt.GenerateFromPassword([]byte(password), bcryptCost)
    return string(hash), err
}

func VerifyPassword(password, hash string) bool {
    return bcrypt.CompareHashAndPassword([]byte(hash), []byte(password)) == nil
}
```

## JWT Tokens

Use `github.com/golang-jwt/jwt/v5`:

```go
import "github.com/golang-jwt/jwt/v5"

func CreateToken(userID, role string, secret []byte) (string, error) {
    claims := jwt.MapClaims{
        "sub":  userID,
        "role": role,
        "exp":  time.Now().Add(15 * time.Minute).Unix(),
    }
    return jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString(secret)
}
```

### Secret Rotation

Support multiple active keys during rotation:

```go
var jwtSecrets = [][]byte{
    []byte(os.Getenv("JWT_SECRET_CURRENT")),
    []byte(os.Getenv("JWT_SECRET_PREVIOUS")),
}

func VerifyToken(tokenStr string) (jwt.MapClaims, error) {
    var lastErr error
    for _, secret := range jwtSecrets {
        token, err := jwt.Parse(tokenStr, func(t *jwt.Token) (any, error) {
            return secret, nil
        }, jwt.WithValidMethods([]string{"HS256"}), jwt.WithExpirationRequired()) // RFC 8725: pin algorithms
        if err == nil {
            return token.Claims.(jwt.MapClaims), nil
        }
        lastErr = err
    }
    return nil, lastErr
}
```

## Randomness

Use `crypto/rand` — never `math/rand` for security purposes:

```go
import "crypto/rand"

func GenerateToken(n int) (string, error) {
    b := make([]byte, n)
    if _, err := rand.Read(b); err != nil {
        return "", err
    }
    return base64.URLEncoding.EncodeToString(b), nil
}
```

## Encryption (AES-256-GCM)

```go
import "crypto/aes"
import "crypto/cipher"

func Encrypt(key, plaintext []byte) ([]byte, error) {
    block, err := aes.NewCipher(key)
    if err != nil {
        return nil, err
    }
    gcm, err := cipher.NewGCM(block)
    if err != nil {
        return nil, err
    }
    nonce := make([]byte, gcm.NonceSize())
    if _, err := rand.Read(nonce); err != nil {
        return nil, err
    }
    return gcm.Seal(nonce, nonce, plaintext, nil), nil
}
```

Use `crypto/subtle.ConstantTimeCompare` for secret comparisons.

## Input Validation

Use `go-playground/validator` for struct-tag validation. Register the JSON tag as the field name so
failures map straight to JSON Pointers:

```go
func newValidator() *validator.Validate {
    v := validator.New(validator.WithRequiredStructEnabled())
    v.RegisterTagNameFunc(func(f reflect.StructField) string {
        name, _, _ := strings.Cut(f.Tag.Get("json"), ",")
        return name
    })
    return v
}

type CreateUserRequest struct {
    Email    string `json:"email" validate:"required,email"`
    Password string `json:"password" validate:"required,min=12,max=128"`
    Name     string `json:"name" validate:"required,min=1,max=100"`
}

func (h *Handler) Create(w http.ResponseWriter, r *http.Request) {
    var req CreateUserRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        writeProblem(w, &Problem{
            Type:   "about:blank",
            Title:  http.StatusText(http.StatusBadRequest),
            Status: http.StatusBadRequest,
            Detail: "request body is not valid JSON",
        })
        return
    }
    if err := h.validate.Struct(req); err != nil {
        verrs, ok := errors.AsType[validator.ValidationErrors](err)
        if !ok {
            writeErr(w, err)
            return
        }
        items := make([]FieldError, 0, len(verrs))
        for _, fe := range verrs {
            items = append(items, FieldError{
                Pointer: "#/" + fe.Field(),
                Detail:  fmt.Sprintf("failed %q validation", fe.Tag()),
            })
        }
        writeProblem(w, Validation(items...))
        return
    }
    // ...
}
```

Never echo `err.Error()` from the validator or decoder to the client; it describes Go types, not the API.

## Database Security

GORM uses parameterized queries by default — never concatenate user input into SQL:

```go
// Good — parameterized
db.Where("email = ?", email).First(&user)

// Bad — SQL injection
db.Where(fmt.Sprintf("email = '%s'", email)).First(&user)
```

## Secrets Management

All secrets are declared as `required` fields in `Config` (`internal/config/config.go`). Missing secrets fail at startup:

```go
type Config struct {
    DatabaseURL string `env:"DATABASE_URL,required"`
    JWTSecret   string `env:"JWT_SECRET,required"`
}
```

For production, load secrets from **GCP Secret Manager** and inject via env vars at deploy time. Never log secrets.

## Security Headers

Apply via middleware:

```go
func securityHeaders(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        w.Header().Set("X-Content-Type-Options", "nosniff")
        w.Header().Set("X-Frame-Options", "DENY")
        w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
        next.ServeHTTP(w, r)
    })
}
```

## Rate Limiting

Use `golang.org/x/time/rate` or chi's `httprate`:

```go
import "github.com/go-chi/httprate"

r.Use(httprate.LimitByIP(100, time.Minute)) // general API
r.With(httprate.LimitByIP(5, 15*time.Minute)).Post("/auth/login", loginHandler)
```

## Error Boundaries

Never expose internal errors to clients. Every error response is an RFC 9457 `Problem` (see
[architecture.md](architecture.md#error-catalog)); anything that isn't one becomes an opaque 500:

```go
func writeProblem(w http.ResponseWriter, p *Problem) {
    w.Header().Set("Content-Type", "application/problem+json")
    w.WriteHeader(p.Status)
    json.NewEncoder(w).Encode(p)
}

func writeErr(w http.ResponseWriter, err error) {
    if p, ok := errors.AsType[*Problem](err); ok {
        writeProblem(w, p)
        return
    }
    slog.Error("unhandled error", "err", err)
    writeProblem(w, &Problem{
        Type:   "about:blank",
        Title:  http.StatusText(http.StatusInternalServerError),
        Status: http.StatusInternalServerError,
        Detail: "an internal error occurred",
    })
}
```

Log the full error internally with the request id that goes in `Instance`; return a generic detail externally.

## Dependency Security

```bash
go mod verify                              # verify checksums
govulncheck ./...                          # scan for known vulnerabilities
go tool golangci-lint run                  # includes gosec security linter
```

Run `govulncheck` in CI on every PR. Pin dependencies; review new deps before adding.

## Static Analysis

Enable `gosec` via golangci-lint (see [code-style.md](code-style.md) for full config). Key rules:

- G101 — hardcoded credentials
- G201/G202 — SQL injection
- G401/G505 — weak crypto
- G404 — insecure random
