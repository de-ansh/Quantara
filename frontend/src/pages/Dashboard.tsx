import {
    TrendingUp,
    Info,
    ArrowUpRight,
    ArrowUp,
    ArrowDown,
    MoveRight,
    Filter,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

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

interface OpportunityItem {
    ticker: string
    name: string
    risk: string
    research: number
    signal: "up" | "up-right" | "right" | "down"
    return: string
    alignment: string
}

interface SignalItem {
    time: string
    type: "BULLISH" | "NEUTRAL" | "BEARISH" | "VOLATILITY"
    text: string
}

const stats: StatItem[] = [
    {
        label: "Portfolio Risk Score",
        value: "72",
        trend: "+2.4%",
        trendStatus: "up",
        isGauge: true
    },
    {
        label: "Recommended Risk Band",
        value: "MODERATE - STEADY",
        subtext: "Confidence: 94%",
        isBadge: true
    },
    {
        label: "Macro Risk Indicator",
        value: "1.2%",
        isSparkline: true
    },
    {
        label: "Volatility Snapshot",
        value: "VIX: 14.22",
        trend: "-0.4%",
        isVol: true
    }
]

const opportunities: OpportunityItem[] = [
    { ticker: "AAPL", name: "Apple Inc.", risk: "12.4", research: 85, signal: "up", return: "+4.22%", alignment: "92.0%" },
    { ticker: "MSFT", name: "Microsoft Corp.", risk: "18.1", research: 90, signal: "up-right", return: "+3.80%", alignment: "88.5%" },
    { ticker: "NVDA", name: "NVIDIA Corp.", risk: "31.5", research: 95, signal: "up", return: "+8.41%", alignment: "96.2%" },
    { ticker: "AMZN", name: "Amazon.com Inc.", risk: "22.8", research: 78, signal: "right", return: "+0.50%", alignment: "75.1%" },
    { ticker: "TSLA", name: "Tesla Inc.", risk: "45.0", research: 65, signal: "down", return: "-1.20%", alignment: "42.3%" },
    { ticker: "GOOGL", name: "Alphabet Inc.", risk: "15.2", research: 82, signal: "up-right", return: "+2.15%", alignment: "89.4%" },
]

const signals: SignalItem[] = [
    { time: "14:02:45", type: "BULLISH", text: "FED RATE UPDATE: STATEMENTS SUGGEST HAWKISH PAUSE. TECH SECTOR INFLOWS DETECTED." },
    { time: "13:58:12", type: "NEUTRAL", text: "AAPL EARNINGS CALL PREP: ANALYST CONSENSUS SHIFTING TO OVERWEIGHT FOR Q3." },
    { time: "13:45:01", type: "BEARISH", text: "CRUDE OIL FUTURES (WTI) BREAKING BELOW $75 SUPPORT. ENERGY EXPOSURE WARNING." },
    { time: "13:30:44", type: "VOLATILITY", text: "VIX SPIKE DETECTED (+1.2%). INDEX PROTECTIVE PUT VOLUME INCREASING." },
    { time: "13:12:10", type: "BULLISH", text: "NVDA UPGRADE FROM GOLDMAN SACHS. PT RAISED TO $1,200. H100 DEMAND STABLE." },
]

export default function Dashboard() {
    return (
        <div className="p-4 space-y-4 flex flex-col h-full bg-background overflow-hidden">
            {/* KPI Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 shrink-0">
                {stats.map((stat, i) => (
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
                                            <circle cx="18" cy="18" r="16" fill="none" className="stroke-primary" strokeWidth="3" strokeDasharray="72, 100" />
                                        </svg>
                                        <span className="absolute text-lg font-bold tracking-tighter text-foreground">{stat.value}</span>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-q-risk-low text-xs font-bold">{stat.trend}</div>
                                        <div className="text-muted-foreground text-[9px] font-medium uppercase tracking-tight">vs prev session</div>
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
                                        <ArrowUpRight className="text-q-risk-low size-4" />
                                    </div>
                                    <div className="w-full h-8 opacity-50">
                                        <svg className="w-full h-full" viewBox="0 0 100 20">
                                            <polyline fill="none" points="0,15 10,12 20,18 30,10 40,14 50,5 60,8 70,2 80,10 90,5 100,8" className="stroke-primary" strokeWidth="1.5" />
                                        </svg>
                                    </div>
                                </>
                            )}

                            {stat.isVol && (
                                <>
                                    <div className="flex justify-between items-baseline">
                                        <div className="text-lg font-mono tracking-tighter font-black text-foreground">{stat.value}</div>
                                        <div className="text-q-risk-high text-xs font-bold">{stat.trend}</div>
                                    </div>
                                    <div className="mt-3 flex gap-1 h-1">
                                        {[1, 1, 1, 1, 0, 0].map((v, idx) => (
                                            <div key={idx} className={cn("flex-1", v ? "bg-q-risk-low" : "bg-q-border")} />
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
                    <div className="flex-1 overflow-auto custom-scrollbar">
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
                    <div className="flex-1 overflow-y-auto custom-scrollbar font-mono text-[10px] leading-relaxed p-0">
                        {signals.map((item, i) => (
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
