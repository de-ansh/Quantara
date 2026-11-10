"""Research assistant chat: explains the app's charts and scores and reasons about buy/hold/avoid.

The model only sees numbers the app itself computes, fetched through tools that call the same
functions as the pages (risk, price history, verdict, research report, signals, holdings).
"""

import json
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI, OpenAIError
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
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
- Know the verdict's inputs: "research outlook" is the research report's bearish (0) to bullish (100) \
view, pulled toward 50 when the report's confidence is low; missing risk inputs are filled with defaults \
(listed in risk.assumed_inputs).
- End buy/sell answers with one short line that this is research, not personalised financial advice. \
Don't repeat that elsewhere.
- Format for a narrow chat panel: short paragraphs and "- " bullet lists; **bold** for the verdict and key \
numbers. No headings, tables or links.
- Tickers: Yahoo form (TCS.NS for NSE, SYMBOL.BO for BSE, plain for US). A bare symbol is looked up on \
NSE first, then BSE, then US; say which listing you used. Use find_ticker when the user names a company \
or a symbol could mean more than one listing."""

TOOLS: list[ChatCompletionToolParam] = [
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
    from app.services.stock_lookup import resolve_ticker

    ticker = await resolve_ticker(db, ticker) or ticker.strip().upper()  # "ITC" means ITC.NS, not a US symbol
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


async def _start(request: ChatRequest, user: dict, redis: Any) -> tuple[list[ChatCompletionMessageParam], AsyncOpenAI]:
    """Validate, rate-limit and build the conversation sent to the model."""
    if request.messages[-1].role != "user":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The last message must be from the user")
    # Each turn is a paid LLM call (several with tools), so cap it per user
    await enforce_rate_limit(redis, f"chat:{user['id']}", CHAT_LIMIT_PER_HOUR, 3600)
    profile = (
        f"User risk profile: {user.get('risk_level') or 'Moderate (not set)'}, "
        f"volatility tolerance {user.get('volatility_tolerance') or 'not set'}, "
        f"horizon {user.get('investment_horizon') or 'not set'} months."
    )
    on_screen = f" The user is looking at {request.ticker.upper()}." if request.ticker else ""
    messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{profile}{on_screen}"}]
    for m in request.messages:
        if m.role == "user":
            messages.append({"role": "user", "content": m.content})
        else:
            messages.append({"role": "assistant", "content": m.content})
    client = AsyncOpenAI(api_key=user.get("openai_api_key") or settings.openai_api_key, timeout=60.0)
    return messages, client


async def _answer_tool_calls(
    calls: list[dict[str, str]], messages: list[ChatCompletionMessageParam], user: dict, db: Any, tickers: list[str]
) -> None:
    """Append the assistant's tool calls and each tool's result to the conversation."""
    messages.append({"role": "assistant", "content": None, "tool_calls": [
        {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}} for c in calls
    ]})
    for c in calls:
        try:
            args = json.loads(c["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {}
        result = await _run_tool(c["name"], args, user, db)
        if c["name"] == "stock_snapshot" and "stock" in result:
            tickers.append(result["stock"]["ticker"])  # the listing actually looked up
        messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(result, default=str)})


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user: CurrentUser, db: DBSession, redis: RedisClient) -> ChatResponse:
    """One assistant turn; the client sends the whole conversation each time (nothing is stored)."""
    messages, client = await _start(request, current_user, redis)
    tickers: list[str] = []
    try:
        for _ in range(MAX_TOOL_ROUNDS + 1):
            resp = await client.chat.completions.create(
                model=settings.openai_model, messages=messages, tools=TOOLS, temperature=0.2,
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return ChatResponse(reply=msg.content or "", tickers=tickers)
            calls = [{"id": c.id, "name": c.function.name, "arguments": c.function.arguments}
                     for c in msg.tool_calls if c.type == "function"]  # the only kind of tool offered
            await _answer_tool_calls(calls, messages, current_user, db, tickers)
    except OpenAIError as e:
        logger.error(f"Chat LLM call failed: {e}")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The assistant is unavailable right now") from e
    raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The assistant needed too many lookups; ask a narrower question")


@router.post("/stream")
async def chat_stream(
    request: ChatRequest, current_user: CurrentUser, db: DBSession, redis: RedisClient
) -> StreamingResponse:
    """Same turn as POST /, but the answer arrives as plain text while the model writes it."""
    messages, client = await _start(request, current_user, redis)  # errors here are normal HTTP errors

    async def answer() -> AsyncIterator[str]:
        tickers: list[str] = []
        try:
            for _ in range(MAX_TOOL_ROUNDS + 1):
                stream = await client.chat.completions.create(
                    model=settings.openai_model, messages=messages, tools=TOOLS, temperature=0.2, stream=True,
                )
                calls: dict[int, dict] = {}
                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue
                    if delta.content:
                        yield delta.content
                    for tc in delta.tool_calls or []:  # a call's id, name and arguments arrive in pieces
                        call = calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                        call["id"] = tc.id or call["id"]
                        call["name"] += (tc.function.name or "") if tc.function else ""
                        call["arguments"] += (tc.function.arguments or "") if tc.function else ""
                if not calls:
                    return
                await _answer_tool_calls(list(calls.values()), messages, current_user, db, tickers)
            yield "\n\nI needed too many lookups for that; please ask a narrower question."
        except OpenAIError as e:  # headers are already sent, so the failure goes into the text
            logger.error(f"Chat LLM stream failed: {e}")
            yield "\n\nThe assistant is unavailable right now. Please try again."

    return StreamingResponse(answer(), media_type="text/plain; charset=utf-8")
