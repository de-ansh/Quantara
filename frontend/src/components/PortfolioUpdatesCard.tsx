import { useState } from "react"
import { Link } from "react-router-dom"
import { CalendarClock } from "lucide-react"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { cn } from "@/lib/utils"
import { dayPct as movePct, money, pct, sumTotals, tone } from "@/lib/money"
import DayChange from "@/components/DayChange"
import PortfolioTotals from "@/components/PortfolioTotals"
import { shortDay, staleNav } from "@/lib/format"
import { usePortfolioUpdates, type HoldingPerformance, type HoldingUpdate, type PortfolioUpdates } from "@/hooks/usePortfolios"

const TONE = { good: "bg-q-risk-low", bad: "bg-q-risk-high", neutral: "bg-muted-foreground" } as const

const dayPct = (h: HoldingPerformance) => movePct(h.market_value, h.day_change)

function UpdateLine({ u }: { u: HoldingUpdate }) {
    return (
        <li className="flex items-start gap-2 text-[11px]">
            <span className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", TONE[u.tone])} aria-hidden="true" />
            <span className="font-mono text-muted-foreground shrink-0 w-12">{shortDay(u.day)}</span>
            <span className={cn("text-foreground", u.upcoming && "flex items-center gap-1")}>
                {u.upcoming && <CalendarClock className="size-3 text-primary" aria-label="Coming up" />}
                {u.text}
            </span>
        </li>
    )
}

const COLLAPSED = 6 // holdings shown before "Show all": the ones with news, then the biggest movers

function PortfolioBlock({ p }: { p: PortfolioUpdates }) {
    const [expanded, setExpanded] = useState(false)
    const { holdings, totals } = p.performance
    // Holdings with news first, then the biggest movers; tickers with news but no share count still show
    const rows = [...holdings]
    for (const ticker of Object.keys(p.updates)) {
        if (!rows.some(h => h.kind !== "fund" && h.ticker === ticker)) {
            rows.push({ kind: "stock", ticker, name: ticker, sector: null, currency: /\.(NS|BO)$/i.test(ticker) ? "INR" : "USD",
                shares: 0, avg_cost: 0, price: null, market_value: null, cost_value: 0, unrealized_pnl: null,
                unrealized_pnl_pct: null, day_change: null, weight_by_value: null })
        }
    }
    const news = (h: HoldingPerformance) => (h.kind === "fund" ? [] : p.updates[h.ticker] ?? [])
    rows.sort((a, b) => (news(b).length > 0 ? 1 : 0) - (news(a).length > 0 ? 1 : 0)
        || Math.abs(dayPct(b) ?? 0) - Math.abs(dayPct(a) ?? 0))
    const withNews = rows.filter(h => news(h).length).length

    return (
        <article aria-label={p.name} className="border-b border-border last:border-b-0">
            <div className="px-4 py-2.5 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 bg-muted/30">
                <Link to={`/portfolios/${p.portfolio_id}`} className="text-sm font-bold text-foreground hover:text-primary">{p.name}</Link>
                <div className="flex flex-wrap gap-x-5 gap-y-1 text-[11px] font-mono">
                    {totals.map(t => (
                        <span key={t.currency} className="flex flex-wrap gap-x-3 gap-y-0.5 [&>span]:whitespace-nowrap">
                            <span className="text-foreground font-bold">{money(t.market_value, t.currency)}</span>
                            <span className={tone(t.day_change)}>Today {money(t.day_change, t.currency, true)}</span>
                            <span className={tone(t.unrealized_pnl)}>P&amp;L {money(t.unrealized_pnl, t.currency, true)} ({pct(t.unrealized_pnl_pct)})</span>
                        </span>
                    ))}
                    <span className="text-muted-foreground">{withNews ? `${withNews} with news` : "No news this week"}</span>
                </div>
            </div>
            {rows.length === 0 ? (
                <p className="px-4 py-2 text-[11px] text-muted-foreground">Add share counts to this portfolio to track it here.</p>
            ) : (
                <>
                <div className="hidden sm:flex justify-end gap-3 px-4 pt-1.5 pb-1 text-[11px] text-muted-foreground border-b border-border">
                    <span className="w-14 text-right">Today</span>
                    <span className="w-24 text-right">Value</span>
                    <span className="w-16 text-right">Gain/loss</span>
                </div>
                <ul className="divide-y divide-border">
                    {(expanded ? rows : rows.slice(0, Math.max(COLLAPSED, withNews))).map(h => (
                        <li key={`${h.kind}-${h.ticker}`} className="px-4 py-2">
                            <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-1 sm:gap-3">
                                {h.kind === "fund" ? (
                                    <span className="text-sm font-medium text-foreground sm:truncate">
                                        {h.name}
                                        {staleNav(h.price_date) && <span className="ml-1.5 text-[11px] font-normal text-muted-foreground">{staleNav(h.price_date)}</span>}
                                    </span>
                                ) : (
                                    <Link to={`/research/${h.ticker}`} className="text-sm font-medium text-foreground hover:text-primary sm:truncate">
                                        {h.ticker} <span className="font-normal text-muted-foreground">{h.name !== h.ticker ? h.name : ""}</span>
                                    </Link>
                                )}
                                <span className="flex justify-end gap-3 text-xs font-mono tabular-nums shrink-0">
                                    <span className="w-14 text-right"><DayChange pct={dayPct(h)} /></span>
                                    <span className="w-24 text-right text-foreground">{money(h.market_value, h.currency)}</span>
                                    <span className={cn("w-16 text-right", tone(h.unrealized_pnl_pct))}>{pct(h.unrealized_pnl_pct)}</span>
                                </span>
                            </div>
                            {news(h).length > 0 && (
                                <ul className="mt-1.5 space-y-1 pl-1">
                                    {news(h).map((u, i) => <UpdateLine key={i} u={u} />)}
                                </ul>
                            )}
                        </li>
                    ))}
                </ul>
                {rows.length > Math.max(COLLAPSED, withNews) && (
                    <button type="button" onClick={() => setExpanded(e => !e)} aria-expanded={expanded}
                        className="w-full px-4 py-2 text-xs font-medium text-primary hover:bg-muted/40 text-left">
                        {expanded ? "Show fewer" : `Show all ${rows.length} holdings`}
                    </button>
                )}
                </>
            )}
        </article>
    )
}

/** Dashboard section: each portfolio's value today and what's new on every holding. */
export default function PortfolioUpdatesCard() {
    const { data: portfolios, isLoading, isError } = usePortfolioUpdates()
    if (!isLoading && !isError && portfolios?.length === 0) return null  // nothing saved yet: keep the dashboard as it was

    return (
        <Panel id="portfolio-updates" title="Your portfolios" description="Value today, and news on each holding: the last 7 days and what's due in the next 14"
            action={<Link to="/portfolios" className="text-xs font-medium text-primary hover:underline">Manage portfolios</Link>}>
            {isLoading ? <PanelSkeleton /> : isError ? <PanelMessage alert>Couldn't load portfolio updates.</PanelMessage> : (
                <>
                    {portfolios && portfolios.length > 1 && (
                        <section aria-label="All portfolios" className="px-4 py-3 border-b border-border">
                            <h3 className="mb-2 text-xs font-medium text-muted-foreground">All {portfolios.length} portfolios together</h3>
                            <PortfolioTotals totals={sumTotals(portfolios.map(p => p.performance.totals))} size="lg" />
                        </section>
                    )}
                    {portfolios?.map(p => <PortfolioBlock key={p.portfolio_id} p={p} />)}
                </>
            )}
        </Panel>
    )
}
