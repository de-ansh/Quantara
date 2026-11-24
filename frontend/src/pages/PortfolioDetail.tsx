import { useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { ArrowDown, ArrowLeft, ArrowUp, Play } from "lucide-react"
import { Button } from "@/components/ui/button"
import PageHeader from "@/components/PageHeader"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { cn, timeAgo } from "@/lib/utils"
import PortfolioTotals from "@/components/PortfolioTotals"
import BalanceCheck from "@/components/BalanceCheck"
import { staleNav } from "@/lib/format"
import { usePortfolioPerformance, usePortfolios, type CurrencyTotals, type HoldingPerformance } from "@/hooks/usePortfolios"
import { dayPct, money, pct, tone } from "@/lib/money"

function Totals({ t }: { t: CurrencyTotals }) {
    const sectors = Object.entries(t.sector_allocation ?? {}).sort((a, b) => b[1] - a[1])
    return (
        <Panel id={`totals-${t.currency}`} title={`${t.currency} holdings`}>
            <div className="p-4 space-y-4">
                <PortfolioTotals totals={[t]} size="lg" />
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

type SortKey = "name" | "value" | "today" | "gain"
// Columns, and the sort each header offers (null: not sortable)
const COLUMNS: [string, SortKey | null][] = [["Holding", "name"], ["Shares / units", null], ["Avg cost", null], ["Price / NAV", null],
    ["Value", "value"], ["Weight", null], ["Today", "today"], ["Gain or loss", "gain"]]
const SORT_VALUE: Record<SortKey, (h: HoldingPerformance) => number | string | null> = {
    name: h => (h.kind === "fund" ? h.name : h.ticker),
    value: h => h.market_value,
    today: h => dayPct(h.market_value, h.day_change),
    gain: h => h.unrealized_pnl_pct,
}

/** Holdings in the chosen order; unknown values (no price, no cost) always last. */
function sortHoldings(holdings: HoldingPerformance[], key: SortKey, ascending: boolean) {
    return [...holdings].sort((a, b) => {
        const x = SORT_VALUE[key](a), y = SORT_VALUE[key](b)
        if (x === null || y === null) return x === null ? (y === null ? 0 : 1) : -1
        const order = typeof x === "string" ? x.localeCompare(String(y)) : x - (y as number)
        return ascending ? order : -order
    })
}

export default function PortfolioDetail() {
    const id = Number(useParams().id)
    const navigate = useNavigate()
    const { data: portfolios = [] } = usePortfolios()
    const portfolio = portfolios.find(p => p.id === id)
    const { data: perf, isLoading, isError } = usePortfolioPerformance(id)
    // Worst first: what's losing money is what needs a look
    const [sort, setSort] = useState<{ key: SortKey; ascending: boolean }>({ key: "gain", ascending: true })
    const sortBy = (key: SortKey) => setSort(s => ({ key, ascending: s.key === key ? !s.ascending : key === "name" || key === "gain" || key === "today" }))

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
                        {perf.totals.length > 0 && <BalanceCheck id={id} />}
                        <Panel id="holdings" title={`${perf.holdings.length} holding${perf.holdings.length === 1 ? "" : "s"}`}
                            description={perf.weight_only_tickers.length > 0 ? `Not valued (weight only, no share count): ${perf.weight_only_tickers.join(", ")}` : undefined}>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="text-xs text-muted-foreground">
                                            {COLUMNS.map(([h, key], i) => (
                                                <th key={h} scope="col" className={cn("px-4 py-2 font-medium whitespace-nowrap", i === 0 ? "text-left" : "text-right")}
                                                    aria-sort={key && sort.key === key ? (sort.ascending ? "ascending" : "descending") : undefined}>
                                                    {key ? (
                                                        <button type="button" onClick={() => sortBy(key)} className="inline-flex items-center gap-1 hover:text-foreground">
                                                            {h}
                                                            {sort.key === key && (sort.ascending ? <ArrowUp className="size-3" aria-hidden="true" /> : <ArrowDown className="size-3" aria-hidden="true" />)}
                                                        </button>
                                                    ) : h}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border">
                                        {sortHoldings(perf.holdings, sort.key, sort.ascending).map(h => (
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
                                                <td className={cn("px-4 py-2 text-right font-mono tabular-nums whitespace-nowrap", tone(h.day_change))}>
                                                    {money(h.day_change, h.currency, true)}
                                                    <span className="block text-xs">{pct(dayPct(h.market_value, h.day_change))}</span>
                                                    {staleNav(h.price_date) && <span className="block text-[11px] font-sans text-muted-foreground">{staleNav(h.price_date)}</span>}
                                                </td>
                                                <td className={cn("px-4 py-2 text-right font-mono tabular-nums whitespace-nowrap", tone(h.unrealized_pnl))}>
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
