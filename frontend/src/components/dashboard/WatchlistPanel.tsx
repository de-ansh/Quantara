import { Link } from "react-router-dom"
import DayChange from "@/components/DayChange"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { useWatchlist } from "@/hooks/useWatchlist"
import { riskWord } from "@/components/dashboard/riskWord"

/** Stocks the user starred: today's move and how risky each is. */
export default function WatchlistPanel() {
    const { data: items = [], isLoading, isError } = useWatchlist()
    return (
        <Panel id="watchlist" title="Watchlist" description="Stocks you've starred"
            action={<Link to="/explorer" className="text-xs font-medium text-primary hover:underline">Find stocks</Link>}>
            {isLoading ? <PanelSkeleton /> : isError ? <PanelMessage alert>Couldn't load your watchlist.</PanelMessage> : items.length === 0 ? (
                <PanelMessage>Star a stock on its page or in Find stocks to follow it here.</PanelMessage>
            ) : (
                <table className="w-full text-sm">
                    <thead>
                        <tr className="text-xs text-muted-foreground text-left">
                            <th scope="col" className="px-4 py-2 font-medium">Stock</th>
                            <th scope="col" className="px-2 py-2 font-medium text-right">Price</th>
                            <th scope="col" className="px-2 py-2 font-medium text-right">Today</th>
                            <th scope="col" className="px-4 py-2 font-medium text-right">Risk</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                        {items.map(w => (
                            <tr key={w.ticker} className="hover:bg-muted/40">
                                <th scope="row" className="px-4 py-2 text-left font-normal">
                                    <Link to={`/research/${w.ticker}`} className="font-medium text-foreground hover:text-primary">{w.ticker}</Link>
                                    <span className="block text-xs text-muted-foreground truncate max-w-[16rem]">{w.name}</span>
                                </th>
                                <td className="px-2 py-2 text-right font-mono tabular-nums">{w.price}</td>
                                <td className="px-2 py-2 text-right"><DayChange pct={w.change_pct} className="text-xs" /></td>
                                <td className="px-4 py-2 text-right text-xs">
                                    {riskWord(w.risk)}{w.risk !== null && <span className="text-muted-foreground"> · {Math.round(w.risk)}</span>}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </Panel>
    )
}
