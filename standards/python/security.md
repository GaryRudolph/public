# Security — Python

Follows [security.md](../security.md).

## Password Hashing

```python
from passlib.hash import bcrypt

ROUNDS = 12

def hash_password(password: str) -> str:
    return bcrypt.using(rounds=ROUNDS).hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.verify(password, hashed)
```

## JWT Tokens

```python
import jwt, os, secrets

def create_token(user_id: str, role: str) -> str:
    return jwt.encode(
        {"user_id": user_id, "role": role},
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
            return jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.InvalidTokenError as e:
            last_error = e
    raise last_error
```

## Session Configuration (Flask)

```python
app.config.update(
    SECRET_KEY=os.environ["SESSION_SECRET"],
    SESSION_COOKIE_NAME="sessionId",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    PERMANENT_SESSION_LIFETIME=900,
)
```

## Input Validation (Pydantic)

```python
from pydantic import BaseModel, EmailStr, Field

class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z\s'-]+$")
    age: int = Field(ge=0, le=150)
```

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

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.route("/api/v1/data")
@limiter.limit("100/15minutes")
def api_data(): pass

@app.route("/api/v1/auth/login", methods=["POST"])
@limiter.limit("5/15minutes")
def login(): pass
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

```python
REQUIRED_ENV_VARS = ["DATABASE_URL", "JWT_SECRET", "API_KEY"]
for var in REQUIRED_ENV_VARS:
    if not os.environ.get(var):
        raise RuntimeError(f"Missing required environment variable: {var}")
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
