import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import DayChange from "@/components/DayChange"
import { cn } from "@/lib/utils"
import { getCurrencySymbol } from "@/lib/currency"
import api from "@/lib/api"

const RANGES = ["1M", "6M", "1Y", "5Y"] as const
type Range = (typeof RANGES)[number]

interface PriceHistory {
    ticker: string
    range: Range
    points: { date: string; close: number }[]
    change_pct: number
}

export default function PriceChart({ ticker }: { ticker: string }) {
    const [range, setRange] = useState<Range>("1Y")
    const { data, isLoading, isError } = useQuery({
        queryKey: ["priceHistory", ticker, range],
        queryFn: async () => (await api.get<PriceHistory>(`/stocks/${ticker}/history`, { params: { range } })).data,
        enabled: !!ticker,
        staleTime: 15 * 60 * 1000,
    })
    const sym = getCurrencySymbol(ticker)
    const up = (data?.change_pct ?? 0) >= 0
    const color = up ? "hsl(var(--q-positive))" : "hsl(var(--q-risk))"
    const fmtDate = (d: string) =>
        new Date(`${d}T00:00:00Z`).toLocaleDateString(undefined, range === "5Y" || range === "1Y" ? { month: "short", year: "2-digit" } : { month: "short", day: "numeric" })

    return (
        <Card className="bg-card border-border shadow-none mb-6">
            <CardHeader className="p-4 pb-2 flex-row items-center justify-between space-y-0">
                <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-3">
                    Price History
                    {data && <DayChange pct={data.change_pct} className="text-xs normal-case" />}
                    {data && <span className="text-[10px] text-muted-foreground font-normal normal-case">over {range}</span>}
                </CardTitle>
                <div role="group" aria-label="Chart range" className="flex border border-border rounded-sm overflow-hidden">
                    {RANGES.map(r => (
                        <button
                            key={r}
                            type="button"
                            onClick={() => setRange(r)}
                            aria-pressed={r === range}
                            className={cn("px-2.5 py-1 text-[10px] font-bold font-mono", r === range ? "bg-primary text-white" : "hover:bg-muted text-muted-foreground")}
                        >
                            {r}
                        </button>
                    ))}
                </div>
            </CardHeader>
            <CardContent className="p-4 pt-0 h-64">
                {isLoading ? (
                    <div className="h-full flex items-center justify-center text-xs text-muted-foreground font-mono">Loading chart…</div>
                ) : isError || !data ? (
                    <div className="h-full flex items-center justify-center text-xs text-muted-foreground">No price history available for {ticker}.</div>
                ) : (
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={data.points} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                            <defs>
                                <linearGradient id="priceFill" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor={color} stopOpacity={0.25} />
                                    <stop offset="100%" stopColor={color} stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} vertical={false} />
                            <XAxis dataKey="date" tickFormatter={fmtDate} minTickGap={40} axisLine={false} tickLine={false}
                                tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
                            <YAxis domain={["auto", "auto"]} width={60} axisLine={false} tickLine={false}
                                tickFormatter={(v) => `${sym}${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                                tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
                            <Tooltip
                                contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", fontSize: "11px" }}
                                labelFormatter={(d) => new Date(`${d}T00:00:00Z`).toLocaleDateString()}
                                formatter={(v) => [`${sym}${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, "Close"]}
                            />
                            <Area type="monotone" dataKey="close" stroke={color} strokeWidth={2} fill="url(#priceFill)" isAnimationActive={false} />
                        </AreaChart>
                    </ResponsiveContainer>
                )}
            </CardContent>
        </Card>
    )
}
