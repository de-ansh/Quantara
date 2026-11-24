import { Link } from "react-router-dom"
import { AlertTriangle, CheckCircle2 } from "lucide-react"
import AdviceNotice from "@/components/AdviceNotice"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { usePortfolioBalance } from "@/hooks/usePortfolios"
import { money } from "@/lib/money"

const CLASSES = ["equity", "debt", "cash", "gold"] as const
const BAR = { equity: "bg-primary", debt: "bg-sky-500", cash: "bg-emerald-500", gold: "bg-amber-500" }

/** What looks lopsided in a portfolio, with how much to move to fix it. */
export default function BalanceCheck({ id }: { id: number }) {
    const { data, isLoading, isError } = usePortfolioBalance(id)
    return (
        <Panel id="balance" title="Balance check"
            description="One company over 20%, one sector over 35%, more equity than your risk profile usually holds, Avoid ratings, and stocks you also hold elsewhere.">
            {isLoading ? <PanelSkeleton rows={2} />
                : isError || !data?.flags || !data.mix ? <PanelMessage alert>Couldn't check this portfolio's balance.</PanelMessage>
                : (
                    <div className="p-4 space-y-4">
                        {Object.entries(data.mix).map(([currency, mix]) => (
                            <div key={currency} className="space-y-1.5">
                                <p className="text-xs text-muted-foreground">
                                    {Object.keys(data.mix).length > 1 && `${currency}: `}
                                    {CLASSES.filter(c => mix[c]).map(c => `${Math.round(mix[c])}% ${c}`).join(" · ")}
                                </p>
                                <div className="flex h-2 rounded-full overflow-hidden bg-muted" aria-hidden="true">
                                    {CLASSES.filter(c => mix[c]).map(c => <div key={c} className={BAR[c]} style={{ width: `${mix[c]}%` }} />)}
                                </div>
                            </div>
                        ))}
                        {data.flags.length === 0 ? (
                            <p className="flex items-center gap-2 text-sm text-q-risk-low">
                                <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" /> Nothing stands out: this portfolio looks balanced.
                            </p>
                        ) : (
                            <ul className="space-y-3">
                                {data.flags.map((f, i) => (
                                    <li key={i} className="flex gap-2 text-sm">
                                        <AlertTriangle className="size-4 shrink-0 mt-0.5 text-amber-500" aria-hidden="true" />
                                        <div className="min-w-0">
                                            <p className="font-medium text-foreground">
                                                {f.ticker && f.kind !== "mix" ? <Link to={`/research/${f.ticker}`} className="hover:underline">{f.title}</Link> : f.title}
                                            </p>
                                            <p className="text-muted-foreground">
                                                {f.detail}
                                                {f.amount ? <> <span className="font-mono tabular-nums text-foreground whitespace-nowrap">About {money(f.amount, f.currency)}</span>.</> : null}
                                            </p>
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        )}
                        {!data.risk_level && (
                            <p className="text-xs text-muted-foreground">
                                Set your risk profile on the <Link to="/account" className="underline">Account</Link> page to also check your equity share and Avoid ratings.
                            </p>
                        )}
                        <AdviceNotice />
                    </div>
                )}
        </Panel>
    )
}
