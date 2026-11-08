"""Research assistant chat: explains the app's charts and scores and reasons about buy/hold/avoid.

The model only sees numbers the app itself computes, fetched through tools that call the same
functions as the pages (risk, price history, verdict, research report, signals, holdings).
"""

import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import settings
from app.core.dependencies import CurrentUser, DBSession, RedisClient, enforce_rate_limit
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

MAX_TOOL_ROUNDS = 4
CHAT_LIMIT_PER_HOUR = 40

SYSTEM_PROMPT = """You are Quantara's research assistant. The user is an individual investor looking at \
Quantara's pages: price charts, risk breakdowns (volatility, beta, leverage, earnings stability, sector, \
valuation), drawdowns, stress scenarios, signals, research reports and a Buy/Hold/Avoid verdict.

How to work:
- Get data with the tools before answering anything about a stock; never invent or estimate numbers. \
If a tool returns nothing for something, say it is unavailable.
- Explain charts and scores in plain language: what the number measures, what range is normal, what it \
means for this stock. Keep it short and concrete; use the numbers.
- When asked whether to buy: give a clear lean (Buy, Hold or Avoid) for the user's risk profile, the 2-4 \
reasons that matter most, the main risk that would change your view, and what to watch next. Respect the \
app's verdict but say so if the data points elsewhere.
- Know the verdict's limits: its "research quality" part is the report model's confidence in its data, \
not a bullish view, and missing inputs are filled with defaults (listed in risk.assumed_inputs).
- End buy/sell answers with one short line that this is research, not personalised financial advice. \
Don't repeat that elsewhere.
- Format for a narrow chat panel: short paragraphs and "- " bullet lists; **bold** for the verdict and key \
numbers. No headings, tables or links.
- Tickers: Yahoo form (TCS.NS for NSE, 500325.BO or SYMBOL.BO for BSE, plain for US). Use find_ticker \
when the user names a company."""

TOOLS = [
    {"type": "function", "function": {
        "name": "stock_snapshot",
        "description": "Everything Quantara shows for one stock: price and fundamentals, 1-month/1-year "
                       "price moves, risk breakdown and stress scenarios, verdict, research report, signals.",
        "parameters": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]},
    }},
    {"type": "function", "function": {
        "name": "find_ticker",
        "description": "Search NSE, BSE and US listings by company name or symbol.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "my_holdings",
        "description": "The user's watchlist and saved portfolios with their positions.",
        "parameters": {"type": "object", "properties": {}},
    }},
]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=30)
    ticker: str | None = Field(default=None, max_length=20, description="Stock open on screen, if any")


class ChatResponse(BaseModel):
    reply: str
    tickers: list[str]  # stocks the answer looked up


def _move(points: list, days_back: int) -> float | None:
    if len(points) <= days_back:
        return None
    start, end = points[-1 - days_back].close, points[-1].close
    return round((end / start - 1) * 100, 2) if start else None


async def stock_snapshot(ticker: str, user: dict, db: Any) -> dict:
    from app.api.v1.recommendations import get_verdict
    from app.api.v1.research import get_price_history, search_stocks
    from app.api.v1.risk import get_stock_risk_analysis
    from app.models.research import ResearchReport
    from app.models.signal import Signal

    ticker = ticker.strip().upper()
    found = (await search_stocks(user, db, query=ticker, track=True)).stocks
    item = next((s for s in found if s.ticker == ticker), None)
    if item is None:
        return {"error": f"{ticker} is not a listed security; try find_ticker"}

    snap: dict[str, Any] = {"stock": item.model_dump(exclude={"status", "signal"}, mode="json")}
    history = (await get_price_history(ticker, user, range="1Y")).points
    if history:
        closes = [p.close for p in history]
        snap["price_history_1y"] = {
            "last_close": closes[-1], "change_1m_pct": _move(history, 21), "change_1y_pct": _move(history, len(history) - 1),
            "high_1y": max(closes), "low_1y": min(closes), "as_of": history[-1].date,
        }
    try:
        risk = await get_stock_risk_analysis(ticker, user, db)
        snap["risk"] = risk.model_dump(exclude={"drawdown_series"}, mode="json")
    except Exception as e:  # risk needs price data; report what's missing instead of failing the chat
        snap["risk"] = {"error": str(e)[:200]}
    snap["verdict"] = (await get_verdict(ticker, user, db)).model_dump()
    report = (await db.execute(select(ResearchReport).where(ResearchReport.ticker == ticker))).scalar_one_or_none()
    snap["research_report"] = (
        {**(report.structured_json or {}), "generated_at": report.updated_at.isoformat()} if report
        else "none yet; the user can generate one on the stock page"
    )
    signals = (await db.execute(
        select(Signal).where(Signal.ticker == ticker).order_by(Signal.timestamp.desc()).limit(5)
    )).scalars().all()
    snap["signals"] = [
        {"type": s.signal_type, "strength": round(s.strength, 1), "date": s.timestamp.date().isoformat()} for s in signals
    ]
    return snap


