import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { useQueries, useQuery } from "@tanstack/react-query"
import { Plus, X } from "lucide-react"
import PageHeader from "@/components/PageHeader"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { Button } from "@/components/ui/button"
import WatchlistButton from "@/components/WatchlistButton"
import { useQuickTickers } from "@/hooks/useStockUniverse"
import { cn } from "@/lib/utils"
import apiClient, { resolveTicker } from "@/lib/api"
import type { RiskAnalysis } from "@/types/api"

const MAX_TICKERS = 4

interface SimulationSnapshot {
    asset_volatilities: Record<string, number>
    correlation_matrix: Record<string, Record<string, number>>
    estimated_tickers: string[]
}

const fmt = (v: number | undefined, digits = 1, suffix = "") => (v === undefined ? "—" : `${v.toFixed(digits)}${suffix}`)
const pct = (fraction: number | undefined) => fmt(fraction === undefined ? undefined : fraction * 100, 1, "%")

/** Correlation cell tint: red for strong co-movement, green for diversifying. */
const corrClass = (c: number) =>
    c >= 0.7 ? "bg-q-risk-high/15 text-q-risk-high" : c >= 0.4 ? "bg-amber-500/15 text-amber-600 dark:text-amber-400" : "bg-q-risk-low/15 text-q-risk-low"

