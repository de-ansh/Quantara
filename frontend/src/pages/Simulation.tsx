import { useState } from "react"
import apiClient from "@/lib/api"
import { keepPreviousData, useQuery } from "@tanstack/react-query"
import {
    Play,
    Zap,
    SlidersHorizontal,
    AlertTriangle,
    Plus,
    Trash2,
    RefreshCw,
    LineChart,
    Grid,
    ShieldCheck,
    Download,
    Save,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { exportToCsv } from "@/lib/export"
import { isIndianAsset } from "@/lib/currency"
import {
    ResponsiveContainer,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip
} from "recharts"
import { useQuickTickers } from "@/hooks/useStockUniverse"
import { usePortfolios, useSavePortfolio } from "@/hooks/usePortfolios"
import { useSearchParams } from "react-router-dom"

interface Holding {
    id: string
    ticker: string
    weight: number
}

const defaultHoldings: Holding[] = [
    { id: "1", ticker: "AAPL", weight: 35 },
    { id: "2", ticker: "NVDA", weight: 25 },
    { id: "3", ticker: "TLT", weight: 20 },
    { id: "4", ticker: "GLD", weight: 12 },
    { id: "5", ticker: "BIL", weight: 8 },
]

type Scenario = "conservative" | "base" | "aggressive"

// API values stay as-is; labels describe what each mode does to the projection.
const SCENARIOS: { value: Scenario; label: string; title: string }[] = [
    { value: "conservative", label: "Stress", title: "Higher volatility, lower returns" },
    { value: "base", label: "Base", title: "Historical estimates as measured" },
    { value: "aggressive", label: "Optimistic", title: "Lower volatility, higher returns" },
]
const scenarioLabel = (v: Scenario) => SCENARIOS.find(s => s.value === v)?.label ?? v

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
    risk_adjusted_return: number
    portfolio_beta: number
    trajectory: TrajectoryPoint[]
    diversification_benefit_pct: number
    asset_volatilities: Record<string, number>
    correlation_matrix: Record<string, Record<string, number>>
    covariance_matrix: number[][]
    estimated_tickers: string[]
}

const toPayloadStocks = (holdings: Holding[]) => {
    const sum = holdings.reduce((acc, h) => acc + h.weight, 0)
    return holdings.map(h => ({ ticker: h.ticker, weight: sum > 0 ? h.weight / sum : 1 / holdings.length }))
}

const INVESTMENT_OPTIONS = [100000, 500000, 1000000, 2500000, 5000000]