async def find_ticker(query: str, user: dict, db: Any) -> dict:
    from app.api.v1.research import search_stocks

    hits = (await search_stocks(user, db, query=query, limit=8)).stocks
    return {"matches": [{"ticker": s.ticker, "name": s.name, "exchange": s.exchange} for s in hits]}


async def my_holdings(user: dict, db: Any) -> dict:
    from app.api.v1.portfolio import list_portfolios
    from app.api.v1.watchlist import get_watchlist

    watch = await get_watchlist(user, db)
    portfolios = await list_portfolios(user, db)
    return {
        "risk_profile": {k: user.get(k) for k in ("risk_level", "volatility_tolerance", "investment_horizon")},
        "watchlist": [{"ticker": s.ticker, "name": s.name, "price": s.price} for s in watch.items],
        "portfolios": [p.model_dump(include={"name", "positions"}, mode="json") for p in portfolios.portfolios],
    }


async def _run_tool(name: str, args: dict, user: dict, db: Any) -> dict:
    if name == "stock_snapshot" and args.get("ticker"):
        return await stock_snapshot(str(args["ticker"]), user, db)
    if name == "find_ticker" and args.get("query"):
        return await find_ticker(str(args["query"]), user, db)
    if name == "my_holdings":
        return await my_holdings(user, db)
    return {"error": f"unknown tool or missing arguments: {name}"}


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user: CurrentUser, db: DBSession, redis: RedisClient) -> ChatResponse:
    """One assistant turn; the client sends the whole conversation each time (nothing is stored)."""
    if request.messages[-1].role != "user":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The last message must be from the user")
    # Each turn is a paid LLM call (several with tools), so cap it per user
    await enforce_rate_limit(redis, f"chat:{current_user['id']}", CHAT_LIMIT_PER_HOUR, 3600)

    profile = (
        f"User risk profile: {current_user.get('risk_level') or 'Moderate (not set)'}, "
        f"volatility tolerance {current_user.get('volatility_tolerance') or 'not set'}, "
        f"horizon {current_user.get('investment_horizon') or 'not set'} months."
    )
    on_screen = f" The user is looking at {request.ticker.upper()}." if request.ticker else ""
    messages: list[dict] = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{profile}{on_screen}"}]
    messages += [m.model_dump() for m in request.messages]

    client = AsyncOpenAI(api_key=current_user.get("openai_api_key") or settings.openai_api_key, timeout=60.0)
    tickers: list[str] = []
    try:
        for _ in range(MAX_TOOL_ROUNDS + 1):
            resp = await client.chat.completions.create(
                model=settings.openai_model, messages=messages, tools=TOOLS, temperature=0.2,
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return ChatResponse(reply=msg.content or "", tickers=tickers)
            messages.append(msg.model_dump(exclude_none=True))
            for call in msg.tool_calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                if call.function.name == "stock_snapshot" and args.get("ticker"):
                    tickers.append(str(args["ticker"]).upper())
                result = await _run_tool(call.function.name, args, current_user, db)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, default=str)})
    except OpenAIError as e:
        logger.error(f"Chat LLM call failed: {e}")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The assistant is unavailable right now") from e
    raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The assistant needed too many lookups; ask a narrower question")
