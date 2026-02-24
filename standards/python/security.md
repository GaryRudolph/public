# Security — Python

Follows general principles in [security.md](../security.md).

## Password Security

### Hashing

```python
# Good - use bcrypt with proper cost factor
from passlib.hash import bcrypt

ROUNDS = 12  # Adjust based on performance/security tradeoff

def hash_password(password: str) -> str:
    return bcrypt.using(rounds=ROUNDS).hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.verify(password, hashed)

# Never do this
import hashlib
hash = hashlib.md5(password.encode()).hexdigest()  # Insecure!
```

### Password Policy

```python
PASSWORD_REQUIREMENTS = {
    "min_length": 12,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_numbers": True,
    "require_special_chars": True,
    "prevent_common_passwords": True,
    "prevent_reuse": 5,  # Don't reuse last 5 passwords
}
```

## Token Security

```python
import jwt
import os

def create_token(user_id: str, role: str) -> str:
    return jwt.encode(
        {"user_id": user_id, "role": role},  # Minimal payload
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )

import secrets

def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)
```

### Secret Rotation

Support multiple active keys during rotation:

```python
import jwt
import os

JWT_SECRETS = [
    os.environ["JWT_SECRET_CURRENT"],
    os.environ["JWT_SECRET_PREVIOUS"],
]

def verify_token(token: str) -> dict:
    last_error = None
    for secret in JWT_SECRETS:
        try:
            return jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.InvalidTokenError as e:
            last_error = e
    raise last_error
```

## Session Management

```python
# Secure session configuration (Flask example)
app.config.update(
    SECRET_KEY=os.environ["SESSION_SECRET"],  # Long random string
    SESSION_COOKIE_NAME="sessionId",          # Don't use default name
    SESSION_COOKIE_SECURE=True,               # HTTPS only
    SESSION_COOKIE_HTTPONLY=True,             # No JavaScript access
    SESSION_COOKIE_SAMESITE="Strict",         # CSRF protection
    PERMANENT_SESSION_LIFETIME=900,           # 15 minutes
)
```

## Multi-Factor Authentication

```python
import pyotp

def generate_mfa_secret() -> str:
    return pyotp.random_base32()

def get_totp_uri(secret: str, email: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name="YourApp")

def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)  # Allow 1 step before/after
```

## Input Validation

### Pydantic Validation

```python
from pydantic import BaseModel, EmailStr, Field

class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z\s'-]+$")
    age: int = Field(ge=0, le=150)

def create_user(input_data: dict):
    data = CreateUserRequest(**input_data)
    # ... proceed with validated data
```

### Sanitization

```python
import bleach

ALLOWED_TAGS = ["b", "i", "em", "strong", "p", "br"]

def sanitize_html(dirty: str) -> str:
    return bleach.clean(dirty, tags=ALLOWED_TAGS, attributes={}, strip=True)
```

### SQL Injection Prevention

```python
import psycopg2

# Good — parameterized queries
cursor.execute("SELECT * FROM users WHERE email = %s", (email,))

# Good — SQLAlchemy ORM
user = session.query(User).filter_by(email=email, role=role).first()

# Never concatenate SQL
cursor.execute(f"SELECT * FROM users WHERE email = '{email}'")  # SQL injection!
```

### File Upload Security

```python
import magic
import uuid
import os

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

MIME_TO_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif"}

def validate_upload(file_data: bytes, declared_mimetype: str) -> str:
    if len(file_data) > MAX_FILE_SIZE:
        raise ValueError("File too large")

    if declared_mimetype not in ALLOWED_MIME_TYPES:
        raise ValueError("Invalid file type")

    actual_type = magic.from_buffer(file_data, mime=True)
    if actual_type != declared_mimetype:
        raise ValueError("File type mismatch")

    ext = MIME_TO_EXT[declared_mimetype]
    return f"{uuid.uuid4()}.{ext}"
```

## XSS Prevention

### Output Encoding

```python
import html

def escape_html(unsafe: str) -> str:
    return html.escape(unsafe, quote=True)

# Template engines like Jinja2 auto-escape by default
# {{ user_input }}  ← safe (auto-escaped)
# {{ user_input | safe }}  ← unsafe, only use for trusted content
```

### Content Security Policy

```python
@app.after_request
def set_security_headers(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://trusted-cdn.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self' https://api.yourapp.com; "
        "frame-ancestors 'none';"
    )
    return response
```

## CSRF Prevention

```python
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)

# For APIs, validate custom header (browsers can't set this cross-origin)
@app.before_request
def verify_csrf():
    if request.method not in ("GET", "HEAD"):
        token = request.headers.get("X-CSRF-Token")
        cookie_token = request.cookies.get("csrfToken")
        if token != cookie_token:
            abort(403, "Invalid CSRF token")
```

## API Security

### Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.route("/api/data")
@limiter.limit("100/15minutes")
def api_data():
    pass

# Stricter for authentication endpoints
@app.route("/api/auth/login", methods=["POST"])
@limiter.limit("5/15minutes")
def login():
    pass
```

### API Key Security

```python
import secrets
import hashlib
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ApiKey:
    id: str
    user_id: str
    key_hash: str  # Store hash, not plain key
    name: str
    permissions: list[str]
    expires_at: datetime
    last_used: datetime

def generate_api_key() -> str:
    return f"app_{secrets.token_urlsafe(32)}"

def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

