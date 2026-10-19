"""Tests for User Credential Encryption and Storage endpoints."""

from unittest.mock import AsyncMock, MagicMock
import pytest

from app.core.security import decrypt_credential, encrypt_credential, mask_credential
from app.api.v1.users import get_user_credentials, update_user_credentials, UserCredentialsUpdate
from app.models.user import User


def test_credential_encryption_roundtrip():
    """Test encrypt_credential and decrypt_credential round-trip."""
    raw_key = "sk-proj-test1234567890abcdefghijklmnopqrstuvwxyz"
    encrypted = encrypt_credential(raw_key)

    assert encrypted is not None
    assert encrypted != raw_key
    assert len(encrypted) > len(raw_key)

    decrypted = decrypt_credential(encrypted)
    assert decrypted == raw_key


def test_credential_masking():
    """Test mask_credential produces privacy-safe masked strings."""
    assert mask_credential(None) is None
    assert mask_credential("") is None
    assert mask_credential("1234") == "********"
    assert mask_credential("sk-proj-1234567890") == "sk-...7890"


@pytest.mark.asyncio
async def test_get_user_credentials_empty():
    """Test get_user_credentials when no keys are configured."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    user = User(
        id=1,
        email="analyst@quantara.com",
        hashed_password="hash",
        openai_api_key=None,
        sec_user_agent=None,
    )
    mock_res.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_res

    current_user = {"id": "1", "email": "analyst@quantara.com"}
    resp = await get_user_credentials(current_user=current_user, db=mock_db)

    assert resp.has_openai_key is False
    assert resp.openai_key_masked is None
    assert resp.sec_user_agent is None


@pytest.mark.asyncio
async def test_update_user_credentials():
    """Test update_user_credentials stores encrypted key and emits audit log."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_res = MagicMock()
    user = User(
        id=1,
        email="analyst@quantara.com",
        hashed_password="hash",
        openai_api_key=None,
        sec_user_agent=None,
    )
    mock_res.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_res

    current_user = {"id": "1", "email": "analyst@quantara.com"}
    raw_key = "sk-proj-securekey123456789"
    payload = UserCredentialsUpdate(
        openai_api_key=raw_key,
        sec_user_agent="Quantara Analytics research@quantara.com"
    )

    resp = await update_user_credentials(
        credentials=payload,
        current_user=current_user,
        db=mock_db
    )

    assert resp.has_openai_key is True
    assert resp.openai_key_masked == "sk-...6789"
    assert resp.sec_user_agent == "Quantara Analytics research@quantara.com"

    # Verify user record stored ciphertext, not plaintext
    assert user.openai_api_key != raw_key
    assert decrypt_credential(user.openai_api_key) == raw_key
    assert user.sec_user_agent == "Quantara Analytics research@quantara.com"
    assert mock_db.commit.await_count >= 1


@pytest.mark.asyncio
async def test_clear_user_credentials():
    """Test clearing credentials by sending empty string."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_res = MagicMock()
    user = User(
        id=1,
        email="analyst@quantara.com",
        hashed_password="hash",
        openai_api_key=encrypt_credential("sk-proj-existing"),
        sec_user_agent="Existing Agent",
    )
    mock_res.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_res

    current_user = {"id": "1", "email": "analyst@quantara.com"}
    payload = UserCredentialsUpdate(openai_api_key="", sec_user_agent="")

    resp = await update_user_credentials(
        credentials=payload,
        current_user=current_user,
        db=mock_db
    )

    assert resp.has_openai_key is False
    assert resp.openai_key_masked is None
    assert resp.sec_user_agent is None
    assert user.openai_api_key is None
    assert user.sec_user_agent is None
