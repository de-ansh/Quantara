"""Tests for one-shot price alerts and their delivery through the alerts feed."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.price_alert import PriceAlert
from app.models.stock import Stock
from app.services import price_service, stock_lookup


async def _headers(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(stock_lookup, "last_close", lambda t: None)


@pytest.mark.asyncio
async def test_create_list_delete_and_validation(client: AsyncClient, db_session):
    db_session.add(Stock(ticker="NVDA", name="NVIDIA", price=200.0))
    await db_session.commit()
    headers = await _headers(client)

    created = await client.post(
        "/api/v1/alerts/price/", headers=headers,
        json={"ticker": "nvda", "direction": "below", "target_price": 180},
    )
    assert created.status_code == 201
    assert created.json()["ticker"] == "NVDA" and created.json()["triggered_at"] is None

    listed = await client.get("/api/v1/alerts/price/?ticker=NVDA", headers=headers)
    assert [a["id"] for a in listed.json()] == [created.json()["id"]]

    bad = await client.post(
        "/api/v1/alerts/price/", headers=headers,
        json={"ticker": "NVDA", "direction": "sideways", "target_price": 1},
    )
    assert bad.status_code == 422
    unknown = await client.post(
        "/api/v1/alerts/price/", headers=headers,
        json={"ticker": "NOPE", "direction": "above", "target_price": 1},
    )
    assert unknown.status_code == 404

    deleted = await client.delete(f"/api/v1/alerts/price/{created.json()['id']}", headers=headers)
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/alerts/price/", headers=headers)).json() == []


@pytest.mark.asyncio
async def test_refresh_triggers_once_and_feeds_the_bell(client: AsyncClient, db_session, monkeypatch):
    db_session.add(Stock(ticker="NVDA", name="NVIDIA", price=200.0))
    await db_session.commit()
    headers = await _headers(client)
    for direction, target in [("below", 180), ("above", 250)]:
        await client.post(
            "/api/v1/alerts/price/", headers=headers,
            json={"ticker": "NVDA", "direction": direction, "target_price": target},
        )

    monkeypatch.setattr(price_service, "fetch_quotes", lambda t: {"NVDA": (175.0, 200.0)})
    await price_service.refresh_prices(db_session)

    alerts = (await db_session.execute(select(PriceAlert).order_by(PriceAlert.id))).scalars().all()
    below, above = alerts
    assert below.triggered_price == 175.0 and below.triggered_at is not None
    assert above.triggered_at is None  # condition not met
    first_fire = below.triggered_at

    # One-shot: a later refresh doesn't re-trigger it
    monkeypatch.setattr(price_service, "fetch_quotes", lambda t: {"NVDA": (170.0, 175.0)})
    await price_service.refresh_prices(db_session)
    await db_session.refresh(below)
    assert below.triggered_at == first_fire and below.triggered_price == 175.0

    feed = (await client.get("/api/v1/watchlist/alerts", headers=headers)).json()
    price_items = [a for a in feed["alerts"] if a["kind"] == "price"]
    assert len(price_items) == 1 and price_items[0]["unread"] is True
    assert "below 180.00" in price_items[0]["message"]
    assert feed["unread_count"] == 1
