import { Link } from "react-router-dom"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { useSignals } from "@/hooks/useSignals"
import { cn } from "@/lib/utils"

const DIRECTION = {
    BULLISH: { word: "Positive", dot: "bg-q-risk-low" },
    BEARISH: { word: "Negative", dot: "bg-q-risk-high" },
    NEUTRAL: { word: "Neutral", dot: "bg-muted-foreground" },
    VOLATILITY: { word: "Volatile", dot: "bg-amber-500" },
} as const

const SHOWN = 8

/** The newest market signals (deals, pledges, promoter stake changes), in words. */
export default function SignalsPanel() {
    const { data: signals = [], isLoading, isError } = useSignals()
    return (
        <Panel id="recent-signals" title="Recent signals" description="Bulk and block deals, promoter pledges and stake changes, newest first"
            action={<Link to="/signals" className="text-xs font-medium text-primary hover:underline">All signals</Link>}>
            {isLoading ? <PanelSkeleton rows={4} /> : isError ? <PanelMessage alert>Couldn't load signals.</PanelMessage> : signals.length === 0 ? (
                <PanelMessage>No signals in the last few days.</PanelMessage>
            ) : (
                <ul className="divide-y divide-border">
                    {signals.slice(0, SHOWN).map((s, i) => (
                        <li key={i} className="px-4 py-2.5 text-sm">
                            <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                                <span>{s.time}</span>
                                <span className="flex items-center gap-1.5">
                                    <span className={cn("size-1.5 rounded-full", DIRECTION[s.type].dot)} aria-hidden="true" />
                                    {DIRECTION[s.type].word}
                                </span>
                            </div>
                            <p className="mt-0.5 text-foreground">
                                {s.ticker && <Link to={`/research/${s.ticker}`} className="font-medium hover:text-primary">{s.ticker}</Link>}
                                {s.ticker ? " · " : ""}{s.summary ?? s.text}
                            </p>
                        </li>
                    ))}
                </ul>
            )}
        </Panel>
    )
}
