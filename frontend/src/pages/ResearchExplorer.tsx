import { useState } from "react"
import {
    Search,
    ChevronDown,
    Filter,
    Bookmark,
    Download,
    List,
    Grid,
    TrendingUp,
    TrendingDown,
    Minus,
    MoreHorizontal,
    Activity,
    Clock,
    CheckCircle2
} from "lucide-react"
import { cn } from "@/lib/utils"

const filters = [
    {
        title: "Valuation",
        metrics: [
            { label: "P/E Ratio", range: "5.0x — 25.0x", left: 20, right: 30 },
            { label: "EV/EBITDA", range: "8.2x — 18.0x", left: 40, right: 10 },
        ]
    },
    {
        title: "Risk Metrics",
        metrics: [
            { label: "Beta Range", range: "0.85 — 1.20", left: 30, right: 40 },
        ]
    }
]

const results = [
    { ticker: "AAPL", price: "$189.42", cap: "2.94T", risk: 14, signal: "High", alpha: "+12.4%", status: "up" },
    { ticker: "MSFT", price: "$415.20", cap: "3.08T", risk: 32, signal: "Strong", alpha: "+8.1%", status: "up" },
    { ticker: "NVDA", price: "$822.79", cap: "2.06T", risk: 68, signal: "Neutral", alpha: "+21.3%", status: "neutral" },
    { ticker: "TSLA", price: "$175.22", cap: "558.2B", risk: 72, signal: "Weak", alpha: "-4.2%", status: "down" },
    { ticker: "GOOGL", price: "$151.24", cap: "1.89T", risk: 21, signal: "Strong", alpha: "+11.5%", status: "up" },
    { ticker: "AMZN", price: "$178.12", cap: "1.85T", risk: 28, signal: "High", alpha: "+14.2%", status: "up" },
    { ticker: "META", price: "$496.22", cap: "1.26T", risk: 18, signal: "Strong", alpha: "+16.8%", status: "up" },
]

export default function ResearchExplorer() {
    const [view, setView] = useState("list")

    return (
        <div className="flex flex-col h-full overflow-hidden bg-background transition-colors">
            <div className="flex flex-1 overflow-hidden">
                {/* Sidebar: Filters */}
                <aside className="w-72 border-r border-border bg-card flex flex-col shrink-0 overflow-y-auto no-scrollbar">
                    <div className="p-4 border-b border-border flex items-center justify-between">
                        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Institutional Filters</h2>
                        <button className="text-[10px] text-primary hover:underline font-bold">Reset All</button>
                    </div>

                    {filters.map((group, i) => (
                        <details key={i} className="border-b border-border group" open>
                            <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted list-none transition-colors">
                                <span className="text-xs font-medium text-foreground">{group.title}</span>
                                <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" />
                            </summary>
                            <div className="px-4 pb-4 space-y-6">
                                {group.metrics.map((metric, j) => (
                                    <div key={j} className="space-y-3">
                                        <div className="flex justify-between items-center text-[10px] font-mono">
                                            <span className="text-muted-foreground/80">{metric.label}</span>
                                            <span className="text-foreground font-bold">{metric.range}</span>
                                        </div>
                                        <div className="h-[2px] bg-border relative">
                                            <div
                                                className="h-[2px] bg-primary absolute"
                                                style={{ left: `${metric.left}%`, right: `${metric.right}%` }}
                                            />
                                            <div className="size-[10px] bg-foreground absolute top-[-4px] rounded-full border-2 border-primary" style={{ left: `${metric.left}%` }} />
                                            <div className="size-[10px] bg-foreground absolute top-[-4px] rounded-full border-2 border-primary" style={{ left: `${100 - metric.right}%` }} />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </details>
                    ))}

                    <details className="border-b border-border group" open>
                        <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-muted list-none transition-colors">
                            <span className="text-xs font-medium text-foreground">Signals</span>
                            <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" />
                        </summary>
                        <div className="px-4 pb-4 space-y-2">
                            {["Institutional Inflow", "Insider Buying", "Options Unusual Vol"].map((signal) => (
                                <label key={signal} className="flex items-center gap-3 p-2 rounded hover:bg-muted cursor-pointer transition-colors">
                                    <input type="checkbox" className="size-3.5 rounded-sm bg-background border-border text-primary focus:ring-0" />
                                    <span className="text-xs text-muted-foreground font-medium">{signal}</span>
                                </label>
                            ))}
                        </div>
                    </details>
                </aside>

                {/* Main Workspace */}
                <main className="flex-1 flex flex-col">
                    {/* Results Top Bar */}
                    <div className="h-14 border-b border-border px-6 flex items-center justify-between bg-card/50 transition-colors">
                        <div className="flex items-center gap-4">
                            <h2 className="text-sm font-semibold text-foreground">1,248 Results Discovery</h2>
                            <span className="h-4 w-[px] bg-border" />
                            <div className="flex gap-2">
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-primary/10 text-primary border border-primary/20 uppercase tracking-tight">PE &lt; 20x</span>
                                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-primary/10 text-primary border border-primary/20 uppercase tracking-tight">Beta &lt; 1.2</span>
                            </div>
                        </div>

                        <div className="flex items-center gap-3">
                            <button className="flex items-center gap-2 px-3 py-1.5 border border-border hover:bg-muted rounded text-xs font-bold transition-colors text-foreground/80">
                                <Bookmark className="size-3.5" />
                                Save Search
                            </button>
                            <div className="h-8 w-[px] bg-border mx-1" />
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
                                {results.map((row, i) => (
                                    <tr key={i} className="hover:bg-muted/30 transition-colors group cursor-pointer">
                                        <td className="px-6 py-4"><input type="checkbox" className="size-3.5 rounded-sm bg-background border-border text-primary focus:ring-0" /></td>
                                        <td className="px-6 py-4 font-black text-foreground">{row.ticker}</td>
                                        <td className="px-6 py-4 text-foreground/90 font-bold">{row.price}</td>
                                        <td className="px-6 py-4 text-muted-foreground">{row.cap}</td>
                                        <td className="px-6 py-4">
                                            <span className={cn(
                                                "px-2 py-0.5 rounded border",
                                                row.risk < 20 ? "bg-green-500/10 text-green-400 border-green-500/20" :
                                                    row.risk < 50 ? "bg-yellow-500/10 text-yellow-400 border-yellow-500/20" :
                                                        "bg-red-500/10 text-red-400 border-red-500/20"
                                            )}>
                                                {row.risk}
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
                                        <td className="px-6 py-4 text-right">
                                            <button className="text-muted-foreground hover:text-foreground transition-colors"><MoreHorizontal className="size-4" /></button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
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
