# Security Standards

## Authentication

- **Passwords**: adaptive hashing (bcrypt, argon2) — never MD5 or SHA-1; minimum 12 chars with complexity; timing-safe comparison
- **Tokens**: short-lived access tokens with minimal payloads; refresh tokens with server-side rotation; cryptographically secure generation
- **Sessions**: cookies marked Secure, HttpOnly, SameSite=Strict; 15-30 min lifetime for sensitive apps; don't use default cookie names
- **MFA**: TOTP or hardware keys; allow small time-step window for clock drift
- **Separate authn from authz**: check permissions at the service layer, not just UI

## Input Validation

- Validate all fields: type, length, range, format, allowed characters
- Use schema validation libraries (Pydantic, Codable, kotlinx.serialization)
- Sanitize HTML: whitelist allowed tags, strip everything else
- Parameterized queries for all database access — never concatenate user input into SQL
- File uploads: check size, MIME type (declared and actual), generate safe filenames

## Security Headers

- `Strict-Transport-Security` — enforce HTTPS
- `Content-Security-Policy` — restrict resource loading
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy` — limit referrer leakage

## API Security

- Rate limits on all endpoints, stricter on auth; return `429` with `Retry-After`
- API keys: store only hashed keys; include expiration and scope

## Secrets Management

- Store in environment variables or secrets manager — never in source code or version control
- Validate required secrets at startup; never log secrets
- Support multiple active keys during rotation (current + previous)

## Dependency Security

- Lock files with hash verification
- Audit regularly (pip-audit, npm audit, Dependabot, Renovate)
- Pin versions; review new dependencies before adding

## Cross-Language Security Parallels

| Concept | Python | Swift / iOS | Kotlin / Android |
|---|---|---|---|
| Secure storage | env vars, secrets manager | Keychain | EncryptedSharedPreferences, Keystore |
| Cryptography | `cryptography` lib | CryptoKit | Android Keystore, javax.crypto |
| Input validation | Pydantic | Codable + manual | kotlinx.serialization + manual |
| Static analysis | Bandit, Ruff `S` rules | Xcode analyzer | detekt security rules |
| Network security | HTTPS enforcement | App Transport Security | Network Security Configuration |

## Security Checklist — Before Deployment

- [ ] Secrets in env vars or secrets manager
- [ ] HTTPS enforced
- [ ] Security headers configured
- [ ] Rate limiting implemented
- [ ] Input validation on all endpoints
- [ ] Parameterized queries for all DB access
- [ ] Authentication and authorization implemented
- [ ] Passwords hashed with adaptive algorithm
- [ ] Dependencies audited
- [ ] Error messages don't leak sensitive info
- [ ] Logging configured (excluding sensitive data)

## Regular Security Tasks

- [ ] Rotate secrets and API keys
- [ ] Review access logs
- [ ] Update dependencies
- [ ] Run security scans
- [ ] Review permissions

## Language-Specific Security

- **[Python](python/security.md)**
- **[Swift / iOS](swift/security.md)**
- **[Kotlin / Android](kotlin/security.md)**
