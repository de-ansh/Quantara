import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { useQueries, useQuery } from "@tanstack/react-query"
import { Columns3, Plus, X } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import WatchlistButton from "@/components/WatchlistButton"
import { useQuickTickers } from "@/hooks/useStockUniverse"
import { cn } from "@/lib/utils"
import apiClient from "@/lib/api"
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
    c >= 0.7 ? "bg-q-risk-high/20 text-q-risk-high" : c >= 0.4 ? "bg-amber-500/15 text-amber-400" : "bg-q-risk-low/15 text-q-risk-low"

export default function Compare() {
    const [searchParams, setSearchParams] = useSearchParams()
    const tickers = [...new Set((searchParams.get("tickers") ?? "").split(",").map(t => t.trim().toUpperCase()).filter(Boolean))].slice(0, MAX_TICKERS)
    const [input, setInput] = useState("")
    const quickTickers = useQuickTickers()

    const setTickers = (next: string[]) => setSearchParams(next.length ? { tickers: next.join(",") } : {})
    const addTicker = (t: string) => {
        const sym = t.trim().toUpperCase()
        if (sym && !tickers.includes(sym) && tickers.length < MAX_TICKERS) setTickers([...tickers, sym])
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

    const rows: { label: string; value: (i: number, t: string) => string }[] = [
        { label: "Risk score", value: i => fmt(risks[i].data?.overall_risk_score) },
        { label: "Risk level", value: i => risks[i].data?.risk_level ?? "—" },
        { label: "Beta", value: i => fmt(risks[i].data?.factor_sensitivities.market_beta, 2) },
        { label: "Annualized volatility", value: (_, t) => pct(sim?.asset_volatilities[t]) },
        { label: "Max drawdown", value: i => pct(risks[i].data?.max_drawdown) },
        { label: "Volatility score", value: i => fmt(risks[i].data?.components.volatility_score) },
        { label: "Leverage score", value: i => fmt(risks[i].data?.components.leverage_score) },
        { label: "Valuation risk", value: i => fmt(risks[i].data?.components.valuation_risk_score) },
        { label: "Earnings stability", value: i => fmt(risks[i].data?.components.earnings_stability_score) },
        {
            label: "Worst stress scenario",
            value: i => {
                const sc = risks[i].data?.scenarios ?? []
                return sc.length ? `${Math.min(...sc.map(s => s.impact_pct)).toFixed(1)}%` : "—"
            },
        },
    ]

    return (
        <div className="p-6 space-y-6 bg-background min-h-full">
            <div className="pb-4 border-b border-border">
                <h1 className="text-2xl font-black uppercase tracking-tight flex items-center gap-2 text-foreground">
                    <Columns3 className="size-6 text-primary" /> Compare Stocks
                </h1>
                <p className="text-[10px] text-muted-foreground uppercase font-bold tracking-widest mt-1">
                    Risk profile and co-movement of up to {MAX_TICKERS} tickers
                </p>
            </div>

            {/* Picker */}
            <div className="flex flex-wrap items-center gap-2">
                {tickers.map(t => (
                    <span key={t} className="flex items-center gap-1 border border-border bg-card px-2 py-1 rounded-sm font-mono text-xs font-bold">
                        {t}
                        <button type="button" aria-label={`Remove ${t}`} onClick={() => setTickers(tickers.filter(x => x !== t))}
                            className="text-muted-foreground hover:text-foreground">
                            <X className="size-3" />
                        </button>
                    </span>
                ))}
                {tickers.length < MAX_TICKERS && (
                    <form onSubmit={e => { e.preventDefault(); addTicker(input) }} className="flex gap-1">
                        <input value={input} onChange={e => setInput(e.target.value)} placeholder="Add ticker" aria-label="Add ticker"
                            className="bg-background border border-border text-xs px-2 py-1 rounded-sm font-mono uppercase w-28 outline-none focus:border-primary" />
                        <Button type="submit" size="sm" className="h-7 px-2" aria-label="Add"><Plus className="size-3" /></Button>
                    </form>
                )}
            </div>
            {tickers.length < MAX_TICKERS && (
                <div className="flex flex-wrap gap-1">
                    {quickTickers.filter(t => !tickers.includes(t)).slice(0, 16).map(t => (
                        <button key={t} type="button" onClick={() => addTicker(t)}
                            className="text-[10px] font-mono font-bold px-1.5 py-0.5 bg-muted/50 hover:bg-muted text-muted-foreground hover:text-foreground border border-border rounded-sm">
                            +{t}
                        </button>
                    ))}
                </div>
            )}

            {tickers.length < 2 ? (
                <p className="border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
                    Pick at least two tickers to compare.
                </p>
            ) : (
                <>
                    <Card className="bg-q-surface border-q-border shadow-none overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-q-border">
                                    <th className="text-left px-4 py-3 text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Metric</th>
                                    {tickers.map((t, i) => (
                                        <th key={t} scope="col" className="text-right px-4 py-3">
                                            <span className="inline-flex items-center gap-1">
                                                <Link to={`/research/${t}`} className="font-mono font-black text-foreground hover:text-primary">{t}</Link>
                                                <WatchlistButton ticker={t} />
                                            </span>
                                            {risks[i].isLoading && <span className="block text-[9px] text-muted-foreground font-normal">loading…</span>}
                                            {risks[i].isError && <span className="block text-[9px] text-q-risk-high font-normal">failed to load</span>}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map(row => (
                                    <tr key={row.label} className="border-b border-q-border/40">
                                        <th scope="row" className="text-left px-4 py-2.5 text-xs text-muted-foreground font-medium">{row.label}</th>
                                        {tickers.map((t, i) => (
                                            <td key={t} className="text-right px-4 py-2.5 font-mono text-foreground">{row.value(i, t)}</td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </Card>

                    <Card className="bg-q-surface border-q-border shadow-none">
                        <CardHeader className="p-4 border-b border-q-border">
                            <CardTitle className="text-xs font-bold uppercase tracking-wider">Correlation (1Y daily returns)</CardTitle>
                        </CardHeader>
                        <CardContent className="p-4 overflow-x-auto">
                            {loadingSim ? (
                                <p className="text-xs text-muted-foreground">Computing correlations…</p>
                            ) : !sim ? (
                                <p className="text-xs text-q-risk-high">Could not compute correlations.</p>
                            ) : (
                                <>
                                    <table className="text-xs font-mono">
                                        <thead>
                                            <tr>
                                                <th />
                                                {tickers.map(t => <th key={t} scope="col" className="px-3 py-1 text-muted-foreground">{t}</th>)}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {tickers.map(a => (
                                                <tr key={a}>
                                                    <th scope="row" className="pr-3 py-1 text-left text-muted-foreground">{a}</th>
                                                    {tickers.map(b => {
                                                        const c = sim.correlation_matrix[a]?.[b]
                                                        return (
                                                            <td key={b} className={cn("px-3 py-1.5 text-center rounded-sm", c !== undefined && a !== b && corrClass(c))}>
                                                                {c === undefined ? "—" : c.toFixed(2)}
                                                            </td>
                                                        )
                                                    })}
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                    {sim.estimated_tickers.length > 0 && (
                                        <p className="mt-3 text-[10px] text-amber-500 uppercase tracking-wider">
                                            No price history for {sim.estimated_tickers.join(", ")}: correlations involving them are asset-class estimates
                                        </p>
                                    )}
                                </>
                            )}
                        </CardContent>
                    </Card>
                </>
            )}
        </div>
    )
}
