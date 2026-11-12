import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import apiClient from "@/lib/api"
import { useNavigate } from "react-router-dom"
import {
    Search,
    ChevronDown,
    Download,
    List,
    Grid,
    Clock,
    X,
    Globe,
} from "lucide-react"
import { cn, timeAgo } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { exportToCsv } from "@/lib/export"
import { isIndianAsset, getMarketLabel } from "@/lib/currency"
import WatchlistButton from "@/components/WatchlistButton"
import type { StockSearchItem } from "@/types/api"
import DayChange from "@/components/DayChange"

const PAGE_SIZE = 25

/** Traded value: ₹ crore for Indian listings, $ millions otherwise. */
const traded = (value: number, ticker: string) =>
    isIndianAsset(ticker) ? `₹${(value / 1e7).toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr` : `$${(value / 1e6).toFixed(0)}M`

interface SavedScreen { id: number; name: string; filters: Record<string, string>; sort: string }

/** Fundamental screens: API parameter -> label; all percents except debt/equity (a ratio). */
const FUNDAMENTALS = [
    { key: "roe_min", label: "Min ROE %" },
    { key: "roce_min", label: "Min ROCE %" },
    { key: "debt_to_equity_max", label: "Max debt / equity" },
    { key: "revenue_growth_min", label: "Min revenue growth %" },
    { key: "revenue_cagr_3y_min", label: "Min 3Y revenue CAGR %" },
    { key: "profit_cagr_3y_min", label: "Min 3Y profit CAGR %" },
    { key: "profit_margin_min", label: "Min profit margin %" },
    { key: "dividend_yield_min", label: "Min dividend yield %" },
    { key: "return_1y_min", label: "Min 1-year return %" },
    { key: "promoter_min", label: "Min promoter holding %" },
    { key: "promoter_change_min", label: "Min promoter change (pts)" },
    { key: "rsi_min", label: "Min RSI (14)" },
    { key: "rsi_max", label: "Max RSI (14)" },
    { key: "sma50_gap_min", label: "Min % vs 50-day avg" },
    { key: "sma200_gap_min", label: "Min % vs 200-day avg" },
    { key: "sma200_gap_max", label: "Max % vs 200-day avg" },
    { key: "from_high_min", label: "Within % of 52-wk high (e.g. -5)" },
    { key: "from_low_max", label: "Max % above 52-wk low" },
    { key: "turnover_min_cr", label: "Min avg traded value (₹ Cr/day)" },
] as const
type FundamentalKey = (typeof FUNDAMENTALS)[number]["key"]
type Fundamentals = Partial<Record<FundamentalKey, string>>

/** Starting points that fill in the filters, so what each screen means stays visible and editable. */
const PRESETS: { label: string; filters: Fundamentals; sort: string }[] = [
    { label: "Quality compounders", filters: { roe_min: "15", debt_to_equity_max: "0.5", revenue_growth_min: "10" }, sort: "-roe" },
    { label: "Dividend payers", filters: { dividend_yield_min: "2.5", debt_to_equity_max: "1" }, sort: "-dividend_yield" },
    { label: "Momentum", filters: { return_1y_min: "20", revenue_growth_min: "5" }, sort: "-return_1y" },
    { label: "Promoters buying", filters: { promoter_change_min: "1" }, sort: "-promoter_change" },
    { label: "Oversold (RSI < 30)", filters: { rsi_max: "30", turnover_min_cr: "5" }, sort: "rsi" },
    { label: "Near 52-week high", filters: { from_high_min: "-5", sma200_gap_min: "0" }, sort: "-from_high" },
    { label: "Above 200-day average", filters: { sma200_gap_min: "0", sma50_gap_min: "0" }, sort: "-return_1y" },
    { label: "Most traded", filters: { turnover_min_cr: "100" }, sort: "-turnover" },
]

const SORTS = [
    { value: "", label: "Ticker (A–Z)" },
    { value: "-market_cap", label: "Market cap" },
    { value: "-roe", label: "ROE" },
    { value: "-roce", label: "ROCE" },
    { value: "-revenue_cagr_3y", label: "3Y revenue CAGR" },
    { value: "-profit_cagr_3y", label: "3Y profit CAGR" },
    { value: "-promoter_change", label: "Promoter change" },
    { value: "-revenue_growth", label: "Revenue growth" },
    { value: "-return_1y", label: "1-year return" },
    { value: "-dividend_yield", label: "Dividend yield" },
    { value: "-turnover", label: "Traded value (last session)" },
    { value: "-from_high", label: "Closest to 52-week high" },
    { value: "rsi", label: "RSI (low first)" },
    { value: "pe", label: "P/E (low first)" },
    { value: "risk", label: "Risk (low first)" },
]

