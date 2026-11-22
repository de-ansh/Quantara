import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import apiClient from "@/lib/api"
import DayChange from "@/components/DayChange"
import PageHeader from "@/components/PageHeader"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { Button } from "@/components/ui/button"
import { cleanTickerDisplay } from "@/lib/currency"
import { indexLevel } from "@/lib/format"

interface IndexQuote { name: string; last: number | null; change: number | null; change_pct: number | null }
interface Flow { category: string; date: string | null; buy: number | null; sell: number | null; net: number | null }
interface Mover { ticker: string; name: string | null; price: number; change_pct: number; turnover?: number | null }
interface Sector { sector: string; stocks: number; avg_change_pct: number; avg_pe: number | null }
interface Overview {
    indices: IndexQuote[] | null
    sector_indices: IndexQuote[] | null
    breadth: { advances: number; declines: number; unchanged: number } | null
    flows: Flow[] | null
    gainers: Mover[]
    losers: Mover[]
    sectors: Sector[]
    most_traded?: Mover[]
}
interface ThemeMember { ticker: string; name: string | null; change_pct: number | null; return_1y_pct: number | null }
interface Theme { name: string; members: ThemeMember[]; avg_change_pct: number | null }

const number = (n: number | null) => (n === null ? "—" : n.toLocaleString("en-IN", { maximumFractionDigits: 2 }))
const Unavailable = ({ what }: { what: string }) => <PanelMessage>{what} unavailable from NSE right now.</PanelMessage>
const StockLink = ({ ticker }: { ticker: string }) => (
    <Link to={`/research/${ticker}`} className="font-medium text-foreground hover:text-primary">{cleanTickerDisplay(ticker)}</Link>
)
const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-")

