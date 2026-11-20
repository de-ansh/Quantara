import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import apiClient, { apiErrorDetail } from "@/lib/api"
import { useRefreshResearch, useResearch } from "@/hooks/useResearch"
import { signalSummary } from "@/hooks/useSignals"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import AdviceNotice from "@/components/AdviceNotice"
import { cn, timeAgo } from "@/lib/utils"
import type { ApiSignal, RiskAnalysis } from "@/types/api"

const TABS = [["summary", "Summary"], ["risk", "Risk factors"], ["signals", "Signals"]] as const
type Tab = (typeof TABS)[number][0]

function Points({ title, items, empty }: { title: string; items: string[]; empty: string }) {
    return (
        <div>
            <h3 className="text-sm font-medium text-foreground">{title}</h3>
            {items.length ? (
                <ul className="mt-2 space-y-1.5 list-disc pl-4 text-sm text-muted-foreground">{items.map(i => <li key={i}>{i}</li>)}</ul>
            ) : <p className="mt-2 text-sm text-muted-foreground">{empty}</p>}
        </div>
    )
}

/** The AI research report, the risk factors behind the score, and recent signals. */
export default function ResearchReport({ ticker, risk }: { ticker: string; risk: RiskAnalysis | undefined }) {
    const [tab, setTab] = useState<Tab>("summary")
    const { data: report, isLoading } = useResearch(ticker)
    const refresh = useRefreshResearch(ticker)
    const { data: signals = [] } = useQuery({
        queryKey: ["stockSignals", ticker],
        queryFn: async () => (await apiClient.get<{ signals: ApiSignal[] }>("/signals", { params: { ticker, limit: 10 } })).data.signals ?? [],
    })
    const c = risk?.components
    // Every bar reads the same way: longer means riskier
    const factors: [string, string, number | undefined][] = [
        ["Price swings", "How much the price has moved around", c?.volatility_score],
        ["Moves with the market", "How strongly it follows market falls", c?.beta_score],
        ["Debt", "How much the company has borrowed", c?.leverage_score],
        ["Unsteady earnings", "How much profits jump around", c ? 100 - c.earnings_stability_score : undefined],
        ["Sector", "Risk that comes with its industry", c?.sector_risk_score],
        ["Valuation", "How expensive the price looks", c?.valuation_risk_score],
    ]
    const outlook = report?.outlook_score
    const outlookWord = outlook == null ? null : outlook >= 60 ? "Positive" : outlook < 40 ? "Negative" : "Neutral"

    return (
        <Panel id="research" title="Research"
            description={report?.generated_at ? `AI report from ${timeAgo(report.generated_at)}` : "AI report, risk factors and recent signals"}
            action={report && (
                <button type="button" onClick={() => refresh.mutate()} disabled={refresh.isPending}
                    className="text-xs font-medium text-primary hover:underline disabled:opacity-50">
                    {refresh.isPending ? "Updating…" : "Update report"}
                </button>
            )}>
            <div role="tablist" aria-label="Research sections" className="flex gap-1 px-4 pt-2 border-b border-border">
                {TABS.map(([id, label]) => (
                    <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
                        className={cn("px-3 py-2 text-sm border-b-2 -mb-px", tab === id ? "border-primary text-foreground font-medium" : "border-transparent text-muted-foreground hover:text-foreground")}>
                        {label}
                    </button>
                ))}
            </div>
            {refresh.isError && <PanelMessage alert>{apiErrorDetail(refresh.error) ?? "Couldn't update the report."}</PanelMessage>}

            {tab === "summary" && (isLoading ? <PanelSkeleton rows={4} /> : !report ? (
                <PanelMessage>No research report for this stock yet. It's written automatically for stocks you hold or watch.</PanelMessage>
            ) : (
                <div className="p-4 space-y-4">
                    <div className="flex flex-wrap gap-2 text-xs">
                        {outlookWord && <span className="rounded-md border border-border px-2 py-0.5">Outlook: {outlookWord} ({Math.round(outlook!)}/100)</span>}
                        <span className="rounded-md border border-border px-2 py-0.5" title="How complete the data behind the report is">Data completeness: {Math.round(report.confidence_score)}%</span>
                    </div>
                    <p className="text-sm leading-relaxed text-foreground">{report.summary}</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <Points title="In its favour" items={report.key_insights?.length ? report.key_insights : report.strengths ?? []} empty="Nothing stands out." />
                        <Points title="Risks to watch" items={report.weaknesses?.length ? report.weaknesses : report.threats ?? []} empty="Nothing stands out." />
                    </div>
                    <AdviceNotice />
                </div>
            ))}

            {tab === "risk" && (!c ? <PanelMessage>No risk analysis for this stock yet.</PanelMessage> : (
                <div className="p-4 space-y-3">
                    <p className="text-xs text-muted-foreground">Each factor is scored 0–100; a longer bar means more risk.</p>
                    {factors.map(([label, help, v]) => (
                        <div key={label}>
                            <div className="flex justify-between text-sm">
                                <span className="text-foreground">{label} <span className="text-xs text-muted-foreground">· {help}</span></span>
                                <span className="font-mono tabular-nums">{v === undefined ? "—" : Math.round(v)}</span>
                            </div>
                            <div className="mt-1 h-1.5 rounded-full bg-muted overflow-hidden">
                                <div className={cn("h-full", (v ?? 0) > 66 ? "bg-q-risk-high" : (v ?? 0) > 33 ? "bg-amber-500" : "bg-q-risk-low")}
                                    style={{ width: `${Math.min(100, Math.max(3, v ?? 0))}%` }} />
                            </div>
                        </div>
                    ))}
                    {risk?.explanation && <p className="text-sm text-muted-foreground pt-1">{risk.explanation}</p>}
                </div>
            ))}

            {tab === "signals" && (signals.length === 0 ? <PanelMessage>No recent deals, pledges or promoter changes for this stock.</PanelMessage> : (
                <ul className="divide-y divide-border">
                    {signals.map(s => (
                        <li key={s.id} className="px-4 py-2.5 text-sm">
                            <span className="text-xs text-muted-foreground">{new Date(s.timestamp).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</span>
                            <p className="text-foreground">{signalSummary(s)}</p>
                        </li>
                    ))}
                </ul>
            ))}
        </Panel>
    )
}
