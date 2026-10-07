# Security — Go

Follows [security.md](../security.md).

## Password Hashing

Hash with **argon2id** ([RFC 9106]) from `golang.org/x/crypto/argon2`, stored as a PHC string so the parameters travel with the hash. The constants are RFC 9106 §4's second recommended option, which are also argon2-cffi's defaults, so Go and Python services verify each other's hashes. The password rules themselves are in [security.md](../security.md#authentication).

```go
import (
    "crypto/rand"
    "crypto/subtle"
    "encoding/base64"
    "errors"
    "fmt"
    "strings"

    "golang.org/x/crypto/argon2"
    "golang.org/x/text/unicode/norm"
)

const (
    argonIterations = 3
    argonMemoryKiB  = 64 * 1024
    argonThreads    = 4
    argonKeyLen     = 32
    argonSaltLen    = 16
)

var (
    b64            = base64.RawStdEncoding
    errInvalidHash = errors.New("invalid argon2id hash")
)

// HashPassword returns $argon2id$v=19$m=65536,t=3,p=4$<salt>$<key>.
func HashPassword(password string) (string, error) {
    salt := make([]byte, argonSaltLen)
    if _, err := rand.Read(salt); err != nil {
        return "", err
    }
    key := argon2.IDKey(nfc(password), salt, argonIterations, argonMemoryKiB, argonThreads, argonKeyLen)
    return fmt.Sprintf("$argon2id$v=%d$m=%d,t=%d,p=%d$%s$%s", argon2.Version,
        argonMemoryKiB, argonIterations, argonThreads,
        b64.EncodeToString(salt), b64.EncodeToString(key)), nil
}

// VerifyPassword hashes with the parameters stored in encoded. needsRehash
// reports a hash made with other parameters: after a successful login,
// store a fresh HashPassword.
func VerifyPassword(password, encoded string) (ok, needsRehash bool, err error) {
    parts := strings.Split(encoded, "$")
    if len(parts) != 6 || parts[1] != "argon2id" || parts[2] != fmt.Sprintf("v=%d", argon2.Version) {
        return false, false, errInvalidHash
    }
    var memoryKiB, iterations uint32
    var threads uint8
    _, err = fmt.Sscanf(parts[3], "m=%d,t=%d,p=%d", &memoryKiB, &iterations, &threads)
    if err != nil || iterations == 0 || threads == 0 { // IDKey panics on zero
        return false, false, errInvalidHash
    }
    salt, err := b64.DecodeString(parts[4])
    if err != nil {
        return false, false, errInvalidHash
    }
    want, err := b64.DecodeString(parts[5])
    if err != nil {
        return false, false, errInvalidHash
    }
    keyLen := len(want) // another service's key length still verifies
    if keyLen < 16 || keyLen > 64 {
        return false, false, errInvalidHash
    }
    got := argon2.IDKey(nfc(password), salt, iterations, memoryKiB, threads, uint32(keyLen))
    ok = subtle.ConstantTimeCompare(got, want) == 1
    needsRehash = memoryKiB != argonMemoryKiB || iterations != argonIterations ||
        threads != argonThreads || len(salt) != argonSaltLen || keyLen != argonKeyLen
    return ok, needsRehash, nil
}

// nfc normalizes before hashing (NIST SP 800-63B-4 §3.1.1.2), so the same
// password typed on two keyboards hashes the same.
func nfc(password string) []byte { return []byte(norm.NFC.String(password)) }
```

`golang.org/x/crypto/bcrypt` is acceptable only for hashes that already exist. It reads at most 72 bytes, and `GenerateFromPassword` returns `ErrPasswordTooLong` beyond that rather than truncating, so it can't accept 64 non-ASCII characters; new code uses argon2id. To move off bcrypt, verify the bcrypt hash and store an argon2id one on the next successful login.

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

Decode request bodies with `encoding/json/v2` (Go 1.27) and `RejectUnknownMembers`. It also rejects duplicate names, invalid UTF-8 and trailing data, and its errors carry a JSON Pointer. v1's `DisallowUnknownFields` returns an untyped error with no location, and its `UnmarshalTypeError.Field` is a dotted path. Map the errors per [Error Responses](../architecture.md#error-responses-rfc-9457):

