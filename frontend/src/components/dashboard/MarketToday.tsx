import DayChange from "@/components/DayChange"
import { useMarketStatus } from "@/hooks/useMarketStatus"
import { changePct, indexLevel } from "@/lib/format"

function Tile({ label, value, change, note }: { label: string; value: number | null | undefined; change?: number | null; note?: string }) {
    return (
        <div className="rounded-lg border border-border bg-card px-4 py-3">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="mt-1 flex items-baseline gap-2">
                <span className="text-lg font-semibold font-mono tabular-nums text-foreground">{indexLevel(value)}</span>
                <DayChange pct={change ?? null} className="text-xs" />
            </p>
            {note && <p className="mt-0.5 text-[11px] text-muted-foreground">{note}</p>}
        </div>
    )
}

const vixNote = (v: number | null | undefined) =>
    v === null || v === undefined ? undefined : v < 15 ? "Calm: small swings expected" : v < 22 ? "Normal swings expected" : "Nervous: big swings expected"

/** The benchmarks and volatility gauges, from the same snapshot as the header ticker. */
export default function MarketToday() {
    const { data, isError } = useMarketStatus()
    const india = data?.india_market
    const us = data?.us_market
    if (isError) return <p role="alert" className="text-sm text-muted-foreground">Market prices are unavailable right now.</p>
    return (
        <section aria-labelledby="market-today" className="space-y-2">
            <div className="flex items-baseline justify-between">
                <h2 id="market-today" className="text-sm font-semibold text-foreground">Market today</h2>
                {india && <p className="text-xs text-muted-foreground">NSE is {india.status === "OPEN" ? "open" : "closed"}</p>}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
                <Tile label={india?.index_name ?? "NIFTY 50"} value={india?.index_value} change={changePct(india?.index_change)} />
                <Tile label={india?.secondary_index_name ?? "SENSEX"} value={india?.secondary_index_value} change={changePct(india?.secondary_index_change)} />
                <Tile label="India VIX (volatility)" value={india?.vix} note={vixNote(india?.vix)} />
                <Tile label={us?.index_name ?? "S&P 500"} value={us?.index_value} change={changePct(us?.index_change)} />
                <Tile label="US VIX (volatility)" value={data?.vix?.value} change={data?.vix?.change_percent} note={vixNote(data?.vix?.value)} />
            </div>
        </section>
    )
}
