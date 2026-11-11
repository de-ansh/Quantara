import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import apiClient from "@/lib/api"
import { useWatchlist } from "@/hooks/useWatchlist"
import { cleanTickerDisplay } from "@/lib/currency"
import { cn } from "@/lib/utils"

interface Earnings { ticker: string; company: string | null; date: string; detail: string | null }
interface Action { ticker: string; company: string | null; subject: string | null; kind: string; ex_date: string | null; record_date: string | null }
interface Ipo { symbol: string | null; company: string | null; status: string; start_date: string | null; end_date: string | null; listing_date: string | null; price: string | null; segment: string | null; subscribed_times: number | null }
interface MarketEvents { earnings: Earnings[] | null; corporate_actions: Action[] | null; ipos: Ipo[] | null }

const TABS = ["Results", "Corporate actions", "IPOs"] as const
const day = (iso: string | null) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—")
const Stock = ({ ticker }: { ticker: string }) => <Link to={`/research/${ticker}`} className="font-mono font-bold text-foreground hover:text-primary">{cleanTickerDisplay(ticker)}</Link>
const Empty = ({ text }: { text: string }) => <p className="p-4 text-sm text-muted-foreground">{text}</p>
const headCell = "p-3 text-left font-normal text-xs text-muted-foreground"
const UNAVAILABLE = "Unavailable from NSE right now."

export default function Events() {
    const [tab, setTab] = useState<(typeof TABS)[number]>("Results")
    const [mineOnly, setMineOnly] = useState(false)
    const { data: watchlist = [] } = useWatchlist()
    const { data, isLoading, isError, refetch } = useQuery({
        queryKey: ["market", "events"],
        queryFn: async () => (await apiClient.get<MarketEvents>("/market/events")).data,
        staleTime: 10 * 60 * 1000,
    })
    const watched = new Set(watchlist.map(w => w.ticker))
    const mine = <T extends { ticker: string }>(rows: T[]) => (mineOnly ? rows.filter(r => watched.has(r.ticker)) : rows)
    const earnings = mine(data?.earnings ?? [])
    const actions = mine(data?.corporate_actions ?? [])

    return (
        <div className="flex flex-col flex-1 p-6 bg-background space-y-4 overflow-y-auto custom-scrollbar">
            <header>
                <h1 className="text-2xl font-bold text-foreground">Events</h1>
                <p className="text-sm text-muted-foreground">Results dates, corporate actions and IPOs from NSE.</p>
            </header>
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Event type">
                    {TABS.map(t => (
                        <button key={t} type="button" aria-pressed={t === tab} onClick={() => setTab(t)}
                            className={cn("px-3 py-1.5 text-sm rounded-sm border transition-colors", t === tab ? "bg-primary border-primary text-primary-foreground" : "border-border text-muted-foreground hover:bg-muted hover:text-foreground")}>
                            {t}
                        </button>
                    ))}
                </div>
                {tab !== "IPOs" && (
                    <label className="flex items-center gap-2 text-sm text-muted-foreground">
                        <input type="checkbox" checked={mineOnly} onChange={e => setMineOnly(e.target.checked)} /> Watchlist only
                    </label>
                )}
            </div>
            {isLoading && <p className="text-sm text-muted-foreground">Loading events…</p>}
            {isError && !data && (
                <div role="alert" className="text-sm text-muted-foreground">
                    Could not load events. <button type="button" className="text-primary underline" onClick={() => refetch()}>Try again</button>
                </div>
            )}
            {data && (
                <div className="bg-q-surface border border-q-border rounded-lg overflow-x-auto">
                    {tab === "Results" && (data.earnings === null ? <Empty text={UNAVAILABLE} /> : earnings.length === 0 ? <Empty text="No upcoming results." /> : (
                        <table className="w-full text-sm">
                            <thead><tr><th scope="col" className={headCell}>Date</th><th scope="col" className={headCell}>Stock</th><th scope="col" className={headCell}>Company</th></tr></thead>
                            <tbody>{earnings.map(e => (
                                <tr key={`${e.ticker}${e.date}`} className="border-t border-border/50">
                                    <td className="p-3 whitespace-nowrap text-muted-foreground">{day(e.date)}</td>
                                    <td className="p-3"><Stock ticker={e.ticker} /></td>
                                    <td className="p-3 text-muted-foreground">{e.company}</td>
                                </tr>
                            ))}</tbody>
                        </table>
                    ))}
                    {tab === "Corporate actions" && (data.corporate_actions === null ? <Empty text={UNAVAILABLE} /> : actions.length === 0 ? <Empty text="No upcoming corporate actions." /> : (
                        <table className="w-full text-sm">
                            <thead><tr><th scope="col" className={headCell}>Ex-date</th><th scope="col" className={headCell}>Stock</th><th scope="col" className={headCell}>Type</th><th scope="col" className={headCell}>Details</th></tr></thead>
                            <tbody>{actions.map((a, i) => (
                                <tr key={`${a.ticker}${i}`} className="border-t border-border/50">
                                    <td className="p-3 whitespace-nowrap text-muted-foreground">{day(a.ex_date)}</td>
                                    <td className="p-3"><Stock ticker={a.ticker} /></td>
                                    <td className="p-3 text-foreground">{a.kind}</td>
                                    <td className="p-3 text-muted-foreground">{a.subject}</td>
                                </tr>
                            ))}</tbody>
                        </table>
                    ))}
                    {tab === "IPOs" && (data.ipos === null ? <Empty text={UNAVAILABLE} /> : data.ipos.length === 0 ? <Empty text="No IPOs to show." /> : (
                        <table className="w-full text-sm">
                            <thead><tr><th scope="col" className={headCell}>Company</th><th scope="col" className={headCell}>Status</th><th scope="col" className={headCell}>Open</th><th scope="col" className={headCell}>Close</th><th scope="col" className={headCell}>Listed</th><th scope="col" className={headCell}>Price</th><th scope="col" className={headCell}>Segment</th></tr></thead>
                            <tbody>{data.ipos.map((o, i) => (
                                <tr key={`${o.symbol}${i}`} className="border-t border-border/50">
                                    <td className="p-3 text-foreground">{o.company}</td>
                                    <td className="p-3 text-muted-foreground">{o.status}{o.subscribed_times !== null && ` (${o.subscribed_times}x)`}</td>
                                    <td className="p-3 whitespace-nowrap text-muted-foreground">{day(o.start_date)}</td>
                                    <td className="p-3 whitespace-nowrap text-muted-foreground">{day(o.end_date)}</td>
                                    <td className="p-3 whitespace-nowrap text-muted-foreground">{day(o.listing_date)}</td>
                                    <td className="p-3 whitespace-nowrap text-muted-foreground">{o.price ?? "—"}</td>
                                    <td className="p-3 text-muted-foreground">{o.segment ?? "—"}</td>
                                </tr>
                            ))}</tbody>
                        </table>
                    ))}
                </div>
            )}
        </div>
    )
}
