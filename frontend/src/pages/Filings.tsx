import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import apiClient from "@/lib/api"
import { useWatchlist } from "@/hooks/useWatchlist"
import { cleanTickerDisplay } from "@/lib/currency"
import { chipClass } from "@/lib/utils"
import PageHeader from "@/components/PageHeader"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { Button } from "@/components/ui/button"

interface Filing { ticker: string; company: string | null; category: string | null; summary: string | null; filed_at: string | null; pdf_url: string | null }

const RANGES = [[1, "Today"], [3, "3 days"], [7, "7 days"]] as const
const time = (s: string | null) => (s ? new Date(s.replace(" ", "T")).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—")

/** Every NSE company's exchange announcements, newest first. */
export default function Filings() {
    const [days, setDays] = useState<number>(1)
    const [category, setCategory] = useState<string | null>(null)
    const [query, setQuery] = useState("")
    const [mineOnly, setMineOnly] = useState(false)
    const { data: watchlist = [] } = useWatchlist()
    const { data, isLoading, isError, refetch } = useQuery({
        queryKey: ["filings", days],
        queryFn: async () => (await apiClient.get<Filing[] | null>("/market/filings", { params: { days } })).data,
        refetchInterval: 120_000,
    })
    const watched = useMemo(() => new Set(watchlist.map(w => w.ticker)), [watchlist])
    const categories = useMemo(() => {
        const counts = new Map<string, number>()
        for (const f of data ?? []) if (f.category) counts.set(f.category, (counts.get(f.category) ?? 0) + 1)
        return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8)
    }, [data])
    const q = query.trim().toLowerCase()
    const rows = (data ?? []).filter(f =>
        (!category || f.category === category)
        && (!mineOnly || watched.has(f.ticker))
        && (!q || f.ticker.toLowerCase().includes(q) || (f.company ?? "").toLowerCase().includes(q) || (f.summary ?? "").toLowerCase().includes(q)))

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto">
            <PageHeader title="Filings" description="Announcements from every NSE company as they're filed. Updates every 2 minutes." />
            <div className="flex flex-wrap items-center gap-3">
                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Period">
                    {RANGES.map(([d, label]) => (
                        <button key={d} type="button" aria-pressed={days === d} onClick={() => setDays(d)}
                            className={chipClass(days === d)}>
                            {label}
                        </button>
                    ))}
                </div>
                <input aria-label="Search filings" value={query} onChange={e => setQuery(e.target.value)} placeholder="Company, symbol or text…"
                    className="h-9 w-56 px-3 bg-background border border-border rounded-md text-sm text-foreground outline-none focus:border-primary" />
                <label className="flex items-center gap-2 text-sm text-muted-foreground">
                    <input type="checkbox" checked={mineOnly} onChange={e => setMineOnly(e.target.checked)} className="accent-primary" /> Watchlist only
                </label>
            </div>
            {categories.length > 0 && (
                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Category">
                    {categories.map(([c, n]) => (
                        <button key={c} type="button" aria-pressed={category === c} onClick={() => setCategory(category === c ? null : c)}
                            className={chipClass(category === c)}>
                            {c} <span className="font-mono tabular-nums opacity-60">{n}</span>
                        </button>
                    ))}
                </div>
            )}
            <Panel id="filing-list" title={data ? `${rows.length} filing${rows.length === 1 ? "" : "s"}` : "Filings"}
                description={rows.length > 300 ? `Showing the newest 300. Narrow by category or search.` : "Newest first"}>
            {isLoading && <PanelSkeleton rows={6} />}
            {(isError || data === null) && (
                <div role="alert" className="p-4 space-y-3 text-sm">
                    <p className="text-q-risk-high">NSE filings are unavailable right now.</p>
                    <Button variant="outline" size="sm" onClick={() => refetch()}>Try again</Button>
                </div>
            )}
            {data && rows.length === 0 && <PanelMessage>No filings match.</PanelMessage>}
            {data && rows.length > 0 && (
                <ul className="divide-y divide-border">
                    {rows.slice(0, 300).map((f, i) => (
                        <li key={`${f.ticker}${f.filed_at}${i}`} className="px-4 py-2.5 text-sm space-y-1">
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                                <span className="text-xs text-muted-foreground whitespace-nowrap">{time(f.filed_at)}</span>
                                <Link to={`/research/${f.ticker}`} className="font-medium text-foreground hover:text-primary">{cleanTickerDisplay(f.ticker)}</Link>
                                <span className="text-xs text-muted-foreground">{f.company}</span>
                                {f.category && <span className="text-xs px-2 py-0.5 rounded-full border border-border text-muted-foreground">{f.category}</span>}
                                {f.pdf_url && <a href={f.pdf_url} target="_blank" rel="noreferrer" className="ml-auto text-xs text-primary hover:underline">PDF</a>}
                            </div>
                            {f.summary && <p className="text-muted-foreground">{f.summary}</p>}
                        </li>
                    ))}
                </ul>
            )}
            </Panel>
        </div>
    )
}