- **`400`**: the body isn't JSON (`*jsontext.SyntacticError`, which includes an empty or truncated body)
- **`422` with a `pointer`**: it's JSON that doesn't fit the type (`*json.SemanticError`): a wrong type, or an unknown member (`ErrUnknownName`), which is how an output-only member arrives
- **`413`**: the body is over the `MaxBytesReader` limit

```go
import (
    "encoding/json/jsontext"
    json "encoding/json/v2"
    "errors"
    "iter"
    "net/http"
    "net/url"
    "strings"
)

const maxBodyBytes = 1 << 20

// decode reads a JSON body strictly. It returns a *Problem for anything the
// client got wrong, and any other error (a failed read) as it is.
func decode(w http.ResponseWriter, r *http.Request, v any) error {
    err := json.UnmarshalRead(http.MaxBytesReader(w, r.Body, maxBodyBytes), v,
        json.RejectUnknownMembers(true))
    if err == nil {
        return nil
    }
    if _, ok := errors.AsType[*http.MaxBytesError](err); ok {
        return &Problem{
            Type:   "about:blank",
            Title:  http.StatusText(http.StatusRequestEntityTooLarge),
            Status: http.StatusRequestEntityTooLarge,
            Detail: "request body is too large",
        }
    }
    if _, ok := errors.AsType[*jsontext.SyntacticError](err); ok {
        return &Problem{
            Type:   "about:blank",
            Title:  http.StatusText(http.StatusBadRequest),
            Status: http.StatusBadRequest,
            Detail: "request body is not valid JSON",
        }
    }
    if se, ok := errors.AsType[*json.SemanticError](err); ok {
        detail := "has the wrong type or format"
        if errors.Is(se.Err, json.ErrUnknownName) {
            detail = "is not a member this request accepts"
        }
        return Validation(FieldError{Pointer: pointer(se.JSONPointer.Tokens()), Detail: detail})
    }
    return err
}

var tokenEscaper = strings.NewReplacer("~", "~0", "/", "~1")

// pointer builds a JSON Pointer in URI fragment form (#/items/0/quantity):
// each token escapes ~ and / (RFC 6901 §3), then is percent-encoded (§6).
func pointer(tokens iter.Seq[string]) string {
    var b strings.Builder
    b.WriteByte('#')
    for t := range tokens {
        b.WriteByte('/')
        b.WriteString(url.PathEscape(tokenEscaper.Replace(t)))
    }
    return b.String()
}
```

Validate with `go-playground/validator`. Register the JSON name as the field name, then build each pointer from the error's `Namespace()` (`CreateOrderRequest.items[0].quantity`), not `Field()`, which is only the last name:

```go
import (
    "errors"
    "fmt"
    "iter"
    "net/http"
    "reflect"
    "strings"

    "github.com/go-playground/validator/v10"
)

func newValidator() *validator.Validate {
    v := validator.New(validator.WithRequiredStructEnabled())
    v.RegisterTagNameFunc(func(f reflect.StructField) string {
        name, _, _ := strings.Cut(f.Tag.Get("json"), ",")
        return name
    })
    return v
}

// namespaceTokens splits a validator namespace into pointer tokens, dropping
// the struct name. It assumes no JSON name or map key holds '.', '[' or ']'.
func namespaceTokens(ns string) iter.Seq[string] {
    _, path, _ := strings.Cut(ns, ".")
    return strings.FieldsFuncSeq(path, func(r rune) bool { return r == '.' || r == '[' || r == ']' })
}

type CreateUserRequest struct {
    Email    string `json:"email" validate:"required,email"`
    Password string `json:"password" validate:"required,min=15,max=128"` // 15 if it's the only factor, 8 with MFA
    Name     string `json:"name" validate:"required,min=1,max=100"`
}

func (h *Handler) Create(w http.ResponseWriter, r *http.Request) {
    var req CreateUserRequest
    if err := decode(w, r, &req); err != nil {
        writeErr(w, r, err)
        return
    }
    if err := h.validate.Struct(req); err != nil {
        verrs, ok := errors.AsType[validator.ValidationErrors](err)
        if !ok {
            writeErr(w, r, err)
            return
        }
        items := make([]FieldError, 0, len(verrs))
        for _, fe := range verrs {
            items = append(items, FieldError{
                Pointer: pointer(namespaceTokens(fe.Namespace())),
                Detail:  fmt.Sprintf("failed %q validation", fe.Tag()),
            })
        }
        writeErr(w, r, Validation(items...))
        return
    }
    // ...
}
```

