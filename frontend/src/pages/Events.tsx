import { Fragment, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import apiClient from "@/lib/api"
import { useWatchlist } from "@/hooks/useWatchlist"
import { cleanTickerDisplay } from "@/lib/currency"
import { chipClass } from "@/lib/utils"
import PageHeader from "@/components/PageHeader"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { Button } from "@/components/ui/button"
import IpoAnalysisPanel from "@/components/IpoAnalysisPanel"
import DeclaredResults from "@/components/DeclaredResults"

interface Earnings { ticker: string; company: string | null; date: string; detail: string | null }
interface Action { ticker: string; company: string | null; subject: string | null; kind: string; ex_date: string | null; record_date: string | null }
interface Ipo { symbol: string | null; company: string | null; status: string; start_date: string | null; end_date: string | null; listing_date: string | null; price: string | null; segment: string | null; subscribed_times: number | null }
interface MarketEvents { earnings: Earnings[] | null; corporate_actions: Action[] | null; ipos: Ipo[] | null }

const TABS = ["Upcoming results", "Declared results", "Corporate actions", "IPOs"] as const
const day = (iso: string | null) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—")
const Stock = ({ ticker }: { ticker: string }) => <Link to={`/research/${ticker}`} className="font-medium text-foreground hover:text-primary">{cleanTickerDisplay(ticker)}</Link>
const Empty = ({ text }: { text: string }) => <PanelMessage>{text}</PanelMessage>
const headCell = "px-4 py-2 text-left font-medium text-xs text-muted-foreground"
const DESCRIPTION: Record<(typeof TABS)[number], string> = {
    "Upcoming results": "Board meetings to approve results, soonest first",
    "Declared results": "Quarterly results filed recently, with growth on last year",
    "Corporate actions": "Dividends, splits, bonuses and buybacks by ex-date (buy before it to qualify)",
    IPOs: "Current and upcoming issues. Analyze reads the offer document",
}
const UNAVAILABLE = "Unavailable from NSE right now."

export default function Events() {
    const [tab, setTab] = useState<(typeof TABS)[number]>("Upcoming results")
    const [mineOnly, setMineOnly] = useState(false)
    const [openIpo, setOpenIpo] = useState<string | null>(null)
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
        <div className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto">
            <PageHeader title="Events" description="Results dates, declared results, corporate actions and IPOs, from NSE." />
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Event type">
                    {TABS.map(t => (
                        <button key={t} type="button" aria-pressed={t === tab} onClick={() => setTab(t)}
                            className={chipClass(t === tab)}>
                            {t}
                        </button>
                    ))}
                </div>
                {tab !== "IPOs" && (
                    <label className="flex items-center gap-2 text-sm text-muted-foreground">
                        <input type="checkbox" checked={mineOnly} onChange={e => setMineOnly(e.target.checked)} className="accent-primary" /> Watchlist only
                    </label>
                )}
            </div>
            {isLoading && <Panel id="events" title={tab}><PanelSkeleton rows={6} /></Panel>}
            {isError && !data && (
                <Panel id="events" title={tab}>
                    <div role="alert" className="p-4 space-y-3 text-sm">
                        <p className="text-q-risk-high">Couldn't load events.</p>
                        <Button variant="outline" size="sm" onClick={() => refetch()}>Try again</Button>
                    </div>
                </Panel>
            )}
            {data && (
                <Panel id="events" title={tab} description={DESCRIPTION[tab]}>
                <div className="overflow-x-auto">
                    {tab === "Declared results" && <DeclaredResults only={mineOnly ? watched : null} />}
                    {tab === "Upcoming results" && (data.earnings === null ? <Empty text={UNAVAILABLE} /> : earnings.length === 0 ? <Empty text="No upcoming results." /> : (
                        <table className="w-full text-sm">
                            <thead><tr><th scope="col" className={headCell}>Date</th><th scope="col" className={headCell}>Stock</th><th scope="col" className={headCell}>Company</th></tr></thead>
                            <tbody>{earnings.map(e => (
                                <tr key={`${e.ticker}${e.date}`} className="border-t border-border">
                                    <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">{day(e.date)}</td>
                                    <td className="px-4 py-2"><Stock ticker={e.ticker} /></td>
                                    <td className="px-4 py-2 text-muted-foreground">{e.company}</td>
                                </tr>
                            ))}</tbody>
                        </table>
                    ))}
                    {tab === "Corporate actions" && (data.corporate_actions === null ? <Empty text={UNAVAILABLE} /> : actions.length === 0 ? <Empty text="No upcoming corporate actions." /> : (
                        <table className="w-full text-sm">
                            <thead><tr><th scope="col" className={headCell}>Ex-date</th><th scope="col" className={headCell}>Stock</th><th scope="col" className={headCell}>Type</th><th scope="col" className={headCell}>Details</th></tr></thead>
                            <tbody>{actions.map((a, i) => (
                                <tr key={`${a.ticker}${i}`} className="border-t border-border">
                                    <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">{day(a.ex_date)}</td>
                                    <td className="px-4 py-2"><Stock ticker={a.ticker} /></td>
                                    <td className="px-4 py-2 text-foreground">{a.kind}</td>
                                    <td className="px-4 py-2 text-muted-foreground">{a.subject}</td>
                                </tr>
                            ))}</tbody>
                        </table>
                    ))}
                    {tab === "IPOs" && (data.ipos === null ? <Empty text={UNAVAILABLE} /> : data.ipos.length === 0 ? <Empty text="No IPOs to show." /> : (
                        <table className="w-full text-sm">
                            <thead><tr><th scope="col" className={headCell}>Company</th><th scope="col" className={headCell}>Status</th><th scope="col" className={headCell}>Open</th><th scope="col" className={headCell}>Close</th><th scope="col" className={headCell}>Listed</th><th scope="col" className={headCell}>Price</th><th scope="col" className={headCell}>Segment</th><th scope="col" className={headCell}><span className="sr-only">Analysis</span></th></tr></thead>
                            <tbody>{data.ipos.map((o, i) => {
                                const key = `${o.symbol}${i}`
                                const series = (o.segment ?? "").toUpperCase().includes("SME") ? "SME" : "EQ"
                                return (<Fragment key={key}>
                                <tr className="border-t border-border">
                                    <td className="px-4 py-2 text-foreground">{o.company}</td>
                                    <td className="px-4 py-2 text-muted-foreground">{o.status}{o.subscribed_times !== null && ` (${o.subscribed_times}x)`}</td>
                                    <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">{day(o.start_date)}</td>
                                    <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">{day(o.end_date)}</td>
                                    <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">{day(o.listing_date)}</td>
                                    <td className="px-4 py-2 whitespace-nowrap text-muted-foreground">{o.price ?? "—"}</td>
                                    <td className="px-4 py-2 text-muted-foreground">{o.segment ?? "—"}</td>
                                    <td className="px-4 py-2">{o.symbol && (
                                        <button type="button" aria-expanded={openIpo === key} onClick={() => setOpenIpo(openIpo === key ? null : key)}
                                            className="whitespace-nowrap rounded-md border border-primary/50 px-2 py-1 text-xs text-primary hover:bg-primary/10">
                                            {openIpo === key ? "Hide" : "Analyze"}
                                        </button>
                                    )}</td>
                                </tr>
                                {openIpo === key && o.symbol && (
                                    <tr className="bg-background/40"><td colSpan={8} className="p-4"><IpoAnalysisPanel symbol={o.symbol} series={series} /></td></tr>
                                )}
                                </Fragment>)
                            })}</tbody>
                        </table>
                    ))}
                </div>
                </Panel>
            )}
        </div>
    )
}
