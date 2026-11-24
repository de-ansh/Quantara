import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Pencil, Play, Plus, RefreshCw, Trash2, Upload, Wallet, X } from "lucide-react"
import PageHeader from "@/components/PageHeader"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { Button } from "@/components/ui/button"
import { cn, timeAgo } from "@/lib/utils"
import { getCurrencySymbol } from "@/lib/currency"
import { apiErrorDetail } from "@/lib/api"
import { fileAsCsv, parseHoldingsCsv } from "@/lib/holdingsCsv"
import PortfolioTotals from "@/components/PortfolioTotals"
import BalanceCheck from "@/components/BalanceCheck"
import { sumTotals } from "@/lib/money"
import {
    matchFunds,
    useDeletePortfolio,
    usePortfolios,
    usePortfolioUpdates,
    useSavePortfolio,
    type CurrencyTotals,
    type Portfolio,
    type PortfolioFund,
} from "@/hooks/usePortfolios"

interface DraftRow {
    key: string
    ticker: string
    weight: string // percent, as typed
    shares: string
    cost: string // average cost per share
}

interface Draft {
    id?: number
    name: string
    description: string
    initialInvestment: string
    rows: DraftRow[]
    funds: PortfolioFund[] // from an import; valued at NAV, not part of the weights
}

const SEGMENT_COLORS = ["bg-primary", "bg-emerald-500", "bg-amber-500", "bg-sky-500", "bg-rose-500", "bg-violet-500"]

let rowSeq = 0
const newRow = (ticker = "", weight = "", shares = "", cost = ""): DraftRow => ({ key: `row-${rowSeq++}`, ticker, weight, shares, cost })

const emptyDraft = (): Draft => ({ name: "", description: "", initialInvestment: "100000", rows: [newRow()], funds: [] })

const toDraft = (p: Portfolio): Draft => ({
    id: p.id,
    name: p.name,
    description: p.description ?? "",
    initialInvestment: String(p.initial_investment),
    rows: p.positions.map(pos => newRow(
        pos.ticker,
        String(Math.round(pos.weight * 1000) / 10),
        pos.shares ? String(pos.shares) : "",
        pos.cost_basis ? String(pos.cost_basis) : "",
    )).concat(p.positions.length ? [] : [newRow()]),
    funds: p.funds ?? [],
})

const portfolioCurrency = (p: Portfolio) =>
    p.funds?.length ? "₹" : getCurrencySymbol(p.positions.find(pos => /\.(NS|BO)$/i.test(pos.ticker))?.ticker)

const ISIN_OF_FUND_HOUSE = /^INF[A-Z0-9]{8}\d$/ // mutual funds and ETFs; an ETF's resolves to its listing instead

/** Returns an error message, or null when the draft can be saved. */
function validate(draft: Draft): string | null {
    if (!draft.name.trim()) return "Give the portfolio a name."
    if (!(Number(draft.initialInvestment) > 0)) return "Initial investment must be greater than 0."
    const rows = draft.rows.filter(r => r.ticker.trim())
    if (rows.length === 0) return draft.funds.length ? null : "Add at least one holding."
    const tickers = rows.map(r => r.ticker.trim().toUpperCase())
    if (new Set(tickers).size !== tickers.length) return "Each ticker can appear only once."
    if (rows.some(r => Number(r.shares) < 0 || Number(r.cost) < 0)) return "Shares and cost can't be negative."
    if (!rows.some(r => r.weight.trim())) {
        // No weights: the server weights by market value, which needs a share count everywhere
        return rows.every(r => Number(r.shares) > 0) ? null : "Enter weights, or a share count for every holding."
    }
    if (rows.some(r => !(Number(r.weight) > 0))) return "Every holding needs a weight above 0%."
    const total = rows.reduce((sum, r) => sum + Number(r.weight), 0)
    if (Math.abs(total - 100) > 0.5) return `Weights add up to ${total.toFixed(1)}%; they must total 100%.`
    return null
}

