import { useQuery } from "@tanstack/react-query"
import apiClient from "@/lib/api"

interface Technicals {
    rsi_14: number | null; sma_20: number | null; sma_50: number | null; sma_200: number | null
    macd: number | null; macd_signal: number | null; high_1y: number; low_1y: number; pct_from_high: number | null; notes: string[]
}

const shown = (n: number | null, suffix = "") => (n === null ? "—" : `${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}${suffix}`)

/** Technical indicators from daily closes; hidden when there isn't enough history. */
export default function TechnicalsCard({ ticker }: { ticker: string }) {
    const { data } = useQuery({
        queryKey: ["technicals", ticker],
        queryFn: async () => (await apiClient.get<Technicals>(`/stocks/${ticker}/technicals`)).data,
        staleTime: 15 * 60 * 1000,
        retry: false,
    })
    if (!data?.notes) return null
    const stats = [
        ["RSI (14)", shown(data.rsi_14)], ["20-day avg", shown(data.sma_20)], ["50-day avg", shown(data.sma_50)], ["200-day avg", shown(data.sma_200)],
        ["MACD", shown(data.macd)], ["MACD signal", shown(data.macd_signal)], ["1-year range", `${shown(data.low_1y)} – ${shown(data.high_1y)}`], ["From 1-year high", shown(data.pct_from_high, "%")],
    ]
    return (
        <section aria-label="Technical indicators" className="mt-4 mb-4 bg-card border border-border rounded-lg p-4">
            <h2 className="text-sm font-semibold text-foreground mb-3">Technicals</h2>
            <dl className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {stats.map(([label, value]) => (
                    <div key={label}>
                        <dt className="text-xs text-muted-foreground">{label}</dt>
                        <dd className="font-mono text-sm font-bold text-foreground">{value}</dd>
                    </div>
                ))}
            </dl>
            <p className="mt-3 text-xs text-muted-foreground">{data.notes.join(" ")}</p>
        </section>
    )
}
