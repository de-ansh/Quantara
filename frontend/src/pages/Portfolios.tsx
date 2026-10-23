import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Briefcase, Pencil, Play, Plus, RefreshCw, Trash2, X } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { cn, timeAgo } from "@/lib/utils"
import { getCurrencySymbol } from "@/lib/currency"
import { apiErrorDetail } from "@/lib/api"
import {
    useDeletePortfolio,
    usePortfolios,
    useSavePortfolio,
    type Portfolio,
} from "@/hooks/usePortfolios"

interface DraftRow {
    key: string
    ticker: string
    weight: string // percent, as typed
}

interface Draft {
    id?: number
    name: string
    description: string
    initialInvestment: string
    rows: DraftRow[]
}

const SEGMENT_COLORS = ["bg-primary", "bg-emerald-500", "bg-amber-500", "bg-sky-500", "bg-rose-500", "bg-violet-500"]

let rowSeq = 0
const newRow = (ticker = "", weight = ""): DraftRow => ({ key: `row-${rowSeq++}`, ticker, weight })

const emptyDraft = (): Draft => ({ name: "", description: "", initialInvestment: "100000", rows: [newRow()] })

const toDraft = (p: Portfolio): Draft => ({
    id: p.id,
    name: p.name,
    description: p.description ?? "",
    initialInvestment: String(p.initial_investment),
    rows: p.positions.map(pos => newRow(pos.ticker, String(Math.round(pos.weight * 1000) / 10))),
})

const portfolioCurrency = (p: Portfolio) => getCurrencySymbol(p.positions.find(pos => /\.(NS|BO)$/i.test(pos.ticker))?.ticker)

/** Returns an error message, or null when the draft can be saved. */
function validate(draft: Draft): string | null {
    if (!draft.name.trim()) return "Give the portfolio a name."
    if (!(Number(draft.initialInvestment) > 0)) return "Initial investment must be greater than 0."
    const rows = draft.rows.filter(r => r.ticker.trim())
    if (rows.length === 0) return "Add at least one holding."
    const tickers = rows.map(r => r.ticker.trim().toUpperCase())
    if (new Set(tickers).size !== tickers.length) return "Each ticker can appear only once."
    if (rows.some(r => !(Number(r.weight) > 0))) return "Every holding needs a weight above 0%."
    const total = rows.reduce((sum, r) => sum + Number(r.weight), 0)
    if (Math.abs(total - 100) > 0.5) return `Weights add up to ${total.toFixed(1)}%; they must total 100%.`
    return null
}

