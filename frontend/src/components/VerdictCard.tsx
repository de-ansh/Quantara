import { useQuery } from "@tanstack/react-query"
import apiClient from "@/lib/api"
import { cn } from "@/lib/utils"

interface Verdict {
    verdict: "Buy" | "Hold" | "Avoid" | "Unrated"
    final_score: number | null
    reasons: string[]
    missing: string[]
    user_risk_level: string
}

const TONE: Record<Verdict["verdict"], string> = {
    Buy: "text-green-500 border-green-500/40 bg-green-500/10",
    Hold: "text-amber-500 border-amber-500/40 bg-amber-500/10",
    Avoid: "text-red-500 border-red-500/40 bg-red-500/10",
    Unrated: "text-muted-foreground border-border bg-muted/30",
}

/** Buy / Hold / Avoid for the viewer's risk profile; `version` refetches once research or risk lands. */
export default function VerdictCard({ ticker, version }: { ticker: string; version?: string | number | null }) {
    const { data, isLoading } = useQuery({
        queryKey: ["verdict", ticker, version],
        queryFn: async () => (await apiClient.get<Verdict>(`/recommendations/${ticker}/verdict`)).data,
    })
    // Unknown values (an older or failing API) fall back to Unrated instead of crashing the page
    const verdict = data?.verdict && data.verdict in TONE ? data.verdict : "Unrated"

    return (
        <section aria-label="Verdict" className="bg-card border border-border p-4 px-5 min-w-[240px] max-w-sm">
            <div className="flex items-center justify-between gap-3">
                <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
                    Verdict{data?.user_risk_level ? ` · ${data.user_risk_level} profile` : ""}
                </span>
                {data?.final_score != null && (
                    <span className="text-xs font-mono text-muted-foreground">{data.final_score}/100</span>
                )}
            </div>
            <div className={cn("mt-2 inline-block border px-3 py-1 text-xl font-black uppercase tracking-wider", TONE[verdict])}>
                {isLoading ? "…" : verdict}
            </div>
            {data?.missing?.length ? (
                <p className="mt-2 text-xs text-muted-foreground">Needs a {data.missing.join(" and ")} first.</p>
            ) : null}
            {data?.reasons?.length ? (
                <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground list-disc pl-4">
                    {data.reasons.map(r => <li key={r}>{r}</li>)}
                </ul>
            ) : null}
        </section>
    )
}
