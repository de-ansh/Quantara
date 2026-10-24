import { useState } from "react"
import {
    TrendingUp,
    TrendingDown,
    CheckCircle2,
    AlertTriangle,
    ShieldCheck,
    BarChart3,
    Radar,
    Activity,
    User,
    Zap,
    ShieldAlert,
    Clock,
    DollarSign,
    Layers,
} from "lucide-react"
import { useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { useRefreshResearch, useResearch } from "@/hooks/useResearch"
import apiClient, { apiErrorDetail } from "@/lib/api"
import { useAuth } from "@/context/AuthContext"
import { cn, timeAgo } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { isIndianAsset, cleanTickerDisplay } from "@/lib/currency"
import WatchlistButton from "@/components/WatchlistButton"
import type { ApiSignal, StockSearchItem } from "@/types/api"
import DayChange from "@/components/DayChange"
import PriceChart from "@/components/PriceChart"
import PriceAlertForm from "@/components/PriceAlertForm"
import AdviceNotice from "@/components/AdviceNotice"

const TABS = [
    { id: "thesis", label: "Investment Thesis" },
    { id: "financials", label: "Financial Health" },
    { id: "risk", label: "Risk Breakdown" },
    { id: "signals", label: "Signal Intelligence" },
    { id: "macro", label: "Macro Exposure" },
] as const

type TabType = typeof TABS[number]["id"]

export default function StockDetail() {
    const { ticker: paramTicker } = useParams()
    const activeTicker = (paramTicker || 'AAPL').toUpperCase()
    const [activeTab, setActiveTab] = useState<TabType>("thesis")
    const { user } = useAuth()

    // 1. Fetch LLM Structured Research Report
    const { data: report, isLoading: loadingReport } = useResearch(activeTicker)
    const refreshReport = useRefreshResearch(activeTicker)

    // 2. Fetch Stock Database Metadata
    const { data: searchData, isLoading: loadingStock } = useQuery({
        queryKey: ['stockMetadata', activeTicker],
        queryFn: async () => {
            const res = await apiClient.get<{ stocks: StockSearchItem[] }>('/stocks/search', { params: { query: activeTicker } })
            const found = res.data.stocks?.find((s) => s.ticker.toUpperCase() === activeTicker)
            return found || res.data.stocks?.[0] || null
        },
        enabled: !!activeTicker,
    })

    // 3. Fetch Stock Risk Analytics
    const { data: riskData, isLoading: loadingRisk } = useQuery({
        queryKey: ['stockRisk', activeTicker],
        queryFn: async () => {
            const res = await apiClient.get(`/stocks/${activeTicker}/risk`)
            return res.data
        },
        enabled: !!activeTicker,
    })

    // 4. Fetch Stock Recent Signals
    const { data: signals = [] } = useQuery({
        queryKey: ['stockSignals', activeTicker],
        queryFn: async () => {
            const res = await apiClient.get<{ signals: ApiSignal[] }>('/signals', { params: { ticker: activeTicker, limit: 10 } })
            return res.data.signals || []
        },
        enabled: !!activeTicker,
    })

    const isLoading = loadingReport || loadingStock || loadingRisk

    // Derive Dynamic Metrics
    // Unknown values render as "—"; never substitute another company's numbers.
    const companyName = searchData?.name || activeTicker
    const sector = searchData?.sector || "Unclassified"
    const price = searchData?.price || "—"
    const marketCap = searchData?.cap || "N/A"
    const peRatio = searchData?.pe ? `${searchData.pe.toFixed(1)}x` : "—"
    const betaVal = searchData?.beta ? Number(searchData.beta).toFixed(2) : "—"
    const alphaStr = searchData?.alpha || "—"
    const statusTrend = searchData?.status || "neutral"

    // Risk Classification
    const riskScoreRaw = riskData?.overall_risk_score ?? searchData?.risk
    const hasRiskScore = riskScoreRaw !== undefined && riskScoreRaw !== null
    const overallRiskScore = hasRiskScore ? Math.round(riskScoreRaw) : 0
    const riskLevel = riskData?.risk_level || (!hasRiskScore ? "Unrated" : overallRiskScore < 34 ? "Conservative" : overallRiskScore < 67 ? "Moderate" : "Aggressive")
    const components = riskData?.components
    const score = (v?: number) => (v === undefined || v === null ? "—" : v.toFixed(1))

    // Dynamic Risk Alignment Calculation
    const userRiskLevel = user?.risk_level || "Moderate"
    const bandRanges: Record<string, [number, number]> = {
        Conservative: [0, 33],
        Moderate: [34, 66],
        Aggressive: [67, 100],
    }
    const [minB, maxB] = bandRanges[userRiskLevel] || [34, 66]
    let alignmentScore = 95
    if (overallRiskScore < minB) {
        alignmentScore = Math.max(30, Math.round(100 - (minB - overallRiskScore) * 1.8))
    } else if (overallRiskScore > maxB) {
        alignmentScore = Math.max(30, Math.round(100 - (overallRiskScore - maxB) * 1.8))
    }

    // Dynamic Stats Table
    const dynamicStats = [
        { label: "P/E Ratio", value: peRatio },
        { label: "Beta (Trailed)", value: betaVal === "—" ? "—" : `${betaVal}x` },
        { label: "Volatility Score", value: `${score(components?.volatility_score)}/100` },
        { label: "Leverage Index", value: components ? `${(100 - components.leverage_score).toFixed(0)}/100` : "—/100" },
        { label: "Earnings Stability", value: `${score(components?.earnings_stability_score)}/100` },
        { label: "Alpha Projection", value: alphaStr },
    ]

    return (
        <div className="flex flex-col flex-1 p-6 bg-background overflow-y-auto custom-scrollbar transition-colors">
            {/* Header Section */}
            <section className="mb-6 flex flex-wrap items-end justify-between gap-6 border-b border-border pb-6">
                <div className="flex flex-col gap-1">
                    <div className="flex items-baseline gap-4">
                        <div className="flex items-center gap-3">
                            <h2 className="text-6xl font-black tracking-tighter text-foreground">{cleanTickerDisplay(activeTicker)}</h2>
                            <WatchlistButton ticker={activeTicker} className="[&_svg]:size-6" />
                            {isIndianAsset(activeTicker) ? (
                                <Badge className="bg-orange-500/10 text-orange-400 border border-orange-500/30 font-mono text-xs uppercase px-2 py-0.5">
                                    🇮🇳 NSE
                                </Badge>
                            ) : (
                                <Badge className="bg-blue-500/10 text-blue-400 border border-blue-500/30 font-mono text-xs uppercase px-2 py-0.5">
                                    🇺🇸 US
                                </Badge>
                            )}
                        </div>
                        <div className={cn(
                            "flex items-center gap-2 px-3 py-1 text-sm font-bold border uppercase tracking-widest shadow-sm",
                            statusTrend === "up"
                                ? "bg-q-risk-low/10 text-q-risk-low border-q-risk-low/20"
                                : statusTrend === "down"
                                    ? "bg-q-risk-high/10 text-q-risk-high border-q-risk-high/20"
                                    : "bg-muted text-muted-foreground border-border"
                        )}>
                            {statusTrend === "up" ? <TrendingUp className="size-4" /> : <TrendingDown className="size-4" />}
                            <span>{alphaStr}</span>
                        </div>
                    </div>
                    <div className="flex items-center gap-3 text-muted-foreground text-sm font-medium">
                        <span className="text-foreground uppercase tracking-wider font-bold">{companyName}</span>
                        <div className="size-1 rounded-full bg-border" />
                        <span>{sector}</span>
                        <div className="size-1 rounded-full bg-border" />
                        <span>Price: <strong className="text-foreground">{price}</strong> <DayChange pct={searchData?.change_pct} className="text-xs" /></span>
                        <div className="size-1 rounded-full bg-border" />
                        <span>MCap: <strong className="text-foreground">{marketCap}</strong></span>
                        {searchData?.price_updated_at && (
                            <>
                                <div className="size-1 rounded-full bg-border" />
                                <span className="text-xs">Price as of {timeAgo(searchData.price_updated_at)}</span>
                            </>
                        )}
                    </div>
                </div>

                {/* Risk Score Indicator */}
                <div className="flex items-center gap-4 bg-card border border-border p-4 px-6 shadow-xl shadow-background/10 transition-colors">
                    <div className="flex flex-col items-end">
                        <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Institutional Risk Score</span>
                        <span className="text-3xl font-black text-foreground leading-none">
                            {hasRiskScore ? overallRiskScore : "—"}
                            <span className="text-lg text-muted-foreground font-medium ml-1">/100</span>
                        </span>
                        <span className={cn(
                            "text-[9px] font-black uppercase tracking-widest mt-1",
                            riskLevel === "Conservative" ? "text-green-400" :
                                riskLevel === "Moderate" ? "text-amber-400" : "text-rose-400"
                        )}>
                            [{riskLevel} Tier]
                        </span>
                    </div>
                    <div className="size-12 flex items-center justify-center relative">
                        <svg className="size-full -rotate-90">
                            <circle cx="24" cy="24" r="20" fill="transparent" stroke="currentColor" className="text-border" strokeWidth="4" />
                            <circle
                                cx="24"
                                cy="24"
                                r="20"
                                fill="transparent"
                                stroke="currentColor"
                                className={overallRiskScore > 66 ? "text-q-risk-high" : overallRiskScore > 33 ? "text-amber-400" : "text-q-risk-low"}
                                strokeWidth="4"
                                strokeDasharray="125.6"
                                strokeDashoffset={125.6 - (125.6 * (overallRiskScore / 100))}
                            />
                        </svg>
                        <ShieldCheck className="absolute text-primary size-5" />
                    </div>
                </div>
            </section>

            <div className="mb-4">
                <PriceAlertForm ticker={activeTicker} />
            </div>
            <PriceChart ticker={activeTicker} />

            {/* Navigation Tabs */}
            <section className="mb-6 flex gap-1 border-b border-border overflow-x-auto no-scrollbar">
                {TABS.map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={cn(
                            "px-6 py-3 text-xs font-bold uppercase tracking-widest transition-all",
                            activeTab === tab.id
                                ? "border-b-2 border-primary bg-primary/10 text-primary"
                                : "border-b-2 border-transparent text-muted-foreground hover:text-foreground"
                        )}
                    >
                        {tab.label}
                    </button>
                ))}
            </section>

            <AdviceNotice className="mb-4" />

            {/* Main Content Layout */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
                <div className="lg:col-span-8 space-y-6">
                    {/* TAB 1: Investment Thesis */}
                    {report && (
                        <div className="flex items-center justify-end gap-2 mb-2 text-[11px] text-muted-foreground">
                            {report.generated_at && <span>Report generated {timeAgo(report.generated_at)}</span>}
                            <button
                                type="button"
                                onClick={() => refreshReport.mutate()}
                                disabled={refreshReport.isPending}
                                className="font-bold text-primary hover:underline disabled:opacity-50"
                            >
                                {refreshReport.isPending ? "Regenerating..." : "Refresh"}
                            </button>
                            {refreshReport.isError && <span className="text-red-400">{apiErrorDetail(refreshReport.error) ?? "Refresh failed"}</span>}
                        </div>
                    )}
                    {activeTab === "thesis" && (
                        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                            {/* Thesis */}
                            <div className="flex flex-col bg-card border border-border shadow-lg transition-colors">
                                <div className="flex items-center gap-2 border-b border-border bg-muted/40 px-4 py-3">
                                    <Zap className="text-primary size-4" />
                                    <h3 className="text-xs font-bold uppercase tracking-widest text-foreground">Investment Thesis</h3>
                                    <span className="ml-auto flex items-center gap-1 rounded bg-primary/20 px-2 py-0.5 text-[10px] font-bold text-primary border border-primary/20">BULLISH</span>
                                </div>
                                <div className="p-6 relative min-h-[220px]">
                                    {isLoading && (
                                        <div className="absolute inset-0 bg-background/50 flex items-center justify-center z-20">
                                            <div className="text-[10px] font-black tracking-widest uppercase animate-pulse">Running_Research_Synthesizer...</div>
                                        </div>
                                    )}
                                    <p className="text-sm leading-relaxed text-muted-foreground mb-4 font-medium">
                                        {report?.summary || `No research report is available for ${companyName} yet.`}
                                    </p>
                                    <ul className="space-y-3">
                                        {(report?.key_insights && report.key_insights.length > 0 ? report.key_insights : (report?.strengths && report.strengths.length > 0 ? report.strengths : [])).map((item, i) => (
                                            <li key={i} className="flex items-start gap-3 group">
                                                <CheckCircle2 className="text-primary size-4 mt-0.5 group-hover:scale-110 transition-transform" />
                                                <span className="text-sm text-foreground/90 font-medium">{item}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>

                            {/* Anti-Thesis */}
                            <div className="flex flex-col bg-card border border-border shadow-lg transition-colors">
                                <div className="flex items-center gap-2 border-b border-border bg-muted/40 px-4 py-3">
                                    <AlertTriangle className="text-q-warning size-4" />
                                    <h3 className="text-xs font-bold uppercase tracking-widest text-foreground">Anti-Thesis & Risks</h3>
                                    <span className="ml-auto flex items-center gap-1 rounded bg-q-warning/20 px-2 py-0.5 text-[10px] font-bold text-q-warning border border-q-warning/20">BEARISH</span>
                                </div>
                                <div className="p-6">
                                    <p className="text-sm leading-relaxed text-muted-foreground mb-4 font-medium">
                                        {report ? "Weaknesses and threats identified in the latest research report." : "No research report is available yet."}
                                    </p>
                                    <ul className="space-y-3">
                                        {(report?.weaknesses && report.weaknesses.length > 0 ? report.weaknesses : (report?.threats && report.threats.length > 0 ? report.threats : [])).map((item, i) => (
                                            <li key={i} className="flex items-start gap-3 group">
                                                <ShieldAlert className="text-q-warning size-4 mt-0.5 group-hover:scale-110 transition-transform" />
                                                <span className="text-sm text-foreground/90 font-medium">{item}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* TAB 2: Financial Health */}
                    {activeTab === "financials" && (
                        <div className="bg-card border border-border p-6 shadow-lg space-y-6">
                            <div className="border-b border-border pb-3 flex items-center justify-between">
                                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground flex items-center gap-2">
                                    <DollarSign className="size-4 text-primary" />
                                    Fundamental Financial Metrics
                                </h3>
                                <Badge variant="outline" className="text-[10px] font-mono">
                                    {isIndianAsset(activeTicker) ? `${cleanTickerDisplay(activeTicker)} SEBI/NSE Filing Data` : `${activeTicker} EDGAR Facts`}
                                </Badge>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div className="p-4 bg-muted/30 border border-border rounded-sm">
                                    <span className="text-[10px] uppercase font-bold text-muted-foreground">Earnings Stability</span>
                                    <div className="text-2xl font-black font-mono text-foreground mt-1">{score(components?.earnings_stability_score)}/100</div>
                                    <p className="text-[10px] text-muted-foreground mt-1">Multi-quarter profitability score</p>
                                </div>
                                <div className="p-4 bg-muted/30 border border-border rounded-sm">
                                    <span className="text-[10px] uppercase font-bold text-muted-foreground">Leverage Score</span>
                                    <div className="text-2xl font-black font-mono text-foreground mt-1">{score(components?.leverage_score)}/100</div>
                                    <p className="text-[10px] text-muted-foreground mt-1">Debt-to-equity vulnerability</p>
                                </div>
                                <div className="p-4 bg-muted/30 border border-border rounded-sm">
                                    <span className="text-[10px] uppercase font-bold text-muted-foreground">Valuation Risk</span>
                                    <div className="text-2xl font-black font-mono text-foreground mt-1">{score(components?.valuation_risk_score)}/100</div>
                                    <p className="text-[10px] text-muted-foreground mt-1">Historical multiple expansion</p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* TAB 3: Risk Breakdown */}
                    {activeTab === "risk" && (
                        <div className="bg-card border border-border p-6 shadow-lg space-y-6">
                            <div className="border-b border-border pb-3 flex items-center justify-between">
                                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground flex items-center gap-2">
                                    <BarChart3 className="size-4 text-primary" />
                                    Multi-Factor Risk Breakdown
                                </h3>
                                <Badge variant="secondary" className="text-[10px] font-mono">{riskLevel} Overall</Badge>
                            </div>
                            <div className="space-y-4">
                                {[
                                    { label: "Annualized Volatility Risk", val: components?.volatility_score ?? 0 },
                                    { label: "Market Beta Exposure", val: components?.beta_score ?? 0 },
                                    { label: "Balance Sheet Leverage", val: components?.leverage_score ?? 0 },
                                    { label: "Earnings Dispersion", val: components ? 100 - components.earnings_stability_score : 0 },
                                    { label: "Sector Systemic Exposure", val: components?.sector_risk_score ?? 0 },
                                    { label: "Valuation Premium Risk", val: components?.valuation_risk_score ?? 0 },
                                ].map((item) => (
                                    <div key={item.label} className="space-y-1">
                                        <div className="flex justify-between text-xs font-mono">
                                            <span className="text-muted-foreground uppercase text-[10px] font-bold">{item.label}</span>
                                            <span className="font-bold text-foreground">{item.val.toFixed(1)}/100</span>
                                        </div>
                                        <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                                            <div
                                                className={cn("h-full transition-all duration-500", item.val > 66 ? "bg-q-risk-high" : item.val > 33 ? "bg-amber-400" : "bg-q-risk-low")}
                                                style={{ width: `${Math.min(100, Math.max(5, item.val))}%` }}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                            {riskData?.explanation && (
                                <p className="text-xs font-mono text-muted-foreground p-3 bg-muted/40 border border-border rounded-sm">
                                    {riskData.explanation}
                                </p>
                            )}
                        </div>
                    )}

                    {/* TAB 4: Signal Intelligence */}
                    {activeTab === "signals" && (
                        <div className="bg-card border border-border p-6 shadow-lg space-y-4">
                            <div className="border-b border-border pb-3 flex items-center justify-between">
                                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground flex items-center gap-2">
                                    <Activity className="size-4 text-primary" />
                                    Active Signals for {activeTicker}
                                </h3>
                                <Badge variant="outline" className="text-[10px] font-mono">{signals.length} Signals Found</Badge>
                            </div>
                            {signals.length === 0 ? (
                                <div className="py-12 text-center font-mono text-xs text-muted-foreground uppercase tracking-widest">
                                    No recent institutional or insider signals recorded for {activeTicker}.
                                </div>
                            ) : (
                                <div className="divide-y divide-border">
                                    {signals.map((sig) => (
                                        <div key={sig.id} className="py-3 flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className="size-2 rounded-full bg-primary" />
                                                <div>
                                                    <span className="text-xs font-bold uppercase text-foreground">{sig.signal_type.replace('_', ' ')}</span>
                                                    <div className="text-[10px] text-muted-foreground font-mono flex items-center gap-2">
                                                        <Clock className="size-3" />
                                                        {new Date(sig.timestamp).toLocaleDateString()}
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-4">
                                                <div className="text-right font-mono">
                                                    <span className="text-[10px] text-muted-foreground">Strength</span>
                                                    <div className="text-xs font-bold text-foreground">{sig.strength.toFixed(1)}%</div>
                                                </div>
                                                <Badge variant="secondary" className="text-[10px]">{(sig.confidence * 100).toFixed(0)}% Conf.</Badge>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {/* TAB 5: Macro Exposure */}
                    {activeTab === "macro" && (
                        <div className="bg-card border border-border p-6 shadow-lg space-y-6">
                            <div className="border-b border-border pb-3 flex items-center justify-between">
                                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground flex items-center gap-2">
                                    <Layers className="size-4 text-primary" />
                                    Macro Regime & Sector Dynamics
                                </h3>
                                <Badge variant="secondary" className="text-[10px]">{sector}</Badge>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="p-4 bg-muted/30 border border-border space-y-2">
                                    <span className="text-[10px] font-bold uppercase text-muted-foreground">Sector Sensitivity</span>
                                    <p className="text-sm font-bold text-foreground">{sector} Industry Index</p>
                                    <p className="text-xs text-muted-foreground leading-relaxed">
                                        Beta of {betaVal === "—" ? "—" : `${betaVal}x`} relative to broad market benchmark ({isIndianAsset(activeTicker) ? "NIFTY 50" : "S&P 500"}).
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Risk Alignment Visualization */}
                    <div className="bg-card border border-border shadow-lg transition-colors">
                        <div className="flex items-center justify-between border-b border-border bg-muted/40 px-4 py-3">
                            <div className="flex items-center gap-2">
                                <Radar className="text-primary size-4" />
                                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground">Risk Alignment Visualization</h3>
                            </div>
                            <div className="flex items-center gap-4 text-[10px] font-bold uppercase tracking-widest">
                                <div className="flex items-center gap-1.5"><div className="size-2 bg-primary" /> User Profile</div>
                                <div className="flex items-center gap-1.5"><div className="size-2 bg-amber-400" /> Asset Profile</div>
                            </div>
                        </div>
                        <div className="flex flex-col items-center justify-center p-8 md:flex-row md:gap-12">
                            <div className="relative size-44">
                                <div className="absolute inset-0 rounded-full border-[10px] border-border" />
                                <div
                                    className="absolute inset-0 rounded-full border-[10px] border-primary transition-all duration-700"
                                    style={{ clipPath: `polygon(50% 50%, 0 0, 100% 0, 100% ${alignmentScore}%)` }}
                                />
                                <div className="absolute inset-0 flex flex-col items-center justify-center">
                                    <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Alignment</span>
                                    <span className="text-4xl font-black text-foreground">{alignmentScore}%</span>
                                </div>
                            </div>
                            <div className="mt-6 grid flex-1 grid-cols-1 gap-4 md:mt-0 md:grid-cols-2">
                                <div className="flex flex-col gap-2 rounded border border-border bg-muted/40 p-4">
                                    <div className="flex items-center justify-between">
                                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">User Risk Profile</span>
                                        <User className="size-3.5 text-primary" />
                                    </div>
                                    <span className="text-base font-bold text-foreground uppercase tracking-tight">{userRiskLevel}</span>
                                    <div className="h-1.5 w-full bg-border">
                                        <div className="h-full bg-primary" style={{ width: userRiskLevel === "Conservative" ? "33%" : userRiskLevel === "Moderate" ? "66%" : "100%" }} />
                                    </div>
                                </div>
                                <div className="flex flex-col gap-2 rounded border border-border bg-muted/40 p-4">
                                    <div className="flex items-center justify-between">
                                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Asset Risk Profile</span>
                                        <TrendingUp className="size-3.5 text-amber-400" />
                                    </div>
                                    <span className="text-base font-bold text-foreground uppercase tracking-tight">{riskLevel} ({overallRiskScore}/100)</span>
                                    <div className="h-1.5 w-full bg-border">
                                        <div className="h-full bg-amber-400" style={{ width: `${overallRiskScore}%` }} />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Sidebar */}
                <aside className="lg:col-span-4 space-y-6">
                    {/* Key Stats */}
                    <div className="bg-card border border-border shadow-lg transition-colors">
                        <div className="border-b border-border bg-muted/40 px-4 py-3">
                            <h3 className="text-xs font-bold uppercase tracking-widest text-foreground">Key Financial Indicators</h3>
                        </div>
                        <div className="divide-y divide-border font-mono">
                            {dynamicStats.map((row) => (
                                <div key={row.label} className="flex items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors">
                                    <span className="text-xs text-muted-foreground uppercase tracking-wider">{row.label}</span>
                                    <span className="text-sm font-bold text-foreground tracking-tighter">{row.value}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Price Action Sparklines */}
                    <div className="bg-card border border-border shadow-lg transition-colors">
                        <div className="border-b border-border bg-muted/40 px-4 py-3">
                            <h3 className="text-xs font-bold uppercase tracking-widest text-foreground">Quantitative Modeling Snapshot</h3>
                        </div>
                        <div className="p-4 space-y-6">
                            {[
                                { label: "Projected Alpha", valColor: alphaStr.startsWith("+") ? "text-q-risk-low" : alphaStr === "—" ? "text-muted-foreground" : "text-q-risk-high", val: alphaStr, fill: "h-2/3" },
                                { label: "Systemic Beta", valColor: Number(betaVal) > 1.2 ? "text-amber-400" : "text-q-risk-low", val: betaVal === "—" ? "—" : `${betaVal}x`, fill: "h-1/2" },
                                { label: "Risk Classification", valColor: "text-primary", val: riskLevel.toUpperCase(), fill: "h-full" },
                            ].map((item) => (
                                <div key={item.label} className="flex items-center justify-between group cursor-help">
                                    <div className="flex flex-col">
                                        <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">{item.label}</span>
                                        <span className={cn("text-lg font-bold tracking-tighter", item.valColor)}>{item.val}</span>
                                    </div>
                                    <div className="h-10 w-32 bg-q-risk-low/5 border-l border-q-risk-low/30 relative overflow-hidden group-hover:bg-q-risk-low/10 transition-colors">
                                        <div className={cn("absolute bottom-0 left-0 w-full bg-gradient-to-t from-q-risk-low/20 to-transparent transition-all duration-500", item.fill)} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </aside>
            </div>
        </div>
    )
}
