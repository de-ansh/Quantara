import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import apiClient from "@/lib/api"
import { useNavigate } from "react-router-dom"
import {
    Search,
    ChevronDown,
    Bookmark,
    Download,
    List,
    Grid,
    TrendingUp,
    TrendingDown,
    Minus,
    MoreHorizontal,
    Clock,
    CheckCircle2
} from "lucide-react"
import { cn } from "@/lib/utils"

export default function ResearchExplorer() {
    const [view, setView] = useState("list")
    const navigate = useNavigate()

    // Filter states
    const [query, setQuery] = useState("")
    const [peLimit, setPeLimit] = useState(50)
    const [betaLimit, setBetaLimit] = useState(2.0)
    const [selectedSignals, setSelectedSignals] = useState<string[]>([])

    // Query backend Stock Search API
    const { data, isLoading } = useQuery({
        queryKey: ["stocksSearch", query, peLimit, betaLimit, selectedSignals],
        queryFn: async () => {
            const params: any = {}
            if (query) params.query = query
            if (peLimit < 50) params.pe_max = peLimit
            if (betaLimit < 2.0) params.beta_max = betaLimit
            if (selectedSignals.length > 0) params.signals = selectedSignals.join(",")

            const res = await apiClient.get("/stocks/search", { params })
            return res.data
        }
    })

    const results = data?.stocks || []
    const totalCount = data?.total_count || 0

    const handleSignalToggle = (signal: string) => {
        setSelectedSignals(prev =>
            prev.includes(signal)
                ? prev.filter(s => s !== signal)
                : [...prev, signal]
        )
    }

    const handleResetAll = () => {
        setQuery("")
        setPeLimit(50)
        setBetaLimit(2.0)
        setSelectedSignals([])
    }

    return (
        <div className="flex flex-col h-full overflow-hidden bg-background transition-colors">
            <div className="flex flex-1 overflow-hidden">
                {/* Sidebar: Filters */}
                <aside className="w-72 border-r border-border bg-card flex flex-col shrink-0 overflow-y-auto no-scrollbar">
                    <div className="p-4 border-b border-border flex items-center justify-between">
                        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Institutional Filters</h2>
                        <button 
                            onClick={handleResetAll}
                            className="text-[10px] text-primary hover:underline font-bold"
                        >
                            Reset All
                        </button>
                    </div>

                    <details className="border-b border-border group" open>
                        <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted list-none transition-colors">
                            <span className="text-xs font-medium text-foreground">Valuation Limits</span>
                            <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" />
                        </summary>
                        <div className="px-4 pb-4 space-y-6">
                            <div className="space-y-3">
                                <div className="flex justify-between items-center text-[10px] font-mono">
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
                                <div className="flex justify-between items-center text-[10px] font-mono">
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
                <main className="flex-1 flex flex-col">
                    {/* Results Top Bar */}
                    <div className="h-14 border-b border-border px-6 flex items-center justify-between bg-card/50 transition-colors">
                        <div className="flex items-center gap-4 flex-grow max-w-lg">
                            <h2 className="text-sm font-semibold text-foreground select-none">
                                {isLoading ? "Syncing..." : `${totalCount} Results Discovery`}
                            </h2>
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
                        </div>

                        <div className="flex items-center gap-3">
                            <button className="flex items-center gap-2 px-3 py-1.5 border border-border hover:bg-muted rounded text-xs font-bold transition-colors text-foreground/80">
                                <Bookmark className="size-3.5" />
                                Save Search
                            </button>
                            <div className="h-8 w-[1px] bg-border mx-1" />
                            <button className="flex items-center gap-2 px-3 py-1.5 border border-border hover:bg-muted rounded text-xs font-bold transition-colors text-foreground/80">
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

                    {/* Results Table */}
                    <div className="flex-1 overflow-auto no-scrollbar bg-background">
                        {isLoading && results.length === 0 ? (
                            <div className="h-64 flex items-center justify-center font-mono text-xs text-muted-foreground uppercase tracking-widest">
                                FETCHING_DB_RECORDS...
                            </div>
                        ) : (
                            <table className="w-full border-collapse text-left">
                                <thead className="sticky top-0 bg-card z-10 transition-colors">
                                    <tr className="border-b border-border">
                                        <th className="px-6 py-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground w-12">
                                            <input type="checkbox" className="size-3.5 rounded-sm bg-background border-border text-primary focus:ring-0" />
                                        </th>
                                        <th className="px-6 py-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Ticker</th>
                                        <th className="px-6 py-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Price</th>
                                        <th className="px-6 py-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Market Cap</th>
                                        <th className="px-6 py-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Risk Score</th>
                                        <th className="px-6 py-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Signal Strength</th>
                                        <th className="px-6 py-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Alpha Projection</th>
                                        <th className="px-6 py-3 text-[10px] font-bold uppercase tracking-wider text-muted-foreground text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-border font-mono text-xs">
                                    {results.map((row: any, i: number) => (
                                        <tr 
                                            key={i} 
                                            onClick={() => navigate(`/research/${row.ticker}`)}
                                            className="hover:bg-muted/30 transition-colors group cursor-pointer"
                                        >
                                            <td className="px-6 py-4" onClick={(e) => e.stopPropagation()}>
                                                <input type="checkbox" className="size-3.5 rounded-sm bg-background border-border text-primary focus:ring-0" />
                                            </td>
                                            <td className="px-6 py-4 font-black text-foreground">{row.ticker}</td>
                                            <td className="px-6 py-4 text-foreground/90 font-bold">{row.price}</td>
                                            <td className="px-6 py-4 text-muted-foreground">{row.cap}</td>
                                            <td className="px-6 py-4">
                                                <span className={cn(
                                                    "px-2 py-0.5 rounded border",
                                                    row.risk < 33.3 ? "bg-green-500/10 text-green-400 border-green-500/20" :
                                                        row.risk < 66.7 ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/20" :
                                                            "bg-red-500/10 text-red-400 border-red-500/20"
                                                )}>
                                                    {Math.round(row.risk)}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className={cn(
                                                    "flex items-center gap-1.5 font-bold",
                                                    row.status === "up" ? "text-primary" : row.status === "down" ? "text-destructive" : "text-muted-foreground"
                                                )}>
                                                    {row.status === "up" ? <TrendingUp className="size-4" /> : row.status === "down" ? <TrendingDown className="size-4" /> : <Minus className="size-4" />}
                                                    <span>{row.signal}</span>
                                                </div>
                                            </td>
                                            <td className={cn("px-6 py-4 font-bold", row.alpha.startsWith("+") ? "text-q-risk-low" : "text-q-risk-high")}>{row.alpha}</td>
                                            <td className="px-6 py-4 text-right" onClick={(e) => e.stopPropagation()}>
                                                <button className="text-muted-foreground hover:text-foreground transition-colors"><MoreHorizontal className="size-4" /></button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </main>
            </div>

            <footer className="h-8 flex items-center border-t border-border bg-card px-6 shrink-0 z-20 transition-colors">
                <div className="flex-1 flex items-center justify-between text-[10px] text-muted-foreground/60 font-bold uppercase tracking-tight">
                    <div className="flex items-center gap-4">
                        <span className="flex items-center gap-1.5"><Clock className="size-3" /> Data as of: Mar 22, 2024 16:45:01 EST</span>
                        <span className="h-2 w-[px] bg-border" />
                        <span>Market Status: <span className="text-q-risk-low">Open</span></span>
                    </div>
                    <p className="max-w-2xl truncate hidden lg:block text-center px-4">
                        Quantara Research Platform is for institutional use only. Not investment advice. Alpha projections are modeled outcomes.
                    </p>
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1 text-q-risk-low">
                            <CheckCircle2 className="size-3" />
                            <span>Systems Operational</span>
                        </div>
                    </div>
                </div>
            </footer>
        </div>
    )
}
