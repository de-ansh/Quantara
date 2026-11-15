import { useState } from "react"
import { Upload } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import apiClient, { apiErrorDetail } from "@/lib/api"
import { parseTradebookCsv, type TradeRow } from "@/lib/tradebookCsv"

interface Plan {
    financial_year: string
    realized_short_term: number
    realized_long_term: number
    tax_so_far: number
    exemption_left: number
    tax_free_harvest: { symbol: string; bought: string; quantity: number; gain: number }[]
    tax_free_total: number
    tax_free_future_saving: number
    loss_harvest: { symbol: string; bought: string; quantity: number; loss: number; long_term: boolean }[]
    loss_harvest_saving: number
    turning_long_term: { symbol: string; bought: string; quantity: number; gain: number; long_term_from: string; tax_if_sold_now: number }[]
    lots: unknown[]
    warnings: string[]
    no_price: string[]
}

const inr = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`
const ticker = (s: string) => s.replace(/\.(NS|BO)$/, "")
const th = "px-3 py-2 text-left text-[11px] font-bold uppercase tracking-wider text-muted-foreground"
const td = "px-3 py-2 font-mono"

function Section({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <Card className="bg-q-surface border-q-border shadow-none">
            <CardHeader className="p-4 pb-2"><CardTitle className="text-sm font-bold">{title}</CardTitle></CardHeader>
            <CardContent className="p-4 pt-0 space-y-3 text-sm overflow-x-auto">{children}</CardContent>
        </Card>
    )
}

export default function TaxHarvest() {
    const [plan, setPlan] = useState<Plan | null>(null)
    const [skipped, setSkipped] = useState<string[]>([])
    const [error, setError] = useState<string | null>(null)
    const [busy, setBusy] = useState(false)

    const load = async (files: FileList) => {
        setError(null)
        setBusy(true)
        try {
            const trades: TradeRow[] = []
            const notes: string[] = []
            for (const file of Array.from(files)) {
                try {
                    const parsed = parseTradebookCsv(await file.text())
                    trades.push(...parsed.trades)
                    notes.push(...parsed.skipped.map(s => `${file.name}, ${s}`))
                } catch (err) {
                    notes.push(`${file.name}: ${err instanceof Error ? err.message : "unreadable"}`)
                }
            }
            setSkipped(notes)
            if (trades.length === 0) {
                setPlan(null)
                setError("No trades found in the chosen files.")
                return
            }
            setPlan((await apiClient.post<Plan>("/tax/harvest", { trades })).data)
        } catch (err) {
            setPlan(null)
            setError(apiErrorDetail(err) ?? "Couldn't work out the plan. Please try again.")
        } finally {
            setBusy(false)
        }
    }

    return (
        <div className="flex flex-col flex-1 p-6 bg-background space-y-6 overflow-y-auto custom-scrollbar">
            <header className="space-y-1 max-w-3xl">
                <h1 className="text-2xl font-bold text-foreground">Tax harvesting</h1>
                <p className="text-sm text-muted-foreground">
                    Upload your tradebook (in Zerodha: Console, then Reports, then Tradebook, equity segment, downloaded as CSV).
                    Pick files covering every buy of the shares you still hold. Trades are used for this answer only and aren't saved.
                </p>
            </header>

            <label className="inline-flex w-fit items-center gap-2 border border-primary text-primary px-4 py-2 text-sm font-bold cursor-pointer hover:bg-primary/10 focus-within:ring-2 focus-within:ring-primary">
                <Upload className="size-4" /> {busy ? "Working…" : "Choose tradebook CSV files"}
                <input type="file" accept=".csv,text/csv" multiple className="sr-only" aria-label="Tradebook CSV files" disabled={busy}
                    onChange={e => {
                        const files = e.target.files
                        if (files?.length) void load(files)
                        e.target.value = ""
                    }} />
            </label>

            {error && <p role="alert" className="text-sm text-q-risk-high">{error}</p>}

            {plan && (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 max-w-6xl">
                    <Section title={`This financial year (FY ${plan.financial_year}) so far`}>
                        <dl className="grid grid-cols-2 gap-x-6 gap-y-2">
                            <dt className="text-muted-foreground">Short-term gains realised</dt><dd className="font-mono text-right">{inr(plan.realized_short_term)}</dd>
                            <dt className="text-muted-foreground">Long-term gains realised</dt><dd className="font-mono text-right">{inr(plan.realized_long_term)}</dd>
                            <dt className="text-muted-foreground">Tax on them</dt><dd className="font-mono text-right">{inr(plan.tax_so_far)}</dd>
                            <dt className="text-muted-foreground">Tax-free long-term allowance left</dt><dd className="font-mono text-right">{inr(plan.exemption_left)}</dd>
                        </dl>
                        <p className="text-xs text-muted-foreground">Only covers trades in these files. Gains elsewhere (another broker, mutual funds) share the same ₹1.25 lakh allowance.</p>
                    </Section>

                    <Section title="1. Book tax-free gains">
                        {plan.tax_free_harvest.length ? (
                            <>
                                <p>
                                    Sell these and buy them back the next trading day to realise <b>{inr(plan.tax_free_total)}</b> of long-term
                                    gains tax-free. Your cost rises by that much, so you pay up to <b>{inr(plan.tax_free_future_saving)}</b> less
                                    tax when you finally sell.
                                </p>
                                <table className="w-full"><thead><tr><th className={th}>Stock</th><th className={th}>Bought</th><th className={th}>Sell</th><th className={th}>Gain</th></tr></thead>
                                    <tbody>{plan.tax_free_harvest.map(x => (
                                        <tr key={x.symbol + x.bought} className="border-t border-q-border"><td className={td}>{ticker(x.symbol)}</td><td className={td}>{x.bought}</td><td className={td}>{x.quantity}</td><td className={td}>{inr(x.gain)}</td></tr>
                                    ))}</tbody></table>
                                <p className="text-xs text-muted-foreground">Sell by the last trading days of March so it settles in this financial year. The bought-back shares start a new 12-month clock.</p>
                            </>
                        ) : <p className="text-muted-foreground">{plan.exemption_left > 0 ? "No holding has a long-term gain to book." : "This year's allowance is already used."}</p>}
                    </Section>

                    <Section title="2. Use losses to cut this year's tax">
                        {plan.loss_harvest.length ? (
                            <>
                                <p>
                                    {plan.loss_harvest_saving > 0
                                        ? <>Selling these losing lots would cut this year's tax by <b>{inr(plan.loss_harvest_saving)}</b>.</>
                                        : <>These lots are at a loss, but there's no taxable gain this year for them to offset. A loss you book can be carried forward 8 years if you file your return on time.</>}
                                </p>
                                <table className="w-full"><thead><tr><th className={th}>Stock</th><th className={th}>Bought</th><th className={th}>Shares</th><th className={th}>Loss</th><th className={th}>Term</th></tr></thead>
                                    <tbody>{plan.loss_harvest.map(x => (
                                        <tr key={x.symbol + x.bought} className="border-t border-q-border"><td className={td}>{ticker(x.symbol)}</td><td className={td}>{x.bought}</td><td className={td}>{x.quantity}</td><td className={td}>{inr(x.loss)}</td><td className={td}>{x.long_term ? "Long" : "Short"}</td></tr>
                                    ))}</tbody></table>
                                <p className="text-xs text-muted-foreground">Short-term losses offset any gain; long-term losses offset only long-term gains.</p>
                            </>
                        ) : <p className="text-muted-foreground">No holding is at a loss.</p>}
                    </Section>

                    <Section title="3. Wait before selling these">
                        {plan.turning_long_term.length ? (
                            <table className="w-full"><thead><tr><th className={th}>Stock</th><th className={th}>Long-term from</th><th className={th}>Gain</th><th className={th}>Tax if sold now</th></tr></thead>
                                <tbody>{plan.turning_long_term.map(x => (
                                    <tr key={x.symbol + x.bought} className="border-t border-q-border"><td className={td}>{ticker(x.symbol)}</td><td className={td}>{x.long_term_from}</td><td className={td}>{inr(x.gain)}</td><td className={td}>{inr(x.tax_if_sold_now)}</td></tr>
                                ))}</tbody></table>
                        ) : <p className="text-muted-foreground">Nothing with a gain turns long-term in the next 30 days.</p>}
                        <p className="text-xs text-muted-foreground">Held more than 12 months, a gain is taxed at 12.5% above the allowance instead of 20%.</p>
                    </Section>
                </div>
            )}

            {plan && (plan.warnings.length > 0 || plan.no_price.length > 0) && (
                <div role="note" className="max-w-6xl border border-amber-500/40 bg-amber-500/10 p-3 text-xs space-y-1">
                    {plan.warnings.map(w => <p key={w}>{w}</p>)}
                    {plan.no_price.length > 0 && <p>No current price for {plan.no_price.map(ticker).join(", ")}, so they're left out.</p>}
                </div>
            )}
            {skipped.length > 0 && (
                <details className="max-w-6xl text-xs text-muted-foreground">
                    <summary>{skipped.length} row{skipped.length === 1 ? "" : "s"} skipped</summary>
                    <ul className="mt-1 list-disc pl-5">{skipped.slice(0, 50).map(s => <li key={s}>{s}</li>)}</ul>
                </details>
            )}
            <p className="max-w-3xl text-xs text-muted-foreground">
                Estimates under the rules for listed shares since 23 July 2024: 20% short-term, 12.5% long-term above ₹1.25 lakh a year,
                plus 4% cess. They ignore surcharge, shares bought before February 2018 and demergers; a stock with a bonus or split since your first trade is left out.
                Not tax advice.
            </p>
        </div>
    )
}
