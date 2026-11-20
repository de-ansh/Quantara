import { Link } from "react-router-dom"
import { Briefcase, CalendarClock } from "lucide-react"
import { cn } from "@/lib/utils"
import { money, pct, tone } from "@/lib/money"
import DayChange from "@/components/DayChange"
import { usePortfolioUpdates, type HoldingPerformance, type HoldingUpdate, type PortfolioUpdates } from "@/hooks/usePortfolios"

const TONE = { good: "bg-q-risk-low", bad: "bg-q-risk-high", neutral: "bg-muted-foreground" } as const

/** "20 Nov" from "2026-11-20", read as a calendar day (no time-zone shift). */
const shortDay = (iso: string) => {
    const [y, m, d] = iso.split("-").map(Number)
    return new Date(y, m - 1, d).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
}

/** Today's move as a percent of yesterday's value. */
const dayPct = (h: HoldingPerformance) =>
    h.day_change !== null && h.market_value !== null && h.market_value - h.day_change > 0
        ? (h.day_change / (h.market_value - h.day_change)) * 100
        : null

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

function PortfolioBlock({ p }: { p: PortfolioUpdates }) {
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
        <article aria-label={p.name} className="border-b border-q-border last:border-b-0">
            <div className="px-4 py-2.5 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 bg-background/30">
                <Link to={`/portfolios/${p.portfolio_id}`} className="text-sm font-bold text-foreground hover:text-primary">{p.name}</Link>
                <div className="flex flex-wrap gap-x-5 gap-y-1 text-[11px] font-mono">
                    {totals.map(t => (
                        <span key={t.currency} className="flex gap-3">
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
                <ul className="divide-y divide-q-border/40">
                    {rows.map(h => (
                        <li key={`${h.kind}-${h.ticker}`} className="px-4 py-2">
                            <div className="flex items-baseline justify-between gap-3">
                                {h.kind === "fund" ? (
                                    <span className="text-xs font-bold text-foreground truncate">{h.name}</span>
                                ) : (
                                    <Link to={`/research/${h.ticker}`} className="text-xs font-black font-mono text-foreground hover:text-primary truncate">
                                        {h.ticker} <span className="font-sans font-normal text-muted-foreground">{h.name !== h.ticker ? h.name : ""}</span>
                                    </Link>
                                )}
                                <span className="flex gap-3 text-[11px] font-mono shrink-0">
                                    <DayChange pct={dayPct(h)} />
                                    <span className="text-foreground">{money(h.market_value, h.currency)}</span>
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
            )}
        </article>
    )
}

/** Dashboard section: each portfolio's value today and what's new on every holding. */
export default function PortfolioUpdatesCard() {
    const { data: portfolios, isLoading, isError } = usePortfolioUpdates()
    if (!isLoading && !isError && portfolios?.length === 0) return null  // nothing saved yet: keep the dashboard as it was

    return (
        <section aria-labelledby="portfolio-updates-heading" className="bg-q-surface border border-q-border shrink-0 flex flex-col max-h-[45vh]">
            <div className="px-4 py-2 border-b border-q-border flex items-center justify-between shrink-0">
                <h2 id="portfolio-updates-heading" className="text-xs font-bold uppercase tracking-wider text-foreground flex items-center gap-2">
                    <Briefcase className="size-3.5 text-primary" /> Your portfolios
                </h2>
                <span className="text-[11px] text-muted-foreground">Last 7 days, and what's due in the next 14</span>
            </div>
            <div className="overflow-y-auto custom-scrollbar">
                {isLoading && <p className="px-4 py-3 text-[11px] text-muted-foreground">Valuing holdings…</p>}
                {isError && <p role="alert" className="px-4 py-3 text-[11px] text-q-risk-high">Couldn't load portfolio updates.</p>}
                {portfolios?.map(p => <PortfolioBlock key={p.portfolio_id} p={p} />)}
            </div>
        </section>
    )
}
