import { useState } from "react"
import { useSearchParams } from "react-router-dom"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import { Download, Play, Plus, RefreshCw, Save, Trash2 } from "lucide-react"
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import apiClient, { resolveTicker } from "@/lib/api"
import { cn } from "@/lib/utils"
import { exportToCsv } from "@/lib/export"
import { isIndianAsset } from "@/lib/currency"
import { useQuickTickers } from "@/hooks/useStockUniverse"
import { usePortfolios, useSavePortfolio } from "@/hooks/usePortfolios"
import PageHeader from "@/components/PageHeader"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { Button } from "@/components/ui/button"

interface Holding {
    id: string
    ticker: string
    weight: number
}

const US_PRESET: Holding[] = [
    { id: "us-1", ticker: "AAPL", weight: 35 },
    { id: "us-2", ticker: "NVDA", weight: 25 },
    { id: "us-3", ticker: "TLT", weight: 20 },
    { id: "us-4", ticker: "GLD", weight: 12 },
    { id: "us-5", ticker: "BIL", weight: 8 },
]
const INDIA_PRESET: Holding[] = [
    { id: "in-1", ticker: "RELIANCE.NS", weight: 35 },
    { id: "in-2", ticker: "TCS.NS", weight: 25 },
    { id: "in-3", ticker: "HDFCBANK.NS", weight: 25 },
    { id: "in-4", ticker: "INFY.NS", weight: 15 },
]

type Scenario = "conservative" | "base" | "aggressive"

// API values stay as-is; labels describe what each mode does to the projection.
const SCENARIOS: { value: Scenario; label: string; title: string }[] = [
    { value: "conservative", label: "Stress", title: "Volatility 20% higher, returns 10% lower" },
    { value: "base", label: "Base", title: "Estimates as measured" },
    { value: "aggressive", label: "Optimistic", title: "Volatility 15% lower, returns 10% higher" },
]

interface TrajectoryPoint {
    month: number
    median: number
    upper_95: number
    lower_5: number
}

interface SimulationResult {
    expected_return: number
    expected_volatility: number
    sharpe_ratio: number
    max_drawdown: number
    portfolio_beta: number
    trajectory: TrajectoryPoint[]
    diversification_benefit_pct: number
    correlation_matrix: Record<string, Record<string, number>>
    estimated_tickers: string[]
    risk_free_pct?: number // weighted by holding: India's rates for Indian stocks, US ones for US stocks
    equity_premium_pct?: number
}

const toPayloadStocks = (holdings: Holding[]) => {
    const sum = holdings.reduce((acc, h) => acc + h.weight, 0)
    return holdings.map(h => ({ ticker: h.ticker, weight: sum > 0 ? h.weight / sum : 1 / holdings.length }))
}

const INVESTMENT_OPTIONS = [100000, 500000, 1000000, 2500000, 5000000]
const HORIZONS = [5, 10, 20, 30]
const fieldClass = "bg-background border border-border text-sm px-2 py-1.5 rounded-md text-foreground outline-none focus:border-primary"

/** Correlation cell tint, same bands as Compare: red moves together, green diversifies. */
const corrClass = (c: number) =>
    c >= 0.7 ? "bg-q-risk-high/15 text-q-risk-high" : c >= 0.4 ? "bg-amber-500/15 text-amber-600 dark:text-amber-400" : "bg-q-risk-low/15 text-q-risk-low"

