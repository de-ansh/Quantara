import { useState } from "react"
import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { Download } from "lucide-react"
import apiClient from "@/lib/api"
import { cn } from "@/lib/utils"
import { exportToCsv } from "@/lib/export"
import { signalSummary } from "@/hooks/useSignals"
import { useWatchlist } from "@/hooks/useWatchlist"
import { usePortfolios } from "@/hooks/usePortfolios"
import PageHeader from "@/components/PageHeader"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { Button } from "@/components/ui/button"
import type { ApiSignal } from "@/types/api"

const KINDS: { type: string; label: string }[] = [
    { type: "large_deal", label: "Bulk & block deals" },
    { type: "promoter_pledge", label: "Promoter pledges" },
    { type: "promoter_holding_change", label: "Promoter stake changes" },
    { type: "institutional_buying", label: "US institutions buying" },
    { type: "insider_buying", label: "US insider buying" },
]

/** Bullish, bearish or neither, read the same way the scores read it. */
const direction = (s: ApiSignal): "Positive" | "Negative" | "Neutral" => {
    const d = s.metadata?.direction
    if (d === "bearish") return "Negative"
    if (d === "bullish" || s.signal_type.endsWith("_buying")) return "Positive"
    return "Neutral"
}
const DOT = { Positive: "bg-q-risk-low", Negative: "bg-q-risk-high", Neutral: "bg-muted-foreground" } as const
const day = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })

/** Market events that often move a stock, newest first, filterable to what the user owns. */
export default function Signals() {
    const [kind, setKind] = useState<string | null>(null)
    const [mineOnly, setMineOnly] = useState(false)
    const { data: signals = [], isLoading, isError } = useQuery({
        queryKey: ["signals", "page"],
        queryFn: async () => (await apiClient.get<{ signals: ApiSignal[] }>("/signals", { params: { limit: 200 } })).data.signals ?? [],
        refetchInterval: 5 * 60_000, // the server collects signals hourly
    })
    const { data: watchlist = [] } = useWatchlist()
    const { data: portfolios = [] } = usePortfolios()
    const mine = new Set([...watchlist.map(w => w.ticker), ...portfolios.flatMap(p => p.positions.map(pos => pos.ticker))])

    const present = KINDS.filter(k => signals.some(s => s.signal_type === k.type)) // no chips for types with nothing to show
    const shown = signals.filter(s => (!kind || s.signal_type === kind) && (!mineOnly || mine.has(s.ticker)))

    const exportShown = () => exportToCsv("quantara_signals.csv", shown.map(s => ({
        date: day(s.timestamp), ticker: s.ticker, what_happened: signalSummary(s), direction: direction(s),
    })))

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto">
            <PageHeader
                title="Signals"
                description="Events that often move a stock: bulk and block deals, promoter pledges and promoter stake changes. Collected hourly from NSE."
                actions={<Button variant="outline" size="sm" onClick={exportShown} disabled={shown.length === 0} className="gap-1.5"><Download className="size-4" /> Export CSV</Button>}
            />

            <div className="flex flex-wrap items-center gap-2">
                <div role="group" aria-label="Signal type" className="flex flex-wrap gap-2">
                    {[{ type: null, label: "All" } as { type: string | null; label: string }, ...present].map(k => (
                        <button key={k.label} type="button" aria-pressed={kind === k.type} onClick={() => setKind(k.type)}
                            className={cn("rounded-full border px-3 py-1 text-sm", kind === k.type ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>
                            {k.label}
                        </button>
                    ))}
                </div>
                <label className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
                    <input type="checkbox" checked={mineOnly} onChange={e => setMineOnly(e.target.checked)} className="accent-primary" />
                    Only stocks I hold or watch
                </label>
            </div>

            <Panel id="signal-list" title={isLoading ? "Signals" : `${shown.length} signal${shown.length === 1 ? "" : "s"}`}
                description="Positive or negative is how the event usually reads for the stock, not a prediction">
                {isLoading ? <PanelSkeleton rows={6} /> : isError ? <PanelMessage alert>Couldn't load signals.</PanelMessage> : shown.length === 0 ? (
                    <PanelMessage>{mineOnly ? "Nothing recent on the stocks you hold or watch." : "No signals yet."}</PanelMessage>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-xs text-muted-foreground text-left">
                                    <th scope="col" className="px-4 py-2 font-medium">Date</th>
                                    <th scope="col" className="px-2 py-2 font-medium">Stock</th>
                                    <th scope="col" className="px-2 py-2 font-medium">What happened</th>
                                    <th scope="col" className="px-4 py-2 font-medium">Reads as</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border">
                                {shown.map(s => {
                                    const dir = direction(s)
                                    return (
                                        <tr key={s.id} className="hover:bg-muted/40">
                                            <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">{day(s.timestamp)}</td>
                                            <th scope="row" className="px-2 py-2 text-left font-medium whitespace-nowrap">
                                                <Link to={`/research/${s.ticker}`} className="text-foreground hover:text-primary">{s.ticker}</Link>
                                                {mine.has(s.ticker) && <span className="ml-1.5 text-xs font-normal text-muted-foreground">(yours)</span>}
                                            </th>
                                            <td className="px-2 py-2 text-foreground">{signalSummary(s)}</td>
                                            <td className="px-4 py-2 whitespace-nowrap">
                                                <span className="flex items-center gap-1.5"><span className={cn("size-1.5 rounded-full", DOT[dir])} aria-hidden="true" />{dir}</span>
                                            </td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </Panel>
        </div>
    )
}
