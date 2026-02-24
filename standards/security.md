# Security Standards

## Security Principles

### Defense in Depth
- Multiple layers of security
- Assume any single layer can be breached
- Validate at every boundary

### Principle of Least Privilege
- Grant minimum necessary permissions
- Limit access duration
- Regular permission audits

### Secure by Default
- Safe defaults in configuration
- Require explicit opt-in for risky features
- Fail securely when errors occur

### Never Trust Input
- Validate all external input
- Sanitize and escape data
- Use parameterized queries
- Validate on server side, not just client

## Authentication & Authorization

### Password Security
- Minimum 12 characters with complexity requirements (upper, lower, digit, special)
- Prevent reuse of recent passwords
- Use adaptive hashing algorithms (bcrypt, argon2) with an appropriate cost factor — never MD5 or SHA-1
- Use timing-safe comparison for password verification

### Token Security
- Use short-lived access tokens with minimal payloads
- Use refresh tokens with server-side rotation
- Generate tokens with cryptographically secure random functions

### Session Management
- Store session secrets outside source code
- Mark cookies as Secure, HttpOnly, SameSite=Strict
- Set short session lifetimes (15-30 minutes for sensitive applications)
- Don't use default cookie names — they reveal the framework

### Multi-Factor Authentication
- Use TOTP (time-based one-time password) or hardware keys for second factor
- Allow a small time-step window to accommodate clock drift
- Store MFA secrets with the same care as passwords

### Separate Authentication from Authorization
- Authentication answers "who are you?"
- Authorization answers "what can you do?"
- Use established libraries for authentication
- Check permissions at the service layer, not just the UI
- Store permissions in a central location

## Input Validation

- Validate all fields: type, length, range, format, and allowed characters
- Use schema validation libraries (Pydantic, Codable, kotlinx.serialization)
- Sanitize HTML input — whitelist allowed tags, strip everything else
- Use parameterized queries for all database access — never concatenate user input into SQL
- Verify file uploads: check size, MIME type (both declared and actual), and generate safe filenames

## Web Application Security

### Cross-Site Scripting (XSS) Prevention
- Encode all dynamic output in HTML, JavaScript, URL, and CSS contexts
- Use template engines that auto-escape by default
- Set a Content Security Policy (CSP) header restricting script sources

### Cross-Site Request Forgery (CSRF) Prevention
- Use anti-CSRF tokens for state-changing requests
- For APIs, validate a custom header that browsers can't set cross-origin
- Set `SameSite` attribute on session cookies

### Security Headers
- `Strict-Transport-Security` — enforce HTTPS
- `Content-Security-Policy` — restrict resource loading
- `X-Content-Type-Options: nosniff` — prevent MIME sniffing
- `X-Frame-Options: DENY` — prevent clickjacking
- `Referrer-Policy` — limit referrer leakage

## API Security

### Rate Limiting
- Apply rate limits to all endpoints, stricter on authentication endpoints
- Use IP-based and user-based limits
- Return `429 Too Many Requests` with a `Retry-After` header

### API Key Security
- Store only hashed keys in the database — never plain text
- Include an expiration date and last-used timestamp
- Scope keys to specific permissions

## Database Security

- Always use parameterized queries — never string interpolation for SQL
- Use ORM query builders where available
- Create application-specific database users with minimal permissions (SELECT, INSERT, UPDATE only)
- Never use root/admin accounts for application connections

## Secrets Management

### Principles
- Store secrets in environment variables or a secrets manager — never in source code, config files, or version control
- Validate that required secrets exist at startup
- Never log secrets or include them in error messages

### Secret Rotation
- Support multiple active keys during rotation (current + previous)
- Automate rotation with a secrets manager where possible
- Rotate immediately after any suspected compromise

## Encryption

### Data at Rest
- Encrypt sensitive data before storing (AES-256-GCM or equivalent)
- Never hardcode encryption keys or IVs in source code
- Use platform-provided key management (Keychain, Android Keystore, KMS)

### Data in Transit
- Enforce HTTPS for all communication
- Redirect HTTP to HTTPS in production
- Use TLS 1.2+ with strong cipher suites
- Consider certificate pinning for high-security endpoints

## Logging & Monitoring

- Log security events: logins, failed logins, permission denials, suspicious activity
- Never log sensitive data (passwords, tokens, API keys, PII)
- Alert on anomalies: repeated failed logins, unusual access patterns
- Track and ban IPs after repeated failed authentication attempts

## Dependency Security

- Use lock files and verify package integrity with hashes
- Audit dependencies for known vulnerabilities regularly (pip-audit, npm audit, Dependabot, Renovate)
- Review new dependencies before adding — check maintenance status, license, and security history
- Pin dependency versions in all build files

## Security Checklist

### Before Deployment
- [ ] All secrets in environment variables or secrets manager
- [ ] HTTPS enforced
- [ ] Security headers configured
- [ ] Rate limiting implemented
- [ ] Input validation on all endpoints
- [ ] Parameterized queries for all database access
- [ ] XSS prevention (output encoding, CSP)
- [ ] CSRF protection enabled
- [ ] Authentication and authorization implemented
- [ ] Passwords properly hashed with adaptive algorithm
- [ ] Dependencies updated and audited
- [ ] Error messages don't leak sensitive info
- [ ] Logging configured (excluding sensitive data)
- [ ] Security testing completed

### Regular Security Tasks
- [ ] Rotate secrets and API keys
- [ ] Review access logs for suspicious activity
- [ ] Update dependencies
- [ ] Run security scans
- [ ] Review and update permissions
- [ ] Test backup and recovery procedures
- [ ] Review security incidents and learnings

## Common Vulnerabilities

### OWASP Top 10
1. **Broken Access Control** — enforce authorization checks at every layer
2. **Cryptographic Failures** — use strong encryption, secure key storage
3. **Injection** — validate and sanitize input, use parameterized queries
4. **Insecure Design** — security by design, threat modeling
5. **Security Misconfiguration** — secure defaults, regular updates
6. **Vulnerable Components** — keep dependencies updated and audited
7. **Authentication Failures** — strong passwords, MFA, secure sessions
8. **Data Integrity Failures** — verify data integrity, use signed updates
9. **Logging Failures** — log security events, monitor for anomalies
10. **Server-Side Request Forgery** — validate URLs, whitelist destinations

## Cross-Language Security Parallels

| Concept | Python | Swift / iOS | Kotlin / Android |
|---|---|---|---|
| Secure storage | Environment variables, secrets manager | Keychain | EncryptedSharedPreferences, Android Keystore |
| Cryptography | `cryptography` library | CryptoKit | Android Keystore, javax.crypto |
| Input validation | Pydantic | Codable + manual checks | kotlinx.serialization + manual checks |
| Static analysis | Bandit, Ruff `S` rules | Xcode analyzer | detekt security rules |
| Network security | HTTPS enforcement | App Transport Security (ATS) | Network Security Configuration |
| Biometric auth | N/A | LocalAuthentication | BiometricPrompt |
| Code obfuscation | N/A | N/A (compiled) | ProGuard / R8 |

## Language-Specific Security

- **[Python](python/security.md)** — bcrypt, JWT, Flask security, Pydantic, Bandit, cryptography lib
- **[Swift / iOS](swift/security.md)** — Keychain, ATS, CryptoKit, biometric auth, OWASP MASVS
- **[Kotlin / Android](kotlin/security.md)** — EncryptedSharedPreferences, Android Keystore, ProGuard/R8, OWASP MASVS

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP MASVS v2 (Mobile)](https://mas.owasp.org/MASVS/)
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Security Headers](https://securityheaders.com/)
