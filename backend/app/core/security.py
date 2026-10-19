import base64
from datetime import datetime, timedelta
import hashlib
from typing import Any

from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

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
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return str(encoded_jwt)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return dict(payload)
    except JWTError:
        return None


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify a JWT token and return the payload."""
    return decode_access_token(token)


def _get_credential_cipher() -> Fernet:
    """Generate a consistent Fernet cipher key derived from application secret_key."""
    key_bytes = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


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