const INDIAN_PRESET: Holding[] = [
    { id: "in-1", ticker: "RELIANCE.NS", weight: 35 },
    { id: "in-2", ticker: "TCS.NS", weight: 25 },
    { id: "in-3", ticker: "HDFCBANK.NS", weight: 25 },
    { id: "in-4", ticker: "INFY.NS", weight: 15 },
]


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
            : defaultHoldings
    })
    const [holdings, setHoldings] = useState<Holding[]>(initialHoldings)
    const [newTickerInput, setNewTickerInput] = useState("")
    // Holdings as of the last Recalculate/load; editing sliders doesn't refetch until then
    const [runHoldings, setRunHoldings] = useState<Holding[]>(initialHoldings)
    const [horizonYears, setHorizonYears] = useState(10)
    const [volatilityAssumption, setVolatilityAssumption] = useState<Scenario>("base")
    const [initialInvestment, setInitialInvestment] = useState(1000000)

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
    const [activeView, setActiveView] = useState<"chart" | "correlation">("chart")

    const { data: marketData } = useQuery({
        queryKey: ["marketStatus"],
        queryFn: async () => {
            const { data } = await apiClient.get("/market/status")
            return data
        },
        refetchInterval: 5000,
    })

    const isIndianPortfolio = holdings.some(h => isIndianAsset(h.ticker))
    const currSym = isIndianPortfolio ? "₹" : "$"

    const totalWeight = holdings.reduce((sum, h) => sum + h.weight, 0)

    const handleNormalize = () => {
        if (totalWeight <= 0) return
        setHoldings(prev =>
            prev.map(h => ({
                ...h,
                weight: Math.round((h.weight / totalWeight) * 100 * 10) / 10
            }))
        )
    }

    const handleAddTicker = (tickerToAdd?: string) => {
        const sym = (tickerToAdd || newTickerInput).trim().toUpperCase()
        if (!sym) return
        if (holdings.some(h => h.ticker === sym)) {
            setNewTickerInput("")
            return
        }
        setHoldings(prev => [
            ...prev,
            { id: `${Date.now()}-${sym}`, ticker: sym, weight: 10 }
        ])
        setNewTickerInput("")
    }

    const handleRemoveTicker = (id: string) => {
        if (holdings.length <= 1) return
        setHoldings(prev => prev.filter(h => h.id !== id))
    }

    const handleWeightChange = (id: string, newWeight: number) => {
        setHoldings(prev =>
            prev.map(h => (h.id === id ? { ...h, weight: newWeight } : h))
        )
    }

    const runStocks = toPayloadStocks(runHoldings)
    const { data: result = null, isFetching: isLoading, refetch } = useQuery<SimulationResult>({
        queryKey: ["simulate", runStocks, initialInvestment, horizonYears, volatilityAssumption],
        queryFn: async () => {
            const { data } = await apiClient.post<SimulationResult>("/portfolio/simulate", {
                stocks: runStocks,
                initial_investment: initialInvestment,
                time_horizon_months: horizonYears * 12,
                volatility_mode: volatilityAssumption,
            })
            return data
        },
        enabled: runStocks.length > 0,
        placeholderData: keepPreviousData,
    })

    const runSimulation = () => {
        const unchanged = JSON.stringify(toPayloadStocks(holdings)) === JSON.stringify(runStocks)
        if (unchanged) refetch()
        else setRunHoldings(holdings)
    }

    // Bind metrics from simulation result
    const metrics = [
        { 
            label: "Forward Sharpe", 
            value: result ? result.sharpe_ratio.toFixed(2) : "—", 
            sub: "Risk-free 2.5%", 
            color: "text-green-400" 
        },
        { 
            label: "Portfolio Beta", 
            value: result ? result.portfolio_beta.toFixed(2) : "—", 
            sub: isIndianPortfolio ? "Rel. to NIFTY 50" : "Rel. to S&P 500" 
        },
        { 
            label: "Est. Annual Return", 
            value: result ? `${result.expected_return.toFixed(1)}%` : "—", 
            sub: `${scenarioLabel(volatilityAssumption).toUpperCase()} Scenario`, 
            color: "text-green-500" 
        },
        { 
            label: "Volatility (Std Dev)", 
            value: result ? `${result.expected_volatility.toFixed(1)}%` : "—", 
            sub: "Annualized MPT" 
        },
        { 
            label: "Diversification Benefit", 
            value: result ? `+${(result.diversification_benefit_pct || 0).toFixed(1)}%` : "—", 
            sub: "Covariance Dampening", 
            color: "text-emerald-400" 
        },
        { 
            label: "Max Drawdown Projection", 
            value: result ? `${result.max_drawdown.toFixed(1)}%` : "—", 
            sub: "Trailing 1Y", 
            color: "text-red-500" 
        },
    ]

    const chartData = result?.trajectory || []

    const handleExportSimulation = () => {
        if (!chartData || chartData.length === 0) return

        const rows = chartData.map((pt) => ({
            year: Number((pt.month / 12).toFixed(1)),
            month: pt.month,
            median_value: Math.round(pt.median || 0),
            upper_95_ci: Math.round(pt.upper_95 || 0),
            lower_5_ci: Math.round(pt.lower_5 || 0),
            expected_return_pct: result?.expected_return?.toFixed(2) ?? "",
            volatility_pct: result?.expected_volatility?.toFixed(2) ?? "",
            sharpe_ratio: result?.sharpe_ratio?.toFixed(2) ?? "",
        }))

        exportToCsv("quantara_portfolio_projection.csv", rows)
    }

    return (
        <div className="flex flex-col h-full bg-background overflow-hidden transition-colors">
            {/* Header */}
            <div className="h-12 border-b border-border flex items-center justify-between px-4 bg-card shrink-0">
                <div className="flex items-center gap-6">
                    <div className="flex items-center gap-2">
                        <div className="size-6 bg-[#1e5df1] flex items-center justify-center">
                            <Zap className="size-3.5 text-white" />
                        </div>
                        <h1 className="text-sm font-black tracking-tighter uppercase">Quantara</h1>
                    </div>
                    <nav className="flex items-center gap-4 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/80">
                        <span className="text-primary">Portfolio Simulation Studio</span>
                        <div className="h-3 w-[1px] bg-border" />
                        <span className="flex items-center gap-1 text-emerald-400">
                            <ShieldCheck className="size-3" />
                            MPT Covariance Engine Active
                        </span>
                    </nav>
                </div>
                <div className="flex items-center gap-4">
                    {marketData?.vix?.value && (
                        <div className="flex items-center gap-2 px-2 py-1 bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[9px] font-mono font-bold uppercase tracking-widest">
                            VIX: {marketData.vix.value} ({marketData.vix.change_percent >= 0 ? "+" : ""}{marketData.vix.change_percent}%)
                        </div>
                    )}
                    <div className="flex items-center gap-2 px-2 py-1 bg-green-500/10 border border-green-500/20 text-green-400 text-[9px] font-bold uppercase tracking-widest">
                        <div className="size-1.5 bg-green-500 rounded-full animate-pulse" />
                        Market Open
                    </div>
                </div>
            </div>

            {/* Macro Alert Banner */}
            {marketData?.alerts?.[0] && (
                <div className="flex items-center gap-3 px-4 py-2 border-b border-amber-500/25 bg-amber-500/5 text-amber-500 text-[10px] font-mono uppercase tracking-wider shrink-0">
                    <span className="flex items-center gap-1.5 shrink-0 font-bold">
                        <AlertTriangle className="size-3.5 animate-pulse" />
                        MACRO_ALERT
                    </span>
                    <span className="h-3 w-[1px] bg-amber-500/30 shrink-0" />
                    <span className="truncate">{marketData.alerts[0].time} - {marketData.alerts[0].text}</span>
                </div>
            )}

            <main className="flex flex-1 overflow-hidden">
                {/* Controls Sidebar */}
                <aside className="w-80 border-r border-border bg-card flex flex-col shrink-0 overflow-y-auto custom-scrollbar">
                    <div className="p-3 border-b border-border bg-muted/20 flex items-center justify-between">
                        <h2 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
                            <SlidersHorizontal className="size-3.5" />
                            Holdings & Allocation
                        </h2>
                        <div className="flex items-center gap-2 font-mono text-[10px]">
                            <span className={cn(
                                "px-1.5 py-0.5 rounded-sm font-bold",
                                Math.abs(totalWeight - 100) < 0.5 ? "bg-green-500/20 text-green-400" : "bg-amber-500/20 text-amber-400"
                            )}>
                                Total: {totalWeight.toFixed(0)}%
                            </span>
                            <button
                                onClick={handleNormalize}
                                title="Normalize weights to 100%"
                                className="text-muted-foreground hover:text-foreground transition-colors p-1"
                            >
                                <RefreshCw className="size-3" />
                            </button>
                        </div>
                    </div>

                    <div className="p-4 space-y-6">
                        {/* Quick Presets */}
                        <div className="space-y-1.5">
                            <span className="text-[9px] font-bold uppercase text-muted-foreground/70 tracking-tighter">
                                Quick Portfolio Presets
                            </span>
                            <div className="flex gap-2">
                                <button
                                    type="button"
                                    onClick={() => setHoldings(defaultHoldings)}
                                    className="flex-1 py-1 px-2 text-[10px] font-bold border border-border bg-muted/40 hover:bg-muted text-foreground rounded-sm transition-colors flex items-center justify-center gap-1"
                                >
                                    <span>🇺🇸</span> US Core
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setHoldings(INDIAN_PRESET)}
                                    className="flex-1 py-1 px-2 text-[10px] font-bold border border-border bg-muted/40 hover:bg-muted text-foreground rounded-sm transition-colors flex items-center justify-center gap-1"
                                >
                                    <span>🇮🇳</span> NIFTY Core
                                </button>
                            </div>
                        </div>

                        {/* Dynamic Stock List */}
                        <section className="space-y-3">
                            <div className="space-y-3">
                                {holdings.map((item) => (
                                    <div key={item.id} className="p-2 border border-border/70 bg-background/50 rounded-sm space-y-1.5">
                                        <div className="flex items-center justify-between text-[11px] font-mono">
                                            <span className="font-bold text-foreground tracking-wider">{item.ticker}</span>
                                            <div className="flex items-center gap-2">
                                                <span className="font-bold text-primary">{item.weight.toFixed(1)}%</span>
                                                {holdings.length > 1 && (
                                                    <button
                                                        onClick={() => handleRemoveTicker(item.id)}
                                                        className="text-muted-foreground hover:text-destructive transition-colors p-0.5"
                                                    >
                                                        <Trash2 className="size-3" />
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                        <input
                                            type="range"
                                            className="w-full h-[2px] bg-border appearance-none cursor-pointer accent-primary"
                                            value={item.weight}
                                            min="0"
                                            max="100"
                                            step="1"
                                            onChange={(e) => handleWeightChange(item.id, parseFloat(e.target.value))}
                                        />
                                    </div>
                                ))}
                            </div>

                            {/* Add Ticker Input */}
                            <div className="pt-2">
                                <div className="flex gap-2">
                                    <input
                                        type="text"
                                        placeholder="Add ticker (e.g. MSFT)..."
                                        value={newTickerInput}
                                        onChange={(e) => setNewTickerInput(e.target.value.toUpperCase())}
                                        onKeyDown={(e) => e.key === "Enter" && handleAddTicker()}
                                        className="flex-1 bg-background border border-border px-2.5 py-1.5 text-[11px] font-mono uppercase focus:outline-none focus:border-primary rounded-sm"
                                    />
                                    <button
                                        onClick={() => handleAddTicker()}
                                        disabled={!newTickerInput.trim()}
                                        className="bg-primary hover:bg-primary/90 text-white px-3 py-1.5 text-[10px] font-bold uppercase rounded-sm flex items-center gap-1 disabled:opacity-40"
                                    >
                                        <Plus className="size-3" /> Add
                                    </button>
                                </div>

                                {/* Quick Chips */}
                                <div className="flex flex-wrap gap-1 mt-2">
                                    {quickTickers.filter(t => !holdings.some(h => h.ticker === t)).map(chip => (
                                        <button
                                            key={chip}
                                            onClick={() => handleAddTicker(chip)}
                                            className="text-[9px] font-mono font-bold px-1.5 py-0.5 bg-muted/50 hover:bg-muted text-muted-foreground hover:text-foreground border border-border rounded-sm transition-colors"
                                        >
                                            +{chip}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </section>

                        {/* Volatility Assumptions */}
                        <section>
                            <h3 className="text-[9px] font-bold uppercase text-muted-foreground/70 mb-2 tracking-tighter">
                                Volatility Scenario
                            </h3>
                            <div className="grid grid-cols-3 border border-border overflow-hidden rounded-sm">
                                {SCENARIOS.map((sc, idx) => (
                                    <button
                                        key={sc.value}
                                        onClick={() => setVolatilityAssumption(sc.value)}
                                        title={sc.title}
                                        aria-pressed={volatilityAssumption === sc.value}
                                        className={cn(
                                            "py-2 text-[9px] font-bold uppercase transition-colors",
                                            idx === 1 && "border-x border-border",
                                            volatilityAssumption === sc.value ? "bg-primary text-white" : "hover:bg-muted"
                                        )}
                                    >
                                        {sc.label}
                                    </button>
                                ))}
                            </div>
                        </section>

                        {/* Parameters */}
                        <section className="space-y-3">
                            <h3 className="text-[9px] font-bold uppercase text-muted-foreground/70 tracking-tighter">
                                Parameters
                            </h3>
                            <div className="flex items-center justify-between">
                                <span className="text-[11px] text-muted-foreground">Initial Capital</span>
                                <select 
                                    value={initialInvestment}
                                    onChange={(e) => setInitialInvestment(Number(e.target.value))}
                                    className="bg-background border border-border text-[10px] py-1 px-2 focus:ring-0 rounded-sm text-foreground font-mono"
                                >
                                    {(INVESTMENT_OPTIONS.includes(initialInvestment)
                                        ? INVESTMENT_OPTIONS
                                        : [...INVESTMENT_OPTIONS, initialInvestment].sort((a, b) => a - b)
                                    ).map(v => (
                                        <option key={v} value={v}>{currSym}{v.toLocaleString()}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-[11px] text-muted-foreground">Time Horizon</span>
                                <select 
                                    value={horizonYears}
                                    onChange={(e) => setHorizonYears(Number(e.target.value))}
                                    className="bg-background border border-border text-[10px] py-1 px-2 focus:ring-0 rounded-sm text-foreground font-mono"
                                >
                                    <option value={5}>5 Years</option>
                                    <option value={10}>10 Years</option>
                                    <option value={20}>20 Years</option>
                                    <option value={30}>30 Years</option>
                                </select>
                            </div>
                            <div className="flex items-center justify-between text-[11px]">
                                <span className="text-muted-foreground">MPT Covariance</span>
                                <span className="font-mono font-bold text-emerald-400">ENABLED</span>
                            </div>
                        </section>

                        <button 
                            onClick={runSimulation}
                            disabled={isLoading}
                            className="w-full bg-primary hover:bg-primary/90 text-white text-[10px] font-black uppercase py-3 mt-4 transition-colors flex items-center justify-center gap-2 shadow-lg shadow-primary/20"
                        >
                            <Play className="size-3.5 fill-current" />
                            {isLoading ? "Simulating..." : "Recalculate Simulation"}
                        </button>

                        {/* Save to portfolios */}
                        <section className="space-y-2 pt-2 border-t border-border">
                            {loaded && (
                                <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider truncate">
                                    Loaded: <span className="text-foreground font-bold">{loaded.name}</span>
                                </p>
                            )}
                            {saveName === null ? (
                                <div className="flex gap-2">
                                    {loaded && (
                                        <button
                                            onClick={() => handleSavePortfolio(false)}
                                            disabled={savePortfolio.isPending}
                                            className="flex-1 border border-border hover:bg-muted text-[10px] font-bold uppercase py-2 rounded-sm flex items-center justify-center gap-1 disabled:opacity-50"
                                        >
                                            <Save className="size-3" /> Update
                                        </button>
                                    )}
                                    <button
                                        onClick={() => setSaveName(loaded ? `${loaded.name} (copy)` : "")}
                                        className="flex-1 border border-border hover:bg-muted text-[10px] font-bold uppercase py-2 rounded-sm flex items-center justify-center gap-1"
                                    >
                                        <Save className="size-3" /> {loaded ? "Save as new" : "Save as portfolio"}
                                    </button>
                                </div>
                            ) : (
                                <form
                                    className="flex gap-2"
                                    onSubmit={(e) => { e.preventDefault(); handleSavePortfolio(true) }}
                                >
                                    <input
                                        autoFocus
                                        value={saveName}
                                        maxLength={100}
                                        onChange={(e) => setSaveName(e.target.value)}
                                        placeholder="Portfolio name"
                                        aria-label="Portfolio name"
                                        className="flex-1 min-w-0 bg-background border border-border text-[11px] px-2 py-1.5 rounded-sm text-foreground outline-none focus:border-primary"
                                    />
                                    <button type="submit" disabled={!saveName.trim() || savePortfolio.isPending}
                                        className="bg-primary text-white text-[10px] font-bold uppercase px-3 rounded-sm disabled:opacity-40">
                                        Save
                                    </button>
                                    <button type="button" onClick={() => setSaveName(null)}
                                        className="text-[10px] text-muted-foreground hover:text-foreground px-1">
                                        Cancel
                                    </button>
                                </form>
                            )}
                            {saveMessage && (
                                <p role="status" className={cn("text-[10px] font-mono", saveMessage.ok ? "text-emerald-400" : "text-q-risk-high")}>
                                    {saveMessage.text}
                                </p>
                            )}
                        </section>
                    </div>
                </aside>

                {/* Workspace Panel */}
                <div className="flex-1 flex flex-col min-w-0">
                    <div className="flex-1 p-6 flex flex-col">
                        <div className="flex items-center justify-between mb-4">
                            <div>
                                <h2 className="text-2xl font-black tracking-tight uppercase text-foreground">Portfolio Projection</h2>
                                <p className="text-[10px] text-muted-foreground font-bold uppercase tracking-widest">
                                    Lognormal 5th–95th Percentile Bands | {scenarioLabel(volatilityAssumption).toUpperCase()} SCENARIO
                                </p>
                                {result && result.estimated_tickers.length > 0 && (
                                    <p className="text-[10px] text-amber-500 font-bold uppercase tracking-widest mt-1">
                                        No price history for {result.estimated_tickers.join(", ")}: using asset-class estimates
                                    </p>
                                )}
                            </div>
                            <div className="flex items-center gap-2">
                                {/* View Toggle */}
                                <div className="flex border border-border rounded-sm overflow-hidden bg-card mr-2">
                                    <button
                                        onClick={() => setActiveView("chart")}
                                        className={cn(
                                            "flex items-center gap-1.5 px-3 py-1.5 text-[9px] font-bold uppercase tracking-wider transition-colors",
                                            activeView === "chart" ? "bg-primary text-white" : "hover:bg-muted text-muted-foreground"
                                        )}
                                    >
                                        <LineChart className="size-3" /> Trajectory
                                    </button>
                                    <button
                                        onClick={() => setActiveView("correlation")}
                                        className={cn(
                                            "flex items-center gap-1.5 px-3 py-1.5 text-[9px] font-bold uppercase tracking-wider transition-colors border-l border-border",
                                            activeView === "correlation" ? "bg-primary text-white" : "hover:bg-muted text-muted-foreground"
                                        )}
                                    >
                                        <Grid className="size-3" /> Correlation Matrix
                                    </button>
                                </div>

                                <button
                                    onClick={handleExportSimulation}
                                    className="flex items-center gap-1.5 px-3 py-1.5 text-[9px] font-bold uppercase tracking-wider transition-colors border border-border rounded-sm hover:bg-muted text-foreground/80 font-mono bg-card"
                                >
                                    <Download className="size-3" /> Export CSV
                                </button>

                                {result && result.diversification_benefit_pct > 0 && (
                                    <div className="flex items-center gap-1.5 px-3 py-1.5 border border-emerald-500/30 bg-emerald-500/10 text-[9px] font-bold uppercase tracking-widest text-emerald-400 font-mono">
                                        <ShieldCheck className="size-3" />
                                        +{result.diversification_benefit_pct.toFixed(1)}% MPT Gain
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Main View Area */}
                        <div className="flex-1 relative border border-border bg-card/30 overflow-hidden shadow-inner flex flex-col">
                            {isLoading && chartData.length === 0 ? (
                                <div className="flex-1 flex items-center justify-center font-mono text-xs text-muted-foreground uppercase tracking-widest">
                                    RUNNING_PORTFOLIO_PROJECTION...
                                </div>
                            ) : activeView === "chart" ? (
                                <div className="flex-1 p-4">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={chartData} margin={{ top: 20, right: 10, left: 10, bottom: 5 }}>
                                            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.1} />
                                            <XAxis 
                                                dataKey="month" 
                                                stroke="hsl(var(--muted-foreground))"
                                                fontSize={9}
                                                fontWeight="bold"
                                                tickFormatter={(v) => `Yr ${(v / 12).toFixed(0)}`}
                                                tickCount={11}
                                            />
                                            <YAxis 
                                                stroke="hsl(var(--muted-foreground))"
                                                fontSize={9}
                                                fontWeight="bold"
                                                tickFormatter={(v) => `${currSym}${(v / 1e6).toFixed(1)}M`}
                                            />
                                            <Tooltip 
                                                contentStyle={{
                                                    backgroundColor: 'hsl(var(--card))',
                                                    borderColor: 'hsl(var(--border))',
                                                    fontSize: '10px',
                                                    fontFamily: 'monospace'
                                                }}
                                                formatter={(val) => [`${currSym}${Number(val).toLocaleString()}`, ""]}
                                                labelFormatter={(label) => `Month: ${label}`}
                                            />
                                            <Area type="monotone" dataKey="upper_95" stroke="none" fill="rgba(30, 93, 241, 0.05)" />
                                            <Area type="monotone" dataKey="lower_5" stroke="none" fill="rgba(30, 93, 241, 0.1)" />
                                            <Area type="monotone" dataKey="median" stroke="hsl(var(--primary))" strokeWidth={3} fill="none" />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            ) : (
                                /* Correlation Matrix Table */
                                <div className="flex-1 p-6 overflow-auto">
                                    <div className="mb-4">
                                        <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">
                                            Asset Pairwise Correlation Matrix ($\rho_{'{i,j}'}$)
                                        </h3>
                                        <p className="text-[10px] text-muted-foreground font-mono">
                                            Evaluated by Quantara Portfolio Analytics Engine. Green indicates negative correlation (risk reduction).
                                        </p>
                                    </div>
                                    <div className="overflow-x-auto border border-border">
                                        <table className="w-full text-xs font-mono">
                                            <thead>
                                                <tr className="border-b border-border bg-muted/40">
                                                    <th className="p-3 text-left font-bold text-muted-foreground uppercase">Ticker</th>
                                                    {holdings.map(h => (
                                                        <th key={h.ticker} className="p-3 text-center font-bold text-foreground">
                                                            {h.ticker}
                                                        </th>
                                                    ))}
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {holdings.map(h1 => (
                                                    <tr key={h1.ticker} className="border-b border-border/50 hover:bg-muted/20">
                                                        <td className="p-3 font-bold text-foreground bg-muted/20">{h1.ticker}</td>
                                                        {holdings.map(h2 => {
                                                            const corr = result?.correlation_matrix?.[h1.ticker]?.[h2.ticker] ?? (h1.ticker === h2.ticker ? 1.0 : 0.4)
                                                            const isSelf = h1.ticker === h2.ticker
                                                            const isNegative = corr < 0
                                                            const isHigh = corr > 0.6 && !isSelf
                                                            return (
                                                                <td 
                                                                    key={h2.ticker} 
                                                                    className={cn(
                                                                        "p-3 text-center tabular-nums font-semibold",
                                                                        isSelf ? "text-muted-foreground bg-muted/10" :
                                                                        isNegative ? "text-green-400 bg-green-500/10 font-bold" :
                                                                        isHigh ? "text-blue-400 bg-blue-500/10" :
                                                                        "text-foreground"
                                                                    )}
                                                                >
                                                                    {corr.toFixed(2)}
                                                                </td>
                                                            )
                                                        })}
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Stats Bar */}
                    <div className="h-72 border-t border-border grid grid-cols-12 shrink-0 bg-background transition-colors">
                        <div className="col-span-12 xl:col-span-4 border-r border-border p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Historical Stress Overlay</h3>
                                <span className="text-[10px] text-destructive font-black tracking-tighter uppercase">
                                    {result ? `${result.max_drawdown.toFixed(1)}% MAX DD` : "— MAX DD"}
                                </span>
                            </div>
                            <div className="flex-1 h-32 bg-card/20 border border-border/50 relative p-3 overflow-hidden group">
                                <div className="absolute inset-0 flex items-end opacity-40">
                                    <div className="w-full h-full flex items-end gap-[1px]">
                                        {[20, 30, 45, 80, 50, 40, 90, 60, 40, 30, 55].map((h, i) => (
                                            <div key={i} className="flex-1 bg-red-500/30 group-hover:bg-red-500/50 transition-colors" style={{ height: `${h}%` }} />
                                        ))}
                                    </div>
                                </div>
                                <div className="relative z-10 flex flex-col justify-between h-full text-[9px] font-mono text-muted-foreground/60 uppercase">
                                    <span>2008 GFC Event Benchmark</span>
                                    <div className="text-right">Risk Factor: Systemic</div>
                                </div>
                            </div>
                        </div>

                        <div className="col-span-12 xl:col-span-8 bg-card/20 p-6">
                            <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-4">Projected Portfolio Metrics</h3>
                            <div className="grid grid-cols-3 gap-px bg-border border border-border">
                                {metrics.map((m, i) => (
                                    <div key={i} className="bg-card p-4 flex flex-col gap-1 hover:bg-muted/50 cursor-help transition-colors">
                                        <span className="text-[9px] font-bold text-muted-foreground/60 uppercase tracking-tight">{m.label}</span>
                                        <span className={cn("text-2xl font-black tabular-nums tracking-tighter", m.color || "text-foreground")}>{m.value}</span>
                                        <span className="text-[9px] text-muted-foreground/80 font-bold uppercase tracking-tighter">{m.sub}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </main>

            <footer className="h-10 border-t border-border bg-background flex items-center justify-between px-6 shrink-0 z-20 transition-colors">
                <div className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground/60 flex items-center gap-6">
                    <span className="flex items-center gap-2"><div className="size-2 bg-green-500 rounded-full" /> Engine: V4.2.1-STABLE</span>
                    <span>LATENCY: 14ms</span>
                    <span>SIM ID: #MC-2024-X891</span>
                </div>
                <p className="text-[9px] text-muted-foreground/60 uppercase font-bold tracking-widest italic">
                    © 2024 Quantara Financial Intelligence Platforms. Institutional Grade.
                </p>
            </footer>
        </div>
    )
}
