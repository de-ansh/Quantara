import { useQuery } from "@tanstack/react-query"
import { cn } from "@/lib/utils"
import apiClient from "@/lib/api"

interface Quarter {
    quarter: string; promoter_pct: number; fii_pct: number | null; dii_pct: number | null
    mf_pct: number | null; retail_pct: number | null; shareholders: number | null
}
type Key = "promoter_pct" | "fii_pct" | "dii_pct" | "mf_pct" | "retail_pct"

const ROWS: [Key, string][] = [
    ["promoter_pct", "Promoters"], ["fii_pct", "Foreign institutions (FII)"], ["dii_pct", "Domestic institutions (DII)"],
    ["mf_pct", "of which mutual funds"], ["retail_pct", "Retail & others"],
]
const label = (q: string) => new Date(`${q}T00:00:00`).toLocaleDateString("en-IN", { month: "short", year: "2-digit" })
const pct = (v: number | null) => (v === null ? "—" : `${v.toFixed(2)}%`)

/** Who owns the company, quarter by quarter, from its NSE shareholding filings (NSE stocks only). */
export default function ShareholdingCard({ ticker }: { ticker: string }) {
    const { data, isLoading } = useQuery({
        queryKey: ["shareholding", ticker],
        queryFn: async () => (await apiClient.get<Quarter[]>(`/stocks/${ticker}/shareholding`)).data,
        enabled: ticker.endsWith(".NS"),
        staleTime: 6 * 60 * 60 * 1000,
        retry: false,
    })
    if (!ticker.endsWith(".NS")) return null
    if (isLoading) return <p role="status" className="mb-4 text-xs text-muted-foreground">Reading shareholding filings…</p>
    if (!data?.length) return null
    const quarters = [...data].reverse()  // oldest first, left to right
    const [latest, previous] = data
    const change = (key: Key) => (latest[key] !== null && previous?.[key] != null ? latest[key]! - previous[key]! : null)

    return (
        <section aria-label="Shareholding pattern" className="mb-4 bg-card border border-border rounded-lg p-4">
            <h2 className="text-sm font-semibold text-foreground mb-3">Shareholding pattern</h2>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead className="text-xs text-muted-foreground">
                        <tr>
                            <th className="text-left font-medium pb-2 pr-3">Holder</th>
                            {quarters.map(q => <th key={q.quarter} className="text-right font-medium pb-2 px-2 whitespace-nowrap">{label(q.quarter)}</th>)}
                            <th className="text-right font-medium pb-2 pl-3 whitespace-nowrap">QoQ change</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                        {ROWS.map(([key, name]) => {
                            const delta = change(key)
                            return (
                                <tr key={key}>
                                    <td className={cn("py-1.5 pr-3 whitespace-nowrap", key === "mf_pct" ? "pl-4 text-xs text-muted-foreground" : "text-foreground")}>{name}</td>
                                    {quarters.map(q => <td key={q.quarter} className="py-1.5 px-2 text-right font-mono">{pct(q[key])}</td>)}
                                    <td className={cn("py-1.5 pl-3 text-right font-mono font-semibold", delta === null || Math.abs(delta) < 0.005 ? "text-muted-foreground" : delta > 0 ? "text-green-500" : "text-red-500")}>
                                        {delta === null ? "—" : `${delta > 0 ? "+" : ""}${delta.toFixed(2)}`}
                                    </td>
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
            </div>
            {latest.shareholders !== null && (
                <p className="mt-3 text-xs text-muted-foreground">
                    {latest.shareholders.toLocaleString("en-IN")} shareholders as of {label(latest.quarter)}
                    {previous?.shareholders ? ` (${latest.shareholders >= previous.shareholders ? "+" : ""}${(latest.shareholders - previous.shareholders).toLocaleString("en-IN")} in the quarter)` : ""}.
                    {" "}From the company's NSE shareholding filings; change is in percentage points.
                </p>
            )}
        </section>
    )
}