const pctCell = (v: number | null | undefined) => {
    if (v == null) return "—"
    const shown = Number(v.toFixed(1)) // colour what is shown: -0.04 reads "0.0%", not a red "-0.0%"
    return <span className={shown > 0 ? "text-green-500" : shown < 0 ? "text-red-500" : ""}>{shown > 0 ? "+" : ""}{(shown || 0).toFixed(1)}%</span>
}

const riskTone = (risk: number | null) =>
    risk == null ? "bg-muted/40 text-muted-foreground border-border" :
        risk < 33.3 ? "bg-green-500/10 text-green-400 border-green-500/20" :
            risk < 66.7 ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/20" :
                "bg-red-500/10 text-red-400 border-red-500/20"

// Research-quality bands from the backend's to_search_item
const signalTone = (signal: string) =>
    signal === "Strong" || signal === "High" ? "text-green-500" :
        signal === "Weak" ? "text-red-500" :
            signal === "Neutral" ? "text-foreground" : "text-muted-foreground"

export default function ResearchExplorer() {
    const [view, setView] = useState("list")
    const navigate = useNavigate()

    // Filter states
    const [selectedMarket, setSelectedMarket] = useState<"all" | "us" | "india">("all")
    const [query, setQuery] = useState("")
    const [peLimit, setPeLimit] = useState(50)
    const [betaLimit, setBetaLimit] = useState(2.0)
    const [selectedSignals, setSelectedSignals] = useState<string[]>([])
    const [fundamentals, setFundamentals] = useState<Fundamentals>({})
    const [sort, setSort] = useState("")
    const [screenName, setScreenName] = useState("")
    const queryClient = useQueryClient()
    const { data: savedScreens = [] } = useQuery({
        queryKey: ["screens"],
        queryFn: async () => (await apiClient.get<SavedScreen[]>("/screens/")).data,
    })
    const refreshScreens = () => queryClient.invalidateQueries({ queryKey: ["screens"] })
    const saveScreen = useMutation({
        mutationFn: () => apiClient.post("/screens/", {
            name: screenName,
            sort,
            filters: {
                ...Object.fromEntries(Object.entries(fundamentals).filter(([, v]) => v)),
                _market: selectedMarket, _pe: String(peLimit), _beta: String(betaLimit), _signals: selectedSignals.join(","),
            },
        }),
        onSuccess: () => { setScreenName(""); void refreshScreens() },
    })
    const deleteScreen = useMutation({
        mutationFn: (id: number) => apiClient.delete(`/screens/${id}`),
        onSuccess: () => { void refreshScreens() },
    })
    const loadScreen = (s: SavedScreen) => {
        const { _market, _pe, _beta, _signals, ...rest } = s.filters
        setFundamentals(rest as Fundamentals)
        setSort(s.sort)
        if (_market) setSelectedMarket(_market as "all" | "us" | "india")
        if (_pe) setPeLimit(Number(_pe))
        if (_beta) setBetaLimit(Number(_beta))
        setSelectedSignals(_signals ? _signals.split(",") : [])
    }
    const activeFundamentals = Object.entries(fundamentals).filter(([, v]) => v !== undefined && v.trim() !== "" && !Number.isNaN(Number(v)))
    const [filtersOpen, setFiltersOpen] = useState(false)
    // Page resets whenever the filters change (derived during render, no effect needed)
    const filterKey = JSON.stringify([query, selectedMarket, peLimit, betaLimit, selectedSignals, activeFundamentals, sort])
    const [pageState, setPageState] = useState({ key: filterKey, page: 0 })
    const page = pageState.key === filterKey ? pageState.page : 0
    const setPage = (p: number) => setPageState({ key: filterKey, page: p })
    const [selectedTickers, setSelectedTickers] = useState<string[]>([])

    // Query backend Stock Search API
    const { data, isLoading } = useQuery({
        queryKey: ["stocksSearch", query, selectedMarket, peLimit, betaLimit, selectedSignals, activeFundamentals, sort, page],
        queryFn: async () => {
            const params: Record<string, string | number> = { limit: PAGE_SIZE, offset: page * PAGE_SIZE }
            if (query) params.query = query
            if (selectedMarket !== "all") params.market = selectedMarket
            if (peLimit < 50) params.pe_max = peLimit
            if (betaLimit < 2.0) params.beta_max = betaLimit
            if (selectedSignals.length > 0) params.signals = selectedSignals.join(",")
            for (const [k, v] of activeFundamentals) params[k] = Number(v)
            if (sort) params.sort = sort

            const res = await apiClient.get<{ stocks: StockSearchItem[]; total_count: number }>("/stocks/search", { params })
            return res.data
        }
    })

    // Mirrors the backend: these filters need fundamentals, which only tracked stocks have
    const dataFiltersOn = peLimit < 50 || betaLimit < 2.0 || selectedSignals.length > 0 || activeFundamentals.length > 0
    const results = data?.stocks || []
    const latestPriceAt = results.map(r => r.price_updated_at).filter((t): t is string => !!t).sort().at(-1)
    const totalCount = data?.total_count || 0
    const { data: health } = useQuery({
        queryKey: ["dataHealth"],
        queryFn: async () => (await apiClient.get<{ tracked?: number; with_fundamentals?: number }>("/market/data-health")).data,
        staleTime: 5 * 60 * 1000,
    })
    // Newly tracked stocks have no call until their fundamentals arrive (about 600 an hour)
    const stillLoading = health?.tracked && health.with_fundamentals !== undefined ? health.tracked - health.with_fundamentals : 0

    const handleSignalToggle = (signal: string) => {
        setSelectedSignals(prev =>
            prev.includes(signal)
                ? prev.filter(s => s !== signal)
                : [...prev, signal]
        )
    }

    const handleResetAll = () => {
        setSelectedMarket("all")
        setQuery("")
        setPeLimit(50)
        setBetaLimit(2.0)
        setSelectedSignals([])
        setFundamentals({})
        setSort("")
        setSelectedTickers([])
    }

    const handleToggleSelect = (ticker: string) => {
        setSelectedTickers(prev =>
            prev.includes(ticker)
                ? prev.filter(t => t !== ticker)
                : [...prev, ticker]
        )
    }

    const handleSelectAll = () => {
        if (selectedTickers.length === results.length && results.length > 0) {
            setSelectedTickers([])
        } else {
            setSelectedTickers(results.map((r) => r.ticker))
        }
    }

    const handleExport = (onlySelected = false) => {
        const source = onlySelected
            ? results.filter((r) => selectedTickers.includes(r.ticker))
            : results

        if (source.length === 0) return

        const exportRows = source.map((r) => ({
            ticker: r.ticker,
            name: r.name || "",
            price: r.price,
            market_cap: r.cap,
            risk_score: r.risk ?? "",
            signal: r.signal,
            call: r.call ?? "",
            sector: r.sector || "",
            pe_ratio: r.pe ?? "",
            beta: r.beta ?? "",
            roe_pct: r.roe_pct ?? "",
            debt_to_equity: r.debt_to_equity ?? "",
            revenue_growth_pct: r.revenue_growth_pct ?? "",
            profit_margin_pct: r.profit_margin_pct ?? "",
            dividend_yield_pct: r.dividend_yield_pct ?? "",
            return_1y_pct: r.return_1y_pct ?? "",
            roce_pct: r.roce_pct ?? "",
            revenue_cagr_3y_pct: r.revenue_cagr_3y_pct ?? "",
            profit_cagr_3y_pct: r.profit_cagr_3y_pct ?? "",
            promoter_pct: r.promoter_pct ?? "",
            promoter_change_pp: r.promoter_change_pp ?? "",
            rsi_14: r.rsi_14 ?? "",
            sma50_gap_pct: r.sma50_gap_pct ?? "",
            sma200_gap_pct: r.sma200_gap_pct ?? "",
            from_high_52w_pct: r.from_high_52w_pct ?? "",
            from_low_52w_pct: r.from_low_52w_pct ?? "",
            turnover_1d: r.turnover_1d ?? "",
            turnover_20d: r.turnover_20d ?? "",
            market: r.exchange ?? getMarketLabel(r.ticker)
        }))

        exportToCsv(
            onlySelected ? "quantara_selected_stocks.csv" : "quantara_stock_screener.csv",
            exportRows
        )
    }

    return (
        <div className="flex flex-col h-full overflow-hidden bg-background transition-colors">
            <div className="flex flex-col md:flex-row flex-1 overflow-y-auto md:overflow-hidden">
                {/* Sidebar: Filters (collapsible panel on phones) */}
                <aside className={cn(
                    "w-full md:w-72 border-b md:border-b-0 md:border-r border-border bg-card flex-col shrink-0 md:overflow-y-auto no-scrollbar",
                    filtersOpen ? "flex" : "hidden md:flex"
                )}>
                    <div className="p-4 border-b border-border flex items-center justify-between">
                        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Institutional Filters</h2>
                        <button 
                            onClick={handleResetAll}
                            className="text-[11px] text-primary hover:underline font-bold"
                        >
                            Reset All
                        </button>
                    </div>

                    {/* Market / Exchange Filter */}
                    <details className="border-b border-border group" open>
                        <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted list-none transition-colors">
                            <span className="text-xs font-medium text-foreground flex items-center gap-1.5">
                                <Globe className="size-3.5 text-primary" /> Exchange / Market
                            </span>
                            <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" />
                        </summary>
                        <div className="px-4 pb-4 space-y-1.5">
                            {[
                                { key: "all" as const, label: "Global (All Markets)", icon: "🌐" },
                                { key: "india" as const, label: "Indian Equities (NSE/BSE)", icon: "🇮🇳" },
                                { key: "us" as const, label: "US Equities (NYSE/NASDAQ)", icon: "🇺🇸" }
                            ].map((m) => (
                                <button
                                    key={m.key}
                                    type="button"
                                    onClick={() => setSelectedMarket(m.key)}
                                    className={cn(
                                        "w-full flex items-center justify-between px-3 py-2 rounded text-xs transition-colors text-left",
                                        selectedMarket === m.key
                                            ? "bg-primary text-white font-bold"
                                            : "hover:bg-muted text-muted-foreground"
                                    )}
                                >
                                    <span className="flex items-center gap-2">
                                        <span>{m.icon}</span>
                                        <span>{m.label}</span>
                                    </span>
                                    {selectedMarket === m.key && (
                                        <span className="size-1.5 rounded-full bg-white animate-pulse" />
                                    )}
                                </button>
                            ))}
                        </div>
                    </details>

                    <details className="border-b border-border group" open>
                        <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted list-none transition-colors">
                            <span className="text-xs font-medium text-foreground">Fundamentals</span>
                            <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" />
                        </summary>
                        <div className="px-4 pb-4 space-y-3">
                            <form
                                className="flex gap-1.5"
                                onSubmit={e => { e.preventDefault(); if (screenName.trim()) saveScreen.mutate() }}
                            >
                                <input
                                    aria-label="Name for this screen"
                                    value={screenName}
                                    maxLength={60}
                                    onChange={e => setScreenName(e.target.value)}
                                    placeholder="Save these filters as…"
                                    className="h-8 flex-1 min-w-0 px-2 bg-background border border-border rounded-sm text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                                />
                                <Button type="submit" size="sm" variant="outline" className="h-8 text-xs" disabled={!screenName.trim() || saveScreen.isPending}>Save</Button>
                            </form>
                            {saveScreen.isError && <p role="alert" className="text-[11px] text-q-risk-high">Could not save this screen.</p>}
                            {savedScreens.length > 0 && (
                                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Saved screens">
                                    {savedScreens.map(s => (
                                        <span key={s.id} className="inline-flex items-center border border-primary/40 rounded-sm text-[11px]">
                                            <button type="button" onClick={() => loadScreen(s)} className="px-2 py-1 hover:bg-muted">{s.name}</button>
                                            <button type="button" aria-label={`Delete ${s.name}`} onClick={() => deleteScreen.mutate(s.id)} className="px-1 py-1 text-muted-foreground hover:text-foreground"><X className="size-3" /></button>
                                        </span>
                                    ))}
                                </div>
                            )}
                            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Preset screens">
                                {PRESETS.map(p => (
                                    <button
                                        key={p.label}
                                        type="button"
                                        onClick={() => { setFundamentals(p.filters); setSort(p.sort) }}
                                        className="text-[11px] px-2 py-1 border border-border rounded-sm hover:bg-muted hover:border-primary/50"
                                    >
                                        {p.label}
                                    </button>
                                ))}
                            </div>
                            <div className="grid grid-cols-2 gap-2">
                                {FUNDAMENTALS.map(f => (
                                    <label key={f.key} className="flex flex-col gap-1 text-[11px] text-muted-foreground">
                                        {f.label}
                                        <input
                                            type="number"
                                            inputMode="decimal"
                                            step="any"
                                            value={fundamentals[f.key] ?? ""}
                                            onChange={e => setFundamentals(prev => ({ ...prev, [f.key]: e.target.value }))}
                                            placeholder="Any"
                                            className="h-8 px-2 bg-background border border-border rounded-sm text-xs text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                                        />
                                    </label>
                                ))}
                            </div>
                            <p className="text-[11px] text-muted-foreground">Covers the Nifty 500 and any stock you've opened. Ratios and returns from Yahoo, daily; ROCE and 3-year CAGR from annual statements, weekly; promoter holding from NSE filings, quarterly; RSI, moving averages, 52-week range and traded value from daily closes, refreshed once a day. Blank means no data, and that stock is left out of a filter.</p>
                        </div>
                    </details>

                    <details className="border-b border-border group" open>
                        <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted list-none transition-colors">
                            <span className="text-xs font-medium text-foreground">Valuation Limits</span>
                            <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" />
                        </summary>
                        <div className="px-4 pb-4 space-y-6">
                            <div className="space-y-3">
                                <div className="flex justify-between items-center text-[11px] font-mono">
                                    <span className="text-muted-foreground/80">MAX P/E Ratio</span>
                                    <span className="text-foreground font-bold">{peLimit === 50 ? "Any" : `${peLimit}.0x`}</span>
                                </div>
                                <input
                                    type="range"
                                    min="5"
                                    max="50"
                                    value={peLimit}
                                    onChange={(e) => setPeLimit(Number(e.target.value))}
                                    className="w-full h-[2px] bg-border appearance-none cursor-pointer accent-primary"
                                />
                            </div>
                        </div>
                    </details>

                    <details className="border-b border-border group" open>
                        <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted list-none transition-colors">
                            <span className="text-xs font-medium text-foreground">Risk Limits</span>
                            <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" />
                        </summary>
                        <div className="px-4 pb-4 space-y-6">
                            <div className="space-y-3">
                                <div className="flex justify-between items-center text-[11px] font-mono">
                                    <span className="text-muted-foreground/80">MAX Beta</span>
                                    <span className="text-foreground font-bold">{betaLimit === 2.0 ? "Any" : betaLimit.toFixed(2)}</span>
                                </div>
                                <input
                                    type="range"
                                    min="0.5"
                                    max="2.0"
                                    step="0.05"
                                    value={betaLimit}
                                    onChange={(e) => setBetaLimit(Number(e.target.value))}
                                    className="w-full h-[2px] bg-border appearance-none cursor-pointer accent-primary"
                                />
                            </div>
                        </div>
                    </details>

                    <details className="border-b border-border group" open>
                        <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted list-none transition-colors">
                            <span className="text-xs font-medium text-foreground">Signals</span>
                            <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" />
                        </summary>
                        <div className="px-4 pb-4 space-y-2">
                            {[
                                { key: "inflow", label: "Institutional Inflow" },
                                { key: "insider", label: "Insider Buying" },
                                { key: "sentiment", label: "Options/Sentiment Spike" }
                            ].map((signal) => (
                                <label key={signal.key} className="flex items-center gap-3 p-2 rounded hover:bg-muted cursor-pointer transition-colors">
                                    <input
                                        type="checkbox"
                                        checked={selectedSignals.includes(signal.key)}
                                        onChange={() => handleSignalToggle(signal.key)}
                                        className="size-3.5 rounded-sm bg-background border-border text-primary focus:ring-0"
                                    />
                                    <span className="text-xs text-muted-foreground font-medium">{signal.label}</span>
                                </label>
                            ))}
                        </div>
                    </details>
                </aside>

                {/* Main Workspace */}
                <main className="flex-1 flex flex-col min-w-0">
                    {/* Results Top Bar */}
                    <div className="min-h-14 py-2 border-b border-border px-3 md:px-6 flex flex-wrap items-center justify-between gap-2 bg-card/50 transition-colors">
                        <div className="flex items-center gap-2 md:gap-4 flex-grow max-w-lg min-w-0">
                            <button
                                type="button"
                                onClick={() => setFiltersOpen(o => !o)}
                                aria-expanded={filtersOpen}
                                className="md:hidden text-xs font-bold border border-border rounded-sm px-2 py-1 shrink-0"
                            >
                                Filters
                            </button>
                            <h2 className="text-sm font-semibold text-foreground select-none">
                                {isLoading ? "Syncing..." : `${totalCount.toLocaleString()} results`}
                            </h2>
                            {stillLoading > 25 && (
                                <span role="status" className="hidden lg:inline text-[11px] text-muted-foreground whitespace-nowrap" title="New stocks get their fundamentals and call over the next few hours">
                                    Data still loading for {stillLoading.toLocaleString()} stocks
                                </span>
                            )}
                            <span className="h-4 w-px bg-border" />
                            <div className="relative flex-1 group">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground group-focus-within:text-primary transition-colors" />
                                <input
                                    type="text"
                                    placeholder="Filter Ticker or Name..."
                                    value={query}
                                    onChange={(e) => setQuery(e.target.value)}
                                    className="w-full bg-muted/50 border border-border rounded pl-9 pr-4 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-primary transition-all text-foreground"
                                />
                            </div>
                            <label className="flex items-center gap-1.5 text-xs text-muted-foreground shrink-0">
                                Sort
                                <select
                                    value={sort}
                                    onChange={e => setSort(e.target.value)}
                                    className="h-7 bg-muted/50 border border-border rounded px-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                                >
                                    {SORTS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                </select>
                            </label>
                        </div>

                        <div className="flex items-center gap-3">
                            <button
                                onClick={() => handleExport(false)}
                                className="flex items-center gap-2 px-3 py-1.5 border border-border hover:bg-muted rounded text-xs font-bold transition-colors text-foreground/80"
                            >
                                <Download className="size-3.5" />
                                Export
                            </button>
                            <div className="flex border border-border rounded overflow-hidden">
                                <button
                                    onClick={() => setView("list")}
                                    className={cn("p-1.5 transition-colors", view === "list" ? "bg-primary text-white" : "text-muted-foreground hover:bg-muted")}
                                >
                                    <List className="size-4" />
                                </button>
                                <button
                                    onClick={() => setView("grid")}
                                    className={cn("p-1.5 transition-colors", view === "grid" ? "bg-primary text-white" : "text-muted-foreground hover:bg-muted")}
                                >
                                    <Grid className="size-4" />
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Bulk Selection Bar */}
                    {selectedTickers.length > 0 && (
                        <div className="bg-primary/10 border-b border-primary/20 px-6 py-2.5 flex items-center justify-between text-xs font-mono shrink-0 animate-in fade-in">
                            <div className="flex items-center gap-3">
                                <span className="font-bold text-foreground">
                                    {selectedTickers.length} of {results.length} Assets Selected
                                </span>
                                <button
                                    onClick={() => setSelectedTickers([])}
                                    className="text-muted-foreground hover:text-foreground underline text-[11px] flex items-center gap-1"
                                >
                                    <X className="size-3" /> Clear
                                </button>
                            </div>
                            <div className="flex items-center gap-2">
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => handleExport(true)}
                                    className="h-7 text-[11px] font-black uppercase tracking-wider bg-background"
                                >
                                    <Download className="size-3 mr-1" />
                                    Export Selected ({selectedTickers.length})
                                </Button>
                                <Button
                                    size="sm"
                                    variant="outline"
                                    disabled={selectedTickers.length < 2 || selectedTickers.length > 4}
                                    title="Select 2–4 stocks to compare side by side"
                                    onClick={() => navigate(`/compare?tickers=${selectedTickers.join(",")}`)}
                                    className="h-7 text-[11px] font-black uppercase tracking-wider bg-background"
                                >
                                    Compare (2–4)
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={() => navigate(`/simulation?tickers=${selectedTickers.join(",")}`)}
                                    className="h-7 text-[11px] font-black uppercase tracking-wider"
                                >
                                    Simulate Selected
                                </Button>
                            </div>
                        </div>
                    )}

                    {dataFiltersOn && (
                        <p role="note" className="px-6 py-2 text-xs text-muted-foreground border-b border-border bg-muted/30">
                            These filters cover tracked stocks only: the Nifty 500 plus any stock you've opened. Clear them to browse
                            every {selectedMarket === "india" ? "Indian " : selectedMarket === "us" ? "US " : ""}listing.
                        </p>
                    )}

                    {/* Results Content Area: List Table or Card Grid */}
                    <div className="flex-1 overflow-auto no-scrollbar bg-background">
                        {isLoading && results.length === 0 ? (
                            <div className="h-64 flex items-center justify-center font-mono text-xs text-muted-foreground uppercase tracking-widest">
                                FETCHING_DB_RECORDS...
                            </div>
                        ) : view === "grid" ? (
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 p-6">
                                {results.map((row) => {
                                    const isSelected = selectedTickers.includes(row.ticker)
                                    return (
                                        <div
                                            key={row.ticker}
                                            onClick={() => navigate(`/research/${row.ticker}`)}
                                            className={cn(
                                                "bg-card border rounded-md p-4 transition-all hover:border-primary/50 hover:shadow-md cursor-pointer flex flex-col justify-between space-y-3 relative group",
                                                isSelected ? "border-primary bg-primary/5 ring-1 ring-primary/30" : "border-border"
                                            )}
                                        >
                                            <div className="flex items-start justify-between">
                                                <div className="flex items-center gap-2.5">
                                                    <input
                                                        type="checkbox"
                                                        checked={isSelected}
                                                        onChange={(e) => {
                                                            e.stopPropagation()
                                                            handleToggleSelect(row.ticker)
                                                        }}
                                                        onClick={(e) => e.stopPropagation()}
                                                        className="size-3.5 rounded-sm bg-background border-border text-primary focus:ring-0 cursor-pointer"
                                                    />
                                                    <div>
                                                        <div className="flex items-center gap-1.5">
                                                            <span className="font-mono text-base font-black text-foreground">{row.ticker}</span>
                                                            <WatchlistButton ticker={row.ticker} />
                                                            <span className={cn(
                                                                "text-[10px] font-bold px-1 py-0.2 rounded border uppercase font-mono",
                                                                isIndianAsset(row.ticker) ? "bg-orange-500/10 text-orange-400 border-orange-500/20" : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                                                            )}>
                                                                {row.exchange ?? getMarketLabel(row.ticker)}
                                                            </span>
                                                            {row.status !== "neutral" && (
                                                                <span className={cn(
                                                                    "text-[10px] font-bold font-mono px-1 py-0.2 rounded",
                                                                    row.status === "up" ? "text-green-400 bg-green-500/10" : "text-rose-400 bg-rose-500/10"
                                                                )}>
                                                                    {row.status === "up" ? "▲" : "▼"}
                                                                </span>
                                                            )}
                                                        </div>
                                                        <div className="text-[11px] text-muted-foreground truncate max-w-[140px] font-medium">
                                                            {row.name || row.sector || "Equity Asset"}
                                                        </div>
                                                    </div>
                                                </div>
                                                <Badge
                                                    variant="outline"
                                                    className={cn(
                                                        "text-[10px] font-mono font-bold px-1.5 py-0.5",
                                                        riskTone(row.risk)
                                                    )}
                                                >
                                                    RISK {row.risk == null ? "—" : Math.round(row.risk)}
                                                </Badge>
                                            </div>

                                            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono py-2 border-y border-border/40">
                                                <div>
                                                    <div className="text-muted-foreground text-[10px]">Price</div>
                                                    <div className="font-bold text-foreground text-xs">{row.price === "N/A" && row.tracked === false ? "Open to load" : <>{row.price} <DayChange pct={row.change_pct} className="text-[11px]" /></>}</div>
                                                </div>
                                                <div className="text-right">
                                                    <div className="text-muted-foreground text-[10px]">Market Cap</div>
                                                    <div className="font-bold text-foreground text-xs">{row.cap}</div>
                                                </div>
                                                <div>
                                                    <div className="text-muted-foreground text-[10px]">Signal</div>
                                                    <div className={cn("font-bold truncate text-xs", signalTone(row.signal))}>
                                                        {row.tracked === false ? "—" : row.signal}
                                                    </div>
                                                </div>
                                                <div className="text-right">
                                                    <div className="text-muted-foreground text-[10px]">Sector</div>
                                                    <div className="font-bold text-foreground text-xs truncate">{row.sector ?? "—"}</div>
                                                </div>
                                            </div>

                                            <div className="flex items-center gap-2 pt-1" onClick={(e) => e.stopPropagation()}>
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => navigate(`/research/${row.ticker}`)}
                                                    className="flex-1 h-7 text-[10px] font-black uppercase tracking-wider border-border hover:bg-muted"
                                                >
                                                    Research
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => navigate(`/risk/${row.ticker}`)}
                                                    className="flex-1 h-7 text-[10px] font-black uppercase tracking-wider border-border hover:bg-muted"
                                                >
                                                    Risk
                                                </Button>
                                            </div>
                                        </div>
                                    )
                                })}
                            </div>
                        ) : (
                            <table className="w-full border-collapse text-left">
                                <thead className="sticky top-0 bg-card z-10 transition-colors">
                                    <tr className="border-b border-border">
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground w-12">
                                            <input
                                                type="checkbox"
                                                checked={results.length > 0 && selectedTickers.length === results.length}
                                                onChange={handleSelectAll}
                                                className="size-3.5 rounded-sm bg-background border-border text-primary focus:ring-0 cursor-pointer"
                                            />
                                        </th>
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Ticker</th>
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Price</th>
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Market Cap</th>
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground" title="Buy / Hold / Avoid from the stock's numbers; open the stock for the full call">Call</th>
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">ROE</th>
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">ROCE</th>
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground" title="Change in promoter holding from the previous quarter">Promoter Δ</th>
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">1Y Return</th>
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground" title="14-day RSI: above 70 overbought, below 30 oversold">RSI</th>
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground" title="Price vs its 52-week high">From High</th>
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground" title="Traded value in the last session">Traded</th>
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Risk Score</th>
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Signal Strength</th>
                                        <th className="px-6 py-3 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Sector</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-border font-mono text-xs">
                                    {results.map((row, i: number) => (
                                        <tr 
                                            key={i} 
                                            onClick={() => navigate(`/research/${row.ticker}`)}
                                            className={cn(
                                                "hover:bg-muted/30 transition-colors group cursor-pointer",
                                                selectedTickers.includes(row.ticker) && "bg-primary/5"
                                            )}
                                        >
                                            <td className="px-6 py-4" onClick={(e) => e.stopPropagation()}>
                                                <input
                                                    type="checkbox"
                                                    checked={selectedTickers.includes(row.ticker)}
                                                    onChange={() => handleToggleSelect(row.ticker)}
                                                    className="size-3.5 rounded-sm bg-background border-border text-primary focus:ring-0 cursor-pointer"
                                                />
                                            </td>
                                            <td className="px-6 py-4 font-black text-foreground">
                                                <div className="flex items-center gap-2">
                                                    <span>{row.ticker}</span>
                                                    <span className={cn(
                                                        "text-[10px] font-bold px-1.5 py-0.5 rounded border uppercase font-mono",
                                                        isIndianAsset(row.ticker) ? "bg-orange-500/10 text-orange-400 border-orange-500/20" : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                                                    )}>
                                                        {row.exchange ?? getMarketLabel(row.ticker)}
                                                    </span>
                                                    <WatchlistButton ticker={row.ticker} />
                                                </div>
                                                <div className="text-[11px] font-sans font-medium text-muted-foreground truncate max-w-[260px]">{row.name}</div>
                                            </td>
                                            <td className="px-6 py-4 text-foreground/90 font-bold">
                                                {row.price === "N/A" && row.tracked === false
                                                    ? <span className="font-sans font-normal text-muted-foreground">Open to load</span>
                                                    : <>{row.price} <DayChange pct={row.change_pct} className="text-[11px] ml-1" /></>}
                                            </td>
                                            <td className="px-6 py-4 text-muted-foreground">{row.cap}</td>
                                            <td className="px-6 py-4">{row.call ? <span className={cn("font-bold", row.call === "Buy" ? "text-green-500" : row.call === "Avoid" ? "text-red-500" : "text-amber-500")}>{row.call}</span> : "—"}</td>
                                            <td className="px-6 py-4 text-muted-foreground">{row.roe_pct == null ? "—" : `${row.roe_pct.toFixed(1)}%`}</td>
                                            <td className="px-6 py-4 text-muted-foreground">{row.roce_pct == null ? "—" : `${row.roce_pct.toFixed(1)}%`}</td>
                                            <td className="px-6 py-4">{row.promoter_change_pp == null ? "—" : <span className={row.promoter_change_pp > 0 ? "text-green-500" : row.promoter_change_pp < 0 ? "text-red-500" : ""}>{row.promoter_change_pp > 0 ? "+" : ""}{row.promoter_change_pp.toFixed(2)} pts</span>}</td>
                                            <td className="px-6 py-4">{pctCell(row.return_1y_pct)}</td>
                                            <td className={cn("px-6 py-4", row.rsi_14 == null ? "text-muted-foreground" : row.rsi_14 >= 70 ? "text-red-500" : row.rsi_14 <= 30 ? "text-green-500" : "text-muted-foreground")}>{row.rsi_14 == null ? "—" : Math.round(row.rsi_14)}</td>
                                            <td className="px-6 py-4 text-muted-foreground">{row.from_high_52w_pct == null ? "—" : `${row.from_high_52w_pct.toFixed(1)}%`}</td>
                                            <td className="px-6 py-4 text-muted-foreground">{row.turnover_1d == null ? "—" : traded(row.turnover_1d, row.ticker)}</td>
                                            <td className="px-6 py-4">
                                                <span className={cn(
                                                    "px-2 py-0.5 rounded border",
                                                    riskTone(row.risk)
                                                )}>
                                                    {row.risk == null ? "—" : Math.round(row.risk)}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className={cn("font-bold", signalTone(row.signal))}>
                                                    {row.tracked === false ? "—" : row.signal}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 text-muted-foreground">{row.sector ?? "—"}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>

                    {totalCount > PAGE_SIZE && (
                        <nav aria-label="Results pages" className="flex items-center justify-between pt-4 text-xs font-mono">
                            <span className="text-muted-foreground">
                                {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, totalCount)} of {totalCount}
                            </span>
                            <div className="flex gap-2">
                                <button type="button" onClick={() => setPage(page - 1)} disabled={page === 0}
                                    className="px-3 py-1.5 border border-border rounded-sm hover:bg-muted disabled:opacity-40">
                                    Prev
                                </button>
                                <button type="button" onClick={() => setPage(page + 1)} disabled={(page + 1) * PAGE_SIZE >= totalCount}
                                    className="px-3 py-1.5 border border-border rounded-sm hover:bg-muted disabled:opacity-40">
                                    Next
                                </button>
                            </div>
                        </nav>
                    )}
                </main>
            </div>

            <footer className="h-8 flex items-center border-t border-border bg-card px-6 shrink-0 z-20 transition-colors">
                <div className="flex-1 flex items-center justify-between gap-4 text-[11px] text-muted-foreground/60 font-bold uppercase tracking-tight">
                    <span className="flex items-center gap-1.5">
                        <Clock className="size-3" /> Prices updated: {latestPriceAt ? timeAgo(latestPriceAt) : "—"}
                    </span>
                    <p className="truncate hidden lg:block">Research insights only. Not investment advice.</p>
                </div>
            </footer>
        </div>
    )
}
