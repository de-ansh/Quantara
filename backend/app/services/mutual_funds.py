"""Mutual fund NAVs from AMFI, and matching a broker's fund rows to AMFI schemes.

AMFI publishes every scheme's latest NAV daily (NAVAll.txt) and a scheme master whose "NAV name" spells out
the plan and option. Both are free and need no key.
"""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.models.listed_security import ListedSecurity
from app.models.mutual_fund import MutualFund

logger = get_logger(__name__)

NAV_ALL = "https://portal.amfiindia.com/spages/NAVAll.txt"
SCHEME_MASTER = "https://portal.amfiindia.com/DownloadSchemeData_Po.aspx?mf=0"
FUNDS_MAX_AGE = timedelta(hours=6)  # NAVs come out once a day, in the evening
_ISIN = re.compile(r"^IN[A-Z0-9]{9}\d$")


@dataclass
class FundNav:
    name: str
    category: str | None
    isin: str | None
    isin_reinvest: str | None
    nav: float
    nav_date: date


def parse_nav_all(text: str) -> dict[int, FundNav]:
    """Scheme code -> NAV row. Section lines like "Open Ended Schemes(Equity Scheme - Mid Cap Fund)" set the category."""
    lines = text.lstrip("﻿").splitlines()
    header = [h.strip().lower() for h in lines[0].split(";")] if lines else []

    def col(prefix: str) -> int:
        return next((i for i, h in enumerate(header) if h.startswith(prefix)), -1)

    code_at, name_at, plan_at, option_at = col("scheme code"), col("scheme name"), col("plan"), col("option")
    nav_at, date_at, reinvest_at = col("net asset value"), col("date"), col("isin div reinvest")
    funds: dict[int, FundNav] = {}
    category: str | None = None
    for line in lines[1:]:
        cells = [c.strip() for c in line.split(";")]
        if len(cells) == 1:
            if m := re.search(r"Schemes?\s*\((.+)\)\s*$", cells[0]):
                category = m[1].strip()
            continue
        if min(code_at, name_at, nav_at, date_at) < 0 or not cells[code_at].isdigit() or len(cells) < len(header):
            continue
        try:
            nav = float(cells[nav_at])
            nav_date = datetime.strptime(cells[date_at], "%d-%b-%Y").date()
        except ValueError:  # "N.A." for schemes without a NAV today
            continue
        # Newer rows spell out plan and option in their own columns; older ones leave them blank
        parts = [cells[name_at]] + [cells[i] for i in (plan_at, option_at) if i >= 0 and cells[i]]
        isins = [c if _ISIN.match(c) else None for c in (cells[1], cells[reinvest_at] if reinvest_at >= 0 else "")]
        funds[int(cells[code_at])] = FundNav(" - ".join(parts), category, isins[0], isins[1], nav, nav_date)
    return funds


def parse_scheme_master(text: str) -> dict[int, str]:
    """Scheme code -> full NAV name ("Example Midcap Fund-Direct Plan-Growth Option")."""
    names: dict[int, str] = {}
    for row in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        code, name = (row.get("Code") or "").strip(), (row.get("Scheme NAV Name") or "").strip()
        if code.isdigit() and name:
            names[int(code)] = name
    return names


async def _download(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
            return (await client.get(url)).raise_for_status().text
    except httpx.HTTPError as e:
        logger.warning(f"AMFI download failed for {url}: {e}")
        return None


async def refresh_funds(db: AsyncSession, max_age: timedelta = FUNDS_MAX_AGE) -> int:
    """Reload every scheme's NAV unless that happened within `max_age`; returns how many rows changed."""
    newest = await db.scalar(select(func.max(MutualFund.updated_at)))
    if newest is not None and newest > utcnow() - max_age:
        return 0
    nav_text = await _download(NAV_ALL)
    if nav_text is None:
        return 0
    master = await _download(SCHEME_MASTER)
    # Without the master, NAVs still load; schemes with blank plan/option columns keep their short names
    names = parse_scheme_master(master) if master else {}
    navs = parse_nav_all(nav_text)
    if not navs:
        logger.warning("AMFI NAV file had no schemes; keeping the old NAVs")
        return 0

    existing = {f.scheme_code: f for f in (await db.execute(select(MutualFund))).scalars()}
    now = utcnow()
    for code, row in navs.items():
        fund = existing.get(code)
        if fund is None:
            fund = MutualFund(scheme_code=code, nav=row.nav, nav_date=row.nav_date)
            db.add(fund)
        elif fund.nav_date != row.nav_date:
            fund.prev_nav = fund.nav
        fund.name = names.get(code, row.name)[:255]
        fund.category = row.category[:150] if row.category else None
        fund.isin, fund.isin_reinvest = row.isin, row.isin_reinvest
        fund.nav, fund.nav_date, fund.updated_at = row.nav, row.nav_date, now
    await db.commit()
    logger.info(f"Refreshed NAVs for {len(navs)} mutual fund schemes")
    return len(navs)


_NOT_GROWTH = {"idcw", "dividend", "payout", "reinvestment", "bonus", "income", "distribution", "withdrawal"}
_NOISE = {"plan", "option", "direct", "regular", "growth", "fund"} | _NOT_GROWTH


def fund_key(name: str, unstated: str = "regular") -> tuple[str, str, str]:
    """(scheme words, plan, option), so "X Fund Direct Growth" (Groww) meets "X Fund - Direct Plan - Growth Option" (AMFI).

    unstated="direct" reads a name that names no plan or option as Direct Growth: Coin, Groww and other app
    platforms list only the bare scheme name and sell only direct plans, growth being the default option.
    """
    words = re.findall(r"[a-z0-9]+", name.lower().replace("&", " and "))
    plan = "direct" if "direct" in words else "regular" if "regular" in words else unstated
    if _NOT_GROWTH & set(words):
        option = "other"
    elif "growth" in words:
        option = "growth"
    else:
        option = "growth" if unstated == "direct" else "other"
    return "".join(w for w in words if w not in _NOISE), plan, option


async def match_funds(db: AsyncSession, rows: list[tuple[str | None, str | None]]) -> list[MutualFund | None]:
    """The scheme each (isin, name) row means, or None: unknown, ambiguous, or an exchange-listed ETF (a stock)."""
    if await db.scalar(select(MutualFund.scheme_code).limit(1)) is None:
        await refresh_funds(db, max_age=timedelta(0))
    funds = (await db.execute(select(MutualFund))).scalars().all()
    by_isin = {i: f for f in funds for i in (f.isin, f.isin_reinvest) if i}
    by_key: dict[tuple[str, str, str], list[MutualFund]] = {}
    for f in funds:
        by_key.setdefault(fund_key(f.name), []).append(f)
    isins = {i.upper() for i, _ in rows if i}
    listed = set((await db.execute(select(ListedSecurity.isin).where(ListedSecurity.isin.in_(isins)))).scalars())

    matches: list[MutualFund | None] = []
    for isin, name in rows:
        code = (isin or "").strip().upper()
        if code in listed:
            matches.append(None)
        elif code in by_isin:
            matches.append(by_isin[code])
        else:
            found = by_key.get(fund_key(name, unstated="direct"), []) if name else []
            matches.append(found[0] if len(found) == 1 else None)  # several: old duplicates, don't guess
    return matches
