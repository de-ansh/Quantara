import { useState } from "react"
import {
    MessageSquare,
    Download,
    TrendingUp,
    TrendingDown,
    Minus,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { exportToCsv } from "@/lib/export"
import {
    ResponsiveContainer,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip
} from "recharts"
import { useQuery } from "@tanstack/react-query"
import apiClient from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { useSignals } from "@/hooks/useSignals"
import { useQuickTickers } from "@/hooks/useStockUniverse"
import { getCurrencySymbol } from "@/lib/currency"
import type { ApiSignal } from "@/types/api"

// Signals are per-ticker aggregates from 13F / Form 4 filings, not individual filers.
interface AccumulationData {
    ticker: string
    institutions: string
    change: string
    date: string
    type: "buy" | "sell"
}

interface InsiderData {
    ticker: string
    insiders: string
    buyVolume: string
    sellVolume: string
    net: string
    date: string
    type: "buy" | "sell"
}

interface SentimentPoint {
    time: string
    timestamp?: string
    social: number
    news: number
    volume?: number
    sentiment_label?: string
}

interface SentimentCurveResponse {
    ticker?: string | null
    period: string
    points: SentimentPoint[]
    current_social_score: number
    current_news_score: number
    sentiment_trend: "IMPROVING" | "STABLE" | "DETERIORATING"
}

const compactMoney = (value: number | undefined, ticker: string) =>
    value === undefined || value === null
        ? "—"
        : `${getCurrencySymbol(ticker)}${Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value)}`

export default function Signals() {
    const { data: liveSignals = [], isLoading: loadingLive } = useSignals({ refetchInterval: 10000 });
    const [selectedSentimentTicker, setSelectedSentimentTicker] = useState<string>("ALL");

    // Fetch dynamic time-bucketed Intraday Sentiment Curve
    const { data: sentimentCurve, isLoading: loadingSentiment } = useQuery<SentimentCurveResponse>({
        queryKey: ["signals", "sentiment-curve", selectedSentimentTicker],
        queryFn: async () => {
            const params: Record<string, string | number> = { hours: 8 }
            if (selectedSentimentTicker !== "ALL") {
                params.ticker = selectedSentimentTicker
            }
            const res = await apiClient.get("/signals/sentiment-curve", { params })
            return res.data
        }
    });

    // Fetch dynamic 13F Institutional Accumulation signals from DB
    const { data: institutionalSignals = [], isLoading: loadingInst } = useQuery<AccumulationData[]>({
        queryKey: ["signals", "institutional_buying"],
        queryFn: async () => {
            const res = await apiClient.get<{ signals: ApiSignal[] }>("/signals", { params: { signal_type: "institutional_buying", limit: 10 } })
            return res.data.signals.map((s): AccumulationData => {
                const changePct: number | undefined = s.metadata?.ownership_change_pct
                return {
                    ticker: s.ticker,
                    institutions: s.metadata?.num_institutions?.toLocaleString() ?? "—",
                    change: changePct === undefined ? "—" : `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`,
                    date: new Date(s.timestamp).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }),
                    type: (changePct ?? 0) >= 0 ? "buy" : "sell"
                }
            })
        }
    })

    // Fetch dynamic SEC Form 4 Insider transaction signals from DB
    const { data: insiderSignals = [], isLoading: loadingInsider } = useQuery<InsiderData[]>({
        queryKey: ["signals", "insider_buying"],
        queryFn: async () => {
            const res = await apiClient.get<{ signals: ApiSignal[] }>("/signals", { params: { signal_type: "insider_buying", limit: 10 } })
            return res.data.signals.map((s): InsiderData => {
                const net: number | undefined = s.metadata?.net_buying
                return {
                    ticker: s.ticker,
                    insiders: s.metadata?.num_insiders?.toLocaleString() ?? "—",
                    buyVolume: compactMoney(s.metadata?.buy_volume, s.ticker),
                    sellVolume: compactMoney(s.metadata?.sell_volume, s.ticker),
                    net: compactMoney(net, s.ticker),
                    date: new Date(s.timestamp).toISOString().split("T")[0],
                    type: (net ?? 0) >= 0 ? "buy" : "sell"
                }
            })
        }
    })

    const finalAccumulation = institutionalSignals
    const finalInsider = insiderSignals
    const finalSentiment = sentimentCurve?.points ?? []
    const universe = useQuickTickers()

    const isAnyLoading = loadingLive || loadingInst || loadingInsider || loadingSentiment

    const handleExportSignals = () => {
        const rows = [
            ...finalAccumulation.map((a) => ({
                signal_stream: "13F Institutional Accumulation",
                ticker: a.ticker,
                filers: a.institutions,
                ownership_change_pct: a.change,
                buy_volume: "",
                sell_volume: "",
                net_buying: "",
                date: a.date
            })),
            ...finalInsider.map((ins) => ({
                signal_stream: "Form 4 Insider Trading",
                ticker: ins.ticker,
                filers: ins.insiders,
                ownership_change_pct: "",
                buy_volume: ins.buyVolume,
                sell_volume: ins.sellVolume,
                net_buying: ins.net,
                date: ins.date
            }))
        ]
        exportToCsv("quantara_market_signals.csv", rows)
    }

    return (
        <div className="flex flex-col h-full bg-background overflow-hidden font-sans">
            {/* Header Info */}
            <div className="flex items-center justify-between px-6 py-3 border-b border-q-border bg-q-surface/50 shrink-0">
                <div className="flex items-center gap-6">
                    <div className="flex flex-col">
                        <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Market Context</span>
                        <div className="flex items-center gap-2">
                            <span className="text-sm font-black text-foreground uppercase tracking-tight">
                                {selectedSentimentTicker === "ALL" ? "All Tracked" : selectedSentimentTicker} Sentiment
                            </span>
                            <Badge variant="secondary" className="bg-q-risk-low/10 text-q-risk-low border-none h-4 px-1.5 text-[9px] font-black font-mono">
                                {sentimentCurve?.sentiment_trend ?? "—"}
                            </Badge>
                        </div>
                    </div>
                    <div className="h-8 w-px bg-q-border hidden sm:block" />
                    <div className="flex flex-col hidden sm:flex font-mono">
                        <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Active Signals</span>
                        <span className="text-sm font-black text-primary">{liveSignals.length}</span>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest mr-2 animate-pulse flex items-center gap-1.5 select-none">
                        <div className="size-1.5 rounded-full bg-q-risk-low animate-ping" /> 
                        {isAnyLoading ? "Synchronizing nodes..." : "Processing Live Feeds"}
                    </span>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={handleExportSignals}
                        title="Export signals to CSV"
                        className="h-8 w-8 text-muted-foreground hover:text-foreground"
                    >
                        <Download className="size-4" />
                    </Button>
                </div>
            </div>

            <main className="flex-1 p-4 grid grid-cols-12 gap-4 overflow-y-auto custom-scrollbar">
                {/* Accumulation */}
                <Card className="col-span-12 lg:col-span-6 flex flex-col bg-q-surface border-q-border overflow-hidden shadow-none">
                    <CardHeader className="p-4 border-b border-q-border bg-background/30 shrink-0">
                        <CardTitle className="text-[10px] font-black uppercase tracking-[0.15em] flex items-center gap-2 text-foreground">
                            <div className="size-1.5 rounded-full bg-primary" />
                            Top 13F Institutional Accumulation
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0 flex-1 overflow-auto custom-scrollbar">
                        <Table>
                            <TableHeader className="bg-q-surface font-mono sticky top-0 z-10 border-b border-q-border">
                                <TableRow className="hover:bg-transparent">
                                    <TableHead className="text-[9px] font-black uppercase h-8 px-4 text-muted-foreground">Ticker</TableHead>
                                    <TableHead className="text-[9px] font-black uppercase h-8 text-right text-muted-foreground">Institutions</TableHead>
                                    <TableHead className="text-[9px] font-black uppercase h-8 text-right text-muted-foreground">Ownership Δ</TableHead>
                                    <TableHead className="text-[9px] font-black uppercase h-8 text-right pr-4 text-muted-foreground">Date</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody className="text-[11px] font-mono">
                                {finalAccumulation.length === 0 && !loadingInst && (
                                    <TableRow className="hover:bg-transparent">
                                        <TableCell colSpan={4} className="px-4 py-6 text-center text-muted-foreground uppercase tracking-widest text-[10px]">
                                            No 13F accumulation signals yet
                                        </TableCell>
                                    </TableRow>
                                )}
                                {finalAccumulation.map((row, i) => (
                                    <TableRow key={i} className="border-q-border hover:bg-primary/5 transition-colors cursor-crosshair">
                                        <TableCell className="px-4 py-2 font-bold text-foreground uppercase tracking-tight">{row.ticker}</TableCell>
                                        <TableCell className="px-4 py-2 text-right text-foreground">{row.institutions}</TableCell>
                                        <TableCell className={cn("px-4 py-2 text-right font-black", row.type === "buy" ? "text-q-risk-low" : "text-q-risk-high")}>
                                            {row.change}
                                        </TableCell>
                                        <TableCell className="px-4 py-2 text-right font-black pr-4 text-foreground">{row.date}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>

                {/* Insiders */}
                <Card className="col-span-12 lg:col-span-6 flex flex-col bg-q-surface border-q-border overflow-hidden shadow-none">
                    <CardHeader className="p-4 border-b border-q-border bg-background/30 shrink-0">
                        <CardTitle className="text-[10px] font-black uppercase tracking-[0.15em] flex items-center gap-2 text-foreground">
                            <div className="size-1.5 rounded-full bg-amber-500" />
                            Recent Insider Buying Activity
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0 flex-1 overflow-auto custom-scrollbar">
                        <Table>
                            <TableHeader className="bg-q-surface font-mono sticky top-0 z-10 border-b border-q-border">
                                <TableRow className="hover:bg-transparent">
                                    <TableHead className="text-[9px] font-black uppercase h-8 px-4 text-muted-foreground">Ticker / Insiders</TableHead>
                                    <TableHead className="text-[9px] font-black uppercase h-8 text-right text-muted-foreground">Bought</TableHead>
                                    <TableHead className="text-[9px] font-black uppercase h-8 text-right text-muted-foreground">Sold</TableHead>
                                    <TableHead className="text-[9px] font-black uppercase h-8 text-right pr-4 text-muted-foreground">Net</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody className="text-[11px] font-mono">
                                {finalInsider.length === 0 && !loadingInsider && (
                                    <TableRow className="hover:bg-transparent">
                                        <TableCell colSpan={4} className="px-4 py-6 text-center text-muted-foreground uppercase tracking-widest text-[10px]">
                                            No Form 4 insider signals yet
                                        </TableCell>
                                    </TableRow>
                                )}
                                {finalInsider.map((row, i) => (
                                    <TableRow key={i} className="border-q-border hover:bg-primary/5 transition-colors cursor-crosshair">
                                        <TableCell className="px-4 py-2">
                                            <div className="font-bold text-foreground uppercase leading-none">{row.ticker}</div>
                                            <div className="text-[9px] text-muted-foreground uppercase font-black mt-0.5">{row.insiders} insiders · {row.date}</div>
                                        </TableCell>
                                        <TableCell className="px-4 py-2 text-right font-black text-foreground">{row.buyVolume}</TableCell>
                                        <TableCell className="px-4 py-2 text-right font-black text-foreground">{row.sellVolume}</TableCell>
                                        <TableCell className={cn("px-4 py-2 text-right font-black pr-4", row.type === "buy" ? "text-q-risk-low" : "text-q-risk-high")}>{row.net}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>

                {/* Signal Side Panel - Inlined for layout consistency across mobile/desktop */}
                <Card className="col-span-12 flex flex-col bg-q-surface border-q-border overflow-hidden shadow-none min-h-[400px]">
                    <CardHeader className="p-4 border-b border-q-border bg-background/30 shrink-0 flex items-center justify-between flex-row">
                        <CardTitle className="text-[10px] font-black uppercase tracking-[0.2em] flex items-center gap-2 text-foreground">
                            <div className="size-2 rounded-full bg-q-risk-high animate-pulse shadow-[0_0_8px_rgba(var(--q-risk-high),1)]" />
                            Live Signal Feed
                        </CardTitle>
                        {loadingLive && <span className="text-[9px] font-bold animate-pulse text-muted-foreground uppercase">Syncing...</span>}
                    </CardHeader>
                    <CardContent className="p-0 flex-1 overflow-y-auto custom-scrollbar font-mono text-[10px] leading-relaxed relative">
                        {loadingLive && liveSignals.length === 0 && (
                            <div className="absolute inset-0 bg-background/50 flex items-center justify-center z-10">
                                <span className="animate-pulse tracking-widest">CONNECTING_TO_NODES...</span>
                            </div>
                        )}
                        {!loadingLive && liveSignals.length === 0 && (
                            <div className="p-6 text-center text-muted-foreground uppercase tracking-widest">No signals detected yet</div>
                        )}
                        {liveSignals.map((item, i) => (
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
                    </CardContent>
                </Card>

                {/* Sentiment Analysis */}
                <Card className="col-span-12 flex flex-col bg-q-surface border-q-border overflow-hidden min-h-[400px] shadow-none">
                    <CardHeader className="px-4 py-2 border-b border-q-border bg-background/30 shrink-0 flex-row items-center justify-between space-y-0 flex-wrap gap-2">
                        <div className="flex flex-wrap items-center gap-4 sm:gap-6">
                            <CardTitle className="text-[10px] font-black uppercase tracking-[0.2em] flex items-center gap-2 text-foreground">
                                <MessageSquare className="size-3.5 text-primary" />
                                Quantitative Sentiment Analysis
                            </CardTitle>
                            <div className="flex items-center gap-3 text-[9px] font-black font-mono tracking-widest text-muted-foreground">
                                <div className="flex items-center gap-1.5">
                                    <div className="size-2 bg-primary rounded-full" />
                                    <span>SOCIAL: {sentimentCurve?.current_social_score?.toFixed(1) ?? "—"}%</span>
                                </div>
                                <div className="flex items-center gap-1.5">
                                    <div className="size-2 bg-q-risk-low rounded-full" />
                                    <span>NEWS: {sentimentCurve?.current_news_score?.toFixed(1) ?? "—"}%</span>
                                </div>
                                {sentimentCurve?.sentiment_trend && (
                                    <Badge
                                        variant="outline"
                                        className={cn(
                                            "text-[8px] font-mono font-bold uppercase border-none px-1.5 py-0",
                                            sentimentCurve.sentiment_trend === "IMPROVING" ? "text-green-400 bg-green-500/10" :
                                            sentimentCurve.sentiment_trend === "DETERIORATING" ? "text-rose-400 bg-rose-500/10" :
                                            "text-muted-foreground bg-muted"
                                        )}
                                    >
                                        {sentimentCurve.sentiment_trend === "IMPROVING" && <TrendingUp className="size-2.5 mr-1 inline" />}
                                        {sentimentCurve.sentiment_trend === "DETERIORATING" && <TrendingDown className="size-2.5 mr-1 inline" />}
                                        {sentimentCurve.sentiment_trend === "STABLE" && <Minus className="size-2.5 mr-1 inline" />}
                                        {sentimentCurve.sentiment_trend}
                                    </Badge>
                                )}
                            </div>
                        </div>
                        <div className="flex items-center gap-1.5">
                            <div className="flex items-center gap-1">
                                {["ALL", ...universe].map((t) => (
                                    <button
                                        key={t}
                                        onClick={() => setSelectedSentimentTicker(t)}
                                        className={cn(
                                            "px-2 py-0.5 text-[9px] font-mono font-bold rounded-sm border transition-colors",
                                            selectedSentimentTicker === t
                                                ? "bg-primary border-primary text-white"
                                                : "border-border text-muted-foreground hover:bg-muted hover:text-foreground"
                                        )}
                                    >
                                        {t.endsWith(".NS") ? `🇮🇳 ${t.replace(".NS", "")}` : t}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent className="p-4 flex-1 flex flex-col bg-background/5">
                        <div className="flex-1 min-h-[280px] relative">
                            {!loadingSentiment && finalSentiment.length === 0 && (
                                <div className="absolute inset-0 flex items-center justify-center font-mono text-[10px] text-muted-foreground uppercase tracking-widest z-10">
                                    No sentiment data in the last 8 hours
                                </div>
                            )}
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={finalSentiment} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="colorSocial" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.2} />
                                            <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                                        </linearGradient>
                                        <linearGradient id="colorNews" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="hsl(var(--q-risk-low))" stopOpacity={0.2} />
                                            <stop offset="95%" stopColor="hsl(var(--q-risk-low))" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--q-border))" opacity={0.3} />
                                    <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))', fontWeight: 'bold' }} />
                                    <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))', fontWeight: 'bold' }} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: 'hsl(var(--q-surface))', borderColor: 'hsl(var(--q-border))', fontSize: '10px', fontWeight: 'bold' }}
                                        formatter={(value, name) => [
                                            `${Number(value).toFixed(1)}%`,
                                            name === "social" ? "Social Mentions Index" : "News Polarity Index"
                                        ]}
                                    />
                                    <Area type="monotone" dataKey="social" stroke="hsl(var(--primary))" strokeWidth={2} fillOpacity={1} fill="url(#colorSocial)" />
                                    <Area type="monotone" dataKey="news" stroke="hsl(var(--q-risk-low))" strokeWidth={2} fillOpacity={1} fill="url(#colorNews)" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </CardContent>
                </Card>
            </main>

            <footer className="h-10 border-t border-border bg-background flex items-center justify-between px-6 shrink-0 z-20 transition-colors">
                <div className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground/60 flex items-center gap-6 font-mono">
                    <span className="flex items-center gap-2"><div className="size-2 bg-green-500 rounded-full" /> Feed Server: Active</span>
                    <span>LATENCY: 12ms</span>
                    <span>SESSION ID: #SF-2024-X492</span>
                </div>
                <p className="text-[9px] text-muted-foreground/60 uppercase font-bold tracking-widest italic">
                    © 2024 Quantara Financial Intelligence Platforms. Institutional Grade.
                </p>
            </footer>
        </div>
    )
}
