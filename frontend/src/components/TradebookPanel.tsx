import { useState } from "react"
import { Upload } from "lucide-react"
import Panel, { PanelSkeleton } from "@/components/Panel"
import { Button } from "@/components/ui/button"
import { useSaveTradebook, useTradebook } from "@/hooks/usePortfolios"
import { apiErrorDetail } from "@/lib/api"
import { shortDay } from "@/lib/format"
import { fileAsCsv } from "@/lib/holdingsCsv"
import { parseTradebookCsv, type TradeRow } from "@/lib/tradebookCsv"
import { pct, tone } from "@/lib/money"
import { cn, timeAgo } from "@/lib/utils"

/** A portfolio's buy history: it gives the rebalancing plan real tax figures, and the portfolio its XIRR. */
export default function TradebookPanel({ id }: { id: number }) {
    const { data: raw, isLoading } = useTradebook(id)
    const data = raw?.imported_at && raw.gaps ? raw : null  // anything else reads as "not imported"
    const save = useSaveTradebook(id)
    const [notes, setNotes] = useState<string[]>([])
    const [error, setError] = useState<string | null>(null)

    const load = async (files: FileList) => {
        setError(null)
        const trades: TradeRow[] = []
        const skipped: string[] = []
        for (const file of Array.from(files)) {
            try {
                const parsed = parseTradebookCsv(await fileAsCsv(file))
                trades.push(...parsed.trades)
                skipped.push(...parsed.skipped.map(s => `${file.name}, ${s}`))
            } catch (err) {
                skipped.push(`${file.name}: ${err instanceof Error ? err.message : "unreadable"}`)
            }
        }
        setNotes(skipped)
        if (!trades.length) { setError("No trades found in the chosen files."); return }
        save.mutate(trades, { onError: err => setError(apiErrorDetail(err) ?? "Couldn't import the tradebook. Please try again.") })
    }

    const picker = (label: string) => (
        <label className={cn("inline-flex w-fit items-center gap-2 rounded-md border border-primary text-primary px-3 py-1.5 text-sm font-medium cursor-pointer hover:bg-primary/10 focus-within:ring-2 focus-within:ring-primary",
            save.isPending && "opacity-60 pointer-events-none")}>
            <Upload className="size-4" aria-hidden="true" /> {save.isPending ? "Importing…" : label}
            <input type="file" accept=".csv,.xlsx,.xls,text/csv" multiple className="sr-only" aria-label="Tradebook files" disabled={save.isPending}
                onChange={e => { const files = e.target.files; if (files?.length) void load(files); e.target.value = "" }} />
        </label>
    )

    return (
        <Panel id={`tradebook-${id}`} title="Tradebook"
            description="Your broker's trade history for this portfolio. Zerodha: Console → Reports → Tradebook (equity). Groww: Reports → Stocks P&L or order history. Pick files covering every buy of what you still hold.">
            {isLoading ? <PanelSkeleton rows={2} /> : (
                <div className="p-4 space-y-3 text-sm">
                    {data ? (
                        <>
                            <dl className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                                <div>
                                    <dt className="text-xs text-muted-foreground">Annual return (XIRR)</dt>
                                    <dd className={cn("font-mono tabular-nums text-lg", tone(data.xirr))}>{data.xirr === null ? "—" : pct(data.xirr)}</dd>
                                </div>
                                <div>
                                    <dt className="text-xs text-muted-foreground">Trades</dt>
                                    <dd className="font-mono tabular-nums">{data.trades.toLocaleString()}{data.first_trade && <span className="text-xs text-muted-foreground"> since {shortDay(data.first_trade)} {data.first_trade.slice(0, 4)}</span>}</dd>
                                </div>
                                <div>
                                    <dt className="text-xs text-muted-foreground">Imported</dt>
                                    <dd>{timeAgo(data.imported_at)}</dd>
                                </div>
                            </dl>
                            <p className="text-xs text-muted-foreground">
                                The rebalancing plan now uses your buy dates: it prefers long-term gains, shows the tax on each sale and says when waiting a few weeks would cut it.
                                {data.xirr === null && " XIRR needs a month of history and a current price for every stock still held."}
                            </p>
                            {data.gaps.length > 0 && (
                                <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 space-y-1">
                                    <p className="font-medium text-foreground">The tradebook doesn't explain every holding</p>
                                    <p className="text-muted-foreground">These are left out of tax figures until a file with their missing buys is added:</p>
                                    <ul className="font-mono text-xs">
                                        {data.gaps.map(g => <li key={g.ticker}>{g.ticker}: {g.portfolio_shares} held, {g.tradebook_shares} in the tradebook</li>)}
                                    </ul>
                                </div>
                            )}
                            {data.warnings.length > 0 && (
                                <ul className="list-disc pl-5 text-xs text-muted-foreground space-y-0.5">{data.warnings.map(w => <li key={w}>{w}</li>)}</ul>
                            )}
                            <div className="flex flex-wrap gap-2">
                                {picker("Replace with new files")}
                                <Button variant="ghost" size="sm" disabled={save.isPending} onClick={() => save.mutate(null)}>Remove</Button>
                            </div>
                        </>
                    ) : (
                        <>
                            <p className="text-muted-foreground">
                                Without buy dates the app can't tell short-term gains (20% tax) from long-term ones (12.5%, the first ₹1.25 lakh a year free),
                                so the rebalancing plan assumes the worst. Import your tradebook to get real tax figures and this portfolio's annual return.
                            </p>
                            {picker("Import tradebook files")}
                        </>
                    )}
                    {error && <p role="alert" className="text-q-risk-high">{error}</p>}
                    {notes.length > 0 && (
                        <details className="text-xs text-muted-foreground">
                            <summary className="cursor-pointer">{notes.length} row{notes.length === 1 ? "" : "s"} skipped</summary>
                            <ul className="mt-1 space-y-0.5">{notes.slice(0, 50).map((n, i) => <li key={i}>{n}</li>)}</ul>
                        </details>
                    )}
                    <p className="text-xs text-muted-foreground">Trades are saved with this portfolio and only you can see them. Remove deletes them.</p>
                </div>
            )}
        </Panel>
    )
}
