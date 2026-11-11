import { useQuery } from "@tanstack/react-query"
import apiClient, { apiErrorDetail } from "@/lib/api"
import { cn } from "@/lib/utils"

interface IpoAnalysis {
    issue: {
        company: string | null; industry: string | null; price_range: string | null; lot: string | null
        fresh_issue_crore: number | null; offer_for_sale_crore: number | null; offer_for_sale_share: number | null
        subscription: Record<string, number>; rhp_url: string | null
    }
    summary: string; financials: string; valuation: string
    pros: string[]; cons: string[]
    recommendation: "Apply" | "Apply for listing gains" | "Avoid" | null
    reasoning: string; confidence: number | null; read_prospectus: boolean
}

const TONE: Record<string, string> = {
    Apply: "text-green-500 border-green-500/40 bg-green-500/10",
    "Apply for listing gains": "text-amber-500 border-amber-500/40 bg-amber-500/10",
    Avoid: "text-red-500 border-red-500/40 bg-red-500/10",
}
const SUBSCRIPTION = [["qib", "Institutions (QIB)"], ["nii", "HNI (NII)"], ["retail", "Retail"], ["employee", "Employees"], ["total", "Total"]]

/** AI analysis of one NSE IPO: call, pros and cons, from issue data and the prospectus. */
export default function IpoAnalysisPanel({ symbol, series }: { symbol: string; series: "EQ" | "SME" }) {
    const { data, isLoading, isError, error } = useQuery({
        queryKey: ["ipoAnalysis", symbol, series],
        queryFn: async () => (await apiClient.get<IpoAnalysis>(`/market/ipos/${encodeURIComponent(symbol)}/analysis`, { params: { series } })).data,
        staleTime: 60 * 60 * 1000,
        retry: false,
    })
    if (isLoading) return <p role="status" className="text-sm text-muted-foreground">Reading the issue data and prospectus… this can take a minute.</p>
    if (isError || !data) return <p role="alert" className="text-sm text-muted-foreground">{apiErrorDetail(error) ?? "Couldn't analyse this IPO."}</p>

    const { issue } = data
    const subs = SUBSCRIPTION.filter(([k]) => issue.subscription[k] !== undefined)
    return (
        <div className="space-y-4 text-sm">
            <div className="flex flex-wrap items-center gap-3">
                <span className={cn("border px-3 py-1 text-base font-black uppercase tracking-wide", data.recommendation ? TONE[data.recommendation] : "text-muted-foreground border-border")}>
                    {data.recommendation ?? "No call"}
                </span>
                {data.confidence !== null && <span className="text-xs text-muted-foreground">Confidence {Math.round(data.confidence)}/100</span>}
                {!data.read_prospectus && <span className="text-xs text-amber-500">Prospectus couldn't be read; based on issue data only</span>}
            </div>
            {data.reasoning && <p className="text-foreground">{data.reasoning}</p>}
            {data.summary && <p className="text-muted-foreground">{data.summary}</p>}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <h4 className="font-semibold text-green-500">Pros</h4>
                    <ul className="mt-1 list-disc pl-4 space-y-0.5 text-muted-foreground">{data.pros.map(p => <li key={p}>{p}</li>)}</ul>
                </div>
                <div>
                    <h4 className="font-semibold text-red-500">Cons</h4>
                    <ul className="mt-1 list-disc pl-4 space-y-0.5 text-muted-foreground">{data.cons.map(c => <li key={c}>{c}</li>)}</ul>
                </div>
            </div>
            {(data.financials || data.valuation) && (
                <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {data.financials && <div><dt className="font-semibold text-foreground">Financials</dt><dd className="text-muted-foreground">{data.financials}</dd></div>}
                    {data.valuation && <div><dt className="font-semibold text-foreground">Valuation</dt><dd className="text-muted-foreground">{data.valuation}</dd></div>}
                </dl>
            )}
            <dl className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div><dt className="text-muted-foreground">Price band</dt><dd className="text-foreground">{issue.price_range ?? "—"}</dd></div>
                <div><dt className="text-muted-foreground">Lot</dt><dd className="text-foreground">{issue.lot ?? "—"}</dd></div>
                <div><dt className="text-muted-foreground">Fresh issue / OFS</dt><dd className="text-foreground">
                    {issue.fresh_issue_crore !== null || issue.offer_for_sale_crore !== null
                        ? `₹${issue.fresh_issue_crore ?? 0} Cr / ₹${issue.offer_for_sale_crore ?? 0} Cr`
                        : issue.offer_for_sale_share !== null ? `${Math.round(issue.offer_for_sale_share * 100)}% is OFS` : "—"}
                </dd></div>
                <div><dt className="text-muted-foreground">Subscription</dt><dd className="text-foreground">
                    {subs.length ? subs.map(([k, label]) => `${label} ${issue.subscription[k]}x`).join(" · ") : "Not available"}
                </dd></div>
            </dl>
            <p className="text-[11px] text-muted-foreground">
                AI analysis of NSE issue data{data.read_prospectus ? " and the prospectus" : ""}. Not investment advice; read the
                {issue.rhp_url ? <> <a href={issue.rhp_url} target="_blank" rel="noreferrer" className="text-primary underline">red herring prospectus</a></> : " prospectus"} before applying.
            </p>
        </div>
    )
}
