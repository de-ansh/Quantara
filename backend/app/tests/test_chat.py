"""Assistant chat: tool calls reach the app's own data, and the reply comes back."""

import json
from types import SimpleNamespace

import pytest

from app.api.v1 import chat as chat_api
from app.models.stock import Stock


def _completion(content=None, tool_calls=None):
    message = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
        model_dump=lambda **kw: {"role": "assistant", "content": content,
                                 "tool_calls": [{"id": t.id, "type": "function",
                                                 "function": {"name": t.function.name, "arguments": t.function.arguments}}
                                                for t in tool_calls or []]},
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeOpenAI:
    """Asks for AAPL's snapshot, then answers; records what it was sent."""

    calls: list[list[dict]] = []

    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, messages, **kwargs):
        FakeOpenAI.calls.append(list(messages))
        if len(FakeOpenAI.calls) == 1:
            call = SimpleNamespace(id="c1", type="function",
                                   function=SimpleNamespace(name="stock_snapshot", arguments='{"ticker": "aapl"}'))
            return _completion(tool_calls=[call])
        return _completion(content="Hold: solid business, but the price already reflects it.")


async def _headers(client):
    login = await client.post("/api/v1/auth/login", json={"email": "test@quantara.com", "password": "password"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_chat_looks_up_the_stock_then_answers(client, db_session, monkeypatch):
    db_session.add(Stock(ticker="AAPL", name="Apple Inc.", sector="Technology", price=200.0, research_score=80.0, risk_score=50.0))
    await db_session.commit()
    FakeOpenAI.calls = []
    monkeypatch.setattr(chat_api, "AsyncOpenAI", FakeOpenAI)

    resp = await client.post(
        "/api/v1/chat/",
        json={"messages": [{"role": "user", "content": "Should I buy Apple?"}], "ticker": "AAPL"},
        headers=await _headers(client),
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"reply": "Hold: solid business, but the price already reflects it.", "tickers": ["AAPL"]}
    system = FakeOpenAI.calls[0][0]["content"]
    assert "looking at AAPL" in system and "risk profile" in system
    tool_msg = FakeOpenAI.calls[1][-1]
    snapshot = json.loads(tool_msg["content"])
    assert tool_msg["role"] == "tool" and snapshot["stock"]["name"] == "Apple Inc."
    assert snapshot["verdict"]["verdict"] in {"Buy", "Hold", "Avoid"}
    assert snapshot["price_history_1y"]["change_1y_pct"] is not None
    assert "overall_risk_score" in snapshot["risk"]


@pytest.mark.asyncio
async def test_chat_rejects_a_conversation_not_ending_with_the_user(client):
    resp = await client.post(
        "/api/v1/chat/", json={"messages": [{"role": "assistant", "content": "hi"}]}, headers=await _headers(client)
    )
    assert resp.status_code == 422


class FakeStreamingOpenAI:
    """Streams a tool call split across chunks, then the answer in pieces."""

    calls: list[list[dict]] = []

    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, messages, stream=False, **kwargs):
        assert stream
        FakeStreamingOpenAI.calls.append(list(messages))
        first_round = len(FakeStreamingOpenAI.calls) == 1

        def chunk(content=None, tool=None):
            return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=content, tool_calls=tool))])

        def tool_piece(**kw):
            fn = SimpleNamespace(name=kw.get("name"), arguments=kw.get("arguments"))
            return [SimpleNamespace(index=0, id=kw.get("id"), function=fn)]

        async def gen():
            if first_round:
                yield chunk(tool=tool_piece(id="c1", name="stock_snapshot", arguments='{"tick'))
                yield chunk(tool=tool_piece(arguments='er": "AAPL"}'))
            else:
                for piece in ["**Hold**: ", "fairly ", "priced."]:
                    yield chunk(content=piece)

        return gen()


@pytest.mark.asyncio
async def test_chat_stream_runs_tools_then_streams_the_answer(client, db_session, monkeypatch):
    db_session.add(Stock(ticker="AAPL", name="Apple Inc.", sector="Technology", price=200.0, research_score=60.0, risk_score=50.0))
    await db_session.commit()
    FakeStreamingOpenAI.calls = []
    monkeypatch.setattr(chat_api, "AsyncOpenAI", FakeStreamingOpenAI)

    resp = await client.post(
        "/api/v1/chat/stream",
        json={"messages": [{"role": "user", "content": "Should I buy Apple?"}]},
        headers=await _headers(client),
    )

    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/plain")
    text, trailer = resp.text.split(chat_api.STREAM_TRAILER)
    assert text == "**Hold**: fairly priced."
    assert json.loads(trailer) == {"tickers": ["AAPL"]}  # the client draws a price chart for each
    # The split tool call was reassembled and answered from the database during the stream
    assistant_call, tool_msg = FakeStreamingOpenAI.calls[1][-2:]
    assert assistant_call["tool_calls"][0]["function"] == {"name": "stock_snapshot", "arguments": '{"ticker": "AAPL"}'}
    assert json.loads(tool_msg["content"])["stock"]["name"] == "Apple Inc."


@pytest.mark.asyncio
async def test_my_holdings_includes_funds_valued_like_the_portfolio_page(db_session):
    from datetime import date

    from sqlalchemy import select

    from app.core.clock import utcnow
    from app.core.dependencies import user_dict
    from app.models.mutual_fund import MutualFund
    from app.models.portfolio import Portfolio, PortfolioFund, PortfolioPosition
    from app.models.user import User

    user = (await db_session.execute(select(User))).scalars().first()
    db_session.add_all([
        Stock(ticker="TCS.NS", name="TCS", price=4000.0, previous_close=3900.0, price_updated_at=utcnow()),
        MutualFund(scheme_code=200001, name="Example Flexi Cap Fund - Direct Plan - Growth", nav=50.0, prev_nav=49.0,
                   nav_date=date(2026, 11, 20)),
    ])
    await db_session.flush()
    pf = Portfolio(user_id=user.id, name="Everything")
    pf.positions.append(PortfolioPosition(ticker="TCS.NS", weight=1.0, shares=2, cost_basis=3500))
    pf.funds.append(PortfolioFund(scheme_code=200001, units=10, cost_basis=40))
    db_session.add(pf)
    await db_session.commit()

    out = await chat_api.my_holdings(user_dict(user), db_session)
    [p] = out["portfolios"]
    by = {h["ticker"]: h for h in p["holdings"]}
    assert by["TCS.NS"]["unrealized_pnl"] == 1000.0 and by["TCS.NS"]["day_change"] == 200.0
    fund = by["200001"]
    assert fund["kind"] == "fund" and fund["name"].startswith("Example Flexi Cap")
    assert fund["market_value"] == 500.0 and fund["unrealized_pnl_pct"] == 25.0 and fund["price_date"] == "2026-11-20"
    assert p["totals"][0]["market_value"] == 8500.0 and "sector_allocation" not in p["totals"][0]
    json.dumps(out)  # goes to the model as JSON