function PortfolioEditor({ initial, onClose }: { initial: Draft; onClose: () => void }) {
    const [draft, setDraft] = useState<Draft>(initial)
    const [error, setError] = useState<string | null>(null)
    const save = useSavePortfolio()

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
        const sum = rows.reduce((s, r) => s + Number(r.weight), 0)
        try {
            await save.mutateAsync({
                id: draft.id,
                name: draft.name.trim(),
                description: draft.description.trim() || null,
                initial_investment: Number(draft.initialInvestment),
                // Rescale so rounding in the inputs still sums to exactly 1
                positions: rows.map(r => ({ ticker: r.ticker.trim().toUpperCase(), weight: Number(r.weight) / sum })),
            })
            onClose()
        } catch (err) {
            setError(apiErrorDetail(err) ?? "Could not save the portfolio. Please try again.")
        }
    }

    const inputClass = "w-full bg-background border border-border text-sm px-3 py-2 rounded-sm text-foreground focus:border-primary focus:ring-0 outline-none"

    return (
        <Card className="bg-card border-border shadow-none">
            <CardHeader className="p-4 border-b border-border flex-row items-center justify-between space-y-0">
                <CardTitle className="text-xs font-bold uppercase tracking-wider">
                    {draft.id ? "Edit Portfolio" : "New Portfolio"}
                </CardTitle>
                <button onClick={onClose} aria-label="Close editor" className="text-muted-foreground hover:text-foreground">
                    <X className="size-4" />
                </button>
            </CardHeader>
            <CardContent className="p-4 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <label className="space-y-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Name</span>
                        <input className={inputClass} value={draft.name} maxLength={100}
                            onChange={e => setDraft(d => ({ ...d, name: e.target.value }))} placeholder="Core growth" />
                    </label>
                    <label className="space-y-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Initial investment</span>
                        <input className={cn(inputClass, "font-mono")} type="number" min={1} value={draft.initialInvestment}
                            onChange={e => setDraft(d => ({ ...d, initialInvestment: e.target.value }))} />
                    </label>
                </div>
                <label className="space-y-1 block">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Description (optional)</span>
                    <input className={inputClass} value={draft.description}
                        onChange={e => setDraft(d => ({ ...d, description: e.target.value }))} />
                </label>

                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Holdings</span>
                        <div className="flex items-center gap-2 font-mono text-[10px]">
                            <span className={cn("px-1.5 py-0.5 rounded-sm font-bold",
                                Math.abs(total - 100) <= 0.5 ? "bg-green-500/20 text-green-400" : "bg-amber-500/20 text-amber-400")}>
                                Total: {total.toFixed(1)}%
                            </span>
                            <button type="button" onClick={normalize} title="Scale weights to 100%"
                                className="flex items-center gap-1 text-muted-foreground hover:text-foreground">
                                <RefreshCw className="size-3" /> Normalize
                            </button>
                        </div>
                    </div>
                    {draft.rows.map(row => (
                        <div key={row.key} className="flex items-center gap-2">
                            <input className={cn(inputClass, "font-mono uppercase flex-1")} placeholder="Ticker (e.g. AAPL, TCS.NS)"
                                aria-label="Ticker" value={row.ticker}
                                onChange={e => updateRow(row.key, { ticker: e.target.value })} />
                            <div className="relative w-28">
                                <input className={cn(inputClass, "font-mono pr-7")} type="number" min={0} max={100} step={0.1}
                                    aria-label={`Weight for ${row.ticker || "holding"}`} value={row.weight}
                                    onChange={e => updateRow(row.key, { weight: e.target.value })} />
                                <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">%</span>
                            </div>
                            <button type="button" aria-label="Remove holding" disabled={draft.rows.length <= 1}
                                onClick={() => setDraft(d => ({ ...d, rows: d.rows.filter(r => r.key !== row.key) }))}
                                className="p-2 text-muted-foreground hover:text-q-risk-high disabled:opacity-30">
                                <Trash2 className="size-4" />
                            </button>
                        </div>
                    ))}
                    <button type="button" onClick={() => setDraft(d => ({ ...d, rows: [...d.rows, newRow()] }))}
                        className="flex items-center gap-1 text-[11px] font-bold text-primary hover:underline">
                        <Plus className="size-3" /> Add holding
                    </button>
                </div>

                {error && <p role="alert" className="text-xs text-q-risk-high">{error}</p>}

                <div className="flex justify-end gap-2">
                    <Button variant="ghost" onClick={onClose}>Cancel</Button>
                    <Button onClick={handleSave} disabled={save.isPending}>
                        {save.isPending ? "Saving..." : "Save portfolio"}
                    </Button>
                </div>
            </CardContent>
        </Card>
    )
}