`min` and `max` count runes, which is how NIST counts password length (one character per code point). Never echo `err.Error()` from the validator or decoder to the client; it describes Go types, not the API.

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

`securityHeaders` goes on every route, after `requestID` and `routerProblems` ([Router Errors](architecture.md#router-errors)). `apiHeaders` goes on the JSON API routes only, so HTML the service also serves (Swagger UI) can send its own CSP ([security.md](../security.md#security-headers)):

```go
func securityHeaders(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        h := w.Header()
        h.Set("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        h.Set("X-Content-Type-Options", "nosniff")
        h.Set("X-Frame-Options", "DENY") // legacy; frame-ancestors overrides it
        h.Set("Referrer-Policy", "strict-origin-when-cross-origin")
        next.ServeHTTP(w, r)
    })
}

// apiHeaders: a JSON API loads nothing, and frame-ancestors doesn't fall back
// to default-src. no-store is the API default; a handler that serves a
// cacheable response sets its own Cache-Control and Vary.
func apiHeaders(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        h := w.Header()
        h.Set("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        h.Set("Cache-Control", "no-store")
        next.ServeHTTP(w, r)
    })
}

r := chi.NewRouter()
r.Use(requestID, routerProblems, securityHeaders)
r.With(apiHeaders).Mount("/api/v1", apiRouter)
r.Mount("/docs", swaggerUI) // HTML: sends its own CSP
```

## Rate Limiting

Use chi's `httprate` with `LimitBy`:

- **Key on the real client IP**: a `ClientIPFrom*` middleware (chi 5.3+) resolves it, and `LimitBy`'s key function reads it with `GetClientIP`. Behind a proxy, use `ClientIPFromXFF` with the proxies' CIDRs, or `ClientIPFromXFFTrustedProxies` when only the hop count is known; with nothing in front, `ClientIPFromRemoteAddr` ([chi middleware]). `LimitByIP` keys every client behind a proxy as one, and `LimitByRealIP` trusts headers any client can forge; both are deprecated. If nothing resolves the IP, every client shares one bucket
- **No `X-RateLimit-*`**: `WithResponseHeaders` with only `RetryAfter` set. httprate can't send the draft `RateLimit` fields ([architecture.md](../architecture.md#api-design))
- **429 is a problem**: the default is `text/plain`. httprate sets `Retry-After` (the window, in seconds) before it calls the `WithLimitHandler` handler. The default error handler sends `err.Error()` as a `text/plain` 428, so route errors through `writeErr` too

```go
import (
    "net/http"
    "time"

    "github.com/go-chi/chi/v5/middleware"
    "github.com/go-chi/httprate"
)

// clientIP buckets IPv6 clients by /64, so one can't rotate addresses.
func clientIP(r *http.Request) (string, error) {
    return httprate.CanonicalizeIP(middleware.GetClientIP(r.Context())), nil
}

func rateLimit(n int, window time.Duration) func(http.Handler) http.Handler {
    return httprate.LimitBy(n, window, clientIP,
        httprate.WithResponseHeaders(httprate.ResponseHeaders{RetryAfter: "Retry-After"}),
        httprate.WithLimitHandler(func(w http.ResponseWriter, r *http.Request) {
            writeProblem(w, r, &Problem{
                Type:   "about:blank",
                Title:  http.StatusText(http.StatusTooManyRequests),
                Status: http.StatusTooManyRequests,
                Detail: "too many requests",
            })
        }),
        httprate.WithErrorHandler(writeErr),
    )
}

// With the other r.Use calls, before any route or Mount: chi panics on a
// middleware added after a route.
r.Use(middleware.ClientIPFromXFF(trustedProxies...)) // the proxies' CIDRs
r.Use(rateLimit(100, time.Minute))                   // general API
r.With(rateLimit(5, 15*time.Minute)).Post("/auth/login", loginHandler)
```

## Request Id

Every response carries `{Product}-Request-Id` ([architecture.md](../architecture.md#custom-headers)). The service mints it and never reads one from the request, so a client can't choose what lands in the logs; `writeProblem` puts the same id in `instance`. Don't use chi's `middleware.RequestID`: it reads and trusts an inbound `X-Request-Id`, never sets a response header, and mints counter ids, not UUIDs.

```go
import (
    "context"
    "net/http"
    "uuid" // standard library since Go 1.27
)

const requestIDHeader = "Example-Request-Id" // {Product}-Request-Id

type requestIDKey struct{}

func requestID(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        id := uuid.NewV4().String()
        w.Header().Set(requestIDHeader, id)
        next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), requestIDKey{}, id)))
    })
}

func RequestID(ctx context.Context) string {
    id, _ := ctx.Value(requestIDKey{}).(string)
    return id
}
```

## Error Boundaries

Never expose internal errors to clients. Every error response is an RFC 9457 `Problem` (see
[architecture.md](architecture.md#error-catalog)). `writeProblem` makes any `5xx` opaque, whatever the caller built, so `&Problem{Status: 500, Detail: err.Error()}` can't leak; what the caller said goes to the log, which the [logging handler](code-style.md#logging) tags with the request id. Anything that isn't a `*Problem` becomes that 500:

```go
import (
    json "encoding/json/v2"
    "errors"
    "log/slog"
    "net/http"
)

func writeProblem(w http.ResponseWriter, r *http.Request, p *Problem) {
    q := *p
    if q.Status >= 500 {
        // the logging handler adds the request id and user id
        slog.ErrorContext(r.Context(), "server error", "status", q.Status, "detail", q.Detail)
        q = Problem{
            Type:   "about:blank",
            Title:  http.StatusText(q.Status),
            Status: q.Status,
            Detail: "an internal error occurred",
        }
    }
    if id := RequestID(r.Context()); id != "" {
        q.Instance = "urn:uuid:" + id
    }
    w.Header().Set("Content-Type", "application/problem+json")
    w.WriteHeader(q.Status)
    _ = json.MarshalWrite(w, &q) // the status is already sent
}

func writeErr(w http.ResponseWriter, r *http.Request, err error) {
    p, ok := errors.AsType[*Problem](err)
    if !ok {
        p = &Problem{Status: http.StatusInternalServerError, Detail: err.Error()}
    }
    writeProblem(w, r, p)
}
```

Unhandled errors are server faults, but one can still wrap an error that quotes input. Decode and validation errors become `4xx` problems and are never logged; subprocess output is user content ([Logging](../security.md#logging)).

## Dependency Security

```bash
go mod verify                              # verify checksums
govulncheck ./...                          # scan for known vulnerabilities
go tool golangci-lint run                  # includes gosec security linter
```

Run `govulncheck` as a blocking check on every PR and on a schedule, since a new advisory can fail code that hasn't changed ([security.md](../security.md#dependency-security)). It fails only on vulnerabilities in functions the code calls, so a failure is worth fixing, and it needs network access to the Go vulnerability database. Pin dependencies; review new deps before adding.

## Static Analysis

Enable `gosec` via golangci-lint (see [code-style.md](code-style.md) for full config). Key rules:

- G101 — hardcoded credentials
- G201/G202 — SQL injection
- G401/G505 — weak crypto
- G404 — insecure random

[chi middleware]: https://pkg.go.dev/github.com/go-chi/chi/v5/middleware#ClientIPFromXFF
[RFC 9106]: https://www.rfc-editor.org/rfc/rfc9106#section-4