export default function Compare() {
    const [searchParams, setSearchParams] = useSearchParams()
    const tickers = [...new Set((searchParams.get("tickers") ?? "").split(",").map(t => t.trim().toUpperCase()).filter(Boolean))].slice(0, MAX_TICKERS)
    const [input, setInput] = useState("")
    const quickTickers = useQuickTickers()

    const setTickers = (next: string[]) => setSearchParams(next.length ? { tickers: next.join(",") } : {})
    const addTicker = async (t: string) => {
        if (!t.trim()) return
        const sym = (await resolveTicker(t)) ?? t.trim().toUpperCase() // "ITC" -> ITC.NS
        if (!tickers.includes(sym) && tickers.length < MAX_TICKERS) setTickers([...tickers, sym])
        setInput("")
    }

    const risks = useQueries({
        queries: tickers.map(t => ({
            queryKey: ["stockRisk", t],
            queryFn: async () => (await apiClient.get<RiskAnalysis>(`/stocks/${t}/risk`)).data,
        })),
    })

    // Equal-weight simulation gives real pairwise correlations and volatilities from price history
    const { data: sim, isLoading: loadingSim } = useQuery({
        queryKey: ["compareSim", tickers],
        queryFn: async () =>
            (await apiClient.post<SimulationSnapshot>("/portfolio/simulate", {
                stocks: tickers.map(t => ({ ticker: t, weight: 1 / tickers.length })),
                initial_investment: 100000,
                time_horizon_months: 12,
            })).data,
        enabled: tickers.length >= 2,
    })

    const rows: { label: string; value: (i: number, t: string) => string; text?: boolean }[] = [
        { label: "Risk score", value: i => fmt(risks[i].data?.overall_risk_score) },
        { label: "Risk level", value: i => risks[i].data?.risk_level ?? "—", text: true },
        { label: "Beta (1.00 moves with the market)", value: i => fmt(risks[i].data?.factor_sensitivities?.market_beta, 2) },
        { label: "Yearly volatility", value: (_, t) => pct(sim?.asset_volatilities?.[t]) },
        { label: "Worst fall in the past year", value: i => pct(risks[i].data?.max_drawdown) },
        { label: "Volatility score", value: i => fmt(risks[i].data?.components?.volatility_score) },
        { label: "Debt score", value: i => fmt(risks[i].data?.components?.leverage_score) },
        { label: "Valuation score", value: i => fmt(risks[i].data?.components?.valuation_risk_score) },
        { label: "Earnings instability score", value: i => fmt(risks[i].data?.components?.earnings_stability_score) },
        {
            label: "Worst modelled shock",
            value: i => {
                const sc = risks[i].data?.scenarios ?? []
                return sc.length ? `${Math.min(...sc.map(s => s.impact_pct)).toFixed(1)}%` : "—"
            },
        },
    ]

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto">
            <PageHeader title="Compare" description={`Risk side by side for up to ${MAX_TICKERS} stocks, and how closely they move together.`} />

            <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                    {tickers.map(t => (
                        <span key={t} className="flex items-center gap-1 rounded-full border border-border bg-card px-3 py-1 text-sm font-medium">
                            {t}
                            <button type="button" aria-label={`Remove ${t}`} onClick={() => setTickers(tickers.filter(x => x !== t))}
                                className="text-muted-foreground hover:text-foreground">
                                <X className="size-3.5" />
                            </button>
                        </span>
                    ))}
                    {tickers.length < MAX_TICKERS && (
                        <form onSubmit={e => { e.preventDefault(); void addTicker(input) }} className="flex gap-1.5">
                            <input value={input} onChange={e => setInput(e.target.value)} placeholder="Add a stock, e.g. ITC" aria-label="Add ticker"
                                className="bg-background border border-border text-sm px-2 py-1.5 rounded-md w-44 outline-none focus:border-primary" />
                            <Button type="submit" size="sm" aria-label="Add" className="gap-1"><Plus className="size-4" /> Add</Button>
                        </form>
                    )}
                </div>
                {tickers.length < MAX_TICKERS && (
                    <div className="flex flex-wrap gap-1.5">
                        {quickTickers.filter(t => !tickers.includes(t)).slice(0, 16).map(t => (
                            <button key={t} type="button" onClick={() => void addTicker(t)} aria-label={`Add ${t}`}
                                className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground">
                                + {t}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            {tickers.length < 2 ? (
                <Panel id="compare-empty" title="Pick stocks"><PanelMessage>Pick at least two stocks to compare.</PanelMessage></Panel>
            ) : (
                <>
                    <Panel id="compare-risk" title="Risk side by side" description="Scores run 0 (lowest risk) to 100 (highest)">
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="text-xs text-muted-foreground">
                                        <th scope="col" className="text-left px-4 py-2 font-medium">Measure</th>
                                        {tickers.map((t, i) => (
                                            <th key={t} scope="col" className="text-right px-4 py-2 font-medium">
                                                <span className="inline-flex items-center gap-1">
                                                    <Link to={`/research/${t}`} className="text-foreground hover:text-primary">{t}</Link>
                                                    <WatchlistButton ticker={t} />
                                                </span>
                                                {risks[i].isLoading && <span className="block text-xs font-normal">Loading…</span>}
                                                {risks[i].isError && <span className="block text-xs font-normal text-q-risk-high">Couldn't load</span>}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-border">
                                    {rows.map(row => (
                                        <tr key={row.label}>
                                            <th scope="row" className="text-left px-4 py-2 font-normal text-muted-foreground">{row.label}</th>
                                            {tickers.map((t, i) => (
                                                <td key={t} className={cn("text-right px-4 py-2 text-foreground", !row.text && "font-mono tabular-nums")}>{row.value(i, t)}</td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </Panel>

                    <Panel id="compare-corr" title="How they move together"
                        description="1.00 means they move exactly together. Red (0.70 and up) moves together, amber is in between, green (below 0.40) helps diversify. From one year of daily returns.">
                        {loadingSim ? <PanelSkeleton rows={tickers.length} /> : !sim ? <PanelMessage alert>Couldn't work out how they move together.</PanelMessage> : (
                            <div className="p-4 overflow-x-auto">
                                <table className="text-sm">
                                    <thead>
                                        <tr>
                                            <td />
                                            {tickers.map(t => <th key={t} scope="col" className="px-3 py-1 text-xs font-medium text-muted-foreground">{t}</th>)}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {tickers.map(a => (
                                            <tr key={a}>
                                                <th scope="row" className="pr-3 py-1 text-left text-xs font-medium text-muted-foreground">{a}</th>
                                                {tickers.map(b => {
                                                    const c = sim.correlation_matrix?.[a]?.[b]
                                                    return (
                                                        <td key={b} className={cn("px-3 py-1.5 text-center font-mono tabular-nums rounded-sm", c !== undefined && a !== b && corrClass(c))}>
                                                            {c === undefined ? "—" : c.toFixed(2)}
                                                        </td>
                                                    )
                                                })}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                                {sim.estimated_tickers?.length > 0 && (
                                    <p role="note" className="mt-3 text-xs text-muted-foreground">
                                        No price history for {sim.estimated_tickers.join(", ")}, so their figures are typical values for that kind of asset.
                                    </p>
                                )}
                            </div>
                        )}
                    </Panel>
                </>
            )}
        </div>
    )
}