function Movers({ title, rows, note = "Among tracked NSE stocks with at least ₹1 Cr traded" }: { title: string; rows: Mover[]; note?: string }) {
    return (
        <Panel id={`movers-${slug(title)}`} title={title} description={note}>
            {rows.length === 0 ? <PanelMessage>No recent prices.</PanelMessage> : (
                <ul className="divide-y divide-border">
                    {rows.map(m => (
                        <li key={m.ticker} className="flex items-center justify-between gap-3 px-4 py-2 text-sm">
                            <span className="min-w-0 truncate"><StockLink ticker={m.ticker} /> <span className="text-xs text-muted-foreground">{m.name}</span></span>
                            <span className="shrink-0 font-mono tabular-nums text-xs">
                                {m.turnover != null && <span className="mr-3 text-foreground">₹{(m.turnover / 1e7).toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr</span>}
                                <span className="mr-3 text-muted-foreground">₹{number(m.price)}</span><DayChange pct={m.change_pct} />
                            </span>
                        </li>
                    ))}
                </ul>
            )}
        </Panel>
    )
}

export default function Markets() {
    const { data, isLoading, isError, refetch } = useQuery({
        queryKey: ["market", "overview"],
        queryFn: async () => (await apiClient.get<Overview>("/market/overview")).data,
        refetchInterval: 120_000,
    })
    const { data: themes } = useQuery({
        queryKey: ["market", "themes"],
        queryFn: async () => (await apiClient.get<Theme[]>("/market/themes")).data,
        staleTime: 10 * 60 * 1000,
    })
    const breadth = data?.breadth
    const breadthTotal = breadth ? breadth.advances + breadth.declines + breadth.unchanged : 0
    const flowDate = data?.flows?.[0]?.date
    const orderedThemes = [...(themes ?? [])].sort((a, b) => (b.avg_change_pct ?? -Infinity) - (a.avg_change_pct ?? -Infinity))

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto">
            <PageHeader title="Markets" description="The Indian market today: indices, breadth, institutional flows, movers, sectors and themes. From NSE and tracked stock prices." />
            {isLoading && <Panel id="markets-loading" title="Indices"><PanelSkeleton rows={4} /></Panel>}
            {isError && !data && (
                <Panel id="markets-error" title="Markets">
                    <div role="alert" className="p-4 space-y-3 text-sm">
                        <p className="text-q-risk-high">Couldn't load market data.</p>
                        <Button variant="outline" size="sm" onClick={() => refetch()}>Try again</Button>
                    </div>
                </Panel>
            )}
            {data && (
                <>
                    {data.indices ? (
                        <dl className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            {data.indices.map(i => (
                                <div key={i.name} className="rounded-lg border border-border bg-card p-4">
                                    <dt className="text-xs text-muted-foreground">{i.name}</dt>
                                    <dd className="text-xl font-semibold font-mono tabular-nums text-foreground">{indexLevel(i.last)}</dd>
                                    <dd><DayChange pct={i.change_pct} className="text-xs" /></dd>
                                </div>
                            ))}
                        </dl>
                    ) : <Panel id="indices" title="Indices"><Unavailable what="Index levels" /></Panel>}

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <Panel id="breadth" title="Market breadth" description="Nifty 500 stocks up and down today">
                            {breadth ? (
                                <div className="p-4">
                                    <div className="flex h-3 rounded-full overflow-hidden bg-muted" role="img" aria-label={`${breadth.advances} advancing, ${breadth.declines} declining`}>
                                        <div className="bg-q-risk-low" style={{ width: `${(breadth.advances / breadthTotal) * 100}%` }} />
                                        <div className="bg-q-risk-high" style={{ width: `${(breadth.declines / breadthTotal) * 100}%` }} />
                                    </div>
                                    <p className="mt-2 flex justify-between text-sm font-mono tabular-nums">
                                        <span className="text-q-risk-low">{breadth.advances} up</span>
                                        <span className="text-muted-foreground">{breadth.unchanged} flat</span>
                                        <span className="text-q-risk-high">{breadth.declines} down</span>
                                    </p>
                                </div>
                            ) : <Unavailable what="Breadth" />}
                        </Panel>
                        <Panel id="flows" title="Foreign and domestic institutions" description={`Cash market, ₹ crore${flowDate ? `, ${flowDate}` : ""}. Net above zero means they bought more than they sold.`}>
                            {data.flows ? (
                                <table className="w-full text-sm">
                                    <thead><tr className="text-xs text-muted-foreground text-right"><th scope="col" className="px-4 py-2 text-left font-medium">Who</th><th scope="col" className="px-2 py-2 font-medium">Bought</th><th scope="col" className="px-2 py-2 font-medium">Sold</th><th scope="col" className="px-4 py-2 font-medium">Net</th></tr></thead>
                                    <tbody className="divide-y divide-border">
                                        {data.flows.map(f => (
                                            <tr key={f.category} className="text-right font-mono tabular-nums">
                                                <th scope="row" className="px-4 py-2 text-left font-sans font-medium text-foreground">{f.category}</th>
                                                <td className="px-2 py-2 text-muted-foreground">{number(f.buy)}</td>
                                                <td className="px-2 py-2 text-muted-foreground">{number(f.sell)}</td>
                                                <td className={(f.net ?? 0) >= 0 ? "px-4 py-2 text-q-risk-low" : "px-4 py-2 text-q-risk-high"}>{(f.net ?? 0) > 0 ? "+" : ""}{number(f.net)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            ) : <Unavailable what="Institutional flows" />}
                        </Panel>
                        <Movers title="Top gainers" rows={data.gainers} />
                        <Movers title="Top losers" rows={data.losers} />
                        {data.most_traded && data.most_traded.length > 0 && (
                            <Movers title="Most traded" rows={data.most_traded} note="Traded value in the last session, among tracked NSE stocks" />
                        )}
                        <Panel id="sector-indices" title="Sector indices" description="NSE sector indices, best first">
                            {data.sector_indices ? (
                                <ul className="divide-y divide-border">
                                    {data.sector_indices.map(s => (
                                        <li key={s.name} className="flex justify-between gap-3 px-4 py-2 text-sm">
                                            <span className="text-foreground">{s.name.replace(/^NIFTY /, "")}</span>
                                            <DayChange pct={s.change_pct} className="text-xs" />
                                        </li>
                                    ))}
                                </ul>
                            ) : <Unavailable what="Sector indices" />}
                        </Panel>
                        <Panel id="sectors" title="Sectors" description="Average of tracked stocks in each sector">
                            {data.sectors.length === 0 ? <PanelMessage>No sector data yet.</PanelMessage> : (
                                <table className="w-full text-sm">
                                    <thead><tr className="text-xs text-muted-foreground text-right"><th scope="col" className="px-4 py-2 text-left font-medium">Sector</th><th scope="col" className="px-2 py-2 font-medium">Stocks</th><th scope="col" className="px-2 py-2 font-medium">Avg P/E</th><th scope="col" className="px-4 py-2 font-medium">Today</th></tr></thead>
                                    <tbody className="divide-y divide-border">
                                        {data.sectors.map(s => (
                                            <tr key={s.sector} className="text-right font-mono tabular-nums">
                                                <th scope="row" className="px-4 py-2 text-left font-sans font-normal text-foreground">{s.sector}</th>
                                                <td className="px-2 py-2 text-muted-foreground">{s.stocks}</td>
                                                <td className="px-2 py-2 text-muted-foreground">{s.avg_pe ?? "—"}</td>
                                                <td className="px-4 py-2"><DayChange pct={s.avg_change_pct} className="text-xs" /></td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </Panel>
                    </div>

                    <Panel id="themes" title="Themes" description="Baskets from NSE's own thematic and sector index members, best today first. Open one to see its stocks.">
                        {themes && orderedThemes.length === 0 ? <Unavailable what="Themes" /> : !themes ? <PanelSkeleton rows={4} /> : (
                            <div className="divide-y divide-border">
                                {orderedThemes.map(t => (
                                    <details key={t.name}>
                                        <summary className="flex items-center justify-between gap-3 px-4 py-2.5 cursor-pointer text-sm text-foreground hover:bg-muted/40">
                                            <span>{t.name} <span className="text-xs text-muted-foreground">{t.members.length} stocks</span></span>
                                            <DayChange pct={t.avg_change_pct} className="text-xs" />
                                        </summary>
                                        <ul className="grid grid-cols-1 md:grid-cols-2 gap-x-6 px-4 pb-3">
                                            {t.members.map(m => (
                                                <li key={m.ticker} className="flex items-center justify-between gap-3 py-1 text-sm">
                                                    <span className="min-w-0 truncate"><StockLink ticker={m.ticker} /> <span className="text-xs text-muted-foreground">{m.name}</span></span>
                                                    <DayChange pct={m.change_pct} className="text-xs shrink-0" />
                                                </li>
                                            ))}
                                        </ul>
                                    </details>
                                ))}
                            </div>
                        )}
                    </Panel>
                </>
            )}
        </div>
    )
}
