import { useQuery } from "@tanstack/react-query"
import apiClient from "@/lib/api"
import { cn } from "@/lib/utils"
import { dataCallLabel } from "@/lib/verdict"

interface Verdict {
    verdict: "Buy" | "Hold" | "Avoid" | "Unrated"
    final_score: number | null
    reasons: string[]
    missing: string[]
    user_risk_level: string
    basis?: "ai" | "data"
    pros?: string[]
    cons?: string[]
}

const TONE: Record<Verdict["verdict"], string> = {
    Buy: "text-green-500 border-green-500/40 bg-green-500/10",
    Hold: "text-amber-500 border-amber-500/40 bg-amber-500/10",
    Avoid: "text-red-500 border-red-500/40 bg-red-500/10",
    Unrated: "text-muted-foreground border-border bg-muted/30",
}
// Not red: it isn't a warning that the price will fall
const WEAK_TONE = "text-slate-500 border-slate-500/40 bg-slate-500/10"

/** Buy / Hold / Avoid for the viewer's risk profile, with pros and cons; `version` refetches once research or risk lands. */
export default function VerdictCard({ ticker, version }: { ticker: string; version?: string | number | null }) {
    const { data, isLoading } = useQuery({
        queryKey: ["verdict", ticker, version],
        queryFn: async () => (await apiClient.get<Verdict>(`/recommendations/${ticker}/verdict`)).data,
    })
    // Unknown values (an older or failing API) fall back to Unrated instead of crashing the page
    const verdict = data?.verdict && data.verdict in TONE ? data.verdict : "Unrated"
    const fromData = data?.basis === "data"
    const weakNumbers = fromData && verdict === "Avoid"

    return (
        <section aria-label="Verdict" className="bg-card border border-border p-4 px-5 min-w-[240px] max-w-md">
            <div className="flex items-center justify-between gap-3">
                <span className="text-[11px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
                    Verdict{data?.user_risk_level ? ` · ${data.user_risk_level} profile` : ""}
                </span>
                {data?.final_score != null && (
                    <span className="text-xs font-mono text-muted-foreground">{data.final_score}/100</span>
                )}
            </div>
            <div className={cn("mt-2 inline-block border px-3 py-1 text-xl font-black uppercase tracking-wider", weakNumbers ? WEAK_TONE : TONE[verdict])}>
                {isLoading ? "…" : fromData ? dataCallLabel(verdict) : verdict}
            </div>
            {data && verdict !== "Unrated" && (
                <p className="mt-1 text-[11px] text-muted-foreground">
                    {fromData ? "From the stock's numbers. The AI verdict replaces this once research is generated." : "From AI research, risk and signals."}
                </p>
            )}
            {weakNumbers && (
                <p className="mt-1 text-[11px] text-muted-foreground">
                    Its returns, profits or debt look weak. In a 2023–25 backtest, stocks like this did no worse than
                    the typical stock, so this describes the numbers and is not a call to sell.
                </p>
            )}
            {data && verdict === "Unrated" && (
                <p className="mt-2 text-xs text-muted-foreground">Not enough data on this stock yet to make a call.</p>
            )}
            {data?.reasons?.length ? (
                <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground list-disc pl-4">
                    {data.reasons.map(r => <li key={r}>{r}</li>)}
                </ul>
            ) : null}
            {(data?.pros?.length || data?.cons?.length) ? (
                <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                    <div>
                        <h4 className="font-bold text-green-500">Pros</h4>
                        {data.pros?.length ? (
                            <ul className="mt-1 space-y-0.5 list-disc pl-4 text-muted-foreground">{data.pros.map(p => <li key={p}>{p}</li>)}</ul>
                        ) : <p className="mt-1 text-muted-foreground">None stand out.</p>}
                    </div>
                    <div>
                        <h4 className="font-bold text-red-500">Cons</h4>
                        {data.cons?.length ? (
                            <ul className="mt-1 space-y-0.5 list-disc pl-4 text-muted-foreground">{data.cons.map(c => <li key={c}>{c}</li>)}</ul>
                        ) : <p className="mt-1 text-muted-foreground">None stand out.</p>}
                    </div>
                </div>
            ) : null}
        </section>
    )
}
