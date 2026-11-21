import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowLeft, Play } from "lucide-react"
import { Button } from "@/components/ui/button"
import PageHeader from "@/components/PageHeader"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { cn, timeAgo } from "@/lib/utils"
import { usePortfolioPerformance, usePortfolios, type CurrencyTotals } from "@/hooks/usePortfolios"
import { money, pct, tone } from "@/lib/money"

function Totals({ t }: { t: CurrencyTotals }) {
    const sectors = Object.entries(t.sector_allocation ?? {}).sort((a, b) => b[1] - a[1])
    return (
        <Panel id={`totals-${t.currency}`} title={`${t.currency} holdings`}>
            <div className="p-4 space-y-4">
                <dl className="grid grid-cols-3 gap-3">
                    <div>
                        <dt className="text-xs text-muted-foreground">Value now</dt>
                        <dd className="text-xl font-semibold font-mono tabular-nums text-foreground">{money(t.market_value, t.currency)}</dd>
                    </div>
                    <div>
                        <dt className="text-xs text-muted-foreground">Gain or loss so far</dt>
                        <dd className={cn("font-mono tabular-nums", tone(t.unrealized_pnl))}>
                            {money(t.unrealized_pnl, t.currency, true)} <span className="text-xs">({pct(t.unrealized_pnl_pct)})</span>
                        </dd>
                    </div>
                    <div>
                        <dt className="text-xs text-muted-foreground">Today</dt>
                        <dd className={cn("font-mono tabular-nums", tone(t.day_change))}>
                            {money(t.day_change, t.currency, true)}
                        </dd>
                    </div>
                </dl>
                {sectors.length > 0 && (
                    <div className="space-y-2 pt-3 border-t border-border">
                        <p className="text-xs font-medium text-muted-foreground">By sector</p>
                        {sectors.map(([sector, share]) => (
                            <div key={sector} className="text-sm">
                                <div className="flex justify-between"><span>{sector}</span><span className="font-mono tabular-nums">{share.toFixed(1)}%</span></div>
                                <div className="h-1.5 bg-muted rounded-full overflow-hidden" aria-hidden="true">
                                    <div className="h-full bg-primary" style={{ width: `${share}%` }} />
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </Panel>
    )
}

const COLUMNS = ["Holding", "Shares / units", "Avg cost", "Price / NAV", "Value", "Weight", "Today", "Gain or loss"]

export default function PortfolioDetail() {
    const id = Number(useParams().id)
    const navigate = useNavigate()
    const { data: portfolios = [] } = usePortfolios()
    const portfolio = portfolios.find(p => p.id === id)
    const { data: perf, isLoading, isError } = usePortfolioPerformance(id)

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto">
            <Link to="/portfolios" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
                <ArrowLeft className="size-4" /> All portfolios
            </Link>
            <PageHeader
                title={portfolio?.name ?? "Portfolio"}
                description={perf?.prices_as_of ? `Value and gain or loss at prices from ${timeAgo(perf.prices_as_of)}.` : "Value and gain or loss of each holding."}
                actions={<Button onClick={() => navigate(`/simulation?portfolio=${id}`)} className="gap-1.5"><Play className="size-4" /> Simulate</Button>}
            />

            {isLoading ? <Panel id="holdings" title="Holdings"><PanelSkeleton rows={5} /></Panel>
                : isError ? <Panel id="holdings" title="Holdings"><PanelMessage alert>Couldn't load this portfolio.</PanelMessage></Panel>
                : perf && perf.holdings.length === 0 ? (
                    <Panel id="holdings" title="Holdings">
                        <PanelMessage>No share counts yet. Edit the portfolio and add shares and average cost to see its value and gain or loss.</PanelMessage>
                    </Panel>
                ) : perf && (
                    <>
                        {perf.totals.length > 0 && (
                            <div className={cn("grid grid-cols-1 gap-6", perf.totals.length > 1 && "md:grid-cols-2")}>
                                {perf.totals.map(t => <Totals key={t.currency} t={t} />)}
                            </div>
                        )}
                        <Panel id="holdings" title={`${perf.holdings.length} holding${perf.holdings.length === 1 ? "" : "s"}`}
                            description={perf.weight_only_tickers.length > 0 ? `Not valued (weight only, no share count): ${perf.weight_only_tickers.join(", ")}` : undefined}>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="text-xs text-muted-foreground">
                                            {COLUMNS.map((h, i) => (
                                                <th key={h} scope="col" className={cn("px-4 py-2 font-medium whitespace-nowrap", i === 0 ? "text-left" : "text-right")}>{h}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border">
                                        {perf.holdings.map(h => (
                                            <tr key={`${h.kind}-${h.ticker}`} className="hover:bg-muted/40">
                                                <th scope="row" className="px-4 py-2 text-left font-normal">
                                                    {h.kind === "fund" ? (
                                                        <span className="font-medium text-foreground">{h.name}</span>
                                                    ) : (
                                                        <Link to={`/research/${h.ticker}`} className="font-medium text-foreground hover:text-primary">{h.ticker}</Link>
                                                    )}
                                                    <span className="block text-xs text-muted-foreground">
                                                        {h.kind === "fund" ? `Mutual fund${h.sector ? ` · ${h.sector}` : ""}` : `${h.name}${h.sector ? ` · ${h.sector}` : ""}`}
                                                    </span>
                                                </th>
                                                <td className="px-4 py-2 text-right font-mono tabular-nums">{h.shares.toLocaleString()}</td>
                                                <td className="px-4 py-2 text-right font-mono tabular-nums">{h.avg_cost ? money(h.avg_cost, h.currency) : "—"}</td>
                                                <td className="px-4 py-2 text-right font-mono tabular-nums">{money(h.price, h.currency)}</td>
                                                <td className="px-4 py-2 text-right font-mono tabular-nums font-medium">{money(h.market_value, h.currency)}</td>
                                                <td className="px-4 py-2 text-right font-mono tabular-nums">{h.weight_by_value === null ? "—" : `${h.weight_by_value.toFixed(1)}%`}</td>
                                                <td className={cn("px-4 py-2 text-right font-mono tabular-nums", tone(h.day_change))}>{money(h.day_change, h.currency, true)}</td>
                                                <td className={cn("px-4 py-2 text-right font-mono tabular-nums", tone(h.unrealized_pnl))}>
                                                    {money(h.unrealized_pnl, h.currency, true)}
                                                    <span className="block text-xs">{pct(h.unrealized_pnl_pct)}</span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </Panel>
                    </>
                )}
        </div>
    )
}
