import { useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Download, RefreshCw, Search } from "lucide-react"
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import apiClient from "@/lib/api"
import { cn } from "@/lib/utils"
import { isIndianAsset } from "@/lib/currency"
import { exportToCsv } from "@/lib/export"
import { useQuickTickers } from "@/hooks/useStockUniverse"
import PageHeader from "@/components/PageHeader"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { Button } from "@/components/ui/button"
import type { RiskAnalysis, StockCorrelation, StressScenario } from "@/types/api"

const QUICK_TICKER_LIMIT = 12

// `input` names the entry in assumed_inputs that makes this factor an estimate
const FACTORS = [
    { key: "volatility", score: "volatility_score", name: "Price volatility", input: "price_history" },
    { key: "beta", score: "beta_score", name: "Market sensitivity (beta)", input: "beta" },
    { key: "leverage", score: "leverage_score", name: "Debt and leverage", input: "debt_to_equity" },
    { key: "earnings_stability", score: "earnings_stability_score", name: "Earnings instability", input: null },
    { key: "sector", score: "sector_risk_score", name: "Sector risk", input: "sector" },
    { key: "valuation", score: "valuation_risk_score", name: "Valuation risk", input: "pe_ratio" },
] as const

const SENSITIVITIES: [string, string][] = [
    ["market_beta", "Market"], ["interest_rate_beta", "Interest rates"], ["oil_beta", "Oil"],
    ["tech_momentum_beta", "Tech momentum"], ["credit_spread_beta", "Credit spreads"],
]

// Same bands the risk engine uses for Conservative / Moderate / Aggressive
const band = (v: number): "Low" | "Moderate" | "High" => (v <= 33.33 ? "Low" : v <= 66.67 ? "Moderate" : "High")
const BAND_TEXT = { Low: "text-q-risk-low", Moderate: "text-amber-600 dark:text-amber-400", High: "text-q-risk-high" }
const BAND_BAR = { Low: "bg-q-risk-low", Moderate: "bg-amber-500", High: "bg-q-risk-high" }
const LEVEL_TEXT: Record<string, string> = { Conservative: BAND_TEXT.Low, Moderate: BAND_TEXT.Moderate, Aggressive: BAND_TEXT.High }

const signed = (v: number, digits = 1) => `${v > 0 ? "+" : ""}${v.toFixed(digits)}`
const words = (s: string) => s.replace(/_/g, " ")

/** The factor contributing most to a scenario's impact ("oil_beta" -> "Oil"). */
const primaryDriver = (sc: StressScenario) => {
    const top = Object.entries(sc.factor_breakdown ?? {}).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))[0]
    if (!top) return "—"
    return SENSITIVITIES.find(([k]) => k === top[0])?.[1] ?? words(top[0].replace(/_beta$/, ""))
}