function PortfolioEditor({ initial, onClose }: { initial: Draft; onClose: () => void }) {
    const [draft, setDraft] = useState<Draft>(initial)
    const [error, setError] = useState<string | null>(null)
    const [notice, setNotice] = useState<string | null>(null)
    const save = useSavePortfolio()

    const importCsv = async (file: File) => {
        setError(null)
        setNotice(null)
        try {
            const { holdings, skipped } = parseHoldingsCsv(await fileAsCsv(file))
            // Rows with only a name, or a fund house's ISIN, may be mutual funds: ask the server which scheme each is
            const maybeFunds = holdings.filter(h => !h.ticker || ISIN_OF_FUND_HOUSE.test(h.ticker))
            const matches = maybeFunds.length
                ? await matchFunds(maybeFunds.map(h => ({ isin: h.ticker || null, name: h.name })))
                : []
            const funds: PortfolioFund[] = []
            const fundRows = new Set<typeof holdings[number]>()
            maybeFunds.forEach((h, i) => {
                const m = matches[i]
                if (m && !funds.some(f => f.scheme_code === m.scheme_code)) {
                    funds.push({ scheme_code: m.scheme_code, name: m.name, units: h.shares, cost_basis: h.cost })
                    fundRows.add(h)
                } else if (!h.ticker) {
                    skipped.push(`${h.name}: not a ticker symbol or a mutual fund we could match`)
                    fundRows.add(h)
                }
            })
            const stocks = holdings.filter(h => !fundRows.has(h))
            if (stocks.length === 0 && funds.length === 0) {
                setError("No holdings found in that file." + (skipped.length ? ` Skipped: ${skipped.join("; ")}` : ""))
                return
            }
            // Weights left blank: the server weights by market value from the share counts. A file of only
            // stocks or only funds replaces that kind and keeps the other, so both files can go in one portfolio
            setDraft(d => {
                const rows = stocks.length ? stocks.map(h => newRow(h.ticker, "", String(h.shares), h.cost ? String(h.cost) : "")) : d.rows
                const kept = funds.length ? funds : d.funds
                const invested = rows.reduce((sum, r) => sum + (Number(r.shares) || 0) * (Number(r.cost) || 0), 0)
                    + kept.reduce((sum, f) => sum + f.units * f.cost_basis, 0)
                return {
                    ...d,
                    name: d.name || "My holdings",
                    initialInvestment: invested > 0 ? String(Math.round(invested)) : d.initialInvestment,
                    rows,
                    funds: kept,
                }
            })
            const parts = [
                stocks.length && `${stocks.length} holding${stocks.length === 1 ? "" : "s"}`,
                funds.length && `${funds.length} mutual fund${funds.length === 1 ? "" : "s"}`,
            ].filter(Boolean)
            setNotice(
                `Imported ${parts.join(" and ")}. Check them, then save.` +
                (skipped.length ? ` Skipped ${skipped.length}: ${skipped.join("; ")}.` : ""),
            )
        } catch (err) {
            setError(apiErrorDetail(err) ?? (err instanceof Error ? err.message : "Couldn't read that file."))
        }
    }

    const total = draft.rows.reduce((sum, r) => sum + (Number(r.weight) || 0), 0)
    const updateRow = (key: string, patch: Partial<DraftRow>) =>
        setDraft(d => ({ ...d, rows: d.rows.map(r => (r.key === key ? { ...r, ...patch } : r)) }))

    const normalize = () => {
        if (total <= 0) return
        setDraft(d => ({
            ...d,
            rows: d.rows.map(r => ({ ...r, weight: String(Math.round(((Number(r.weight) || 0) / total) * 1000) / 10) })),
        }))
    }

    const handleSave = async () => {
        const problem = validate(draft)
        if (problem) {
            setError(problem)
            return
        }
        setError(null)
        const rows = draft.rows.filter(r => r.ticker.trim())
        const sum = rows.reduce((s, r) => s + (Number(r.weight) || 0), 0)
        try {
            await save.mutateAsync({
                id: draft.id,
                name: draft.name.trim(),
                description: draft.description.trim() || null,
                initial_investment: Number(draft.initialInvestment),
                // Rescale so rounding in the inputs still sums to exactly 1
                positions: rows.map(r => ({
                    ticker: r.ticker.trim().toUpperCase(),
                    weight: sum > 0 ? Number(r.weight) / sum : 0,
                    shares: Number(r.shares) || 0,
                    cost_basis: Number(r.cost) || 0,
                })),
                funds: draft.funds.map(({ scheme_code, units, cost_basis }) => ({ scheme_code, units, cost_basis })),
            })
            onClose()
        } catch (err) {
            setError(apiErrorDetail(err) ?? "Could not save the portfolio. Please try again.")
        }
    }

    const inputClass = "w-full bg-background border border-border text-sm px-3 py-2 rounded-md text-foreground focus:border-primary focus:ring-0 outline-none"
    const labelClass = "text-xs font-medium text-muted-foreground"

    return (
        <Panel id="portfolio-editor" title={draft.id ? "Edit portfolio" : "New portfolio"}
            action={<button onClick={onClose} aria-label="Close editor" className="text-muted-foreground hover:text-foreground"><X className="size-4" /></button>}>
            <div className="p-4 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <label className="space-y-1">
                        <span className={labelClass}>Name</span>
                        <input className={inputClass} value={draft.name} maxLength={100}
                            onChange={e => setDraft(d => ({ ...d, name: e.target.value }))} placeholder="Core growth" />
                    </label>
                    <label className="space-y-1">
                        <span className={labelClass}>Amount invested</span>
                        <input className={cn(inputClass, "font-mono tabular-nums")} type="number" min={1} value={draft.initialInvestment}
                            onChange={e => setDraft(d => ({ ...d, initialInvestment: e.target.value }))} />
                    </label>
                </div>
                <label className="space-y-1 block">
                    <span className={labelClass}>Description (optional)</span>
                    <input className={inputClass} value={draft.description}
                        onChange={e => setDraft(d => ({ ...d, description: e.target.value }))} />
                </label>

                <div className="space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-sm font-medium text-foreground">Holdings</span>
                        <div className="flex items-center gap-3 text-xs">
                            <span className={cn("font-mono tabular-nums", Math.abs(total - 100) <= 0.5 ? "text-q-risk-low" : "text-amber-600 dark:text-amber-400")}>
                                Weights total {total.toFixed(1)}%
                            </span>
                            <button type="button" onClick={normalize} className="flex items-center gap-1 text-muted-foreground hover:text-foreground">
                                <RefreshCw className="size-3" /> Scale to 100%
                            </button>
                            <label title="Fill the holdings from your broker's holdings export (CSV or Excel)"
                                className="flex items-center gap-1 text-primary hover:underline cursor-pointer focus-within:ring-2 focus-within:ring-primary rounded-sm">
                                <Upload className="size-3" /> Import file
                                <input type="file" accept=".csv,.xlsx,.xls,text/csv" className="sr-only" aria-label="Import holdings CSV"
                                    onChange={e => {
                                        const file = e.target.files?.[0]
                                        e.target.value = ""  // choosing the same file again still triggers a change
                                        if (file) void importCsv(file)
                                    }} />
                            </label>
                        </div>
                    </div>
                    <p className="text-xs text-muted-foreground">
                        Weights drive the simulator. Add shares and average cost to track value and gain or loss, or leave
                        weights blank to weight by market value.
                    </p>
                    {draft.rows.map(row => (
                        <div key={row.key} className="flex items-center gap-2">
                            <input className={cn(inputClass, "uppercase flex-1")} placeholder="Ticker (e.g. AAPL, TCS.NS)"
                                aria-label="Ticker" value={row.ticker}
                                onChange={e => updateRow(row.key, { ticker: e.target.value })} />
                            <div className="relative w-28">
                                <input className={cn(inputClass, "font-mono tabular-nums pr-7")} type="number" min={0} max={100} step={0.1}
                                    aria-label={`Weight for ${row.ticker || "holding"}`} value={row.weight}
                                    onChange={e => updateRow(row.key, { weight: e.target.value })} />
                                <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">%</span>
                            </div>
                            <input className={cn(inputClass, "font-mono tabular-nums w-24")} type="number" min={0} step="any" placeholder="Shares"
                                aria-label={`Shares of ${row.ticker || "holding"}`} value={row.shares}
                                onChange={e => updateRow(row.key, { shares: e.target.value })} />
                            <input className={cn(inputClass, "font-mono tabular-nums w-28")} type="number" min={0} step="any" placeholder="Avg cost"
                                aria-label={`Average cost of ${row.ticker || "holding"}`} value={row.cost}
                                onChange={e => updateRow(row.key, { cost: e.target.value })} />
                            <button type="button" aria-label="Remove holding" disabled={draft.rows.length <= 1}
                                onClick={() => setDraft(d => ({ ...d, rows: d.rows.filter(r => r.key !== row.key) }))}
                                className="p-2 text-muted-foreground hover:text-q-risk-high disabled:opacity-30">
                                <Trash2 className="size-4" />
                            </button>
                        </div>
                    ))}
                    <button type="button" onClick={() => setDraft(d => ({ ...d, rows: [...d.rows, newRow()] }))}
                        className="flex items-center gap-1 text-sm text-primary hover:underline">
                        <Plus className="size-4" /> Add holding
                    </button>
                </div>

                {draft.funds.length > 0 && (
                    <div className="space-y-2">
                        <span className="text-sm font-medium text-foreground">Mutual funds</span>
                        <p className="text-xs text-muted-foreground">
                            Valued at the latest NAV. They count in value and gain or loss, not in the simulator. Import a fund file again to change them.
                        </p>
                        <ul className="space-y-1">
                            {draft.funds.map(f => (
                                <li key={f.scheme_code} className="flex items-center gap-2 text-sm border border-border rounded-md px-3 py-2">
                                    <span className="flex-1 text-foreground">{f.name}</span>
                                    <span className="font-mono tabular-nums text-muted-foreground">
                                        {f.units.toLocaleString()} units{f.cost_basis ? ` @ ₹${f.cost_basis.toLocaleString("en-IN")}` : ""}
                                    </span>
                                    <button type="button" aria-label={`Remove ${f.name}`}
                                        onClick={() => setDraft(d => ({ ...d, funds: d.funds.filter(x => x.scheme_code !== f.scheme_code) }))}
                                        className="p-1 text-muted-foreground hover:text-q-risk-high">
                                        <Trash2 className="size-4" />
                                    </button>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {notice && <p role="status" className="text-sm text-muted-foreground">{notice}</p>}
                {error && <p role="alert" className="text-sm text-q-risk-high">{error}</p>}

                <div className="flex justify-end gap-2">
                    <Button variant="ghost" onClick={onClose}>Cancel</Button>
                    <Button onClick={handleSave} disabled={save.isPending}>
                        {save.isPending ? "Saving…" : "Save portfolio"}
                    </Button>
                </div>
            </div>
        </Panel>
    )
}

function PortfolioCard({ portfolio, totals, onEdit }: { portfolio: Portfolio; totals?: CurrencyTotals[]; onEdit: () => void }) {
    const navigate = useNavigate()
    const remove = useDeletePortfolio()
    const [confirming, setConfirming] = useState(false)
    const sym = portfolioCurrency(portfolio)
    const holdingsCount = `${portfolio.positions.length} holding${portfolio.positions.length === 1 ? "" : "s"}` +
        (portfolio.funds?.length ? ` and ${portfolio.funds.length} fund${portfolio.funds.length === 1 ? "" : "s"}` : "")

    return (
        <Panel id={`portfolio-${portfolio.id}`} title={portfolio.name} className="flex flex-col"
            description={portfolio.description || `Updated ${timeAgo(portfolio.updated_at)}`}>
            <div className="p-4 space-y-3 flex-1 flex flex-col">
                {totals && totals.length > 0 ? (
                    <>
                        <PortfolioTotals totals={totals} />
                        <p className="text-xs text-muted-foreground">{holdingsCount}</p>
                    </>
                ) : (
                    // No share counts (weights only): nothing to value, so show what was put in
                    <div className="flex items-baseline justify-between">
                        <span className="text-lg font-semibold font-mono tabular-nums text-foreground">
                            {sym}{portfolio.initial_investment.toLocaleString(sym === "₹" ? "en-IN" : "en-US")}
                            <span className="ml-1.5 font-sans text-xs font-normal text-muted-foreground">invested</span>
                        </span>
                        <span className="text-xs text-muted-foreground">{holdingsCount}</span>
                    </div>
                )}

                {portfolio.positions.length > 0 && (
                    <>
                        <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted" aria-hidden="true">
                            {portfolio.positions.map((pos, i) => (
                                <div key={pos.ticker} className={SEGMENT_COLORS[i % SEGMENT_COLORS.length]} style={{ width: `${pos.weight * 100}%` }} />
                            ))}
                        </div>
                        <ul aria-label="Weights" className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
                            {portfolio.positions.map((pos, i) => (
                                <li key={pos.ticker} className="flex items-center gap-1.5">
                                    <span className={cn("size-2 rounded-full", SEGMENT_COLORS[i % SEGMENT_COLORS.length])} aria-hidden="true" />
                                    <span className="text-foreground font-medium">{pos.ticker}</span>
                                    <span className="font-mono tabular-nums text-muted-foreground">{(pos.weight * 100).toFixed(1)}%</span>
                                </li>
                            ))}
                        </ul>
                    </>
                )}

                <div className="flex items-center gap-2 pt-3 mt-auto border-t border-border">
                    <Button size="sm" variant="outline" onClick={() => navigate(`/portfolios/${portfolio.id}`)} className="gap-1.5">
                        <Wallet className="size-4" /> Holdings
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => navigate(`/simulation?portfolio=${portfolio.id}`)} className="gap-1.5">
                        <Play className="size-4" /> Simulate
                    </Button>
                    <Button size="sm" variant="ghost" onClick={onEdit} className="gap-1.5">
                        <Pencil className="size-4" /> Edit
                    </Button>
                    <div className="ml-auto">
                        {confirming ? (
                            <span className="flex items-center gap-2 text-sm">
                                Delete?
                                <button className="font-medium text-q-risk-high hover:underline" disabled={remove.isPending}
                                    onClick={() => remove.mutate(portfolio.id)}>Yes</button>
                                <button className="text-muted-foreground hover:underline" onClick={() => setConfirming(false)}>No</button>
                            </span>
                        ) : (
                            <Button size="sm" variant="ghost" onClick={() => setConfirming(true)} aria-label={`Delete ${portfolio.name}`}
                                className="text-muted-foreground hover:text-q-risk-high">
                                <Trash2 className="size-4" />
                            </Button>
                        )}
                    </div>
                </div>
            </div>
        </Panel>
    )
}

export default function Portfolios() {
    const { data: portfolios = [], isLoading, isError } = usePortfolios()
    const { data: values } = usePortfolioUpdates()  // the dashboard's query: value, today and gain or loss per portfolio
    const totalsOf = (id: number) => values?.find(v => v.portfolio_id === id)?.performance.totals
    const valued = (values ?? []).filter(v => v.performance.totals.length > 0)
    const [editing, setEditing] = useState<Draft | null>(null)
    const newButton = <Button onClick={() => setEditing(emptyDraft())} className="gap-1.5"><Plus className="size-4" /> New portfolio</Button>

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto">
            <PageHeader
                title="Portfolios"
                description="Your holdings, imported from a broker file or typed in. Open one to see its value, or run it through the simulator."
                actions={!editing && newButton}
            />

            {editing && <PortfolioEditor key={editing.id ?? "new"} initial={editing} onClose={() => setEditing(null)} />}

            {valued.length > 1 && (
                <Panel id="all-portfolios" title={`All ${valued.length} portfolios together`} description="Every holding you've given a share count, at the latest prices">
                    <div className="p-4"><PortfolioTotals totals={sumTotals(valued.map(v => v.performance.totals))} size="lg" /></div>
                </Panel>
            )}

            {isLoading ? <Panel id="portfolio-list" title="Portfolios"><PanelSkeleton /></Panel>
                : isError ? <Panel id="portfolio-list" title="Portfolios"><PanelMessage alert>Couldn't load portfolios.</PanelMessage></Panel>
                : portfolios.length === 0 && !editing ? (
                    <Panel id="portfolio-list" title="No portfolios yet">
                        <div className="p-4 space-y-3">
                            <p className="text-sm text-muted-foreground">
                                Create one here (you can import your broker's holdings file), or build an allocation in Simulation and save it.
                            </p>
                            {newButton}
                        </div>
                    </Panel>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                        {portfolios.map(p => <PortfolioCard key={p.id} portfolio={p} totals={totalsOf(p.id)} onEdit={() => setEditing(toDraft(p))} />)}
                    </div>
                )}

            {valued.length > 1 && <BalanceCheck id="all" />}
        </div>
    )
}
