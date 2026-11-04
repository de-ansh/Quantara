"""Two-factor login: authenticator-app codes (TOTP, RFC 6238) and single-use recovery codes."""

import hashlib
import hmac
import secrets
import time

import pyotp

from app.core.security import decrypt_credential
from app.models.user import User

ISSUER = "Quantara"
RECOVERY_CODE_COUNT = 8


def new_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    """otpauth:// link that authenticator apps read from a QR code."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def _hash_recovery(code: str) -> str:
    return hashlib.sha256(code.replace("-", "").strip().lower().encode()).hexdigest()


def new_recovery_codes() -> tuple[list[str], list[str]]:
    """(codes to show the user once, hashes to store)."""
    codes = [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(RECOVERY_CODE_COUNT)]
    return codes, [_hash_recovery(c) for c in codes]


def verify_totp(user: User, code: str, secret: str | None = None) -> bool:
    """Check a 6-digit app code (one step of clock drift allowed, no replays); records it on success."""
    secret = secret or decrypt_credential(user.totp_secret)
    code = code.replace(" ", "").strip()
    if not secret or not (code.isdigit() and len(code) == 6):
        return False
    totp = pyotp.TOTP(secret)
    now = int(time.time()) // totp.interval
    for counter in (now - 1, now, now + 1):
        if counter > (user.totp_last_counter or -1) and hmac.compare_digest(
            totp.generate_otp(counter), code
        ):
            user.totp_last_counter = counter
            return True
    return False


def verify_second_factor(user: User, code: str) -> bool:
    """An app code, or an unused recovery code (consumed on success). Caller commits."""
    if verify_totp(user, code):
        return True
    remaining = list(user.totp_recovery_codes or [])
    hashed = _hash_recovery(code)
    if hashed in remaining:
        remaining.remove(hashed)
        user.totp_recovery_codes = remaining  # reassign so SQLAlchemy sees the JSON change
        return True
    return False
