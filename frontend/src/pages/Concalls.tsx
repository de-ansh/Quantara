import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import apiClient, { apiErrorDetail } from "@/lib/api"
import { useWatchlist } from "@/hooks/useWatchlist"
import { cleanTickerDisplay } from "@/lib/currency"
import { cn } from "@/lib/utils"

type Kind = "transcript" | "recording" | "schedule"
interface Concall { ticker: string; company: string | null; kind: Kind; summary: string | null; filed_at: string | null; pdf_url: string | null }
interface Summary extends Concall {
    quarter: string; tone: "Positive" | "Neutral" | "Cautious" | null; summary: string; guidance: string
    highlights: string[]; concerns: string[]
}

const RANGES = [[1, "Today"], [7, "7 days"], [30, "30 days"]] as const
const KINDS: [Kind | null, string][] = [[null, "All"], ["transcript", "Transcripts"], ["recording", "Recordings"], ["schedule", "Schedules"]]
const KIND_LABEL: Record<Kind, string> = { transcript: "Transcript", recording: "Recording", schedule: "Call scheduled" }
const TONE: Record<string, string> = {
    Positive: "text-green-500 border-green-500/40 bg-green-500/10",
    Neutral: "text-muted-foreground border-border",
    Cautious: "text-amber-500 border-amber-500/40 bg-amber-500/10",
}
const time = (s: string | null) => (s ? new Date(s.replace(" ", "T")).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—")

function CallSummary({ ticker }: { ticker: string }) {
    const symbol = cleanTickerDisplay(ticker)
    const { data, isLoading, isError, error } = useQuery({
        queryKey: ["concallSummary", symbol],
        queryFn: async () => (await apiClient.get<Summary>(`/market/concalls/${encodeURIComponent(symbol)}/summary`)).data,
        staleTime: 60 * 60 * 1000,
        retry: false,
    })
    if (isLoading) return <p role="status" className="text-sm text-muted-foreground">Reading the transcript… this can take a minute.</p>
    if (isError || !data) return <p role="alert" className="text-sm text-muted-foreground">{apiErrorDetail(error) ?? "Couldn't summarise this call."}</p>
    return (
        <div className="space-y-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
                {data.tone && <span className={cn("border px-2 py-0.5 text-xs font-bold uppercase", TONE[data.tone])}>{data.tone} tone</span>}
                {data.quarter && <span className="text-xs text-muted-foreground">{data.quarter}</span>}
            </div>
            {data.summary && <p className="text-foreground">{data.summary}</p>}
            {data.guidance && <p className="text-muted-foreground"><span className="font-semibold text-foreground">Guidance: </span>{data.guidance}</p>}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {data.highlights.length > 0 && <div>
                    <h4 className="font-semibold text-green-500">Highlights</h4>
                    <ul className="mt-1 list-disc pl-4 space-y-0.5 text-muted-foreground">{data.highlights.map(p => <li key={p}>{p}</li>)}</ul>
                </div>}
                {data.concerns.length > 0 && <div>
                    <h4 className="font-semibold text-red-500">Concerns</h4>
                    <ul className="mt-1 list-disc pl-4 space-y-0.5 text-muted-foreground">{data.concerns.map(p => <li key={p}>{p}</li>)}</ul>
                </div>}
            </div>
            <p className="text-xs text-muted-foreground">AI summary of the transcript; check the PDF before acting on it.</p>
        </div>
    )
}

/** Earnings calls from every NSE company: upcoming schedules, recordings and transcripts with AI summaries. */
export default function Concalls() {
    const [days, setDays] = useState<number>(7)
    const [kind, setKind] = useState<Kind | null>("transcript")
    const [query, setQuery] = useState("")
    const [mineOnly, setMineOnly] = useState(false)
    const [open, setOpen] = useState<string | null>(null)
    const { data: watchlist = [] } = useWatchlist()
    const { data, isLoading, isError, refetch } = useQuery({
        queryKey: ["concalls", days],
        queryFn: async () => (await apiClient.get<Concall[] | null>("/market/concalls", { params: { days } })).data,
        refetchInterval: 10 * 60_000,
    })
    const watched = useMemo(() => new Set(watchlist.map(w => w.ticker)), [watchlist])
    const q = query.trim().toLowerCase()
    const rows = (data ?? []).filter(c =>
        (!kind || c.kind === kind)
        && (!mineOnly || watched.has(c.ticker))
        && (!q || c.ticker.toLowerCase().includes(q) || (c.company ?? "").toLowerCase().includes(q)))
    const counts = useMemo(() => {
        const n: Record<string, number> = {}
        for (const c of data ?? []) n[c.kind] = (n[c.kind] ?? 0) + 1
        return n
    }, [data])

    return (
        <div className="flex flex-col flex-1 p-6 bg-background space-y-4 overflow-y-auto custom-scrollbar">
            <header>
                <h1 className="text-2xl font-bold text-foreground">Concalls</h1>
                <p className="text-sm text-muted-foreground">Earnings calls from every NSE company: schedules, recordings and transcripts. Open a transcript for an AI summary.</p>
            </header>
            <div className="flex flex-wrap items-center gap-3">
                <div className="flex gap-1.5" role="group" aria-label="Period">
                    {RANGES.map(([d, label]) => (
                        <button key={d} type="button" aria-pressed={days === d} onClick={() => setDays(d)}
                            className={cn("px-3 py-1.5 text-sm rounded-sm border", days === d ? "bg-primary border-primary text-primary-foreground" : "border-border text-muted-foreground hover:bg-muted")}>
                            {label}
                        </button>
                    ))}
                </div>
                <input aria-label="Search calls" value={query} onChange={e => setQuery(e.target.value)} placeholder="Company or symbol…"
                    className="h-9 w-56 px-3 bg-background border border-border rounded-sm text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary" />
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                    <input type="checkbox" checked={mineOnly} onChange={e => setMineOnly(e.target.checked)} /> Watchlist only
                </label>
            </div>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Type">
                {KINDS.map(([k, label]) => (
                    <button key={label} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}
                        className={cn("px-2 py-1 text-xs rounded-sm border", kind === k ? "border-primary text-primary bg-primary/10" : "border-border text-muted-foreground hover:bg-muted")}>
                        {label} {data && <span className="opacity-60">{k ? counts[k] ?? 0 : data.length}</span>}
                    </button>
                ))}
            </div>
            {isLoading && <p className="text-sm text-muted-foreground">Loading calls…</p>}
            {(isError || data === null) && (
                <div role="alert" className="text-sm text-muted-foreground">
                    NSE announcements are unavailable right now. <button type="button" className="text-primary underline" onClick={() => refetch()}>Try again</button>
                </div>
            )}
            {data && (
                <ul className="bg-q-surface border border-q-border rounded-lg divide-y divide-border/50">
                    {rows.length === 0 && <li className="p-4 text-sm text-muted-foreground">No calls match.</li>}
                    {rows.slice(0, 300).map((c, i) => {
                        const id = `${c.ticker}${c.filed_at}${i}`
                        return (
                            <li key={id} className="p-3 text-sm space-y-2">
                                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                                    <span className="text-xs text-muted-foreground whitespace-nowrap">{time(c.filed_at)}</span>
                                    <Link to={`/research/${c.ticker}`} className="font-mono font-bold text-foreground hover:text-primary">{cleanTickerDisplay(c.ticker)}</Link>
                                    <span className="text-xs text-muted-foreground">{c.company}</span>
                                    <span className="text-[11px] px-1.5 py-0.5 rounded-sm border border-border text-muted-foreground">{KIND_LABEL[c.kind]}</span>
                                    <span className="ml-auto flex items-center gap-3">
                                        {c.kind === "transcript" && c.pdf_url && (
                                            <button type="button" aria-expanded={open === id} onClick={() => setOpen(open === id ? null : id)} className="text-xs text-primary hover:underline">
                                                {open === id ? "Hide summary" : "AI summary"}
                                            </button>
                                        )}
                                        {c.pdf_url && <a href={c.pdf_url} target="_blank" rel="noreferrer" className="text-xs text-primary hover:underline">PDF</a>}
                                    </span>
                                </div>
                                {c.summary && <p className="text-muted-foreground">{c.summary}</p>}
                                {open === id && <div className="border-l-2 border-primary/40 pl-3"><CallSummary ticker={c.ticker} /></div>}
                            </li>
                        )
                    })}
                </ul>
            )}
            {rows.length > 300 && <p className="text-xs text-muted-foreground">Showing the newest 300 of {rows.length}. Narrow by type or search.</p>}
        </div>
    )
}
