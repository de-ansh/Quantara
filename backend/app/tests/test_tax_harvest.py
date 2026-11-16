"""Tax harvesting must follow Indian capital gains rules exactly; these pin the rules down."""

from datetime import date

import pytest

from app.services.tax_harvest import Trade, build_book, harvest_plan, long_term_from, tax_on

TODAY = date(2026, 11, 15)  # financial year 2026-27


def t(symbol: str, day: str, side: str, qty: float, price: float) -> Trade:
    return Trade(symbol, date.fromisoformat(day), side, qty, price)


def test_long_term_means_held_more_than_twelve_months():
    assert long_term_from(date(2025, 1, 15)) == date(2026, 1, 16)  # a sale on 15 Jan 2026 is still short-term
    assert long_term_from(date(2024, 2, 29)) == date(2025, 3, 1)


def test_set_off_rules_and_exemption():
    assert tax_on(0, 125_000) == 0  # within the exemption
    assert tax_on(0, 225_000) == pytest.approx(100_000 * 0.125 * 1.04)
    assert tax_on(50_000, 0) == pytest.approx(50_000 * 0.20 * 1.04)
    # A short-term loss offsets long-term gains; a long-term loss can't offset short-term gains
    assert tax_on(-100_000, 225_000) == 0
    assert tax_on(50_000, -80_000) == pytest.approx(50_000 * 0.20 * 1.04)


def test_fifo_splits_this_years_gains_into_short_and_long_term():
    book = build_book([
        t("ITC", "2024-06-01", "buy", 100, 400),
        t("ITC", "2026-02-01", "buy", 100, 450),
        t("ITC", "2025-08-01", "sell", 10, 420),   # last financial year: not this year's gain
        t("ITC", "2026-07-01", "sell", 120, 500),  # 90 from the 2024 lot (long), 30 from the 2026 lot (short)
    ], TODAY)
    assert book.realized.long_term == pytest.approx(90 * 100)
    assert book.realized.short_term == pytest.approx(30 * 50)
    [left] = book.lots
    assert (left.bought, left.quantity, left.cost) == (date(2026, 2, 1), 70, 450)


def test_intraday_round_trips_are_not_capital_gains():
    book = build_book([
        t("INFY", "2025-01-10", "buy", 10, 1500),
        t("INFY", "2026-06-02", "buy", 5, 1600),
        t("INFY", "2026-06-02", "sell", 8, 1650),  # 5 squared off intraday, 3 sold from the 2025 lot
    ], TODAY)
    assert book.realized.long_term == pytest.approx(3 * 150) and book.realized.short_term == 0
    assert [(lot.quantity, lot.cost) for lot in book.lots] == [(7, 1500)]


def test_sells_without_buys_are_flagged_not_guessed():
    book = build_book([t("IRFC", "2026-05-01", "buy", 100, 120), t("IRFC", "2026-06-01", "sell", 200, 130)], TODAY)
    assert book.lots == [] and "IRFC: sold 100 more shares" in book.warnings[0]