async def validate_api_key(key: str) -> ApiKey | None:
    key_hash = hash_api_key(key)
    api_key = await db.find_by_hash(key_hash)

    if not api_key or api_key.expires_at < datetime.utcnow():
        return None

    await db.update_last_used(api_key.id)
    return api_key
```

## Database Security

### Least Privilege

```sql
-- Create application user with minimal permissions
CREATE USER app_user WITH PASSWORD 'secure_password';

-- Grant only necessary permissions
GRANT SELECT, INSERT, UPDATE ON users TO app_user;
GRANT SELECT ON products TO app_user;

-- Don't grant DROP, DELETE on production tables
-- Don't use root/admin accounts for applications
```

## Secrets Management

```python
import os
from dotenv import load_dotenv

load_dotenv()

REQUIRED_ENV_VARS = ["DATABASE_URL", "JWT_SECRET", "API_KEY"]
for var in REQUIRED_ENV_VARS:
    if not os.environ.get(var):
        raise RuntimeError(f"Missing required environment variable: {var}")

# Never log secrets
print(f"Using database: {os.environ['DATABASE_URL']}")  # Bad!
print("Database configured")  # Good
```

## Encryption

### Data at Rest

```python
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY = bytes.fromhex(os.environ["ENCRYPTION_KEY"])  # 32 bytes

def encrypt(plaintext: str) -> dict:
    nonce = os.urandom(12)
    aesgcm = AESGCM(KEY)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return {
        "ciphertext": ciphertext.hex(),
        "nonce": nonce.hex(),
    }

def decrypt(ciphertext_hex: str, nonce_hex: str) -> str:
    aesgcm = AESGCM(KEY)
    plaintext = aesgcm.decrypt(
        bytes.fromhex(nonce_hex),
        bytes.fromhex(ciphertext_hex),
        None,
    )
    return plaintext.decode()
```

### Data in Transit

```python
@app.before_request
def enforce_https():
    if not request.is_secure and app.env == "production":
        url = request.url.replace("http://", "https://", 1)
        return redirect(url, code=301)

@app.after_request
def set_security_headers(response):
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```

## Security Headers

```python
from flask_talisman import Talisman

Talisman(app,
    content_security_policy={
        "default-src": "'self'",
        "style-src": ["'self'", "'unsafe-inline'"],
        "script-src": "'self'",
        "img-src": ["'self'", "data:", "https:"],
    },
    strict_transport_security=True,
    strict_transport_security_max_age=31536000,
    strict_transport_security_include_subdomains=True,
    strict_transport_security_preload=True,
)
```

## Logging & Monitoring

```python
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

@dataclass
class SecurityEvent:
    type: Literal["login", "logout", "failed_login", "permission_denied", "suspicious_activity"]
    ip: str
    user_agent: str
    timestamp: datetime
    user_id: str | None = None
    details: dict | None = None

def log_security_event(event: SecurityEvent):
    safe_details = {k: v for k, v in (event.details or {}).items()
                    if k not in ("password", "token", "api_key")}

    logging.getLogger("security").info({
        **vars(event),
        "details": safe_details,
    })

    if should_alert(event):
        alert_security_team(event)

failed_attempts: dict[str, int] = {}

def track_failed_login(ip: str):
    failed_attempts[ip] = failed_attempts.get(ip, 0) + 1

    if failed_attempts[ip] > 5:
        log_security_event(SecurityEvent(
            type="suspicious_activity",
            ip=ip,
            user_agent=request.headers.get("User-Agent", ""),
            timestamp=datetime.utcnow(),
            details={"failed_attempts": failed_attempts[ip]},
        ))
        ban_ip(ip, duration_seconds=15 * 60)
```

## Dangerous Functions

Never use on untrusted input:

```python
eval(user_input)              # Arbitrary code execution
exec(user_input)              # Arbitrary code execution
pickle.loads(untrusted_data)  # Arbitrary code execution
yaml.load(data)               # Use yaml.safe_load() instead
```

## Subprocess Security

```python
import subprocess

# Good — explicit argument list, no shell
subprocess.run(["ls", "-la", path], shell=False, check=True)

# Vulnerable to injection — never use shell=True with dynamic input
subprocess.run(f"ls -la {path}", shell=True)
```

## Randomness

```python
import secrets
import random

# Good — cryptographically secure
token = secrets.token_urlsafe(32)
otp = secrets.randbelow(1000000)

# Bad — predictable, not for security
token = random.randint(0, 999999)  # Never use random for security
```

## Static Analysis

Run [Bandit](https://bandit.readthedocs.io/) as part of CI to catch common security issues:

```bash
bandit -r src/ -c pyproject.toml
```

Or integrate via Ruff with the `S` (flake8-bandit) rule set in `[tool.ruff.lint]`.

## Dependency Security

```bash
# Check for vulnerabilities
pip-audit

# Or with safety
safety check

# Use Dependabot or Renovate for automated updates

# Use a lock file — prefer modern lock formats
# uv.lock (uv), poetry.lock (Poetry), or requirements.txt (pip)

# Verify package integrity with hashes
pip install --require-hashes -r requirements.txt
```

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [Bandit (Python Security)](https://bandit.readthedocs.io/)
- [Flask-Talisman](https://github.com/GoogleCloudPlatform/flask-talisman)
- [passlib](https://passlib.readthedocs.io/)
- [PyJWT](https://pyjwt.readthedocs.io/)
