# Security — Python

Follows [security.md](../security.md).

## Password Hashing

Use **argon2-cffi**. Its defaults are RFC 9106 §4's second recommended option, the same parameters as the Go example, so either service verifies the other's hashes. The password rules themselves are in [security.md](../security.md#authentication).

```python
import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()


def _nfc(password: str) -> str:
    return unicodedata.normalize("NFC", password)  # NIST SP 800-63B-4 §3.1.1.2


def hash_password(password: str) -> str:
    return _hasher.hash(_nfc(password))


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, _nfc(password))
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    """After a successful login, store a fresh hash_password() when True."""
    return _hasher.check_needs_rehash(hashed)
```

Don't use passlib: its last release was 2020-10, and it fails on its first bcrypt hash with bcrypt 5. To move existing bcrypt hashes, pwdlib's `PasswordHash((Argon2Hasher(), BcryptHasher()))` verifies both, and `verify_and_update` returns an argon2id hash to store. The `bcrypt` package itself raises `ValueError` on passwords over 72 bytes rather than truncating.

## JWT Tokens

```python
import jwt, os, secrets
from datetime import UTC, datetime, timedelta

def create_token(user_id: str, role: str) -> str:
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": datetime.now(UTC) + timedelta(minutes=15)},
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )

def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)
```

### Secret Rotation

Support multiple active keys during rotation:

```python
JWT_SECRETS = [os.environ["JWT_SECRET_CURRENT"], os.environ["JWT_SECRET_PREVIOUS"]]

def verify_token(token: str) -> dict:
    last_error = None
    for secret in JWT_SECRETS:
        try:
            return jwt.decode(  # RFC 8725: pin algorithms, require exp
                token, secret, algorithms=["HS256"], options={"require": ["exp", "sub"]}
            )
        except jwt.InvalidTokenError as e:
            last_error = e
    raise last_error
```

## Cookie / Session Configuration (FastAPI)

Use `SessionMiddleware` from Starlette for cookie-based sessions:

```python
from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="__Host-session",  # needs Secure (https_only), Path=/ and no domain: the defaults
    https_only=True,
    same_site="strict",
    max_age=900,
)
```

## Input Validation (Pydantic)

```python
from pydantic import BaseModel, EmailStr, Field

class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=15, max_length=128)  # 15 if it's the only factor, 8 with MFA
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z\s'-]+$")
    age: int = Field(ge=0, le=150)
```

`min_length` counts code points, which is how NIST counts password length.

## File Upload Validation

```python
import magic, uuid

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024
MIME_TO_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif"}

def validate_upload(file_data: bytes, declared_mimetype: str) -> str:
    if len(file_data) > MAX_FILE_SIZE:
        raise ValueError("File too large")
    if declared_mimetype not in ALLOWED_MIME_TYPES:
        raise ValueError("Invalid file type")
    actual_type = magic.from_buffer(file_data, mime=True)
    if actual_type != declared_mimetype:
        raise ValueError("File type mismatch")
    return f"{uuid.uuid4()}.{MIME_TO_EXT[declared_mimetype]}"
```

## Rate Limiting

Use `slowapi` with FastAPI:

- **Key on the real client IP**: `get_remote_address` reads `request.client`, which behind a proxy is the proxy. Run Uvicorn with `--forwarded-allow-ips` set to the proxies' addresses so it resolves the client from `X-Forwarded-For`; never `*`, which takes the leftmost entry, and any client can write that
- **No `X-RateLimit-*`**: leave `headers_enabled` off
- **429 is a problem with `Retry-After`**: `RateLimitExceeded` is an `HTTPException`, so the problem handler for those ([architecture.md](architecture.md#error-catalog-pattern)) renders it, but with no `Retry-After`. Add the header, then render it with the same `http_problem`

```python
import time

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.problems import http_problem

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limited(request: Request, exc: RateLimitExceeded) -> Response:
    limit, keys = request.state.view_rate_limit
    reset_at, _ = limiter.limiter.get_window_stats(limit, *keys)
    exc.headers = {"Retry-After": str(max(1, int(reset_at - time.time())))}
    return http_problem(request, exc)


@router.get("/api/v1/data")
@limiter.limit("100/15minutes")
async def api_data(request: Request) -> dict: ...


@router.post("/api/v1/auth/login")
@limiter.limit("5/15minutes")
async def login(request: Request) -> dict: ...
```

## API Key Security

```python
import secrets, hashlib

def generate_api_key() -> str:
    return f"app_{secrets.token_urlsafe(32)}"

def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()
```

## Secrets Management

All secrets are declared as required fields in `Settings` (`app/core/config.py`). `pydantic-settings` raises a `ValidationError` at startup if any are missing — no manual checks needed:

```python
class Settings(BaseSettings):
    database_url: str       # required — missing = startup failure
    jwt_secret: str         # required
    api_key: str            # required
    environment: str = "development"  # optional with default
```

## Encryption (AES-256-GCM)

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY = bytes.fromhex(os.environ["ENCRYPTION_KEY"])

def encrypt(plaintext: str) -> dict:
    nonce = os.urandom(12)
    ciphertext = AESGCM(KEY).encrypt(nonce, plaintext.encode(), None)
    return {"ciphertext": ciphertext.hex(), "nonce": nonce.hex()}
```

## Randomness

```python
import secrets
token = secrets.token_urlsafe(32)       # cryptographically secure
otp = secrets.randbelow(1000000)
# Never use random.randint() for security purposes
```

## Static Analysis

Run Bandit in CI: `bandit -r src/ -c pyproject.toml`

Or integrate via Ruff with the `S` rule set.

## Dependency Security

```bash
pip-audit                                    # check for vulnerabilities
pip install --require-hashes -r requirements.txt  # verify integrity
```

Run `pip-audit` as a blocking check on every PR and on a schedule ([security.md](../security.md#dependency-security)). It has no reachability analysis, so it also fails on code the service never calls; silence a finding with `--ignore-vuln <id>` and a written reason.