export default function Simulation() {
    const quickTickers = useQuickTickers()
    const [searchParams] = useSearchParams()
    const { data: portfolios = [] } = usePortfolios()
    const savePortfolio = useSavePortfolio()
    const [loaded, setLoaded] = useState<{ id: number; name: string } | null>(null)
    const [saveName, setSaveName] = useState<string | null>(null)
    const [saveMessage, setSaveMessage] = useState<{ text: string; ok: boolean } | null>(null)
    // ?tickers=A,B,C (from Explorer) starts an equal-weight portfolio of those tickers
    const [initialHoldings] = useState<Holding[]>(() => {
        const tickers = [...new Set((searchParams.get("tickers") ?? "").split(",").map(t => t.trim().toUpperCase()).filter(Boolean))]
        return tickers.length
            ? tickers.map(t => ({ id: `q-${t}`, ticker: t, weight: Math.round(1000 / tickers.length) / 10 }))
            : US_PRESET
    })
    const [holdings, setHoldings] = useState<Holding[]>(initialHoldings)
    const [newTickerInput, setNewTickerInput] = useState("")
    // Holdings as of the last run; editing weights doesn't refetch until then
    const [runHoldings, setRunHoldings] = useState<Holding[]>(initialHoldings)
    const [horizonYears, setHorizonYears] = useState(10)
    const [scenario, setScenario] = useState<Scenario>("base")
    const [initialInvestment, setInitialInvestment] = useState(1000000)
    const [view, setView] = useState<"chart" | "correlation">("chart")

    // Load ?portfolio=<id> once its data arrives (state adjusted during render, not in an effect)
    const requested = portfolios.find(p => String(p.id) === searchParams.get("portfolio"))
    if (requested && loaded?.id !== requested.id) {
        setLoaded({ id: requested.id, name: requested.name })
        setHoldings(requested.positions.map(pos => ({
            id: `p-${requested.id}-${pos.ticker}`,
            ticker: pos.ticker,
            weight: Math.round(pos.weight * 1000) / 10,
        })))
        setInitialInvestment(requested.initial_investment)
        setRunHoldings(requested.positions.map(pos => ({
            id: `p-${requested.id}-${pos.ticker}`,
            ticker: pos.ticker,
            weight: pos.weight * 100,
        })))
    }

    const handleSavePortfolio = async (asNew: boolean) => {
        const name = asNew ? saveName?.trim() : loaded?.name
        if (!name) return
        const sum = holdings.reduce((acc, h) => acc + h.weight, 0)
        if (sum <= 0) return
        try {
            const saved = await savePortfolio.mutateAsync({
                id: asNew ? undefined : loaded?.id,
                name,
                description: null,
                initial_investment: initialInvestment,
                positions: holdings.map(h => ({ ticker: h.ticker, weight: h.weight / sum })),
            })
            setLoaded({ id: saved.id, name: saved.name })
            setSaveName(null)
            setSaveMessage({ text: asNew ? `Saved as "${saved.name}"` : `Updated "${saved.name}"`, ok: true })
        } catch {
            setSaveMessage({ text: "Could not save portfolio", ok: false })
        }
        setTimeout(() => setSaveMessage(null), 3000)
    }

    const isIndian = holdings.some(h => isIndianAsset(h.ticker))
    const currSym = isIndian ? "₹" : "$"
    const locale = isIndian ? "en-IN" : "en-US"
    const amount = (v: number) => `${currSym}${Math.round(v).toLocaleString(locale)}`
    const totalWeight = holdings.reduce((sum, h) => sum + h.weight, 0)

    const handleNormalize = () => {
        if (totalWeight <= 0) return
        setHoldings(prev => prev.map(h => ({ ...h, weight: Math.round((h.weight / totalWeight) * 1000) / 10 })))
    }

    const handleAddTicker = async (tickerToAdd?: string) => {
        const typed = (tickerToAdd || newTickerInput).trim()
        if (!typed) return
        // The listing the user means ("ITC" -> ITC.NS); unknown input is kept so the run reports it
        const sym = (await resolveTicker(typed)) ?? typed.toUpperCase()
        if (!holdings.some(h => h.ticker === sym)) setHoldings(prev => [...prev, { id: `${Date.now()}-${sym}`, ticker: sym, weight: 10 }])
        setNewTickerInput("")
    }

    const runStocks = toPayloadStocks(runHoldings)
    const { data: result = null, isFetching, isError, refetch } = useQuery<SimulationResult>({
        queryKey: ["simulate", runStocks, initialInvestment, horizonYears, scenario],
        queryFn: async () => (await apiClient.post<SimulationResult>("/portfolio/simulate", {
            stocks: runStocks,
            initial_investment: initialInvestment,
            time_horizon_months: horizonYears * 12,
            volatility_mode: scenario,
        })).data,
        enabled: runStocks.length > 0,
        placeholderData: keepPreviousData,
    })

    const runSimulation = () => {
        if (JSON.stringify(toPayloadStocks(holdings)) === JSON.stringify(runStocks)) refetch()
        else setRunHoldings(holdings)
    }
    const edited = JSON.stringify(toPayloadStocks(holdings)) !== JSON.stringify(runStocks)

    const chartData = result?.trajectory ?? []
    const end = chartData[chartData.length - 1]

    const handleExport = () => exportToCsv("quantara_portfolio_projection.csv", chartData.map(pt => ({
        year: Number((pt.month / 12).toFixed(1)),
        month: pt.month,
        median_value: Math.round(pt.median),
        upper_95_ci: Math.round(pt.upper_95),
        lower_5_ci: Math.round(pt.lower_5),
        expected_return_pct: result?.expected_return.toFixed(2) ?? "",
        volatility_pct: result?.expected_volatility.toFixed(2) ?? "",
        sharpe_ratio: result?.sharpe_ratio.toFixed(2) ?? "",
    })))

    const metrics = result ? [
        { label: "Estimated yearly return", value: `${result.expected_return.toFixed(1)}%`, note: `From each holding's beta: ${result.risk_free_pct ?? 2.5}% plus beta × ${result.equity_premium_pct ?? 5.5}%` },
        { label: "Volatility", value: `${result.expected_volatility.toFixed(1)}%`, note: "Typical yearly swing (one standard deviation)" },
        { label: "Return per unit of risk", value: result.sharpe_ratio.toFixed(2), note: `Sharpe ratio, above a ${result.risk_free_pct ?? 2.5}% risk-free rate` },
        { label: `Beta vs ${isIndian ? "Nifty 50" : "S&P 500"}`, value: result.portfolio_beta.toFixed(2), note: "1.00 moves with the market" },
        { label: "Worst fall in the past year", value: `${result.max_drawdown.toFixed(1)}%`, note: "Peak to trough, at these weights" },
        { label: "Risk cut by diversifying", value: `${(result.diversification_benefit_pct || 0).toFixed(1)}%`, note: "Lower volatility than the holdings' own swings averaged, because they don't all move together" },
    ] : []

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto">
            <PageHeader
                title="Simulation"
                description="Project how a mix of holdings might grow, with a range of likely outcomes. Estimates from past prices, not a forecast."
                actions={<Button variant="outline" size="sm" onClick={handleExport} disabled={chartData.length === 0} className="gap-1.5"><Download className="size-4" /> Export CSV</Button>}
            />

            <div className="grid grid-cols-1 lg:grid-cols-[22rem_1fr] gap-6 items-start">
                <aside className="space-y-6">
                    <Panel id="sim-holdings" title="Holdings"
                        description={loaded ? <>From the portfolio <span className="text-foreground font-medium">{loaded.name}</span></> : "Weights are scaled to 100% when the simulation runs"}
                        action={
                            <span className="flex items-center gap-2 text-xs">
                                <span className={cn("font-mono tabular-nums", Math.abs(totalWeight - 100) < 0.5 ? "text-q-risk-low" : "text-amber-600 dark:text-amber-400")}>
                                    Total {totalWeight.toFixed(0)}%
                                </span>
                                <button type="button" onClick={handleNormalize} className="flex items-center gap-1 text-muted-foreground hover:text-foreground">
                                    <RefreshCw className="size-3" /> Scale to 100%
                                </button>
                            </span>
                        }>
                        <div className="p-4 space-y-4">
                            <div className="flex gap-2">
                                <Button type="button" variant="outline" size="sm" className="flex-1" onClick={() => setHoldings(US_PRESET)}>US example</Button>
                                <Button type="button" variant="outline" size="sm" className="flex-1" onClick={() => setHoldings(INDIA_PRESET)}>India example</Button>
                            </div>
                            <ul className="space-y-3">
                                {holdings.map(item => (
                                    <li key={item.id} className="space-y-1">
                                        <div className="flex items-center justify-between text-sm">
                                            <span className="font-medium text-foreground">{item.ticker}</span>
                                            <span className="flex items-center gap-2">
                                                <span className="font-mono tabular-nums">{item.weight.toFixed(1)}%</span>
                                                <button type="button" aria-label={`Remove ${item.ticker}`} disabled={holdings.length <= 1}
                                                    onClick={() => setHoldings(prev => prev.filter(h => h.id !== item.id))}
                                                    className="p-0.5 text-muted-foreground hover:text-q-risk-high disabled:opacity-30">
                                                    <Trash2 className="size-3.5" />
                                                </button>
                                            </span>
                                        </div>
                                        <input type="range" min={0} max={100} step={1} value={item.weight} aria-label={`Weight for ${item.ticker}`}
                                            onChange={e => setHoldings(prev => prev.map(h => (h.id === item.id ? { ...h, weight: Number(e.target.value) } : h)))}
                                            className="w-full accent-primary" />
                                    </li>
                                ))}
                            </ul>
                            <form className="flex gap-2" onSubmit={e => { e.preventDefault(); void handleAddTicker() }}>
                                <input value={newTickerInput} onChange={e => setNewTickerInput(e.target.value)} placeholder="Add a stock, e.g. ITC"
                                    aria-label="Add a stock" className={cn(fieldClass, "flex-1 min-w-0")} />
                                <Button type="submit" size="sm" disabled={!newTickerInput.trim()} className="gap-1"><Plus className="size-4" /> Add</Button>
                            </form>
                            {quickTickers.some(t => !holdings.some(h => h.ticker === t)) && (
                                <div className="flex flex-wrap gap-1.5">
                                    {quickTickers.filter(t => !holdings.some(h => h.ticker === t)).slice(0, 12).map(t => (
                                        <button key={t} type="button" onClick={() => void handleAddTicker(t)} aria-label={`Add ${t}`}
                                            className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground">
                                            + {t}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </Panel>

                    <Panel id="sim-settings" title="Assumptions">
                        <div className="p-4 space-y-4 text-sm">
                            <label className="flex items-center justify-between gap-3">
                                <span className="text-muted-foreground">Starting amount</span>
                                <select value={initialInvestment} onChange={e => setInitialInvestment(Number(e.target.value))} className={cn(fieldClass, "font-mono tabular-nums")}>
                                    {(INVESTMENT_OPTIONS.includes(initialInvestment) ? INVESTMENT_OPTIONS : [...INVESTMENT_OPTIONS, initialInvestment].sort((a, b) => a - b))
                                        .map(v => <option key={v} value={v}>{amount(v)}</option>)}
                                </select>
                            </label>
                            <label className="flex items-center justify-between gap-3">
                                <span className="text-muted-foreground">Years</span>
                                <select value={horizonYears} onChange={e => setHorizonYears(Number(e.target.value))} className={fieldClass}>
                                    {HORIZONS.map(y => <option key={y} value={y}>{y} years</option>)}
                                </select>
                            </label>
                            <div className="space-y-1.5">
                                <span className="text-muted-foreground">Scenario</span>
                                <div role="group" aria-label="Scenario" className="grid grid-cols-3 gap-1">
                                    {SCENARIOS.map(sc => (
                                        <button key={sc.value} type="button" title={sc.title} aria-pressed={scenario === sc.value} onClick={() => setScenario(sc.value)}
                                            className={cn("rounded-md border px-2 py-1.5", scenario === sc.value ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>
                                            {sc.label}
                                        </button>
                                    ))}
                                </div>
                                <p className="text-xs text-muted-foreground">{SCENARIOS.find(s => s.value === scenario)?.title}</p>
                            </div>
                            <Button onClick={runSimulation} disabled={isFetching} className="w-full gap-1.5">
                                <Play className="size-4" /> {isFetching ? "Running…" : edited ? "Run with these holdings" : "Run again"}
                            </Button>
                        </div>
                    </Panel>

                    <Panel id="sim-save" title="Save">
                        <div className="p-4 space-y-2">
                            {saveName === null ? (
                                <div className="flex gap-2">
                                    {loaded && (
                                        <Button variant="outline" size="sm" className="flex-1 gap-1.5" disabled={savePortfolio.isPending} onClick={() => handleSavePortfolio(false)}>
                                            <Save className="size-4" /> Update {loaded.name}
                                        </Button>
                                    )}
                                    <Button variant="outline" size="sm" className="flex-1 gap-1.5" onClick={() => setSaveName(loaded ? `${loaded.name} (copy)` : "")}>
                                        <Save className="size-4" /> {loaded ? "Save as new" : "Save as portfolio"}
                                    </Button>
                                </div>
                            ) : (
                                <form className="flex gap-2" onSubmit={e => { e.preventDefault(); void handleSavePortfolio(true) }}>
                                    <input autoFocus value={saveName} maxLength={100} onChange={e => setSaveName(e.target.value)} placeholder="Portfolio name"
                                        aria-label="Portfolio name" className={cn(fieldClass, "flex-1 min-w-0")} />
                                    <Button type="submit" size="sm" disabled={!saveName.trim() || savePortfolio.isPending}>Save</Button>
                                    <Button type="button" size="sm" variant="ghost" onClick={() => setSaveName(null)}>Cancel</Button>
                                </form>
                            )}
                            {saveMessage && <p role="status" className={cn("text-sm", saveMessage.ok ? "text-q-risk-low" : "text-q-risk-high")}>{saveMessage.text}</p>}
                        </div>
                    </Panel>
                </aside>

                <div className="space-y-6 min-w-0">
                    <Panel id="sim-projection" title={`Value over ${horizonYears} years`}
                        description={end
                            ? <>Middle outcome <span className="font-mono tabular-nums text-foreground">{amount(end.median)}</span>; 9 in 10 outcomes fall between <span className="font-mono tabular-nums">{amount(end.lower_5)}</span> and <span className="font-mono tabular-nums">{amount(end.upper_95)}</span></>
                            : "The line is the middle outcome; the band holds 9 in 10 outcomes"}
                        action={
                            <div role="group" aria-label="View" className="flex gap-1">
                                {([["chart", "Growth"], ["correlation", "How they move together"]] as const).map(([v, label]) => (
                                    <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)}
                                        className={cn("rounded-full border px-3 py-1 text-xs", view === v ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>
                                        {label}
                                    </button>
                                ))}
                            </div>
                        }>
                        {result && result.estimated_tickers.length > 0 && (
                            <p role="note" className="mx-4 mt-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs">
                                No price history for {result.estimated_tickers.join(", ")}, so typical figures for that kind of asset are used.
                            </p>
                        )}
                        {isFetching && !result ? <PanelSkeleton rows={6} /> : isError && !result ? (
                            <PanelMessage alert>Couldn't run the simulation. Check the tickers and try again.</PanelMessage>
                        ) : !result ? <PanelMessage>Add holdings and run the simulation.</PanelMessage> : view === "chart" ? (
                            <div className="h-80 p-4">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                                        <XAxis dataKey="month" type="number" domain={[0, "dataMax"]} stroke="hsl(var(--muted-foreground))" fontSize={12}
                                            ticks={Array.from({ length: horizonYears / 5 + 1 }, (_, i) => i * 60)} tickFormatter={v => `Year ${v / 12}`} />
                                        <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} width={70}
                                            tickFormatter={v => isIndian ? `₹${(v / 1e5).toLocaleString("en-IN", { maximumFractionDigits: 1 })}L` : `$${(v / 1e6).toFixed(1)}M`} />
                                        <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", fontSize: 12 }}
                                            labelFormatter={m => `Year ${(Number(m) / 12).toFixed(1)}`}
                                            formatter={v => (Array.isArray(v) ? [`${amount(Number(v[0]))} to ${amount(Number(v[1]))}`, "9 in 10 outcomes"] : [amount(Number(v)), "Middle outcome"])} />
                                        <Area type="monotone" dataKey={(p: TrajectoryPoint) => [p.lower_5, p.upper_95]} name="range" stroke="none" fill="hsl(var(--primary))" fillOpacity={0.12} />
                                        <Area type="monotone" dataKey="median" name="median" stroke="hsl(var(--primary))" strokeWidth={2} fill="none" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        ) : (
                            <div className="p-4 overflow-x-auto">
                                <table className="text-sm">
                                    <thead>
                                        <tr>
                                            <td />
                                            {runHoldings.map(h => <th key={h.ticker} scope="col" className="px-3 py-1 text-xs font-medium text-muted-foreground">{h.ticker}</th>)}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {runHoldings.map(a => (
                                            <tr key={a.ticker}>
                                                <th scope="row" className="pr-3 py-1 text-left text-xs font-medium text-muted-foreground">{a.ticker}</th>
                                                {runHoldings.map(b => {
                                                    const c = result.correlation_matrix?.[a.ticker]?.[b.ticker]
                                                    return (
                                                        <td key={b.ticker} className={cn("px-3 py-1.5 text-center font-mono tabular-nums rounded-sm", c !== undefined && a.ticker !== b.ticker && corrClass(c))}>
                                                            {c === undefined ? "—" : c.toFixed(2)}
                                                        </td>
                                                    )
                                                })}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                                <p className="mt-3 text-xs text-muted-foreground">
                                    1.00 means two holdings move exactly together. Red (0.70 and up) moves together, amber is in between,
                                    green (below 0.40) helps diversify. From one year of daily returns.
                                </p>
                            </div>
                        )}
                    </Panel>

                    {result && (
                        <Panel id="sim-metrics" title="Risk and return"
                            description={`${SCENARIOS.find(s => s.value === scenario)?.label} scenario. Figures are yearly unless stated.`}>
                            <dl className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 divide-y sm:divide-y-0 divide-border">
                                {metrics.map(m => (
                                    <div key={m.label} className="p-4 space-y-0.5">
                                        <dt className="text-xs text-muted-foreground">{m.label}</dt>
                                        <dd className="text-xl font-semibold font-mono tabular-nums text-foreground">{m.value}</dd>
                                        <dd className="text-xs text-muted-foreground">{m.note}</dd>
                                    </div>
                                ))}
                            </dl>
                        </Panel>
                    )}
                </div>
            </div>
        </div>
    )
}
