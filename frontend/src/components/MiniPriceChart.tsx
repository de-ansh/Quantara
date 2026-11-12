import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from "recharts"
import api from "@/lib/api"
import { cleanTickerDisplay, getCurrencySymbol } from "@/lib/currency"

interface PriceHistory { points: { date: string; close: number }[]; change_pct: number }

/** Six-month price line for a stock the chat answer looked up; links to the stock page. */
export default function MiniPriceChart({ ticker }: { ticker: string }) {
    const { data, isError } = useQuery({
        queryKey: ["priceHistory", ticker, "6M"],
        queryFn: async () => (await api.get<PriceHistory>(`/stocks/${ticker}/history`, { params: { range: "6M" } })).data,
        staleTime: 15 * 60 * 1000,
        retry: false,
    })
    if (isError || (data && data.points.length < 2)) return null
    const up = (data?.change_pct ?? 0) >= 0
    const color = up ? "#22c55e" : "#ef4444"
    const sym = getCurrencySymbol(ticker)
    return (
        <figure aria-label={`${cleanTickerDisplay(ticker)} price, last 6 months`} className="mt-2 rounded-md border border-border bg-background/60 p-2">
            <figcaption className="flex items-center justify-between text-[11px]">
                <Link to={`/research/${ticker}`} className="font-mono font-bold text-foreground hover:text-primary">{cleanTickerDisplay(ticker)}</Link>
                {data && <span className={up ? "text-green-500" : "text-red-500"}>{up ? "+" : ""}{data.change_pct.toFixed(2)}% in 6 months</span>}
            </figcaption>
            <div className="h-20">
                {data ? (
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={data.points} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                            <YAxis hide domain={["auto", "auto"]} />
                            <Tooltip
                                contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", fontSize: "11px" }}
                                labelFormatter={(_, p) => (p?.[0] ? new Date(`${p[0].payload.date}T00:00:00Z`).toLocaleDateString() : "")}
                                formatter={(v) => [`${sym}${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`, "Close"]}
                            />
                            <Area type="monotone" dataKey="close" stroke={color} strokeWidth={1.5} fill={color} fillOpacity={0.12} isAnimationActive={false} />
                        </AreaChart>
                    </ResponsiveContainer>
                ) : <p className="h-full flex items-center justify-center text-[11px] text-muted-foreground">Loading chart…</p>}
            </div>
        </figure>
    )
}
