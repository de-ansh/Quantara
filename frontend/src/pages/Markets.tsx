import type { ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import apiClient from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import DayChange from "@/components/DayChange"
import { cleanTickerDisplay } from "@/lib/currency"

interface IndexQuote { name: string; last: number | null; change: number | null; change_pct: number | null }
interface Flow { category: string; date: string | null; buy: number | null; sell: number | null; net: number | null }
interface Mover { ticker: string; name: string | null; price: number; change_pct: number }
interface Sector { sector: string; stocks: number; avg_change_pct: number; avg_pe: number | null }
interface Overview {
    indices: IndexQuote[] | null
    sector_indices: IndexQuote[] | null
    breadth: { advances: number; declines: number; unchanged: number } | null
    flows: Flow[] | null
    gainers: Mover[]
    losers: Mover[]
    sectors: Sector[]
}
interface ThemeMember { ticker: string; name: string | null; change_pct: number | null; return_1y_pct: number | null }
interface Theme { name: string; members: ThemeMember[]; avg_change_pct: number | null }

const number = (n: number | null) => (n === null ? "—" : n.toLocaleString("en-IN", { maximumFractionDigits: 2 }))
const Unavailable = ({ what }: { what: string }) => <p className="text-sm text-muted-foreground">{what} unavailable from NSE right now.</p>
const StockLink = ({ ticker }: { ticker: string }) => (
    <Link to={`/research/${ticker}`} className="font-mono font-bold text-foreground hover:text-primary">{cleanTickerDisplay(ticker)}</Link>
)

function Panel({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
    return (
        <Card className="bg-q-surface border-q-border shadow-none">
            <CardHeader className="p-5 pb-2 space-y-0.5">
                <CardTitle className="text-sm font-semibold text-foreground">{title}</CardTitle>
                {note && <p className="text-xs text-muted-foreground">{note}</p>}
            </CardHeader>
            <CardContent className="p-5 pt-2">{children}</CardContent>
        </Card>
    )
}

function Movers({ title, rows }: { title: string; rows: Mover[] }) {
    return (
        <Panel title={title} note="Among tracked NSE stocks">
            {rows.length === 0 && <p className="text-sm text-muted-foreground">No recent prices.</p>}
            <ul className="divide-y divide-border/50">
                {rows.map(m => (
                    <li key={m.ticker} className="flex items-center justify-between gap-3 py-1.5 text-sm">
                        <span className="min-w-0"><StockLink ticker={m.ticker} /> <span className="text-xs text-muted-foreground truncate">{m.name}</span></span>
                        <span className="shrink-0 font-mono text-xs"><span className="mr-3 text-muted-foreground">₹{number(m.price)}</span><DayChange pct={m.change_pct} /></span>
                    </li>
                ))}
            </ul>
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
        <div className="flex flex-col flex-1 p-6 bg-background space-y-6 overflow-y-auto custom-scrollbar">
            <header>
                <h1 className="text-2xl font-bold text-foreground">Markets</h1>
                <p className="text-sm text-muted-foreground">Indian market today, from NSE and tracked stock prices.</p>
            </header>
            {isLoading && <p className="text-sm text-muted-foreground">Loading market data…</p>}
            {isError && !data && (
                <div role="alert" className="text-sm text-muted-foreground">
                    Could not load market data. <button type="button" className="text-primary underline" onClick={() => refetch()}>Try again</button>
                </div>
            )}
            {data && (
                <>
                    {data.indices
                        ? (
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                                {data.indices.map(i => (
                                    <Card key={i.name} className="bg-q-surface border-q-border shadow-none">
                                        <CardContent className="p-4">
                                            <p className="text-xs text-muted-foreground">{i.name}</p>
                                            <p className="text-xl font-bold font-mono text-foreground">{number(i.last)}</p>
                                            <DayChange pct={i.change_pct} className="text-xs" />
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        )
                        : <Unavailable what="Index levels" />}

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        <Panel title="Market breadth" note="Nifty 500 advances and declines">
                            {breadth ? (
                                <>
                                    <div className="flex h-3 rounded-full overflow-hidden bg-q-border/30" role="img" aria-label={`${breadth.advances} advancing, ${breadth.declines} declining`}>
                                        <div className="bg-q-risk-low" style={{ width: `${(breadth.advances / breadthTotal) * 100}%` }} />
                                        <div className="bg-q-risk-high" style={{ width: `${(breadth.declines / breadthTotal) * 100}%` }} />
                                    </div>
                                    <p className="mt-2 flex justify-between text-sm font-mono">
                                        <span className="text-q-risk-low">{breadth.advances} up</span>
                                        <span className="text-muted-foreground">{breadth.unchanged} flat</span>
                                        <span className="text-q-risk-high">{breadth.declines} down</span>
                                    </p>
                                </>
                            ) : <Unavailable what="Breadth" />}
                        </Panel>
                        <Panel title="FII / DII cash flows" note={flowDate ? `₹ crore, ${flowDate}` : "₹ crore"}>
                            {data.flows ? (
                                <table className="w-full text-sm font-mono">
                                    <thead><tr className="text-xs text-muted-foreground text-right"><th scope="col" className="text-left font-normal">Who</th><th scope="col" className="font-normal">Bought</th><th scope="col" className="font-normal">Sold</th><th scope="col" className="font-normal">Net</th></tr></thead>
                                    <tbody>
                                        {data.flows.map(f => (
                                            <tr key={f.category} className="text-right">
                                                <th scope="row" className="text-left font-bold text-foreground">{f.category}</th>
                                                <td className="text-muted-foreground">{number(f.buy)}</td>
                                                <td className="text-muted-foreground">{number(f.sell)}</td>
                                                <td className={(f.net ?? 0) >= 0 ? "text-q-risk-low" : "text-q-risk-high"}>{number(f.net)}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            ) : <Unavailable what="Institutional flows" />}
                        </Panel>
                        <Movers title="Top gainers" rows={data.gainers} />
                        <Movers title="Top losers" rows={data.losers} />
                        <Panel title="Sector indices" note="NSE sector indices, best first">
                            {data.sector_indices ? (
                                <ul className="divide-y divide-border/50">
                                    {data.sector_indices.map(s => (
                                        <li key={s.name} className="flex justify-between gap-3 py-1.5 text-sm">
                                            <span className="text-foreground">{s.name.replace(/^NIFTY /, "")}</span>
                                            <DayChange pct={s.change_pct} className="text-xs" />
                                        </li>
                                    ))}
                                </ul>
                            ) : <Unavailable what="Sector indices" />}
                        </Panel>
                        <Panel title="Sector explorer" note="Average of tracked stocks in each sector">
                            {data.sectors.length === 0 && <p className="text-sm text-muted-foreground">No sector data yet.</p>}
                            {data.sectors.length > 0 && (
                                <table className="w-full text-sm">
                                    <thead><tr className="text-xs text-muted-foreground text-right"><th scope="col" className="text-left font-normal">Sector</th><th scope="col" className="font-normal">Stocks</th><th scope="col" className="font-normal">Avg P/E</th><th scope="col" className="font-normal">Today</th></tr></thead>
                                    <tbody>
                                        {data.sectors.map(s => (
                                            <tr key={s.sector} className="border-t border-border/50 text-right font-mono">
                                                <th scope="row" className="py-1.5 text-left font-sans font-normal text-foreground">{s.sector}</th>
                                                <td className="text-muted-foreground">{s.stocks}</td>
                                                <td className="text-muted-foreground">{s.avg_pe ?? "—"}</td>
                                                <td><DayChange pct={s.avg_change_pct} className="text-xs" /></td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            )}
                        </Panel>
                    </div>

                    <section aria-label="Theme baskets" className="space-y-2">
                        <h2 className="text-sm font-semibold text-foreground">Themes</h2>
                        <p className="text-xs text-muted-foreground">Baskets are NSE's own thematic and sector index members.</p>
                        {themes && orderedThemes.length === 0 && <Unavailable what="Themes" />}
                        {orderedThemes.map(t => (
                            <details key={t.name} className="bg-q-surface border border-q-border rounded-lg">
                                <summary className="flex items-center justify-between gap-3 p-3 cursor-pointer text-sm text-foreground">
                                    <span>{t.name} <span className="text-xs text-muted-foreground">{t.members.length} stocks</span></span>
                                    <DayChange pct={t.avg_change_pct} className="text-xs" />
                                </summary>
                                <ul className="grid grid-cols-1 md:grid-cols-2 gap-x-6 px-3 pb-3">
                                    {t.members.map(m => (
                                        <li key={m.ticker} className="flex items-center justify-between gap-3 py-1 text-sm">
                                            <span className="min-w-0 truncate"><StockLink ticker={m.ticker} /> <span className="text-xs text-muted-foreground">{m.name}</span></span>
                                            <DayChange pct={m.change_pct} className="text-xs shrink-0" />
                                        </li>
                                    ))}
                                </ul>
                            </details>
                        ))}
                    </section>
                </>
            )}
        </div>
    )
}
