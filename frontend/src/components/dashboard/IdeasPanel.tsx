import { Link } from "react-router-dom"
import AdviceNotice from "@/components/AdviceNotice"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { useRecommendations } from "@/hooks/useRecommendations"
import { riskWord } from "@/components/dashboard/riskWord"
import YourSectorTag from "@/components/YourSectorTag"

const COLUMNS: [string, string][] = [
    ["Match", "Overall fit for your profile, out of 100"],
    ["Risk", "How risky the stock is, out of 100 (higher is riskier)"],
    ["Research", "Quality of the business from AI research, out of 100"],
    ["Signals", "Recent market signals: deals, pledges, stake changes"],
]

/** Stocks that score best for the user's risk profile. */
export default function IdeasPanel({ riskLevel }: { riskLevel: string }) {
    const { data: ideas = [], isLoading, isError } = useRecommendations()
    return (
        <Panel id="ideas" title={`Ideas for a ${riskLevel.toLowerCase()} investor`}
            description="Ranked by research quality, recent signals and how well the risk fits you. A starting point, not a buy list.">
            <AdviceNotice className="px-4 pt-2" />
            {isLoading ? <PanelSkeleton /> : isError ? <PanelMessage alert>Couldn't load ideas.</PanelMessage> : ideas.length === 0 ? (
                <PanelMessage>No ideas yet. They appear once enough stocks have research reports.</PanelMessage>
            ) : (
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-xs text-muted-foreground">
                                <th scope="col" className="px-4 py-2 font-medium text-left">Stock</th>
                                {COLUMNS.map(([name, help]) => (
                                    <th key={name} scope="col" title={help} className="px-3 py-2 font-medium text-right cursor-help underline decoration-dotted underline-offset-4">{name}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                            {ideas.map(o => (
                                <tr key={o.ticker} className="hover:bg-muted/40">
                                    <th scope="row" className="px-4 py-2 text-left font-medium">
                                        <Link to={`/research/${o.ticker}`} className="text-foreground hover:text-primary">{o.ticker}</Link>
                                        <YourSectorTag sector={o.sector} />
                                    </th>
                                    <td className="px-3 py-2 text-right font-mono tabular-nums font-semibold">{o.score}</td>
                                    <td className="px-3 py-2 text-right text-xs">{riskWord(o.risk)} <span className="text-muted-foreground font-mono">· {Number.isFinite(o.risk) ? o.risk.toFixed(1) : "—"}</span></td>
                                    <td className="px-3 py-2 text-right font-mono tabular-nums">{o.research}</td>
                                    <td className="px-3 py-2 text-right text-xs">{o.signal === "up" ? "Strong" : o.signal === "down" ? "Weak" : "Neutral"}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </Panel>
    )
}
