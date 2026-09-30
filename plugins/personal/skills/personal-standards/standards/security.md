# Security Standards

## Authentication

- **Passwords**: adaptive hashing, argon2id ([RFC 9106]) preferred, bcrypt acceptable — never MD5 or SHA-1; minimum 12 chars with complexity; timing-safe comparison
- **Tokens**: short-lived access tokens with minimal payloads; refresh tokens with server-side rotation; cryptographically secure generation
- **JWTs**: follow the JWT BCP ([RFC 8725]) — pin the accepted algorithms, always set and require `exp`, check `iss` and `aud` when more than one service issues or accepts tokens
- **OAuth 2.0**: follow the Security BCP ([RFC 9700]) — authorization code with PKCE ([RFC 7636]) for every client; no implicit or password grants
- **Native apps** (iOS, Android): sign in through the system browser (`ASWebAuthenticationSession`, Custom Tabs), never an embedded web view ([RFC 8252])
- **Sessions**: cookies ([RFC 6265]) marked Secure, HttpOnly, SameSite=Strict; 15-30 min lifetime for sensitive apps; don't use default cookie names
- **MFA**: TOTP ([RFC 6238]) or WebAuthn hardware keys; allow small time-step window for clock drift
- **Separate authn from authz**: check permissions at the service layer, not just UI

## Input Validation

- Validate all fields: type, length, range, format, allowed characters
- Use schema validation libraries (Pydantic, Codable, kotlinx.serialization)
- Sanitize HTML: whitelist allowed tags, strip everything else
- Parameterized queries for all database access — never concatenate user input into SQL
- File uploads: check size, MIME type (declared and actual), generate safe filenames

## Security Headers

- `Strict-Transport-Security` ([RFC 6797]) — enforce HTTPS; TLS 1.2 minimum, 1.3 preferred ([RFC 9325])
- `Content-Security-Policy` — restrict resource loading
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy` — limit referrer leakage

## API Security

- Rate limits on all endpoints, stricter on auth; return `429` ([RFC 6585]) with `Retry-After` ([RFC 9110]) as an RFC 9457 problem ([architecture.md](architecture.md#error-responses-rfc-9457))
- API keys: store only hashed keys; include expiration and scope

## Secrets Management

- Never commit **plaintext** secrets to source repositories
- Externalize secrets to environment variables, managed secret stores, or a dedicated encrypted secrets repository — not into application source trees
- Validate required secrets at startup; never log secrets
- Support multiple active keys during rotation (current + previous)
- For a candidate estate-wide approach (SOPS + age in a private GitHub repo, per-consumer access control), see **[Secrets Management](secrets/README.md)**

## Dependency Security

- Lock files with hash verification
- Audit regularly (pip-audit, npm audit, Dependabot, Renovate)
- Pin versions; review new dependencies before adding

## Cross-Language Security Parallels

| Concept | Python | Swift / iOS | Kotlin / Android | Go |
|---|---|---|---|---|
| Secure storage | env vars, secrets manager | Keychain | EncryptedSharedPreferences, Keystore | env vars, GCP Secret Manager |
| Cryptography | `cryptography` lib | CryptoKit | Android Keystore, javax.crypto | `crypto/*`, `golang.org/x/crypto` |
| Input validation | Pydantic | Codable + manual | kotlinx.serialization + manual | go-playground/validator |
| Static analysis | Bandit, Ruff `S` rules | Xcode analyzer | detekt security rules | gosec, govulncheck |
| Network security | HTTPS enforcement | App Transport Security | Network Security Configuration | security-headers middleware |

## Security Checklist — Before Deployment

- [ ] Secrets externalized (env vars, secret store, or encrypted secrets repo — not plaintext in source)
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
- **[Go](go/security.md)**

[RFC 6238]: https://www.rfc-editor.org/rfc/rfc6238
[RFC 6265]: https://www.rfc-editor.org/rfc/rfc6265
[RFC 6585]: https://www.rfc-editor.org/rfc/rfc6585
[RFC 6797]: https://www.rfc-editor.org/rfc/rfc6797
[RFC 7636]: https://www.rfc-editor.org/rfc/rfc7636
[RFC 8252]: https://www.rfc-editor.org/rfc/rfc8252
[RFC 8725]: https://www.rfc-editor.org/rfc/rfc8725
[RFC 9106]: https://www.rfc-editor.org/rfc/rfc9106
[RFC 9110]: https://www.rfc-editor.org/rfc/rfc9110
[RFC 9325]: https://www.rfc-editor.org/rfc/rfc9325
[RFC 9700]: https://www.rfc-editor.org/rfc/rfc9700
