import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import apiClient from "@/lib/api"
import { cn } from "@/lib/utils"

interface Outcome {
    verdict: "Buy" | "Hold" | "Avoid"
    count: number
    avg_return_pct: number
    vs_all_rated_pct: number
    share_that_rose_pct: number
}

interface TrackRecord {
    risk_level: string
    horizon_days: number
    tracking_since: string | null
    first_results_on: string | null
    all_rated_avg_return_pct: number | null
    verdicts: Outcome[]
}

const HORIZONS = [30, 90, 180] as const
const pct = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`
const day = (iso: string) => new Date(iso).toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" })

/** How stocks given each verdict did afterwards, so the verdicts can be trusted or retuned on evidence. */
export default function TrackRecordCard() {
    const [horizon, setHorizon] = useState<(typeof HORIZONS)[number]>(30)
    const { data, isLoading, isError } = useQuery({
        queryKey: ["trackRecord", horizon],
        queryFn: async () =>
            (await apiClient.get<TrackRecord>("/recommendations/track-record", { params: { horizon_days: horizon } })).data,
    })

    return (
        <section aria-labelledby="track-record-heading" className="bg-q-surface border border-q-border shrink-0">
            <div className="px-4 py-2 border-b border-q-border flex items-center justify-between gap-2">
                <h2 id="track-record-heading" className="text-xs font-bold uppercase tracking-wider text-foreground">
                    Verdict track record{data ? ` · ${data.risk_level}` : ""}
                </h2>
                <div role="group" aria-label="Time after the verdict" className="flex gap-1">
                    {HORIZONS.map(h => (
                        <button
                            key={h}
                            type="button"
                            aria-pressed={horizon === h}
                            onClick={() => setHorizon(h)}
                            className={cn(
                                "px-2 py-0.5 text-[11px] font-mono border rounded-sm",
                                horizon === h ? "bg-primary text-primary-foreground border-primary" : "border-q-border text-muted-foreground hover:text-foreground"
                            )}
                        >
                            {h}d
                        </button>
                    ))}
                </div>
            </div>
            <div className="px-4 py-3 text-xs">
                {isLoading ? (
                    <p className="text-muted-foreground">Loading…</p>
                ) : isError || !data || !Array.isArray(data.verdicts) ? (
                    <p className="text-muted-foreground">Track record unavailable.</p>
                ) : data.verdicts.length === 0 ? (
                    <p className="text-muted-foreground">
                        {data.tracking_since && data.first_results_on
                            ? `Recording verdicts daily since ${day(data.tracking_since)}. First ${horizon}-day results on ${day(data.first_results_on)}.`
                            : "Verdicts are recorded daily once stocks have research reports; results follow after the chosen period."}
                    </p>
                ) : (
                    <>
                        <table className="w-full text-left">
                            <caption className="sr-only">Average return {horizon} days after each verdict</caption>
                            <thead className="text-[11px] text-muted-foreground">
                                <tr>
                                    <th scope="col" className="font-medium pb-1">Verdict</th>
                                    <th scope="col" className="font-medium pb-1 text-right">Calls</th>
                                    <th scope="col" className="font-medium pb-1 text-right">Avg return</th>
                                    <th scope="col" className="font-medium pb-1 text-right">vs all rated</th>
                                    <th scope="col" className="font-medium pb-1 text-right">Rose</th>
                                </tr>
                            </thead>
                            <tbody className="font-mono">
                                {data.verdicts.map(v => (
                                    <tr key={v.verdict} className="border-t border-q-border/50">
                                        <th scope="row" className="py-1 font-sans font-semibold text-foreground">{v.verdict}</th>
                                        <td className="py-1 text-right">{v.count}</td>
                                        <td className="py-1 text-right">{pct(v.avg_return_pct)}</td>
                                        <td className={cn("py-1 text-right", v.vs_all_rated_pct > 0 ? "text-green-500" : v.vs_all_rated_pct < 0 ? "text-red-500" : "")}>
                                            {pct(v.vs_all_rated_pct)}
                                        </td>
                                        <td className="py-1 text-right">{v.share_that_rose_pct.toFixed(0)}%</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        <p className="mt-2 text-[11px] text-muted-foreground">
                            All rated stocks averaged {pct(data.all_rated_avg_return_pct ?? 0)} over {horizon} days. Verdicts are working if Buy
                            beats that and Avoid trails it. Past results don't predict future returns.
                        </p>
                    </>
                )}
            </div>
        </section>
    )
}
