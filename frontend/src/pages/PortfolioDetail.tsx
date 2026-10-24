import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, Play } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { cn, timeAgo } from "@/lib/utils"
import { usePortfolioPerformance, usePortfolios, type CurrencyTotals } from "@/hooks/usePortfolios"

const SYMBOL = { USD: "$", INR: "₹" } as const

const money = (v: number | null | undefined, currency: "USD" | "INR", signed = false) => {
    if (v === null || v === undefined) return "—"
    const sign = signed && v > 0 ? "+" : v < 0 ? "-" : ""
    return `${sign}${SYMBOL[currency]}${Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`)
const tone = (v: number | null | undefined) => (!v ? "text-muted-foreground" : v > 0 ? "text-q-risk-low" : "text-q-risk-high")

function TotalsCard({ t }: { t: CurrencyTotals }) {
    const sectors = Object.entries(t.sector_allocation).sort((a, b) => b[1] - a[1])
    return (
        <Card className="bg-q-surface border-q-border shadow-none">
            <CardHeader className="p-4 pb-2">
                <CardTitle className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{t.currency} holdings</CardTitle>
            </CardHeader>
            <CardContent className="p-4 pt-0 space-y-3">
                <div className="text-2xl font-black font-mono text-foreground">{money(t.market_value, t.currency)}</div>
                <dl className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                        <dt className="text-muted-foreground">Unrealized P&amp;L</dt>
                        <dd className={cn("font-mono font-bold", tone(t.unrealized_pnl))}>
                            {money(t.unrealized_pnl, t.currency, true)} <span className="text-[10px]">{pct(t.unrealized_pnl_pct)}</span>
                        </dd>
                    </div>
                    <div>
                        <dt className="text-muted-foreground">Today</dt>
                        <dd className={cn("font-mono font-bold", tone(t.day_change))}>{money(t.day_change, t.currency, true)}</dd>
                    </div>
                </dl>
                {sectors.length > 0 && (
                    <div className="space-y-1.5 pt-2 border-t border-q-border/50">
                        <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Sector allocation</p>
                        {sectors.map(([sector, share]) => (
                            <div key={sector} className="text-[11px]">
                                <div className="flex justify-between"><span>{sector}</span><span className="font-mono">{share.toFixed(1)}%</span></div>
                                <div className="h-1.5 bg-q-border rounded-full overflow-hidden">
                                    <div className="h-full bg-primary" style={{ width: `${share}%` }} />
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

export default function PortfolioDetail() {
    const id = Number(useParams().id)
    const navigate = useNavigate()
    const { data: portfolios = [] } = usePortfolios()
    const portfolio = portfolios.find(p => p.id === id)
    const { data: perf, isLoading, isError } = usePortfolioPerformance(id)

    return (
        <div className="p-6 space-y-6 bg-background min-h-full">
            <div className="flex flex-wrap items-end justify-between gap-3 pb-4 border-b border-border">
                <div>
                    <Link to="/portfolios" className="text-[11px] text-muted-foreground hover:text-foreground flex items-center gap-1 mb-2">
                        <ArrowLeft className="size-3" /> All portfolios
                    </Link>
                    <h1 className="text-2xl font-black tracking-tight text-foreground">{portfolio?.name ?? "Portfolio"}</h1>
                    {perf?.prices_as_of && (
                        <p className="text-[10px] text-muted-foreground uppercase tracking-widest mt-1">Prices as of {timeAgo(perf.prices_as_of)}</p>
                    )}
                </div>
                <Button onClick={() => navigate(`/simulation?portfolio=${id}`)} className="gap-1">
                    <Play className="size-3" /> Simulate
                </Button>
            </div>

            {isLoading && <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground">Valuing holdings…</p>}
            {isError && <p role="alert" className="text-xs text-q-risk-high">Could not load this portfolio.</p>}

            {perf && perf.holdings.length === 0 && (
                <div className="border border-dashed border-border p-10 text-center space-y-2">
                    <p className="text-sm font-bold text-foreground">No share counts yet</p>
                    <p className="text-xs text-muted-foreground">
                        Edit the portfolio and add shares and average cost to see its value and P&amp;L.
                    </p>
                </div>
            )}

            {perf && perf.totals.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {perf.totals.map(t => <TotalsCard key={t.currency} t={t} />)}
                </div>
            )}

            {perf && perf.holdings.length > 0 && (
                <Card className="bg-q-surface border-q-border shadow-none overflow-x-auto">
                    <table className="w-full text-xs">
                        <thead>
                            <tr className="border-b border-q-border text-[10px] uppercase tracking-wider text-muted-foreground">
                                {["Holding", "Shares", "Avg cost", "Price", "Market value", "Weight", "Today", "Unrealized P&L"].map((h, i) => (
                                    <th key={h} scope="col" className={cn("px-4 py-3 font-bold", i === 0 ? "text-left" : "text-right")}>{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {perf.holdings.map(h => (
                                <tr key={h.ticker} className="border-b border-q-border/40 hover:bg-primary/5">
                                    <th scope="row" className="px-4 py-2.5 text-left">
                                        <Link to={`/research/${h.ticker}`} className="font-mono font-black text-foreground hover:text-primary">{h.ticker}</Link>
                                        <span className="block text-[10px] text-muted-foreground font-normal">{h.name}{h.sector ? ` · ${h.sector}` : ""}</span>
                                    </th>
                                    <td className="px-4 py-2.5 text-right font-mono">{h.shares.toLocaleString()}</td>
                                    <td className="px-4 py-2.5 text-right font-mono">{h.avg_cost ? money(h.avg_cost, h.currency) : "—"}</td>
                                    <td className="px-4 py-2.5 text-right font-mono">{money(h.price, h.currency)}</td>
                                    <td className="px-4 py-2.5 text-right font-mono font-bold">{money(h.market_value, h.currency)}</td>
                                    <td className="px-4 py-2.5 text-right font-mono">{h.weight_by_value === null ? "—" : `${h.weight_by_value.toFixed(1)}%`}</td>
                                    <td className={cn("px-4 py-2.5 text-right font-mono", tone(h.day_change))}>{money(h.day_change, h.currency, true)}</td>
                                    <td className={cn("px-4 py-2.5 text-right font-mono font-bold", tone(h.unrealized_pnl))}>
                                        {money(h.unrealized_pnl, h.currency, true)}
                                        <span className="block text-[10px] font-normal">{pct(h.unrealized_pnl_pct)}</span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </Card>
            )}

            {perf && perf.weight_only_tickers.length > 0 && (
                <p className="text-[11px] text-muted-foreground">
                    Not valued (weight only, no share count): {perf.weight_only_tickers.join(", ")}
                </p>
            )}
        </div>
    )
}