function PortfolioCard({ portfolio, onEdit }: { portfolio: Portfolio; onEdit: () => void }) {
    const navigate = useNavigate()
    const remove = useDeletePortfolio()
    const [confirming, setConfirming] = useState(false)
    const sym = portfolioCurrency(portfolio)

    return (
        <Card className="bg-q-surface border-q-border shadow-none flex flex-col">
            <CardHeader className="p-4 pb-2 space-y-1">
                <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-sm font-bold text-foreground">{portfolio.name}</CardTitle>
                    <span className="text-[10px] font-mono text-muted-foreground shrink-0">
                        Updated {timeAgo(portfolio.updated_at)}
                    </span>
                </div>
                {portfolio.description && <p className="text-xs text-muted-foreground">{portfolio.description}</p>}
            </CardHeader>
            <CardContent className="p-4 pt-2 space-y-3 flex-1 flex flex-col">
                <div className="flex items-baseline justify-between font-mono">
                    <span className="text-lg font-bold text-foreground">{sym}{portfolio.initial_investment.toLocaleString()}</span>
                    <span className="text-[10px] uppercase text-muted-foreground">{portfolio.positions.length} holdings</span>
                </div>

                {/* Allocation bar */}
                <div className="flex h-2 w-full overflow-hidden rounded-full bg-q-border" aria-hidden="true">
                    {portfolio.positions.map((pos, i) => (
                        <div key={pos.ticker} className={SEGMENT_COLORS[i % SEGMENT_COLORS.length]} style={{ width: `${pos.weight * 100}%` }} />
                    ))}
                </div>
                <ul className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] font-mono">
                    {portfolio.positions.map((pos, i) => (
                        <li key={pos.ticker} className="flex items-center gap-1.5">
                            <span className={cn("size-2 rounded-full", SEGMENT_COLORS[i % SEGMENT_COLORS.length])} />
                            <span className="text-foreground font-bold">{pos.ticker}</span>
                            <span className="text-muted-foreground">{(pos.weight * 100).toFixed(1)}%</span>
                        </li>
                    ))}
                </ul>

                <div className="flex items-center gap-2 pt-2 mt-auto border-t border-q-border/50">
                    <Button size="sm" onClick={() => navigate(`/simulation?portfolio=${portfolio.id}`)} className="gap-1">
                        <Play className="size-3" /> Simulate
                    </Button>
                    <Button size="sm" variant="ghost" onClick={onEdit} className="gap-1">
                        <Pencil className="size-3" /> Edit
                    </Button>
                    <div className="ml-auto">
                        {confirming ? (
                            <span className="flex items-center gap-2 text-[11px]">
                                Delete?
                                <button className="font-bold text-q-risk-high hover:underline" disabled={remove.isPending}
                                    onClick={() => remove.mutate(portfolio.id)}>Yes</button>
                                <button className="text-muted-foreground hover:underline" onClick={() => setConfirming(false)}>No</button>
                            </span>
                        ) : (
                            <Button size="sm" variant="ghost" onClick={() => setConfirming(true)} aria-label={`Delete ${portfolio.name}`}
                                className="text-muted-foreground hover:text-q-risk-high">
                                <Trash2 className="size-3.5" />
                            </Button>
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}

export default function Portfolios() {
    const { data: portfolios = [], isLoading, isError } = usePortfolios()
    const [editing, setEditing] = useState<Draft | null>(null)

    return (
        <div className="p-6 space-y-6 bg-background min-h-full">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-border">
                <div>
                    <h1 className="text-2xl font-black uppercase tracking-tight flex items-center gap-2 text-foreground">
                        <Briefcase className="size-6 text-primary" /> Portfolios
                    </h1>
                    <p className="text-[10px] text-muted-foreground uppercase font-bold tracking-widest mt-1">
                        Save allocations and run them through the simulator
                    </p>
                </div>
                {!editing && (
                    <Button onClick={() => setEditing(emptyDraft())} className="gap-1">
                        <Plus className="size-4" /> New portfolio
                    </Button>
                )}
            </div>

            {editing && <PortfolioEditor key={editing.id ?? "new"} initial={editing} onClose={() => setEditing(null)} />}

            {isLoading && <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground">Loading portfolios...</p>}
            {isError && <p role="alert" className="text-xs text-q-risk-high">Could not load portfolios.</p>}

            {!isLoading && !isError && portfolios.length === 0 && !editing && (
                <div className="border border-dashed border-border p-10 text-center space-y-3">
                    <p className="text-sm text-foreground font-bold">No portfolios yet</p>
                    <p className="text-xs text-muted-foreground">
                        Create one here, or build an allocation in Simulation and save it.
                    </p>
                    <Button onClick={() => setEditing(emptyDraft())} className="gap-1">
                        <Plus className="size-4" /> New portfolio
                    </Button>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {portfolios.map(p => (
                    <PortfolioCard key={p.id} portfolio={p} onEdit={() => setEditing(toDraft(p))} />
                ))}
            </div>
        </div>
    )
}
