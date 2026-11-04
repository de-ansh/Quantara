"""Tests for stored credentials, rate limiting, research cache freshness and inactive users."""

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1 import research
from app.core.clock import utcnow
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

    report.updated_at = utcnow() - timedelta(
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
async def test_password_reset_via_slack(client: AsyncClient, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from app.api.v1 import auth

    posted: list[str] = []

    async def fake_slack(text: str) -> None:
        posted.append(text)

    monkeypatch.setattr(auth, "notify_slack", fake_slack)
    monkeypatch.setattr(settings, "slack_webhook_url", None)
    off = await client.post("/api/v1/auth/forgot-password", json={"email": "test@quantara.com"})
    assert off.status_code == 503

    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.test/x")
    old_headers = await _auth_headers(client)
    # Unknown emails get the same reply and post nothing
    unknown = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@x.com"})
    assert unknown.status_code == 202 and posted == []

    sent = await client.post("/api/v1/auth/forgot-password", json={"email": "test@quantara.com"})
    assert sent.status_code == 202 and unknown.json() == sent.json()
    link = posted[0].split()[-1]
    token = parse_qs(urlparse(link).query)["token"][0]

    # A reset token is not an access token
    as_bearer = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert as_bearer.status_code == 401
    bad = await client.post(
        "/api/v1/auth/reset-password", json={"token": "junk", "new_password": "reset-pass-123"}
    )
    assert bad.status_code == 400

    ok = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "reset-pass-123"}
    )
    assert ok.status_code == 204
    # Single use, existing sessions revoked, only the new password logs in
    reused = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "another-pass-1"}
    )
    assert reused.status_code == 400
    assert (await client.get("/api/v1/users/me", headers=old_headers)).status_code == 401
    login = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "reset-pass-123"}
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_two_factor_login(client: AsyncClient):
    import time

    import pyotp

    creds = {"email": "test@quantara.com", "password": "password"}
    headers = await _auth_headers(client)

    setup = await client.post("/api/v1/auth/2fa/setup", headers=headers)
    assert setup.status_code == 200 and setup.json()["otpauth_uri"].startswith("otpauth://totp/")
    totp = pyotp.TOTP(setup.json()["secret"])
    # Not on until the app proves it has the secret
    assert (await client.post("/api/v1/auth/login", json=creds)).status_code == 200
    wrong = await client.post("/api/v1/auth/2fa/enable", json={"code": "000000"}, headers=headers)
    assert wrong.status_code == 400
    enable_code = totp.now()
    enabled = await client.post("/api/v1/auth/2fa/enable", json={"code": enable_code}, headers=headers)
    assert enabled.status_code == 200
    recovery = enabled.json()["recovery_codes"]
    assert len(recovery) == 8
    me = (await client.get("/api/v1/users/me", headers=headers)).json()
    assert me["two_factor_enabled"] is True and me["recovery_codes_left"] == 8

    # Password alone is no longer enough
    no_code = await client.post("/api/v1/auth/login", json=creds)
    assert no_code.status_code == 401 and no_code.json()["detail"] == "two_factor_required"
    bad = await client.post("/api/v1/auth/login", json={**creds, "totp_code": "123456"})
    assert bad.status_code == 401 and bad.json()["detail"] == "Invalid two-factor code"
    # A code already used can't be replayed
    replay = await client.post("/api/v1/auth/login", json={**creds, "totp_code": enable_code})
    assert replay.status_code == 401
    next_code = totp.at(time.time() + totp.interval)
    ok = await client.post("/api/v1/auth/login", json={**creds, "totp_code": next_code})
    assert ok.status_code == 200

    # Recovery codes work once, with or without the dash
    rec = await client.post(
        "/api/v1/auth/login", json={**creds, "totp_code": recovery[0].replace("-", "").upper()}
    )
    assert rec.status_code == 200
    again = await client.post("/api/v1/auth/login", json={**creds, "totp_code": recovery[0]})
    assert again.status_code == 401

    bad_off = await client.post(
        "/api/v1/auth/2fa/disable", json={"password": "nope", "code": recovery[1]}, headers=headers
    )
    assert bad_off.status_code == 400
    off = await client.post(
        "/api/v1/auth/2fa/disable", json={"password": "password", "code": recovery[1]}, headers=headers
    )
    assert off.status_code == 204
    assert (await client.post("/api/v1/auth/login", json=creds)).status_code == 200


async def _enable_two_factor(client: AsyncClient, headers: dict):
    import pyotp

    secret = (await client.post("/api/v1/auth/2fa/setup", headers=headers)).json()["secret"]
    enabled = await client.post(
        "/api/v1/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=headers
    )
    return enabled.json()["recovery_codes"]


@pytest.mark.asyncio
async def test_regenerate_recovery_codes(client: AsyncClient):
    creds = {"email": "test@quantara.com", "password": "password"}
    headers = await _auth_headers(client)
    old = await _enable_two_factor(client, headers)

    wrong = await client.post(
        "/api/v1/auth/2fa/recovery-codes", json={"password": "nope", "code": old[0]}, headers=headers
    )
    assert wrong.status_code == 400
    new = await client.post(
        "/api/v1/auth/2fa/recovery-codes", json={"password": "password", "code": old[0]}, headers=headers
    )
    assert new.status_code == 200
    codes = new.json()["recovery_codes"]
    assert len(codes) == 8 and not set(codes) & set(old)

    # Old codes are gone, new ones work
    stale = await client.post("/api/v1/auth/login", json={**creds, "totp_code": old[1]})
    assert stale.status_code == 401
    fresh = await client.post("/api/v1/auth/login", json={**creds, "totp_code": codes[0]})
    assert fresh.status_code == 200


@pytest.mark.asyncio
async def test_reset_link_can_turn_off_two_factor(client: AsyncClient, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    from app.api.v1 import auth

    posted: list[str] = []

    async def fake_slack(text: str) -> None:
        posted.append(text)

    monkeypatch.setattr(auth, "notify_slack", fake_slack)
    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.test/x")
    await _enable_two_factor(client, await _auth_headers(client))

    async def reset(new_password: str, disable: bool) -> int:
        await client.post("/api/v1/auth/forgot-password", json={"email": "test@quantara.com"})
        token = parse_qs(urlparse(posted[-1].split()[-1]).query)["token"][0]
        resp = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": new_password, "disable_two_factor": disable},
        )
        return resp.status_code

    # A plain reset keeps two-factor on
    assert await reset("reset-pass-123", disable=False) == 204
    login = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "reset-pass-123"}
    )
    assert login.json()["detail"] == "two_factor_required"

    # Opting in turns it off and warns the Slack channel
    assert await reset("reset-pass-456", disable=True) == 204
    assert "turned off" in posted[-1]
    login = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "reset-pass-456"}
    )
    assert login.status_code == 200


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
    generated = utcnow() - timedelta(hours=2)
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
