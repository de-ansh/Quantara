import { useState } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import apiClient from "@/lib/api"
import {
    BarChart3,
    Zap,
    Download,
    Droplets,
    Globe,
    Search,
    DollarSign,
    ShieldAlert,
    Sliders,
    AlertTriangle,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
    ResponsiveContainer,
    CartesianGrid,
    XAxis,
    YAxis,
    Tooltip,
    LineChart,
    Line
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from "@/components/ui/dialog"
import { isIndianAsset } from "@/lib/currency"
import { exportToCsv } from "@/lib/export"
import { useQuickTickers } from "@/hooks/useStockUniverse"
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

// Same bands the risk engine uses for Conservative / Moderate / Aggressive
const band = (v: number): "LOW" | "MODERATE" | "HIGH" => (v <= 33.33 ? "LOW" : v <= 66.67 ? "MODERATE" : "HIGH")
const BAND_TEXT = { LOW: "text-q-risk-low", MODERATE: "text-amber-500", HIGH: "text-q-risk-high" }
const BAND_BAR = { LOW: "bg-q-risk-low", MODERATE: "bg-amber-500", HIGH: "bg-q-risk-high" }

export default function Risk() {
    const universe = useQuickTickers()
    const { ticker: urlTicker } = useParams()
    const navigate = useNavigate()
    const [localTicker, setLocalTicker] = useState("NVDA")
    const [tickerInput, setTickerInput] = useState("")
    const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null)
    const [isAdvancedOpen, setIsAdvancedOpen] = useState(false)

    const activeTicker = (urlTicker || localTicker).toUpperCase()

    // Fetch dynamic stock risk details from backend
    const { data: riskData, isLoading, isFetching, isError, refetch: refetchRisk } = useQuery({
        queryKey: ["stockRisk", activeTicker],
        queryFn: async () => {
            const res = await apiClient.get<RiskAnalysis>(`/stocks/${activeTicker}/risk`)
            return res.data
        }
    })

    // Fetch dynamic peer and benchmark correlation data
    const { data: corrData, isFetching: isFetchingCorr, refetch: refetchCorr } = useQuery({
        queryKey: ["stockCorrelation", activeTicker],
        queryFn: async () => {
            const res = await apiClient.get<StockCorrelation>(`/stocks/${activeTicker}/correlation`)
            return res.data
        }
    })

    const handleRefetch = () => {
        refetchRisk()
        refetchCorr()
    }

    const handleSelectTicker = (t: string) => {
        setLocalTicker(t)
        navigate(`/risk/${t}`)
    }

    const handleCustomSearch = (e: React.FormEvent) => {
        e.preventDefault()
        if (tickerInput.trim()) {
            handleSelectTicker(tickerInput.trim().toUpperCase())
            setTickerInput("")
        }
    }

    // Missing data renders as "—" / empty bars; no placeholder scores.
    const components = riskData?.components
    const score = (v?: number) => (v === undefined ? "—" : v.toFixed(1))
    const assumed = riskData?.assumed_inputs ?? []
    const hasPrices = !!riskData && !assumed.includes("price_history")
    const marketBeta = riskData?.factor_sensitivities?.market_beta
    const riskLevel = riskData?.risk_level ?? "Unrated"
    const overallRiskScore = riskData?.overall_risk_score
    const drawdownPct = hasPrices && riskData.max_drawdown < 0 ? Math.abs(riskData.max_drawdown * 100) : undefined

    const factors = riskData && components
        ? FACTORS.map(f => {
            const v = components[f.score]
            const weight = riskData.component_weights[f.key] ?? 0
            return { ...f, v, weight, points: v * weight, estimated: f.input !== null && assumed.includes(f.input) }
        }).sort((a, b) => b.points - a.points)
        : []
    const weightedTotal = factors.reduce((sum, f) => sum + f.points, 0)
    const drawdownLift = overallRiskScore === undefined ? 0 : overallRiskScore - weightedTotal

    // Scenario ids come from the risk engine (US and India sets); match on keywords
    const getScenarioIcon = (id: string) => {
        if (/rate|repo|fed/.test(id)) return BarChart3
        if (/recession|slowdown|monsoon/.test(id)) return Globe
        if (/oil|crude/.test(id)) return Droplets
        if (/ai_|capex|infra/.test(id)) return Zap
        if (/credit|spread/.test(id)) return ShieldAlert
        if (/usd|inr|fx/.test(id)) return DollarSign
        return Sliders
    }

    /** The factor contributing most to a scenario's impact. */
    const primaryDriver = (sc: StressScenario) => {
        const top = Object.entries(sc.factor_breakdown).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))[0]
        return top ? top[0].replace(/_/g, " ") : "—"
    }

    // Worst first, so the shortlist shows the scenarios that matter
    const allScenarios: StressScenario[] = [...(riskData?.scenarios ?? [])].sort((a, b) => a.impact_pct - b.impact_pct)
    const worstScenario = allScenarios[0]

    const activeScenarioId = selectedScenarioId || allScenarios[0]?.id
    const activeScenario = allScenarios.find(sc => sc.id === activeScenarioId) || allScenarios[0]

    const fromRisk = (v?: number) => (v === undefined ? {} : { trend: band(v), tone: band(v), fill: `${Math.min(v, 100)}%` })
    const kpis: { label: string; value: string; trend?: string; tone?: keyof typeof BAND_TEXT; fill?: string }[] = [
        { label: "Overall Risk Score", value: `${score(overallRiskScore)}/100`, ...fromRisk(overallRiskScore) },
        {
            label: `Beta vs ${isIndianAsset(activeTicker) ? "NIFTY 50" : "S&P 500"}`,
            value: marketBeta === undefined ? "—" : marketBeta.toFixed(2),
            ...fromRisk(components?.beta_score),
        },
        { label: "1-Year Max Drawdown", value: drawdownPct === undefined ? "—" : `-${drawdownPct.toFixed(1)}%`, ...fromRisk(drawdownPct === undefined ? undefined : drawdownPct / 0.6) }, // engine: a 60% fall is maximal risk
        {
            label: "Worst Scenario",
            value: worstScenario ? `${worstScenario.impact_pct.toFixed(1)}%` : "—",
            ...(worstScenario && {
                trend: worstScenario.name,
                tone: worstScenario.impact_pct < 0 ? "HIGH" as const : "LOW" as const,
                fill: `${Math.min(Math.abs(worstScenario.impact_pct), 100)}%`,
            }),
        },
    ]

    const handleExport = () => {
        if (!riskData) return
        exportToCsv(`risk-${activeTicker}.csv`, [
            { section: "Summary", item: "Overall risk score", value: riskData.overall_risk_score.toFixed(1), detail: riskData.risk_level },
            ...factors.map(f => ({
                section: "Factor", item: f.name, value: f.v.toFixed(1),
                detail: `${(f.weight * 100).toFixed(0)}% weight, adds ${f.points.toFixed(1)} points${f.estimated ? ", estimated" : ""}`,
            })),
            ...allScenarios.map(s => ({ section: "Scenario", item: s.name, value: `${s.impact_pct.toFixed(1)}%`, detail: s.narrative ?? "" })),
            ...(corrData?.peers ?? []).map(p => ({ section: "Peer correlation", item: p.ticker, value: p.correlation.toFixed(2), detail: p.relationship })),
        ], [
            { key: "section", label: "Section" },
            { key: "item", label: "Item" },
            { key: "value", label: "Value" },
            { key: "detail", label: "Detail" },
        ])
    }

    return (
        <div className="flex flex-col flex-1 p-6 bg-background space-y-6 overflow-y-auto custom-scrollbar">
            {/* Ticker Selector Row */}
            <div className="flex flex-wrap items-center justify-between gap-4 bg-card border border-border p-3 px-4 shrink-0 rounded-sm">
                <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-widest mr-2">Quick Tickers:</span>
                    <div className="flex flex-wrap gap-1.5">
                        {universe.slice(0, QUICK_TICKER_LIMIT).map((t) => (
                            <button
                                key={t}
                                onClick={() => handleSelectTicker(t)}
                                className={cn(
                                    "px-2.5 py-1 text-[11px] font-bold rounded-sm border transition-colors font-mono",
                                    activeTicker === t
                                        ? "bg-primary border-primary text-white"
                                        : "border-border hover:bg-muted text-muted-foreground hover:text-foreground"
                                )}
                            >
                                {t.endsWith(".NS") ? `🇮🇳 ${t.replace(".NS", "")}` : t}
                            </button>
                        ))}
                    </div>
                </div>

                <form onSubmit={handleCustomSearch} className="flex items-center gap-2">
                    <div className="relative group">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground group-focus-within:text-primary transition-colors" />
                        <input
                            type="text"
                            placeholder="Ticker, e.g. TCS.NS"
                            aria-label="Ticker to analyze"
                            value={tickerInput}
                            onChange={(e) => setTickerInput(e.target.value)}
                            className="bg-background border border-border rounded pl-8 pr-3 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-primary w-48 font-mono text-foreground"
                        />
                    </div>
                    <Button type="submit" size="sm" className="h-7 text-[10px] font-black uppercase tracking-widest">Analyze</Button>
                </form>
            </div>

            {/* Risk Context Header */}
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-q-border pb-6 shrink-0">
                <div className="space-y-1">
                    <span className="text-primary font-mono text-[11px] font-black uppercase tracking-widest">Risk Breakdown</span>
                    <h2 className="text-3xl font-black tracking-tighter uppercase text-foreground leading-none">
                        {activeTicker} | <span className={cn(
                            riskLevel === "Conservative" ? "text-q-risk-low" :
                                riskLevel === "Moderate" ? "text-amber-500" :
                                    riskLevel === "Aggressive" ? "text-q-risk-high" : "text-muted-foreground"
                        )}>Risk: {riskLevel} ({score(overallRiskScore)})</span>
                    </h2>
                    <p className="text-muted-foreground text-xs max-w-2xl">
                        {riskData?.explanation || "Scored from one year of prices and the latest reported financials."}
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <Button onClick={handleExport} disabled={!riskData} variant="outline" size="sm" className="bg-q-surface border-q-border text-[11px] font-black uppercase tracking-[0.15em] hover:bg-muted h-9 px-4">
                        <Download className="mr-2 size-3.5" />
                        Export Data
                    </Button>
                    <Button
                        onClick={handleRefetch}
                        disabled={isFetching || isFetchingCorr}
                        size="sm"
                        className="bg-primary hover:brightness-110 text-primary-foreground text-[11px] font-black uppercase tracking-[0.15em] h-9 px-4"
                    >
                        {isFetching || isFetchingCorr ? "Recalculating..." : "Recalculate"}
                    </Button>
                </div>
            </header>

            {isLoading ? (
                <div className="h-64 flex items-center justify-center font-mono text-xs text-muted-foreground uppercase tracking-widest">
                    Calculating risk...
                </div>
            ) : isError && !riskData ? (
                <div role="alert" className="h-64 flex flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
                    <p>Could not load risk data for {activeTicker}.</p>
                    <Button variant="outline" size="sm" onClick={handleRefetch}>Try again</Button>
                </div>
            ) : (
                <>
                    {riskData && riskData.assumed_inputs.length > 0 && (
                        <div role="status" className="flex items-center gap-2 px-4 py-2 border border-amber-500/25 bg-amber-500/5 text-amber-500 text-[11px] font-mono uppercase tracking-wider rounded-sm">
                            <AlertTriangle className="size-3.5 shrink-0" />
                            <span>
                                Estimate: no data for {riskData.assumed_inputs.map(i => i.replace(/_/g, " ")).join(", ")}.
                                Defaults were used, so factors marked Estimated are approximate.
                            </span>
                        </div>
                    )}

                    {/* KPI Row */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 shrink-0">
                        {kpis.map((stat, i) => (
                            <Card key={i} className="bg-q-surface border-q-border shadow-none overflow-hidden group">
                                <CardHeader className="p-5 pb-2 flex-row items-start justify-between space-y-0">
                                    <CardTitle className="text-[11px] font-black text-muted-foreground uppercase tracking-[0.2em] leading-none">{stat.label}</CardTitle>
                                    {stat.tone && <Badge variant="outline" title={stat.trend} className={cn("block max-w-[50%] truncate text-right text-[10px] font-black bg-transparent border-none p-0 leading-none", BAND_TEXT[stat.tone])}>{stat.trend}</Badge>}
                                </CardHeader>
                                <CardContent className="p-5 pt-0">
                                    <div className="text-2xl font-black tabular-nums tracking-tighter text-foreground leading-none mb-4">{stat.value}</div>

                                    {stat.fill && stat.tone && (
                                        <div className="h-2 w-full bg-q-border/30 rounded-full overflow-hidden">
                                            <div className={cn("h-full transition-all duration-1000", BAND_BAR[stat.tone])} style={{ width: stat.fill }} />
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0 flex-1">
                        {/* Attribution */}
                        <Card className="lg:col-span-8 bg-q-surface border-q-border shadow-none flex flex-col">
                            <CardHeader className="p-6 border-b border-q-border flex-row items-center justify-between space-y-0 bg-background/20">
                                <div>
                                    <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-foreground">What Drives This Score</CardTitle>
                                    <p className="text-[10px] text-muted-foreground font-black uppercase tracking-widest mt-0.5">Each factor scored 0-100, largest contribution first</p>
                                </div>
                            </CardHeader>
                            <CardContent className="p-6 space-y-5 flex-1 overflow-auto custom-scrollbar">
                                {factors.map((f) => (
                                    <div key={f.key} className="space-y-1.5" data-testid={`factor-${f.key}`}>
                                        <div className="flex flex-wrap justify-between gap-x-4 text-[11px] font-black uppercase tracking-widest font-mono">
                                            <span className="text-foreground">
                                                {f.name}
                                                {f.estimated && <span className="ml-2 text-amber-500">Estimated</span>}
                                            </span>
                                            <span className="text-muted-foreground">
                                                {f.v.toFixed(1)}/100 × {(f.weight * 100).toFixed(0)}% = <span className="text-foreground">+{f.points.toFixed(1)} pts</span>
                                            </span>
                                        </div>
                                        <div className="h-2 bg-q-border/30 rounded-full overflow-hidden">
                                            <div className={cn("h-full transition-all duration-1000", BAND_BAR[band(f.v)])} style={{ width: `${Math.min(f.v, 100)}%` }} />
                                        </div>
                                    </div>
                                ))}
                            </CardContent>
                            <div className="p-6 pt-0 mt-auto">
                                <Separator className="bg-q-border mb-4" />
                                <div className="flex flex-wrap items-baseline justify-between gap-3">
                                    <p className="text-xs text-muted-foreground">
                                        {drawdownLift > 0.05 && drawdownPct !== undefined
                                            ? `Factors add up to ${weightedTotal.toFixed(1)}. Raised by ${drawdownLift.toFixed(1)} because the stock fell ${drawdownPct.toFixed(0)}% from its peak this year.`
                                            : "The overall score is the sum of the weighted factors."}
                                    </p>
                                    <div className="flex items-baseline gap-2 text-3xl font-black tabular-nums tracking-tighter text-foreground leading-none">
                                        {score(overallRiskScore)}
                                        <span className="text-[11px] font-black text-muted-foreground uppercase tracking-widest">/100</span>
                                    </div>
                                </div>
                            </div>
                        </Card>

                        {/* Scenarios */}
                        <Card className="lg:col-span-4 bg-q-surface border-q-border shadow-none flex flex-col">
                            <CardHeader className="p-6 border-b border-q-border bg-background/20">
                                <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-foreground">Scenario Analysis (Shock Engine)</CardTitle>
                                <p className="text-[10px] text-muted-foreground font-black uppercase tracking-widest mt-0.5">Modelled % impact, worst first</p>
                            </CardHeader>
                            <CardContent className="p-4 space-y-2 flex-1 overflow-auto custom-scrollbar">
                                {allScenarios.length === 0 && (
                                    <p className="p-3 text-[11px] text-muted-foreground uppercase tracking-widest">No stress scenarios available</p>
                                )}
                                {allScenarios.slice(0, 4).map((s) => {
                                    const Icon = getScenarioIcon(s.id)
                                    const isPositive = s.impact_pct >= 0
                                    const isSelected = s.id === activeScenario?.id
                                    return (
                                        <button
                                            type="button"
                                            key={s.id}
                                            aria-pressed={isSelected}
                                            onClick={() => setSelectedScenarioId(s.id)}
                                            className={cn(
                                                "w-full text-left p-3 rounded-md bg-background/50 border transition-all cursor-pointer group flex items-center justify-between",
                                                isSelected
                                                    ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                                                    : "border-q-border/50 hover:border-q-border hover:bg-background"
                                            )}
                                        >
                                            <div className="flex items-center gap-3">
                                                <div className={cn(
                                                    "p-2 rounded bg-background border border-q-border group-hover:scale-110 transition-transform",
                                                    isPositive ? "text-q-risk-low" : "text-q-risk-high"
                                                )}>
                                                    <Icon className="size-4" />
                                                </div>
                                                <div>
                                                    <p className="text-[11px] font-black uppercase tracking-tight text-foreground">{s.name}</p>
                                                    <p className="text-[10px] text-muted-foreground font-black uppercase font-mono tracking-widest">{s.type}</p>
                                                </div>
                                            </div>
                                            <span className={cn(
                                                "font-mono font-black text-sm",
                                                isPositive ? "text-q-risk-low" : "text-q-risk-high"
                                            )}>
                                                {isPositive ? `+${s.impact_pct.toFixed(1)}%` : `${s.impact_pct.toFixed(1)}%`}
                                            </span>
                                        </button>
                                    )
                                })}

                                {activeScenario && (
                                    <div className="p-3 rounded-md bg-background/80 border border-q-border/60 text-[11px] space-y-1.5 mt-2">
                                        <div className="flex justify-between font-mono font-bold">
                                            <span className="text-muted-foreground uppercase text-[10px]">Primary Driver:</span>
                                            <span className="text-foreground text-[10px] text-right truncate ml-2 uppercase">{primaryDriver(activeScenario)}</span>
                                        </div>
                                        {activeScenario.narrative && (
                                            <p className="text-[10px] text-muted-foreground font-mono leading-snug">{activeScenario.narrative}</p>
                                        )}
                                    </div>
                                )}
                            </CardContent>
                            <div className="p-4">
                                <Button
                                    variant="secondary"
                                    onClick={() => setIsAdvancedOpen(true)}
                                    className="w-full text-[11px] font-black uppercase tracking-[0.2em] h-10 border border-q-border/50"
                                >
                                    All Scenarios ({allScenarios.length})
                                </Button>
                            </div>
                        </Card>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 shrink-0">
                        {/* Drawdown */}
                        <Card className="bg-q-surface border-q-border shadow-none overflow-hidden">
                            <CardHeader className="p-6 border-b border-q-border bg-background/20 flex-row items-center justify-between space-y-0">
                                <div>
                                    <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-foreground">1-Year Drawdown</CardTitle>
                                    <p className="text-[10px] text-muted-foreground font-black uppercase tracking-widest mt-0.5">Price as % of its peak, then a modelled stress path</p>
                                </div>
                                <div className="flex items-center gap-4 text-[10px] font-black font-mono tracking-widest">
                                    <div className="flex items-center gap-1.5 text-primary"><div className="size-2 bg-primary rounded-full" /> ACTUAL</div>
                                    <div className="flex items-center gap-1.5 text-q-risk-high"><div className="size-2 bg-q-risk-high rounded-full" /> MODELLED</div>
                                </div>
                            </CardHeader>
                            <CardContent className="p-6">
                                {/* Without price history the engine's series is synthetic, so it isn't charted */}
                                {!hasPrices || riskData.drawdown_series.length === 0 ? (
                                    <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
                                        No price history for {activeTicker} yet.
                                    </div>
                                ) : (
                                <div className="h-64 relative">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart data={riskData.drawdown_series}>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--q-border))" opacity={0.3} />
                                            <XAxis
                                                dataKey="time"
                                                axisLine={{ stroke: 'hsl(var(--q-border))' }}
                                                tickLine={false}
                                                tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))', fontWeight: 'bold' }}
                                            />
                                            <YAxis
                                                domain={[0, 100]}
                                                axisLine={false}
                                                tickLine={false}
                                                tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))', fontWeight: 'bold' }}
                                                tickFormatter={(v) => `${v}%`}
                                            />
                                            <Tooltip
                                                contentStyle={{
                                                    backgroundColor: 'hsl(var(--q-surface))',
                                                    borderColor: 'hsl(var(--q-border))',
                                                    fontSize: '10px',
                                                    fontWeight: 'bold',
                                                    textTransform: 'uppercase'
                                                }}
                                                formatter={(value, name) => [
                                                    `${Number(value).toFixed(1)}% (DD: -${(100 - Number(value)).toFixed(1)}%)`,
                                                    name === "historical" ? "Actual" : "Modelled stress"
                                                ]}
                                            />
                                            <Line
                                                type="monotone"
                                                dataKey="historical"
                                                stroke="hsl(var(--primary))"
                                                strokeWidth={2.5}
                                                dot={false}
                                                animationDuration={1500}
                                            />
                                            <Line
                                                type="monotone"
                                                dataKey="projected"
                                                stroke="hsl(var(--q-risk))"
                                                strokeWidth={2.5}
                                                strokeDasharray="4 4"
                                                dot={false}
                                                animationDuration={2000}
                                            />
                                        </LineChart>
                                    </ResponsiveContainer>
                                </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Dynamic Peer Correlation Matrix */}
                        <Card className="bg-q-surface border-q-border shadow-none overflow-hidden">
                            <CardHeader className="p-6 border-b border-q-border bg-background/20 flex-row items-center justify-between space-y-0">
                                <div>
                                    <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-foreground">Sector Peer & Cross-Asset Correlation</CardTitle>
                                    <p className="text-[10px] text-muted-foreground font-black uppercase tracking-widest mt-0.5">
                                        Pairwise co-movement with {activeTicker} ({corrData?.sector || "sector unknown"})
                                    </p>
                                </div>
                                <div className="flex items-center gap-2 font-mono text-[10px] font-black uppercase">
                                    <span className="text-muted-foreground">{corrData?.benchmark_ticker || (isIndianAsset(activeTicker) ? "NIFTY 50" : "S&P 500")}:</span>
                                    <Badge variant="outline" className="text-primary font-mono font-bold bg-primary/10 border-primary/30">
                                        Corr {corrData ? corrData.benchmark_correlation.toFixed(2) : "—"}
                                    </Badge>
                                </div>
                            </CardHeader>
                            <CardContent className="p-4 bg-background/5 border-b border-q-border/30">
                                {(corrData?.peers ?? []).length === 0 && (
                                    <p className="h-64 flex items-center justify-center text-sm text-muted-foreground">No peer correlation data for {activeTicker}.</p>
                                )}
                                <div className="grid grid-cols-2 md:grid-cols-3 content-start gap-2 max-h-64 overflow-y-auto custom-scrollbar">
                                    {(corrData?.peers || []).map((peer) => {
                                        const corr = peer.correlation
                                        const isNegative = corr < 0
                                        const isHigh = corr >= 0.65
                                        const isLow = corr < 0.35 && !isNegative
                                        const colorClass = isNegative 
                                            ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/30"
                                            : isHigh
                                            ? "bg-red-500/20 text-red-400 border-red-500/30 hover:bg-red-500/30"
                                            : isLow
                                            ? "bg-blue-500/20 text-blue-400 border-blue-500/30 hover:bg-blue-500/30"
                                            : "bg-amber-500/20 text-amber-400 border-amber-500/30 hover:bg-amber-500/30"

                                        return (
                                            <button
                                                type="button"
                                                key={peer.ticker}
                                                onClick={() => handleSelectTicker(peer.ticker)}
                                                className={cn(
                                                    "text-left p-2.5 text-[10px] font-black flex flex-col justify-between transition-all hover:scale-105 hover:z-10 cursor-pointer border rounded-sm group shadow-md",
                                                    colorClass
                                                )}
                                            >
                                                <div className="flex justify-between items-start">
                                                    <div>
                                                        <span className="font-mono text-xs font-black tracking-tight">{peer.ticker}</span>
                                                        <div className="text-[10px] font-bold text-muted-foreground uppercase truncate max-w-[80px]">
                                                            {peer.sector}
                                                        </div>
                                                    </div>
                                                    <span className="text-[10px] font-mono px-1 py-0.5 rounded bg-background/50 border border-current/20">
                                                        β {peer.beta.toFixed(1)}
                                                    </span>
                                                </div>
                                                <div className="flex items-end justify-between mt-2">
                                                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                                                        {peer.relationship}
                                                    </span>
                                                    <span className="font-mono font-black text-xs">
                                                        {corr >= 0 ? `+${corr.toFixed(2)}` : corr.toFixed(2)}
                                                    </span>
                                                </div>
                                            </button>
                                        )
                                    })}
                                </div>
                            </CardContent>
                            <div className="p-4 px-6 bg-q-surface flex flex-wrap justify-between items-center text-[10px] font-black font-mono text-muted-foreground uppercase tracking-[0.2em] gap-2">
                                <span className="flex items-center gap-1.5 text-emerald-400"><div className="size-2 bg-emerald-500 rounded-full" /> Negative / Hedge</span>
                                <span className="flex items-center gap-1.5 text-blue-400"><div className="size-2 bg-blue-500 rounded-full" /> Low Correlation</span>
                                <span className="flex items-center gap-1.5 text-amber-400"><div className="size-2 bg-amber-500 rounded-full" /> Moderate</span>
                                <span className="flex items-center gap-1.5 text-red-400"><div className="size-2 bg-red-500 rounded-full" /> High Concentration</span>
                            </div>
                        </Card>
                    </div>
                </>
            )}

            {/* Advanced Scenarios Dialog Modal */}
            <Dialog open={isAdvancedOpen} onOpenChange={setIsAdvancedOpen}>
                <DialogContent className="max-w-3xl bg-background border-border text-foreground">
                    <DialogHeader>
                        <DialogTitle className="text-sm font-black uppercase tracking-widest flex items-center gap-2">
                            <ShieldAlert className="size-4 text-primary" />
                            Multi-Factor Stress Scenarios & Sensitivities: {activeTicker}
                        </DialogTitle>
                        <DialogDescription className="text-xs text-muted-foreground">
                            Deterministic multi-factor stress tests projecting asset sensitivity against historical and synthetic macroeconomic shocks.
                        </DialogDescription>
                    </DialogHeader>

                    {/* Factor Sensitivities Summary */}
                    {riskData?.factor_sensitivities && (
                        <div className="p-3 bg-muted/40 border border-border rounded-sm space-y-2">
                            <span className="text-[11px] font-bold uppercase tracking-widest text-muted-foreground">Estimated Factor Betas (&beta;):</span>
                            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center font-mono">
                                <div className="p-2 bg-background border border-border rounded-sm">
                                    <div className="text-[10px] text-muted-foreground">Market Beta</div>
                                    <div className="text-xs font-bold text-foreground">
                                        {riskData.factor_sensitivities.market_beta?.toFixed(2) ?? "—"}
                                    </div>
                                </div>
                                <div className="p-2 bg-background border border-border rounded-sm">
                                    <div className="text-[10px] text-muted-foreground">Rate Beta</div>
                                    <div className="text-xs font-bold text-foreground">
                                        {riskData.factor_sensitivities.interest_rate_beta?.toFixed(2) ?? "—"}
                                    </div>
                                </div>
                                <div className="p-2 bg-background border border-border rounded-sm">
                                    <div className="text-[10px] text-muted-foreground">Oil Beta</div>
                                    <div className="text-xs font-bold text-foreground">
                                        {riskData.factor_sensitivities.oil_beta?.toFixed(2) ?? "—"}
                                    </div>
                                </div>
                                <div className="p-2 bg-background border border-border rounded-sm">
                                    <div className="text-[10px] text-muted-foreground">Tech Mom Beta</div>
                                    <div className="text-xs font-bold text-foreground">
                                        {riskData.factor_sensitivities.tech_momentum_beta?.toFixed(2) ?? "—"}
                                    </div>
                                </div>
                                <div className="p-2 bg-background border border-border rounded-sm">
                                    <div className="text-[10px] text-muted-foreground">Credit Beta</div>
                                    <div className="text-xs font-bold text-foreground">
                                        {riskData.factor_sensitivities.credit_spread_beta?.toFixed(2) ?? "—"}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Scenarios List */}
                    <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1">
                        {allScenarios.map((s) => {
                            const Icon = getScenarioIcon(s.id)
                            const isPositive = s.impact_pct >= 0
                            return (
                                <div
                                    key={s.id}
                                    className="p-3 bg-card border border-border rounded-sm space-y-2"
                                >
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2.5">
                                            <div className={cn(
                                                "p-1.5 rounded bg-muted/60 border border-border",
                                                isPositive ? "text-green-500" : "text-rose-500"
                                            )}>
                                                <Icon className="size-4" />
                                            </div>
                                            <div>
                                                <div className="text-xs font-bold uppercase">{s.name}</div>
                                                <div className="text-[11px] text-muted-foreground font-mono">{s.type}</div>
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <div className={cn(
                                                "font-mono font-bold text-sm",
                                                isPositive ? "text-green-500" : "text-rose-500"
                                            )}>
                                                {isPositive ? `+${s.impact_pct.toFixed(1)}%` : `${s.impact_pct.toFixed(1)}%`}
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex items-center justify-between text-[11px] text-muted-foreground font-mono pt-1 border-t border-border/40">
                                        <span>Driver: <strong className="text-foreground uppercase">{primaryDriver(s)}</strong></span>
                                        {s.narrative && <span className="text-right ml-2">{s.narrative}</span>}
                                    </div>

                                    {s.factor_breakdown && Object.keys(s.factor_breakdown).length > 0 && (
                                        <div className="grid grid-cols-2 gap-1.5 pt-1 text-[10px] font-mono bg-muted/30 p-2 rounded">
                                            {Object.entries(s.factor_breakdown).map(([factor, val]) => (
                                                <div key={factor} className="flex justify-between">
                                                    <span className="text-muted-foreground">{factor.replace(/_/g, " ")}:</span>
                                                    <span className={cn(
                                                        "font-semibold",
                                                        val >= 0 ? "text-green-500" : "text-rose-500"
                                                    )}>
                                                        {val >= 0 ? `+${Number(val).toFixed(1)}%` : `${Number(val).toFixed(1)}%`}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )
                        })}
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    )
}