def test_plan_uses_the_exemption_harvests_losses_and_spots_lots_nearly_long_term():
    book = build_book([
        t("ITC", "2024-06-01", "buy", 1000, 300),     # long-term, +100 a share
        t("HDFC", "2025-03-01", "buy", 100, 1800),    # long-term, -300 a share
        t("TCS", "2025-12-01", "buy", 10, 3000),      # long-term from 2 Dec 2026: soon, +500 a share
        t("ZOMATO", "2026-08-01", "buy", 100, 300),   # short-term, -50 a share
        t("WIPRO", "2026-04-10", "buy", 100, 200),
        t("WIPRO", "2026-09-10", "sell", 100, 600),   # realised short-term +40,000
    ], TODAY)
    plan = harvest_plan(book, {"ITC": 400, "HDFC": 1500, "TCS": 3500, "ZOMATO": 250}, TODAY)

    assert plan["financial_year"] == "2026-27"
    assert plan["realized_short_term"] == 40_000 and plan["tax_so_far"] == pytest.approx(40_000 * 0.2 * 1.04)
    # The whole ₹1.25 lakh is unused: 1,000 ITC shares carry +1,00,000, all of it tax-free
    assert plan["tax_free_harvest"] == [{"symbol": "ITC", "bought": "2024-06-01", "quantity": 1000, "gain": 100_000}]
    assert plan["exemption_left"] == 125_000
    # Selling ZOMATO (-5,000 short) cuts the 40,000 short-term gain; HDFC's long-term loss can't touch it
    assert plan["loss_harvest_saving"] == pytest.approx(5_000 * 0.2 * 1.04)
    assert [x["symbol"] for x in plan["loss_harvest"]] == ["HDFC", "ZOMATO"]
    assert plan["turning_long_term"] == [{
        "symbol": "TCS", "bought": "2025-12-01", "quantity": 10, "gain": 5_000, "long_term_from": "2026-12-02",
        "tax_if_sold_now": pytest.approx(5_000 * 0.2 * 1.04),
    }]


def test_harvest_stops_at_the_exemption_in_whole_shares():
    book = build_book([t("ITC", "2024-06-01", "buy", 5000, 300)], TODAY)
    plan = harvest_plan(book, {"ITC": 400}, TODAY)
    assert plan["tax_free_harvest"] == [{"symbol": "ITC", "bought": "2024-06-01", "quantity": 1250, "gain": 125_000}]


@pytest.mark.asyncio
async def test_harvest_endpoint_resolves_broker_symbols_and_prices(client, db_session, monkeypatch):
    from datetime import timedelta

    from app.api.v1 import tax

    monkeypatch.setattr(tax, "_split_dates", lambda t: None if t == "NOPRICE" else [])  # no network

    from app.models.listed_security import ListedSecurity
    from app.models.stock import Stock
    from app.tests.test_stock_directory import _headers

    db_session.add_all([
        ListedSecurity(ticker="ITC.NS", name="ITC Limited", exchange="NSE"),
        Stock(ticker="ITC.NS", name="ITC Limited", price=400.0),
    ])
    await db_session.commit()
    old = (date.today() - timedelta(days=800)).isoformat()
    body = {"trades": [
        {"symbol": "ITC", "date": old, "side": "buy", "quantity": 100, "price": 300},
        {"symbol": "NOPRICE", "date": old, "side": "buy", "quantity": 5, "price": 10},
    ]}
    res = await client.post("/api/v1/tax/harvest", json=body, headers=await _headers(client))
    assert res.status_code == 200, res.text
    plan = res.json()
    assert plan["lots"][0]["symbol"] == "ITC.NS" and plan["lots"][0]["gain"] == 10_000
    assert plan["tax_free_harvest"][0]["quantity"] == 100 and plan["no_price"] == ["NOPRICE"]
    assert "Couldn't check for bonuses or splits on NOPRICE" in plan["warnings"][0]
    assert (await client.post("/api/v1/tax/harvest", json=body)).status_code in (401, 403)


def test_a_bonus_or_split_after_the_first_trade_leaves_the_stock_out():
    trades = [t("HDFCBANK", "2024-09-02", "buy", 20, 1650), t("HDFCBANK", "2026-06-01", "sell", 5, 800),
              t("ITC", "2024-06-01", "buy", 10, 300)]
    splits = {"HDFCBANK": [date(2019, 9, 19), date(2025, 8, 26)], "ITC": [date(2016, 7, 1)]}  # ITC's is before
    book = build_book(trades, TODAY, splits)
    assert [lot.symbol for lot in book.lots] == ["ITC"]
    assert book.realized.long_term == 0  # HDFC's sale isn't counted from wrong share counts
    assert "HDFCBANK: had a bonus or split on 2025-08-26" in book.warnings[0]
