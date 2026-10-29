import base64
import hashlib
from datetime import timedelta
from typing import Any

from cryptography.fernet import Fernet, MultiFernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.clock import utcnow
from app.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return bool(pwd_context.verify(plain_password, hashed_password))


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return str(pwd_context.hash(password))


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = utcnow() + expires_delta
    else:
        expire = utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire, "iat": utcnow(), "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return str(encoded_jwt)


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create a long-lived JWT that can only be exchanged at /auth/refresh."""
    to_encode = data.copy()
    now = utcnow()
    to_encode.update(
        {
            "exp": now + timedelta(days=settings.refresh_token_expire_days),
            "iat": now,
            "type": "refresh",
        }
    )
    return str(jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm))


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return dict(payload)
    except JWTError:
        return None


def verify_token(token: str, token_type: str = "access") -> dict[str, Any] | None:
    """Verify a JWT and return its payload if it is the expected token type."""
    payload = decode_access_token(token)
    if payload is None:
        return None
    # Tokens issued before the type claim existed are access tokens.
    if payload.get("type", "access") != token_type:
        return None
    return payload


def _get_credential_cipher() -> MultiFernet:
    """Encrypt with credential_encryption_key when set; still decrypt secret_key-derived values."""
    key_bytes = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    keys = [Fernet(base64.urlsafe_b64encode(key_bytes))]
    if settings.credential_encryption_key:
        keys.insert(0, Fernet(settings.credential_encryption_key.encode("utf-8")))
    return MultiFernet(keys)


def encrypt_credential(plain_text: str | None) -> str | None:
    """Encrypt a sensitive credential string using AES-CBC Fernet."""
    if not plain_text or not plain_text.strip():
        return None
    cipher = _get_credential_cipher()
    return cipher.encrypt(plain_text.strip().encode("utf-8")).decode("utf-8")


def decrypt_credential(cipher_text: str | None) -> str | None:
    """Decrypt a sensitive credential string."""
    if not cipher_text or not cipher_text.strip():
        return None
    try:
        cipher = _get_credential_cipher()
        return cipher.decrypt(cipher_text.strip().encode("utf-8")).decode("utf-8")
    except Exception:
        return None


def mask_credential(value: str | None) -> str | None:
    """Return masked representation of a secret key (e.g. sk-...abcd)."""
    if not value or not value.strip():
        return None
    v = value.strip()
    if len(v) <= 8:
        return "********"
    return f"{v[:3]}...{v[-4:]}"