export default function Risk() {
    const universe = useQuickTickers()
    const { ticker: urlTicker } = useParams()
    const navigate = useNavigate()
    const [tickerInput, setTickerInput] = useState("")
    const activeTicker = (urlTicker || "NVDA").toUpperCase()

    const { data: riskData, isLoading, isFetching, isError, refetch: refetchRisk } = useQuery({
        queryKey: ["stockRisk", activeTicker],
        queryFn: async () => (await apiClient.get<RiskAnalysis>(`/stocks/${activeTicker}/risk`)).data,
    })
    const { data: corrData, isFetching: isFetchingCorr, refetch: refetchCorr } = useQuery({
        queryKey: ["stockCorrelation", activeTicker],
        queryFn: async () => (await apiClient.get<StockCorrelation>(`/stocks/${activeTicker}/correlation`)).data,
    })
    const refresh = () => { void refetchRisk(); void refetchCorr() }
    const select = (t: string) => navigate(`/risk/${t}`)

    // Missing data renders as "—" / empty bars; no placeholder scores.
    const components = riskData?.components
    const score = (v?: number) => (v === undefined ? "—" : v.toFixed(1))
    const assumed = riskData?.assumed_inputs ?? []
    const hasPrices = !!riskData && !assumed.includes("price_history")
    const marketBeta = riskData?.factor_sensitivities?.market_beta
    const riskLevel = riskData?.risk_level ?? "Unrated"
    const overallRiskScore = riskData?.overall_risk_score
    const drawdownPct = hasPrices && riskData.max_drawdown < 0 ? Math.abs(riskData.max_drawdown * 100) : undefined
    const benchmark = isIndianAsset(activeTicker) ? "Nifty 50" : "S&P 500"

    const factors = riskData && components
        ? FACTORS.map(f => {
            const v = components[f.score]
            const weight = riskData.component_weights?.[f.key] ?? 0
            return { ...f, v, weight, points: v * weight, estimated: f.input !== null && assumed.includes(f.input) }
        }).sort((a, b) => b.points - a.points)
        : []
    const weightedTotal = factors.reduce((sum, f) => sum + f.points, 0)
    const drawdownLift = overallRiskScore === undefined ? 0 : overallRiskScore - weightedTotal

    // Worst first
    const scenarios: StressScenario[] = [...(riskData?.scenarios ?? [])].sort((a, b) => a.impact_pct - b.impact_pct)
    const worst = scenarios[0]
    const sensitivities = SENSITIVITIES.filter(([k]) => riskData?.factor_sensitivities?.[k] !== undefined)

    const kpis: { label: string; value: string; note?: string; band?: keyof typeof BAND_BAR; fill?: number }[] = [
        { label: "Risk score", value: `${score(overallRiskScore)} / 100`, ...(overallRiskScore !== undefined && { band: band(overallRiskScore), fill: overallRiskScore }) },
        { label: `Beta vs ${benchmark}`, value: marketBeta === undefined ? "—" : marketBeta.toFixed(2), note: "1.00 moves with the market",
            // a missing beta gets a default score, so no band for it
            ...(components && !assumed.includes("beta") && { band: band(components.beta_score), fill: components.beta_score }) },
        // engine: a 60% fall is maximal risk
        { label: "Worst fall in the past year", value: drawdownPct === undefined ? "—" : `-${drawdownPct.toFixed(1)}%`,
            ...(drawdownPct !== undefined && { band: band(drawdownPct / 0.6), fill: drawdownPct / 0.6 }) },
        { label: "Worst modelled shock", value: worst ? `${signed(worst.impact_pct)}%` : "—", note: worst?.name },
    ]

    const handleExport = () => {
        if (!riskData) return
        exportToCsv(`risk-${activeTicker}.csv`, [
            { section: "Summary", item: "Overall risk score", value: riskData.overall_risk_score.toFixed(1), detail: riskData.risk_level },
            ...factors.map(f => ({
                section: "Factor", item: f.name, value: f.v.toFixed(1),
                detail: `${(f.weight * 100).toFixed(0)}% weight, adds ${f.points.toFixed(1)} points${f.estimated ? ", estimated" : ""}`,
            })),
            ...scenarios.map(s => ({ section: "Scenario", item: s.name, value: `${s.impact_pct.toFixed(1)}%`, detail: s.narrative ?? "" })),
            ...(corrData?.peers ?? []).map(p => ({ section: "Peer correlation", item: p.ticker, value: p.correlation.toFixed(2), detail: p.relationship })),
        ], [
            { key: "section", label: "Section" },
            { key: "item", label: "Item" },
            { key: "value", label: "Value" },
            { key: "detail", label: "Detail" },
        ])
    }

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto">
            <PageHeader
                title="Risk breakdown"
                description="How risky a stock is, what drives the score, and how it might react to market shocks. Scored from one year of prices and the latest financials."
                actions={<>
                    <Button variant="outline" size="sm" onClick={handleExport} disabled={!riskData} className="gap-1.5"><Download className="size-4" /> Export CSV</Button>
                    <Button variant="outline" size="sm" onClick={refresh} disabled={isFetching || isFetchingCorr} className="gap-1.5">
                        <RefreshCw className="size-4" /> {isFetching || isFetchingCorr ? "Refreshing…" : "Refresh"}
                    </Button>
                </>}
            />

            <div className="flex flex-wrap items-center gap-2">
                <form onSubmit={e => { e.preventDefault(); if (tickerInput.trim()) { select(tickerInput.trim().toUpperCase()); setTickerInput("") } }} className="flex items-center gap-1.5">
                    <div className="relative">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" aria-hidden="true" />
                        <input value={tickerInput} onChange={e => setTickerInput(e.target.value)} placeholder="Ticker, e.g. TCS.NS" aria-label="Ticker to analyze"
                            className="bg-background border border-border rounded-md pl-8 pr-3 py-1.5 text-sm w-48 outline-none focus:border-primary" />
                    </div>
                    <Button type="submit" size="sm">Analyze</Button>
                </form>
                <div role="group" aria-label="Quick picks" className="flex flex-wrap gap-1.5">
                    {universe.slice(0, QUICK_TICKER_LIMIT).map(t => (
                        <button key={t} type="button" aria-pressed={activeTicker === t} onClick={() => select(t)}
                            className={cn("rounded-full border px-3 py-1 text-xs", activeTicker === t ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>
                            {t}
                        </button>
                    ))}
                </div>
            </div>

            {isLoading ? <Panel id="risk-summary" title={activeTicker}><PanelSkeleton rows={4} /></Panel> : isError && !riskData ? (
                <Panel id="risk-summary" title={activeTicker}>
                    <div role="alert" className="p-4 space-y-3 text-sm">
                        <p className="text-q-risk-high">Could not load risk data for {activeTicker}.</p>
                        <Button variant="outline" size="sm" onClick={refresh}>Try again</Button>
                    </div>
                </Panel>
            ) : (
                <>
                    <Panel id="risk-summary" title={`${activeTicker}: ${riskLevel} risk`}
                        description={riskData?.explanation}
                        action={<Link to={`/research/${activeTicker}`} className="text-sm text-primary hover:underline">Stock page</Link>}>
                        {assumed.length > 0 && (
                            <p role="status" className="mx-4 mt-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs">
                                No data for {assumed.map(words).join(", ")}, so defaults were used. Factors marked Estimated are approximate.
                            </p>
                        )}
                        <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
                            {kpis.map(k => (
                                <div key={k.label} className="p-4 space-y-1">
                                    <dt className="text-xs text-muted-foreground">{k.label}</dt>
                                    <dd className={cn("text-xl font-semibold font-mono tabular-nums", k.label === "Risk score" ? LEVEL_TEXT[riskLevel] ?? "text-foreground" : "text-foreground")}>{k.value}</dd>
                                    {k.band && (
                                        <dd className="flex items-center gap-2 text-xs">
                                            <span className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden" aria-hidden="true">
                                                <span className={cn("block h-full", BAND_BAR[k.band])} style={{ width: `${Math.min(k.fill ?? 0, 100)}%` }} />
                                            </span>
                                            <span className={BAND_TEXT[k.band]}>{k.band}</span>
                                        </dd>
                                    )}
                                    {k.note && <dd className="text-xs text-muted-foreground truncate" title={k.note}>{k.note}</dd>}
                                </div>
                            ))}
                        </dl>
                    </Panel>

                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
                        <Panel id="risk-factors" title="What drives the score" description="Each factor is scored 0 (low risk) to 100 and weighted; largest contribution first">
                            <div className="p-4 space-y-4">
                                {factors.map(f => (
                                    <div key={f.key} className="space-y-1" data-testid={`factor-${f.key}`}>
                                        <div className="flex flex-wrap justify-between gap-x-4 text-sm">
                                            <span className="text-foreground">
                                                {f.name}
                                                {f.estimated && <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">Estimated</span>}
                                            </span>
                                            <span className="font-mono tabular-nums text-xs text-muted-foreground">
                                                {f.v.toFixed(1)}/100 × {(f.weight * 100).toFixed(0)}% = <span className="text-foreground">+{f.points.toFixed(1)} pts</span>
                                            </span>
                                        </div>
                                        <div className="h-1.5 bg-muted rounded-full overflow-hidden" aria-hidden="true">
                                            <div className={cn("h-full", BAND_BAR[band(f.v)])} style={{ width: `${Math.min(f.v, 100)}%` }} />
                                        </div>
                                    </div>
                                ))}
                                <p className="pt-3 border-t border-border text-sm text-muted-foreground">
                                    {drawdownLift > 0.05 && drawdownPct !== undefined
                                        ? `Factors add up to ${weightedTotal.toFixed(1)}. Raised by ${drawdownLift.toFixed(1)} because the stock fell ${drawdownPct.toFixed(0)}% from its peak this year.`
                                        : "The overall score is the sum of the weighted factors."}
                                    {" "}Score: <span className="font-mono tabular-nums text-foreground">{score(overallRiskScore)}</span>.
                                </p>
                            </div>
                        </Panel>

                        <Panel id="risk-shocks" title="How it might react to shocks" description="Modelled change in price for each scenario, worst first">
                            {scenarios.length === 0 ? <PanelMessage>No scenarios for this stock.</PanelMessage> : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-xs text-muted-foreground">
                                                <th scope="col" className="px-4 py-2 text-left font-medium">Scenario</th>
                                                <th scope="col" className="px-2 py-2 text-left font-medium">Main driver</th>
                                                <th scope="col" className="px-4 py-2 text-right font-medium">Change</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-border">
                                            {scenarios.map(s => (
                                                <tr key={s.id}>
                                                    <th scope="row" className="px-4 py-2 text-left font-normal">
                                                        <span className="text-foreground">{s.name}</span>
                                                        <span className="block text-xs text-muted-foreground">{s.narrative ?? s.type}</span>
                                                    </th>
                                                    <td className="px-2 py-2 text-muted-foreground">{primaryDriver(s)}</td>
                                                    <td className={cn("px-4 py-2 text-right font-mono tabular-nums", s.impact_pct < 0 ? "text-q-risk-high" : "text-q-risk-low")}>
                                                        {signed(s.impact_pct)}%
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                            {sensitivities.length > 0 && (
                                <div className="px-4 py-3 border-t border-border">
                                    <p className="text-xs text-muted-foreground mb-2">Sensitivity to each factor (beta; 1.00 moves one for one)</p>
                                    <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                                        {sensitivities.map(([k, label]) => (
                                            <div key={k} className="flex gap-1.5">
                                                <dt className="text-muted-foreground">{label}</dt>
                                                <dd className="font-mono tabular-nums">{riskData?.factor_sensitivities[k].toFixed(2)}</dd>
                                            </div>
                                        ))}
                                    </dl>
                                </div>
                            )}
                        </Panel>
                    </div>

                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
                        <Panel id="risk-drawdown" title="Fall from peak, past year"
                            description="Price as a share of its highest point so far (solid), then a modelled stress path (dashed)">
                            {/* Without price history the engine's series is synthetic, so it isn't charted */}
                            {!hasPrices || !riskData.drawdown_series?.length ? <PanelMessage>No price history for {activeTicker} yet.</PanelMessage> : (
                                <div className="h-64 p-4">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={riskData.drawdown_series}>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                                            <XAxis dataKey="time" tickLine={false} stroke="hsl(var(--muted-foreground))" fontSize={12} />
                                            <YAxis domain={[0, 100]} axisLine={false} tickLine={false} stroke="hsl(var(--muted-foreground))" fontSize={12} tickFormatter={v => `${v}%`} />
                                            <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", fontSize: 12 }}
                                                formatter={(value, name) => [
                                                    `${Number(value).toFixed(1)}% of peak (down ${(100 - Number(value)).toFixed(1)}%)`,
                                                    name === "historical" ? "Actual" : "Modelled stress",
                                                ]} />
                                            <Line type="monotone" dataKey="historical" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
                                            <Line type="monotone" dataKey="projected" stroke="hsl(var(--q-risk))" strokeWidth={2} strokeDasharray="4 4" dot={false} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                            )}
                        </Panel>

                        <Panel id="risk-peers" title="How it moves with peers"
                            description={corrData
                                ? <>Sector: {corrData.sector || "unknown"}. Moves with the {corrData.benchmark_ticker || benchmark} at <span className="font-mono tabular-nums">{corrData.benchmark_correlation?.toFixed(2) ?? "—"}</span> (1.00 is in lockstep).</>
                                : "Correlation of daily returns over the past year"}>
                            {(corrData?.peers ?? []).length === 0 ? <PanelMessage>No peer data for {activeTicker}.</PanelMessage> : (
                                <div className="overflow-x-auto max-h-80 overflow-y-auto">
                                    <table className="w-full text-sm">
                                        <thead>
                                            <tr className="text-xs text-muted-foreground">
                                                <th scope="col" className="px-4 py-2 text-left font-medium">Stock</th>
                                                <th scope="col" className="px-2 py-2 text-left font-medium">Relationship</th>
                                                <th scope="col" className="px-2 py-2 text-right font-medium">Beta</th>
                                                <th scope="col" className="px-4 py-2 text-right font-medium">Correlation</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-border">
                                            {corrData!.peers.map(p => (
                                                <tr key={p.ticker} className="hover:bg-muted/40">
                                                    <th scope="row" className="px-4 py-2 text-left font-normal">
                                                        <Link to={`/risk/${p.ticker}`} className="font-medium text-foreground hover:text-primary">{p.ticker}</Link>
                                                        <span className="block text-xs text-muted-foreground">{p.sector}</span>
                                                    </th>
                                                    <td className="px-2 py-2 text-muted-foreground">{p.relationship}</td>
                                                    <td className="px-2 py-2 text-right font-mono tabular-nums">{p.beta?.toFixed(2) ?? "—"}</td>
                                                    <td className="px-4 py-2 text-right font-mono tabular-nums">{signed(p.correlation, 2)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </Panel>
                    </div>
                </>
            )}
        </div>
    )
}
