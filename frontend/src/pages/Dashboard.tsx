import {
    Info,
    ArrowUpRight,
    ArrowUp,
    ArrowDown,
    MoveRight,
    Filter,
    AlertTriangle,
    Star,
} from "lucide-react"
import { Link } from "react-router-dom"
import { useWatchlist } from "@/hooks/useWatchlist"
import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { useSignals } from "@/hooks/useSignals"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useRecommendations } from "@/hooks/useRecommendations"
import { useQuery } from "@tanstack/react-query"
import apiClient from "@/lib/api"

interface StatItem {
    label: string
    value: string
    trend?: string
    trendStatus?: "up" | "down"
    subtext?: string
    isGauge?: boolean
    isBadge?: boolean
    isSparkline?: boolean
    isVol?: boolean
}

export default function Dashboard() {
    const { data: watchlist = [], isLoading: loadingWatchlist } = useWatchlist()
    const { data: opportunities = [], isLoading: isLoadingOpportunities } = useRecommendations();
    const { data: liveSignals = [], isLoading: isLoadingSignals } = useSignals({ refetchInterval: 5000 });

    const { data: marketData } = useQuery({
        queryKey: ["marketStatus"],
        queryFn: async () => {
            const { data } = await apiClient.get("/market/status")
            return data
        },
        refetchInterval: 5000,
    })

    const { data: profile } = useQuery({
        queryKey: ["userProfile"],
        queryFn: async () => {
            const { data } = await apiClient.get("/users/me")
            return data
        },
    })

    const avgRisk = opportunities.length
        ? Math.round(opportunities.reduce((sum, o) => sum + Number(o.risk), 0) / opportunities.length)
        : 0
    const spxChange: string | undefined = marketData?.us_market?.index_change
    const vix: number | undefined = marketData?.vix?.value
    const vixPct: number | undefined = marketData?.vix?.change_percent

    const currentStats: StatItem[] = [
        {
            label: "Avg Opportunity Risk",
            value: opportunities.length ? String(avgRisk) : "--",
            subtext: `${opportunities.length} ranked assets`,
            isGauge: true
        },
        {
            label: "Recommended Risk Band",
            value: (profile?.risk_level ?? "Moderate").toUpperCase(),
            subtext: profile?.volatility_tolerance != null
                ? `Vol tolerance: ${profile.volatility_tolerance}`
                : "Complete risk onboarding",
            isBadge: true
        },
        {
            label: "S&P 500 Session Move",
            value: spxChange ?? "--",
            trendStatus: spxChange?.startsWith("-") ? "down" : "up",
            isSparkline: true
        },
        {
            label: "Volatility Snapshot",
            value: vix !== undefined ? `VIX: ${vix}` : "VIX: --",
            trend: vixPct !== undefined ? `${vixPct >= 0 ? "+" : ""}${vixPct}%` : undefined,
            trendStatus: vixPct !== undefined && vixPct < 0 ? "down" : "up",
            isVol: true
        }
    ]
    // VIX 10..40 mapped onto the 6-segment meter
    const vixSegments = vix !== undefined ? Math.min(6, Math.max(1, Math.ceil(((vix - 10) / 30) * 6))) : 0

    const latestAlert = marketData?.alerts?.[0]

    return (
        <div className="p-4 space-y-4 flex flex-col h-full bg-background overflow-hidden">
            {/* Macro Alert Banner */}
            {latestAlert && (
                <div className="flex items-center gap-3 px-4 py-2 border border-amber-500/25 bg-amber-500/5 text-amber-500 text-[10px] font-mono uppercase tracking-wider shrink-0 rounded-sm">
                    <span className="flex items-center gap-1.5 shrink-0 font-bold">
                        <AlertTriangle className="size-3.5 animate-pulse" />
                        MACRO_ALERT
                    </span>
                    <span className="h-3 w-[1px] bg-amber-500/30 shrink-0" />
                    <span className="truncate">{latestAlert.time} - {latestAlert.text}</span>
                </div>
            )}

            {/* KPI Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 shrink-0">
                {currentStats.map((stat, i) => (
                    <Card key={i} className="bg-q-surface border-q-border flex flex-col justify-between min-h-[140px] shadow-none">
                        <CardHeader className="p-4 pb-2 flex-row items-start justify-between space-y-0">
                            <CardTitle className="text-[11px] font-bold text-muted-foreground uppercase tracking-widest leading-none">{stat.label}</CardTitle>
                            <Info className="size-3 text-muted-foreground" />
                        </CardHeader>
                        <CardContent className="p-4 pt-0">
                            {stat.isGauge && (
                                <div className="flex items-end justify-between">
                                    <div className="relative flex items-center justify-center size-16">
                                        <svg className="size-full -rotate-90" viewBox="0 0 36 36">
                                            <circle cx="18" cy="18" r="16" fill="none" className="stroke-muted" strokeWidth="3" />
                                            <circle cx="18" cy="18" r="16" fill="none" className="stroke-primary" strokeWidth="3" strokeDasharray={`${avgRisk}, 100`} />
                                        </svg>
                                        <span className="absolute text-lg font-bold tracking-tighter text-foreground">{stat.value}</span>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-muted-foreground text-[9px] font-medium uppercase tracking-tight">{stat.subtext}</div>
                                    </div>
                                </div>
                            )}

                            {stat.isBadge && (
                                <>
                                    <div className="text-lg font-bold text-foreground leading-tight mb-2">{stat.value}</div>
                                    <div className="flex items-center gap-2">
                                        <Badge variant="outline" className="bg-q-risk-low/10 text-q-risk-low border-q-risk-low/20 text-[9px] font-black tracking-widest py-0">LOCKED</Badge>
                                        <span className="text-muted-foreground text-[10px] uppercase font-bold tracking-tighter">{stat.subtext}</span>
                                    </div>
                                </>
                            )}

                            {stat.isSparkline && (
                                <>
                                    <div className="flex items-end gap-2 mb-2">
                                        <span className="text-2xl font-bold leading-none tracking-tight text-foreground">{stat.value}</span>
                                        {stat.trendStatus === "down"
                                            ? <ArrowDown className="text-q-risk-high size-4" />
                                            : <ArrowUpRight className="text-q-risk-low size-4" />}
                                    </div>
                                    <div className="text-muted-foreground text-[9px] font-medium uppercase tracking-tight">vs prev close</div>
                                </>
                            )}

                            {stat.isVol && (
                                <>
                                    <div className="flex justify-between items-baseline">
                                        <div className="text-lg font-mono tracking-tighter font-black text-foreground">{stat.value}</div>
                                        <div className={cn("text-xs font-bold", stat.trendStatus === "down" ? "text-q-risk-low" : "text-q-risk-high")}>{stat.trend}</div>
                                    </div>
                                    <div className="mt-3 flex gap-1 h-1">
                                        {Array.from({ length: 6 }, (_, idx) => (
                                            <div key={idx} className={cn("flex-1", idx < vixSegments ? (idx < 2 ? "bg-q-risk-low" : idx < 4 ? "bg-amber-500" : "bg-q-risk-high") : "bg-q-border")} />
                                        ))}
                                    </div>
                                    <div className="flex justify-between mt-1 text-[9px] text-muted-foreground uppercase font-black tracking-widest">
                                        <span>Low</span>
                                        <span>High</span>
                                    </div>
                                </>
                            )}
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Watchlist */}
            <section aria-labelledby="watchlist-heading" className="bg-q-surface border border-q-border shrink-0">
                <div className="px-4 py-2 border-b border-q-border flex items-center justify-between">
                    <h2 id="watchlist-heading" className="text-xs font-bold uppercase tracking-wider text-foreground flex items-center gap-2">
                        <Star className="size-3.5 text-amber-400 fill-current" /> Watchlist
                    </h2>
                    <Link to="/explorer" className="text-[10px] font-bold uppercase tracking-wider text-primary hover:underline">
                        Browse stocks
                    </Link>
                </div>
                {watchlist.length === 0 ? (
                    <p className="px-4 py-3 text-[11px] text-muted-foreground">
                        {loadingWatchlist ? "Loading..." : "Star a stock in Research Explorer or Stock Detail to pin it here."}
                    </p>
                ) : (
                    <ul className="flex gap-2 overflow-x-auto custom-scrollbar p-3">
                        {watchlist.map(w => (
                            <li key={w.ticker} className="shrink-0">
                                <Link
                                    to={`/research/${w.ticker}`}
                                    className="flex flex-col gap-0.5 min-w-[130px] border border-q-border hover:border-primary/60 bg-background/40 px-3 py-2 rounded-sm transition-colors"
                                >
                                    <span className="flex items-center justify-between gap-2 font-mono">
                                        <span className="text-xs font-black text-foreground">{w.ticker}</span>
                                        <span className={cn("text-[9px] font-bold", w.status === "up" ? "text-q-risk-low" : w.status === "down" ? "text-q-risk-high" : "text-muted-foreground")}>
                                            {w.alpha}
                                        </span>
                                    </span>
                                    <span className="text-sm font-bold font-mono text-foreground">{w.price}</span>
                                    <span className="text-[9px] uppercase text-muted-foreground font-bold">Risk {w.risk.toFixed(0)} · {w.signal}</span>
                                </Link>
                            </li>
                        ))}
                    </ul>
                )}
            </section>

            <div className="flex flex-1 gap-4 overflow-hidden min-h-0">
                {/* Opportunities Table */}
                <section className="flex-1 min-w-0 bg-q-surface border border-q-border flex flex-col overflow-hidden">
                    <div className="px-4 py-3 border-b border-q-border flex items-center justify-between bg-q-surface shrink-0">
                        <h2 className="text-xs font-bold uppercase tracking-wider text-foreground">Top Risk-Aligned Opportunities</h2>
                        <div className="flex items-center gap-4 text-xs">
                            <span className="text-muted-foreground hidden sm:inline font-medium text-[10px] uppercase tracking-widest">Filters: Active</span>
                            <Filter className="size-4 text-muted-foreground cursor-pointer hover:text-foreground transition-colors" />
                        </div>
                    </div>
                    <div className="flex-1 overflow-auto custom-scrollbar relative">
                        {isLoadingOpportunities && (
                            <div className="absolute inset-0 bg-background/50 flex items-center justify-center z-20">
                                <div className="text-[10px] font-black tracking-widest uppercase animate-pulse">Synchronizing_Engine...</div>
                            </div>
                        )}
                        <Table>
                            <TableHeader className="bg-q-surface sticky top-0 z-10">
                                <TableRow className="border-q-border hover:bg-transparent">
                                    <TableHead className="text-[10px] font-black uppercase tracking-widest h-10 px-4">Ticker</TableHead>
                                    <TableHead className="text-[10px] font-black uppercase tracking-widest h-10 text-right">Risk Score</TableHead>
                                    <TableHead className="text-[10px] font-black uppercase tracking-widest h-10">Research Score</TableHead>
                                    <TableHead className="text-[10px] font-black uppercase tracking-widest h-10 text-center">Signal</TableHead>
                                    <TableHead className="text-[10px] font-black uppercase tracking-widest h-10 text-right">Exp. Return</TableHead>
                                    <TableHead className="text-[10px] font-black uppercase tracking-widest h-10 text-center">Alignment</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody className="text-xs">
                                {opportunities.map((row) => (
                                    <TableRow key={row.ticker} className="border-q-border hover:bg-primary/5 cursor-pointer group transition-colors">
                                        <TableCell className="px-4 py-3 font-bold text-foreground">
                                            {row.ticker} <span className="text-[10px] font-normal text-muted-foreground ml-1 hidden lg:inline">{row.name}</span>
                                        </TableCell>
                                        <TableCell className="px-4 py-3 text-right font-mono text-foreground font-bold">{row.risk}</TableCell>
                                        <TableCell className="px-4 py-3 min-w-[120px]">
                                            <div className="flex items-center gap-2">
                                                <div className="flex-1 h-1.5 bg-q-border rounded-full overflow-hidden">
                                                    <div className="h-full bg-primary transition-all duration-700 shadow-[0_0_8px_rgba(var(--primary),0.5)]" style={{ width: `${row.research}%` }} />
                                                </div>
                                                <span className="w-4 text-right font-mono text-[10px] text-muted-foreground font-bold">{row.research}</span>
                                            </div>
                                        </TableCell>
                                        <TableCell className="px-4 py-3">
                                            <div className="flex justify-center">
                                                {row.signal === "up" && <ArrowUp className="text-q-risk-low size-4" />}
                                                {row.signal === "up-right" && <ArrowUpRight className="text-q-risk-low size-4" />}
                                                {row.signal === "right" && <MoveRight className="text-muted-foreground size-4" />}
                                                {row.signal === "down" && <ArrowDown className="text-q-risk-high size-4" />}
                                            </div>
                                        </TableCell>
                                        <TableCell className={cn("px-4 py-3 text-right font-mono font-bold", row.return.startsWith("+") ? "text-q-risk-low" : "text-q-risk-high")}>
                                            {row.return}
                                        </TableCell>
                                        <TableCell className="px-4 py-3 text-center">
                                            <Badge variant="secondary" className="bg-primary/10 text-primary border-none font-black text-[10px] tracking-tight">{row.alignment}</Badge>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                </section>

                {/* Signal Side Panel */}
                <aside className="w-80 bg-q-surface border border-q-border flex flex-col hidden xl:flex overflow-hidden">
                    <div className="p-4 border-b border-q-border bg-q-surface shrink-0">
                        <h2 className="text-xs font-bold uppercase tracking-[0.2em] text-foreground flex items-center gap-2">
                            <div className="size-2 rounded-full bg-q-risk-high animate-pulse shadow-[0_0_8px_rgba(var(--q-risk-high),1)]" />
                            Live Signal Feed
                        </h2>
                    </div>
                    <div className="flex-1 overflow-y-auto custom-scrollbar font-mono text-[10px] leading-relaxed p-0 relative">
                        {isLoadingSignals && (
                            <div className="absolute inset-0 bg-background/50 flex items-center justify-center z-20">
                                <div className="text-[10px] font-black tracking-widest uppercase animate-pulse">Listening_to_Market...</div>
                            </div>
                        )}
                        {(liveSignals.length > 0 ? liveSignals : (marketData?.alerts ?? []) as typeof liveSignals).map((item, i) => (
                            <div key={i} className="p-3 border-b border-q-border/30 hover:bg-primary/5 transition-colors cursor-help">
                                <div className="flex justify-between mb-1">
                                    <span className="text-muted-foreground font-bold">{item.time}</span>
                                    <span className={cn(
                                        "font-black uppercase tracking-[0.05em]",
                                        item.type === "BULLISH" ? "text-q-risk-low" :
                                            item.type === "BEARISH" ? "text-q-risk-high" :
                                                item.type === "VOLATILITY" ? "text-amber-500" : "text-muted-foreground"
                                    )}>[{item.type}]</span>
                                </div>
                                <p className="text-foreground uppercase tracking-tight leading-tight font-medium">{item.text}</p>
                            </div>
                        ))}
                    </div>
                    <div className="p-4 bg-background border-t border-q-border shrink-0">
                        <div className="flex items-center gap-3">
                            <span className="text-primary text-[10px] font-black uppercase tracking-widest">Engine Ready</span>
                            <div className="h-1 flex-1 bg-q-border overflow-hidden rounded-full">
                                <div className="h-full bg-primary w-2/3 animate-pulse" />
                            </div>
                        </div>
                    </div>
                </aside>
            </div>
        </div>
    )
}
