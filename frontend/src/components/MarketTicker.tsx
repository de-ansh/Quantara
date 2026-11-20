import DayChange from "@/components/DayChange"
import { useMarketStatus } from "@/hooks/useMarketStatus"
import { changePct, indexLevel } from "@/lib/format"

function Quote({ name, value, change }: { name: string; value: number | null | undefined; change: string | null | undefined }) {
    return (
        <span className="flex items-baseline gap-1.5 whitespace-nowrap">
            <span className="font-medium text-foreground">{name}</span>
            <span className="font-mono tabular-nums text-foreground">{indexLevel(value)}</span>
            <DayChange pct={changePct(change)} className="text-[11px]" />
        </span>
    )
}

/** Header strip: the benchmarks with today's move, and whether each market is trading. */
export default function MarketTicker() {
    const { data } = useMarketStatus()
    const india = data?.india_market
    const us = data?.us_market
    if (!india && !us) return null
    return (
        <div className="hidden xl:flex items-center gap-4 text-xs border border-border rounded-md px-3 py-1.5" aria-label="Market indices">
            {india && (
                <>
                    <span className="text-[11px] text-muted-foreground">NSE {india.status === "OPEN" ? "open" : "closed"}</span>
                    <Quote name={india.index_name} value={india.index_value} change={india.index_change} />
                    {india.secondary_index_name && (
                        <Quote name={india.secondary_index_name} value={india.secondary_index_value} change={india.secondary_index_change} />
                    )}
                </>
            )}
            {us && (
                <>
                    <span className="h-3 w-px bg-border" aria-hidden="true" />
                    <Quote name={us.index_name} value={us.index_value} change={us.index_change} />
                </>
            )}
        </div>
    )
}
