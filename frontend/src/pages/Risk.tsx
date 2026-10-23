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
import { useQuickTickers } from "@/hooks/useStockUniverse"
import type { RiskAnalysis, StockCorrelation, StressScenario } from "@/types/api"




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
    const { data: riskData, isLoading, refetch: refetchRisk } = useQuery({
        queryKey: ["stockRisk", activeTicker],
        queryFn: async () => {
            const res = await apiClient.get<RiskAnalysis>(`/stocks/${activeTicker}/risk`)
            return res.data
        }
    })

    // Fetch dynamic peer and benchmark correlation data
    const { data: corrData, refetch: refetchCorr } = useQuery({
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
    const level = (v?: number) => (v === undefined ? "" : v > 60 ? "ELEVATED" : v > 40 ? "MODERATE" : "LOW")
    const status = (v?: number) => (v !== undefined && v > 60 ? "danger" : "success")
    const marketBeta = riskData?.factor_sensitivities?.market_beta
    const riskLevel = riskData?.risk_level ?? "Unrated"
    const overallRiskScore = riskData?.overall_risk_score

    const kpis = [
        {
            label: `Beta vs ${isIndianAsset(activeTicker) ? "NIFTY 50" : "S&P 500"}`,
            value: marketBeta === undefined ? "—" : marketBeta.toFixed(2),
            trend: level(components?.beta_score),
            status: status(components?.beta_score),
            fill: `${components?.beta_score ?? 0}%`
        },
        {
            label: "Annual Volatility Score",
            value: `${score(components?.volatility_score)}/100`,
            trend: level(components?.volatility_score),
            status: status(components?.volatility_score),
            fill: `${components?.volatility_score ?? 0}%`
        },
        {
            label: "Liquidity/Leverage Index",
            value: components ? `${(100 - components.leverage_score).toFixed(0)}/100` : "—/100",
            trend: level(components?.leverage_score),
            status: status(components?.leverage_score),
            dots: components ? Math.round((100 - components.leverage_score) / 10) : 0
        },
        {
            label: "Valuation Risk Score",
            value: `${score(components?.valuation_risk_score)}/100`,
            trend: level(components?.valuation_risk_score),
            status: status(components?.valuation_risk_score),
            fill: `${components?.valuation_risk_score ?? 0}%`
        },
    ]

    const factors = [
        { name: "MARKET SYSTEMIC RISK (BETA)", v: components?.beta_score, opacity: "bg-primary/40" },
        { name: "SECTOR RISK OVERLAYS", v: components?.sector_risk_score, opacity: "bg-primary/30" },
        { name: "VALUATION EXPOSURE", v: components?.valuation_risk_score, opacity: "bg-primary/20" },
        { name: "LEVERAGE RISK COEFFICIENT", v: components?.leverage_score, opacity: "bg-primary/10" },
    ].map(f => ({ ...f, val: `${score(f.v)}%`, width: `${f.v ?? 0}%` }))

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

    const allScenarios: StressScenario[] = riskData?.scenarios ?? []

    const activeScenarioId = selectedScenarioId || allScenarios[0]?.id
    const activeScenario = allScenarios.find(sc => sc.id === activeScenarioId) || allScenarios[0]

    return (
        <div className="flex flex-col flex-1 p-6 bg-background space-y-6 overflow-y-auto custom-scrollbar">
            {/* Ticker Selector Row */}
            <div className="flex flex-wrap items-center justify-between gap-4 bg-card border border-border p-3 px-4 shrink-0 rounded-sm">
                <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mr-2">Quick Tickers:</span>
                    <div className="flex flex-wrap gap-1.5">
                        {universe.map((t) => (
                            <button
                                key={t}
                                onClick={() => handleSelectTicker(t)}
                                className={cn(
                                    "px-2.5 py-1 text-[10px] font-bold rounded-sm border transition-colors font-mono",
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
                            placeholder="Enter Ticker (e.g. TLT)..."
                            value={tickerInput}
                            onChange={(e) => setTickerInput(e.target.value)}
                            className="bg-background border border-border rounded pl-8 pr-3 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-primary w-44 font-mono text-foreground"
                        />
                    </div>
                    <Button type="submit" size="sm" className="h-7 text-[9px] font-black uppercase tracking-widest">Analyze</Button>
                </form>
            </div>

            {/* Risk Context Header */}
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-q-border pb-6 shrink-0">
                <div className="space-y-1">
                    <div className="flex items-center gap-3">
                        <span className="text-primary font-mono text-[10px] font-black uppercase tracking-widest">Equity Intelligence</span>
                        <div className="size-1 rounded-full bg-q-border" />
                        <span className="text-muted-foreground font-mono text-[10px] font-black uppercase tracking-widest leading-none">Live Data Feed</span>
                    </div>
                    <h2 className="text-3xl font-black tracking-tighter uppercase text-foreground leading-none">
                        Asset: {activeTicker} | <span className={cn(
                            riskLevel === "Conservative" ? "text-green-400" :
                                riskLevel === "Moderate" ? "text-yellow-400" : "text-q-risk-high"
                        )}>Risk: {riskLevel} ({score(overallRiskScore)})</span>
                    </h2>
                    <p className="text-muted-foreground text-[11px] max-w-2xl font-bold uppercase tracking-tight">
                        Decomposed risk factors based on 252-day trailing variance and institutional SEC EDGAR debt/profitability metrics.
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <Button variant="outline" size="sm" className="bg-q-surface border-q-border text-[10px] font-black uppercase tracking-[0.15em] hover:bg-muted h-9 px-4">
                        <Download className="mr-2 size-3.5" />
                        Export Data
                    </Button>
                    <Button
                        onClick={handleRefetch}
                        disabled={isLoading}
                        size="sm"
                        className="bg-primary hover:brightness-110 text-primary-foreground text-[10px] font-black uppercase tracking-[0.15em] h-9 px-4"
                    >
                        {isLoading ? "Recalculating..." : "Recalculate Model"}
                    </Button>
                </div>
            </header>

            {isLoading ? (
                <div className="h-64 flex items-center justify-center font-mono text-xs text-muted-foreground uppercase tracking-widest">
                    EXECUTING_DETERMINISTIC_RISK_ENGINE...
                </div>
            ) : (
                <>
                    {riskData && riskData.assumed_inputs.length > 0 && (
                        <div role="status" className="flex items-center gap-2 px-4 py-2 border border-amber-500/25 bg-amber-500/5 text-amber-500 text-[10px] font-mono uppercase tracking-wider rounded-sm">
                            <AlertTriangle className="size-3.5 shrink-0" />
                            <span>
                                Estimate: no data for {riskData.assumed_inputs.map(i => i.replace(/_/g, " ")).join(", ")}.
                                Defaults were used and dependent factors are hidden.
                            </span>
                        </div>
                    )}

                    {/* KPI Row */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 shrink-0">
                        {kpis.map((stat, i) => (
                            <Card key={i} className="bg-q-surface border-q-border shadow-none overflow-hidden group">
                                <CardHeader className="p-5 pb-2 flex-row items-start justify-between space-y-0">
                                    <CardTitle className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.2em] leading-none">{stat.label}</CardTitle>
                                    <Badge variant="outline" className={cn("text-[8px] font-black bg-transparent border-none p-0 leading-none", stat.status === "danger" ? "text-q-risk-high" : "text-q-risk-low")}>{stat.trend}</Badge>
                                </CardHeader>
                                <CardContent className="p-5 pt-0">
                                    <div className="text-2xl font-black tabular-nums tracking-tighter text-foreground leading-none mb-4">{stat.value}</div>

                                    {stat.fill && (
                                        <div className="h-2 w-full bg-q-border/30 rounded-full overflow-hidden">
                                            <div className="h-full bg-primary transition-all duration-1000" style={{ width: stat.fill }} />
                                        </div>
                                    )}

                                    {stat.dots !== undefined && (
                                        <div className="grid grid-cols-10 gap-1.5 h-2">
                                            {[...Array(10)].map((_, idx) => (
                                                <div key={idx} className={cn("rounded-full", idx < (stat.dots ?? 0) ? "bg-q-risk-low" : "bg-q-border")} />
                                            ))}
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
                                    <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-foreground">Factor Risk Attribution</CardTitle>
                                    <p className="text-[9px] text-muted-foreground font-black uppercase tracking-widest mt-0.5">Marginal contribution to total portfolio risk</p>
                                </div>
                                <Badge variant="outline" className="text-[9px] font-black font-mono text-muted-foreground border-q-border rounded-sm h-6">MODEL: MULTI-FACTOR</Badge>
                            </CardHeader>
                            <CardContent className="p-6 space-y-6 flex-1 overflow-auto custom-scrollbar">
                                {factors.map((f, i) => (
                                    <div key={i} className="space-y-2">
                                        <div className="flex justify-between text-[10px] font-black uppercase tracking-widest font-mono">
                                            <span className="text-muted-foreground">{f.name}</span>
                                            <span className="text-foreground">{f.val}</span>
                                        </div>
                                        <div className="h-6 bg-background border border-q-border relative overflow-hidden group cursor-help rounded-sm">
                                            <div className={cn("absolute inset-y-0 bg-primary/30 border-r-2 border-primary transition-all duration-1000", f.opacity)} style={{ width: f.width }} />
                                            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:animate-shimmer" />
                                        </div>
                                    </div>
                                ))}
                            </CardContent>
                            <div className="p-6 pt-0 mt-auto">
                                <Separator className="bg-q-border mb-4" />
                                <div className="flex justify-end">
                                    <div className="text-right">
                                        <p className="text-[10px] text-muted-foreground font-black uppercase tracking-[0.2em] mb-1">Total Attributed Risk</p>
                                        <div className="flex items-baseline justify-end gap-3 text-3xl font-black tabular-nums tracking-tighter text-foreground leading-none">
                                            {score(overallRiskScore)}%
                                            <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest">Residual: {overallRiskScore === undefined ? "—" : (100 - overallRiskScore).toFixed(0)}%</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </Card>

                        {/* Scenarios */}
                        <Card className="lg:col-span-4 bg-q-surface border-q-border shadow-none flex flex-col">
                            <CardHeader className="p-6 border-b border-q-border bg-background/20">
                                <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-foreground">Scenario Analysis (Shock Engine)</CardTitle>
                                <p className="text-[9px] text-muted-foreground font-black uppercase tracking-widest mt-0.5">Projected % impact under market shocks</p>
                            </CardHeader>
                            <CardContent className="p-4 space-y-2 flex-1 overflow-auto custom-scrollbar">
                                {allScenarios.length === 0 && (
                                    <p className="p-3 text-[10px] text-muted-foreground uppercase tracking-widest">No stress scenarios available</p>
                                )}
                                {allScenarios.slice(0, 4).map((s) => {
                                    const Icon = getScenarioIcon(s.id)
                                    const isPositive = s.impact_pct >= 0
                                    const isSelected = s.id === activeScenario?.id
                                    return (
                                        <div
                                            key={s.id}
                                            onClick={() => setSelectedScenarioId(s.id)}
                                            className={cn(
                                                "p-3 rounded-md bg-background/50 border transition-all cursor-pointer group flex items-center justify-between",
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
                                                    <p className="text-[10px] font-black uppercase tracking-tight text-foreground">{s.name}</p>
                                                    <p className="text-[8px] text-muted-foreground font-black uppercase font-mono tracking-widest">{s.type}</p>
                                                </div>
                                            </div>
                                            <span className={cn(
                                                "font-mono font-black text-sm",
                                                isPositive ? "text-q-risk-low" : "text-q-risk-high"
                                            )}>
                                                {isPositive ? `+${s.impact_pct.toFixed(1)}%` : `${s.impact_pct.toFixed(1)}%`}
                                            </span>
                                        </div>
                                    )
                                })}

                                {activeScenario && (
                                    <div className="p-3 rounded-md bg-background/80 border border-q-border/60 text-[10px] space-y-1.5 mt-2">
                                        <div className="flex justify-between font-mono font-bold">
                                            <span className="text-muted-foreground uppercase text-[9px]">Primary Driver:</span>
                                            <span className="text-foreground text-[9px] text-right truncate ml-2 uppercase">{primaryDriver(activeScenario)}</span>
                                        </div>
                                        {activeScenario.narrative && (
                                            <p className="text-[9px] text-muted-foreground font-mono leading-snug">{activeScenario.narrative}</p>
                                        )}
                                    </div>
                                )}
                            </CardContent>
                            <div className="p-4">
                                <Button
                                    variant="secondary"
                                    onClick={() => setIsAdvancedOpen(true)}
                                    className="w-full text-[10px] font-black uppercase tracking-[0.2em] h-10 border border-q-border/50"
                                >
                                    Load Advanced Scenarios ({allScenarios.length})
                                </Button>
                            </div>
                        </Card>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 shrink-0">
                        {/* Drawdown */}
                        <Card className="bg-q-surface border-q-border shadow-none overflow-hidden">
                            <CardHeader className="p-6 border-b border-q-border bg-background/20 flex-row items-center justify-between space-y-0">
                                <div>
                                    <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-foreground">Historical Max Drawdown</CardTitle>
                                    <p className="text-[9px] text-muted-foreground font-black uppercase tracking-widest mt-0.5">
                                        Historical vs. Projected Stressed Performance
                                        {riskData?.max_drawdown !== undefined && (
                                            <span className="ml-2 font-mono text-q-risk-high font-bold">
                                                [1Y Max DD: {(riskData.max_drawdown * 100).toFixed(1)}%]
                                            </span>
                                        )}
                                    </p>
                                </div>
                                <div className="flex items-center gap-4 text-[9px] font-black font-mono tracking-widest">
                                    <div className="flex items-center gap-1.5 text-primary"><div className="size-2 bg-primary rounded-full" /> HIST</div>
                                    <div className="flex items-center gap-1.5 text-q-risk-high"><div className="size-2 bg-q-risk-high rounded-full" /> PROJ STRESS</div>
                                </div>
                            </CardHeader>
                            <CardContent className="p-6">
                                <div className="h-64 relative">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <LineChart
                                            data={
                                                riskData?.drawdown_series && riskData.drawdown_series.length > 0
                                                    ? riskData.drawdown_series
                                                    : [
                                                        { time: "Jan '24", historical: 100 },
                                                        { time: "Feb '24", historical: 95 },
                                                        { time: "Mar '24", historical: 98 },
                                                        { time: "Apr '24", historical: 85 },
                                                        { time: "May '24", historical: 88 },
                                                        { time: "Jun '24", historical: 70 },
                                                        { time: "Jul '24", historical: 75 },
                                                        { time: "Aug '24", historical: 60 },
                                                        { time: "Sep '24", historical: 65, projected: 65 },
                                                        { time: "Oct '24", projected: 55 },
                                                        { time: "Nov '24", projected: 58 },
                                                        { time: "Dec '24", projected: 45 },
                                                    ]
                                            }
                                        >
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
                                                    name === "historical" ? "Recovery vs Peak" : "Stressed Projection"
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
                                                stroke="hsl(var(--q-risk-high))"
                                                strokeWidth={2.5}
                                                strokeDasharray="4 4"
                                                dot={false}
                                                animationDuration={2000}
                                            />
                                        </LineChart>
                                    </ResponsiveContainer>
                                    <div className="absolute top-2 left-10 text-[9px] font-black font-mono text-muted-foreground bg-background/50 px-1">0% PEAK</div>
                                    <div className="absolute bottom-6 left-10 text-[9px] font-black font-mono text-q-risk-high bg-q-risk-high/10 px-1 border border-q-risk-high/20">
                                        HIST MAX DD: {riskData?.max_drawdown ? `${(riskData.max_drawdown * 100).toFixed(1)}%` : "—"} | WORST SCENARIO: {allScenarios.length ? `${Math.min(...allScenarios.map(sc => sc.impact_pct)).toFixed(1)}%` : "—"}
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Dynamic Peer Correlation Matrix */}
                        <Card className="bg-q-surface border-q-border shadow-none overflow-hidden">
                            <CardHeader className="p-6 border-b border-q-border bg-background/20 flex-row items-center justify-between space-y-0">
                                <div>
                                    <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-foreground">Sector Peer & Cross-Asset Correlation</CardTitle>
                                    <p className="text-[9px] text-muted-foreground font-black uppercase tracking-widest mt-0.5">
                                        Pairwise co-movement with {activeTicker} ({corrData?.sector || "sector unknown"})
                                    </p>
                                </div>
                                <div className="flex items-center gap-2 font-mono text-[9px] font-black uppercase">
                                    <span className="text-muted-foreground">{corrData?.benchmark_ticker || (isIndianAsset(activeTicker) ? "NIFTY 50" : "S&P 500")}:</span>
                                    <Badge variant="outline" className="text-primary font-mono font-bold bg-primary/10 border-primary/30">
                                        ρ = {corrData ? corrData.benchmark_correlation.toFixed(2) : "—"}
                                    </Badge>
                                </div>
                            </CardHeader>
                            <CardContent className="p-4 bg-background/5 border-b border-q-border/30">
                                <div className="grid grid-cols-2 md:grid-cols-5 gap-2 h-64 overflow-y-auto custom-scrollbar">
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
                                            <div
                                                key={peer.ticker}
                                                onClick={() => handleSelectTicker(peer.ticker)}
                                                className={cn(
                                                    "p-2.5 text-[9px] font-black flex flex-col justify-between transition-all hover:scale-105 hover:z-10 cursor-pointer border rounded-sm group shadow-md",
                                                    colorClass
                                                )}
                                            >
                                                <div className="flex justify-between items-start">
                                                    <div>
                                                        <span className="font-mono text-xs font-black tracking-tight">{peer.ticker}</span>
                                                        <div className="text-[7.5px] font-bold text-muted-foreground uppercase truncate max-w-[80px]">
                                                            {peer.sector}
                                                        </div>
                                                    </div>
                                                    <span className="text-[7.5px] font-mono px-1 py-0.5 rounded bg-background/50 border border-current/20">
                                                        β {peer.beta.toFixed(1)}
                                                    </span>
                                                </div>
                                                <div className="flex items-end justify-between mt-2">
                                                    <span className="text-[7.5px] font-bold uppercase tracking-wider text-muted-foreground">
                                                        {peer.relationship}
                                                    </span>
                                                    <span className="font-mono font-black text-xs">
                                                        {corr >= 0 ? `+${corr.toFixed(2)}` : corr.toFixed(2)}
                                                    </span>
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            </CardContent>
                            <div className="p-4 px-6 bg-q-surface flex flex-wrap justify-between items-center text-[9px] font-black font-mono text-muted-foreground uppercase tracking-[0.2em] gap-2">
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
                            <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Estimated Factor Betas (&beta;):</span>
                            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-center font-mono">
                                <div className="p-2 bg-background border border-border rounded-sm">
                                    <div className="text-[9px] text-muted-foreground">Market Beta</div>
                                    <div className="text-xs font-bold text-foreground">
                                        {riskData.factor_sensitivities.market_beta?.toFixed(2) ?? "—"}
                                    </div>
                                </div>
                                <div className="p-2 bg-background border border-border rounded-sm">
                                    <div className="text-[9px] text-muted-foreground">Rate Beta</div>
                                    <div className="text-xs font-bold text-foreground">
                                        {riskData.factor_sensitivities.interest_rate_beta?.toFixed(2) ?? "—"}
                                    </div>
                                </div>
                                <div className="p-2 bg-background border border-border rounded-sm">
                                    <div className="text-[9px] text-muted-foreground">Oil Beta</div>
                                    <div className="text-xs font-bold text-foreground">
                                        {riskData.factor_sensitivities.oil_beta?.toFixed(2) ?? "—"}
                                    </div>
                                </div>
                                <div className="p-2 bg-background border border-border rounded-sm">
                                    <div className="text-[9px] text-muted-foreground">Tech Mom Beta</div>
                                    <div className="text-xs font-bold text-foreground">
                                        {riskData.factor_sensitivities.tech_momentum_beta?.toFixed(2) ?? "—"}
                                    </div>
                                </div>
                                <div className="p-2 bg-background border border-border rounded-sm">
                                    <div className="text-[9px] text-muted-foreground">Credit Beta</div>
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
                                                <div className="text-[10px] text-muted-foreground font-mono">{s.type}</div>
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

                                    <div className="flex items-center justify-between text-[10px] text-muted-foreground font-mono pt-1 border-t border-border/40">
                                        <span>Driver: <strong className="text-foreground uppercase">{primaryDriver(s)}</strong></span>
                                        {s.narrative && <span className="text-right truncate ml-2">{s.narrative}</span>}
                                    </div>

                                    {s.factor_breakdown && Object.keys(s.factor_breakdown).length > 0 && (
                                        <div className="grid grid-cols-2 gap-1.5 pt-1 text-[9px] font-mono bg-muted/30 p-2 rounded">
                                            {Object.entries(s.factor_breakdown).map(([factor, val]) => (
                                                <div key={factor} className="flex justify-between">
                                                    <span className="text-muted-foreground">{factor}:</span>
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
