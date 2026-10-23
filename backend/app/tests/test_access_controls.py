"""Tests for stored credentials, rate limiting, research cache freshness and inactive users."""

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1 import research
from app.core.config import settings
from app.models.research import ResearchReport
from app.models.stock import Stock
from app.models.user import User

REPORT = {
    "ticker": "AAPL",
    "summary": "fresh",
    "key_insights": [],
    "strengths": [],
    "weaknesses": [],
    "opportunities": [],
    "threats": [],
    "confidence_score": 80.0,
}


async def _auth_headers(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def fake_generate(monkeypatch):
    calls: list[dict] = []

    async def _generate(db, ticker, openai_api_key=None, sec_user_agent=None):
        calls.append({"openai_api_key": openai_api_key, "sec_user_agent": sec_user_agent})
        return {**REPORT, "ticker": ticker}

    monkeypatch.setattr(research.research_engine, "generate_research_report", _generate)
    return calls


@pytest.mark.asyncio
async def test_research_uses_stored_openai_key(client: AsyncClient, fake_generate):
    headers = await _auth_headers(client)
    await client.put(
        "/api/v1/users/credentials",
        json={"openai_api_key": "sk-proj-stored-key-123456789", "sec_user_agent": "Me me@x.com"},
        headers=headers,
    )

    resp = await client.get("/api/v1/stocks/AAPL/research", headers=headers)

    assert resp.status_code == 200
    assert fake_generate == [
        {"openai_api_key": "sk-proj-stored-key-123456789", "sec_user_agent": "Me me@x.com"}
    ]


@pytest.mark.asyncio
async def test_fresh_report_is_cached_and_stale_report_regenerates(
    client: AsyncClient, db_session, fake_generate
):
    headers = await _auth_headers(client)
    db_session.add(Stock(ticker="AAPL", name="Apple Inc."))
    await db_session.commit()
    report = ResearchReport(
        ticker="AAPL", structured_json={**REPORT, "summary": "cached"}, confidence_score=80.0
    )
    db_session.add(report)
    await db_session.commit()

    resp = await client.get("/api/v1/stocks/AAPL/research", headers=headers)
    assert resp.json()["summary"] == "cached"
    assert fake_generate == []

    report.updated_at = datetime.utcnow() - timedelta(
        hours=settings.research_cache_max_age_hours + 1
    )
    await db_session.commit()

    resp = await client.get("/api/v1/stocks/AAPL/research", headers=headers)
    assert resp.json()["summary"] == "fresh"
    assert len(fake_generate) == 1


@pytest.mark.asyncio
async def test_login_is_rate_limited(client: AsyncClient):
    payload = {"email": "test@quantara.com", "password": "wrong-password"}
    codes = [
        (await client.post("/api/v1/auth/login", json=payload)).status_code
        for _ in range(settings.login_rate_limit_per_minute + 1)
    ]
    assert codes[:-1] == [401] * settings.login_rate_limit_per_minute
    assert codes[-1] == 429


@pytest.mark.asyncio
async def test_inactive_user_cannot_login_or_use_token(client: AsyncClient, db_session):
    headers = await _auth_headers(client)

    user = (
        await db_session.execute(select(User).where(User.email == "test@quantara.com"))
    ).scalar_one()
    user.is_active = False
    await db_session.commit()

    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 401
    login = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"}
    )
    assert login.status_code == 401


@pytest.mark.asyncio
async def test_register_rejects_short_password(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "short@quantara.com", "password": "abc"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_refresh_token_lives_in_httponly_cookie(client: AsyncClient):
    login = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"}
    )
    assert "refresh_token" not in login.json()
    cookie = login.headers["set-cookie"].lower()
    assert "quantara_refresh=" in cookie
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api/v1/auth" in cookie

    # The cookie (kept by the client) mints a new access token
    refreshed = await client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    me = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"}
    )
    assert me.status_code == 200

    # A refresh token is never accepted as an access token
    refresh_value = client.cookies.get("quantara_refresh")
    as_bearer = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {refresh_value}"}
    )
    assert as_bearer.status_code == 401

    # Without the cookie, refresh fails
    client.cookies.clear()
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


def test_credential_encryption_key_overrides_secret_derivation(monkeypatch):
    from cryptography.fernet import Fernet

    from app.core import security

    legacy = security.encrypt_credential("sk-legacy")
    monkeypatch.setattr(settings, "credential_encryption_key", Fernet.generate_key().decode())
    token = security.encrypt_credential("sk-new")
    assert security.decrypt_credential(token) == "sk-new"
    # Values stored before the key was configured remain readable
    assert security.decrypt_credential(legacy) == "sk-legacy"
    # New values no longer depend on secret_key
    monkeypatch.setattr(settings, "secret_key", "x" * 64)
    assert security.decrypt_credential(token) == "sk-new"


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient):
    old_headers = await _auth_headers(client)

    wrong = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "nope", "new_password": "new-password-123"},
        headers=old_headers,
    )
    assert wrong.status_code == 400

    ok = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "password", "new_password": "new-password-123"},
        headers=old_headers,
    )
    assert ok.status_code == 200
    new_headers = {"Authorization": f"Bearer {ok.json()['access_token']}"}

    # Old sessions are revoked, the returned tokens work, and only the new password logs in
    assert (await client.get("/api/v1/users/me", headers=old_headers)).status_code == 401
    assert (await client.get("/api/v1/users/me", headers=new_headers)).status_code == 200
    old_login = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"}
    )
    assert old_login.status_code == 401
    new_login = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "new-password-123"}
    )
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_report_age_is_returned_and_refresh_bypasses_cache(
    client: AsyncClient, db_session, fake_generate
):
    headers = await _auth_headers(client)
    db_session.add(Stock(ticker="AAPL", name="Apple Inc."))
    await db_session.commit()
    generated = datetime.utcnow() - timedelta(hours=2)
    db_session.add(
        ResearchReport(
            ticker="AAPL",
            structured_json={**REPORT, "summary": "cached"},
            confidence_score=80.0,
            updated_at=generated,
        )
    )
    await db_session.commit()

    cached = (await client.get("/api/v1/stocks/AAPL/research", headers=headers)).json()
    assert cached["summary"] == "cached"
    assert cached["generated_at"].startswith(generated.isoformat()[:16])

    fresh = await client.get("/api/v1/stocks/AAPL/research?refresh=true", headers=headers)
    assert fresh.json()["summary"] == "fresh"
    assert len(fake_generate) == 1
