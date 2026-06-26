import { useState, useEffect } from "react"
import apiClient from "@/lib/api"
import {
    Play,
    Download,
    Settings,
    Bell,
    ChevronDown,
    Zap,
    SlidersHorizontal
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
    ResponsiveContainer,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip
} from "recharts"

const initialAllocation = [
    { label: "Equities", val: 60 },
    { label: "Fixed Income", val: 25 },
    { label: "Alternatives", val: 10 },
    { label: "Cash", val: 5 },
]

export default function Simulation() {
    const [allocation, setAllocation] = useState(initialAllocation)
    const [isLoading, setIsLoading] = useState(false)
    const [result, setResult] = useState<any>(null)
    const [horizonYears, setHorizonYears] = useState(10)
    const [volatilityAssumption, setVolatilityAssumption] = useState("base")

    const runSimulation = async () => {
        setIsLoading(true)
        try {
            // Map asset allocations to representative tickers
            const stocks = allocation.map(item => {
                let ticker = "AAPL"
                if (item.label === "Fixed Income") ticker = "TLT"
                else if (item.label === "Alternatives") ticker = "GLD"
                else if (item.label === "Cash") ticker = "BIL"
                
                return {
                    ticker,
                    weight: item.val / 100.0
                }
            })

            // Normalize weights if the sum is not exactly 1.0 (to avoid division by zero or bad return calculation)
            const sum = stocks.reduce((acc, s) => acc + s.weight, 0)
            if (sum > 0) {
                stocks.forEach(s => {
                    s.weight = s.weight / sum
                })
            }

            const payload = {
                stocks,
                initial_investment: 1000000.0, // $1M base
                time_horizon_months: horizonYears * 12
            }

            const res = await apiClient.post("/portfolio/simulate", payload)
            setResult(res.data)
        } catch (error) {
            console.error("Simulation run failed:", error)
        } finally {
            setIsLoading(false)
        }
    }

    // Trigger simulation on mount and whenever the time horizon changes
    useEffect(() => {
        runSimulation()
    }, [horizonYears])

    // Bind metrics from simulation result
    const metrics = [
        { 
            label: "Forward Sharpe", 
            value: result ? result.sharpe_ratio.toFixed(2) : "1.84", 
            sub: "CI: 1.6 - 2.1", 
            color: "text-green-400" 
        },
        { 
            label: "Portfolio Beta", 
            value: result ? (result.expected_volatility / 14).toFixed(2) : "0.92", 
            sub: "Rel. to S&P 500" 
        },
        { 
            label: "Est. Annual Return", 
            value: result ? `${result.expected_return.toFixed(1)}%` : "8.5%", 
            sub: "Model Projection", 
            color: "text-green-500" 
        },
        { 
            label: "Volatility (Std Dev)", 
            value: result ? `${result.expected_volatility.toFixed(1)}%` : "12.4%", 
            sub: "Annualized" 
        },
        { 
            label: "Risk-Adjusted Return", 
            value: result ? `${result.risk_adjusted_return.toFixed(1)}%` : "7.1%", 
            sub: "Sharpe Penalized", 
            color: "text-[#1e5df1]" 
        },
        { 
            label: "Max Drawdown Projection", 
            value: result ? `${result.max_drawdown.toFixed(1)}%` : "-12.3%", 
            sub: "Stressed Market Scenario", 
            color: "text-red-500" 
        },
    ]

    const chartData = result?.trajectory || []

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
                        <span className="text-primary">Portfolio Simulation</span>
                        <div className="h-3 w-[1px] bg-border" />
                        <span className="hover:text-foreground cursor-pointer transition-colors">Risk Engine</span>
                        <div className="h-3 w-[1px] bg-border" />
                        <span className="hover:text-foreground cursor-pointer transition-colors">Reporting</span>
                    </nav>
                </div>
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 px-2 py-1 bg-green-500/10 border border-green-500/20 text-green-400 text-[9px] font-bold uppercase tracking-widest">
                        <div className="size-1.5 bg-green-500 rounded-full animate-pulse" />
                        Market Open
                    </div>
                    <div className="flex items-center gap-2 border-l border-border pl-4 text-muted-foreground">
                        <Bell className="size-4 hover:text-foreground cursor-pointer" />
                        <Settings className="size-4 hover:text-foreground cursor-pointer" />
                        <div className="size-6 bg-muted rounded-sm ml-1" />
                    </div>
                </div>
            </div>

            <main className="flex flex-1 overflow-hidden">
                {/* Controls */}
                <aside className="w-72 border-r border-border bg-card flex flex-col shrink-0 overflow-y-auto custom-scrollbar">
                    <div className="p-3 border-b border-border bg-muted/20">
                        <h2 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-2">
                            <SlidersHorizontal className="size-3.5" />
                            Model Controls
                        </h2>
                    </div>
                    <div className="p-4 space-y-6">
                        <section>
                            <h3 className="text-[9px] font-bold uppercase text-muted-foreground/80 mb-3 tracking-tighter">Target Allocation (%)</h3>
                            <div className="space-y-4">
                                {allocation.map((item, i) => (
                                    <div key={i} className="space-y-1">
                                        <div className="flex justify-between text-[11px] font-mono">
                                            <span className="text-muted-foreground">{item.label}</span>
                                            <span className="font-bold text-foreground">{item.val.toFixed(1)}%</span>
                                        </div>
                                        <input
                                            type="range"
                                            className="w-full h-[2px] bg-border appearance-none cursor-pointer accent-primary"
                                            value={item.val}
                                            min="0"
                                            max="100"
                                            onChange={(e) => {
                                                const newAlloc = [...allocation]
                                                newAlloc[i].val = parseFloat(e.target.value)
                                                setAllocation(newAlloc)
                                            }}
                                        />
                                    </div>
                                ))}
                            </div>
                        </section>

                        <section>
                            <h3 className="text-[9px] font-bold uppercase text-muted-foreground/60 mb-3 tracking-tighter">Volatility Assumptions</h3>
                            <div className="grid grid-cols-3 border border-border overflow-hidden rounded-sm">
                                <button 
                                    onClick={() => setVolatilityAssumption("conservative")}
                                    className={cn("py-2 text-[9px] font-bold uppercase transition-colors", volatilityAssumption === "conservative" ? "bg-primary text-white" : "hover:bg-muted")}
                                >
                                    Cons.
                                </button>
                                <button 
                                    onClick={() => setVolatilityAssumption("base")}
                                    className={cn("py-2 text-[9px] font-bold uppercase transition-colors border-x border-border", volatilityAssumption === "base" ? "bg-primary text-white" : "hover:bg-muted")}
                                >
                                    Base
                                </button>
                                <button 
                                    onClick={() => setVolatilityAssumption("aggressive")}
                                    className={cn("py-2 text-[9px] font-bold uppercase transition-colors", volatilityAssumption === "aggressive" ? "bg-primary text-white" : "hover:bg-muted")}
                                >
                                    Aggr.
                                </button>
                            </div>
                        </section>

                        <section className="space-y-3">
                            <h3 className="text-[9px] font-bold uppercase text-muted-foreground/60 tracking-tighter">Parameters</h3>
                            <div className="flex items-center justify-between">
                                <span className="text-[11px] text-muted-foreground">Time Horizon</span>
                                <select 
                                    value={horizonYears}
                                    onChange={(e) => setHorizonYears(Number(e.target.value))}
                                    className="bg-background border border-border text-[10px] py-1 px-2 focus:ring-0 rounded-sm text-foreground font-mono"
                                >
                                    <option value={10}>10 Years</option>
                                    <option value={20}>20 Years</option>
                                    <option value={30}>30 Years</option>
                                </select>
                            </div>
                            <div className="flex items-center justify-between text-[11px]">
                                <span className="text-muted-foreground">Iterations</span>
                                <span className="font-mono font-bold text-foreground">10,000</span>
                            </div>
                            <label className="flex items-center justify-between cursor-pointer">
                                <span className="text-[11px] text-muted-foreground">Inflation Adjusted</span>
                                <input type="checkbox" defaultChecked className="size-3.5 rounded-none bg-background border-border text-primary focus:ring-0" />
                            </label>
                        </section>

                        <button 
                            onClick={runSimulation}
                            disabled={isLoading}
                            className="w-full bg-primary hover:bg-primary/90 text-white text-[10px] font-black uppercase py-3 mt-4 transition-colors flex items-center justify-center gap-2 shadow-lg shadow-primary/20"
                        >
                            <Play className="size-3.5 fill-current" />
                            {isLoading ? "Simulating..." : "Run Simulation"}
                        </button>
                    </div>
                </aside>

                {/* Workspace */}
                <div className="flex-1 flex flex-col min-w-0">
                    <div className="flex-1 p-6 flex flex-col">
                        <div className="flex items-center justify-between mb-6">
                            <div>
                                <h2 className="text-2xl font-black tracking-tight uppercase text-foreground">Monte Carlo Simulation</h2>
                                <p className="text-[10px] text-muted-foreground font-bold uppercase tracking-widest">Projected Portfolio Value Distribution | {volatilityAssumption.toUpperCase()} CASE</p>
                            </div>
                            <div className="flex gap-2">
                                <div className="flex items-center gap-2 px-3 py-1.5 border border-border bg-card text-[9px] font-bold uppercase tracking-widest text-foreground/80">
                                    <div className="size-2 bg-[#1e5df1]/10 border border-[#1e5df1]/30" />
                                    95% Confidence Band
                                </div>
                                <div className="flex items-center gap-2 px-3 py-1.5 border border-border bg-card text-[9px] font-bold uppercase tracking-widest text-foreground/80">
                                    <div className="size-2 bg-primary" />
                                    Median Outcome
                                </div>
                            </div>
                        </div>

                        <div className="flex-1 relative border border-border bg-card/30 overflow-hidden shadow-inner flex flex-col">
                            {isLoading && chartData.length === 0 ? (
                                <div className="flex-1 flex items-center justify-center font-mono text-xs text-muted-foreground uppercase tracking-widest">
                                    RUNNING_MONTE_CARLO_SIMULATION_PASS...
                                </div>
                            ) : (
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
                                                tickFormatter={(v) => `$${(v / 1e6).toFixed(1)}M`}
                                            />
                                            <Tooltip 
                                                contentStyle={{
                                                    backgroundColor: 'hsl(var(--card))',
                                                    borderColor: 'hsl(var(--border))',
                                                    fontSize: '10px',
                                                    fontFamily: 'monospace'
                                                }}
                                                formatter={(val: any) => [`$${parseFloat(val).toLocaleString()}`, ""]}
                                                labelFormatter={(label) => `Month: ${label}`}
                                            />
                                            <Area type="monotone" dataKey="upper_95" stroke="none" fill="rgba(30, 93, 241, 0.05)" />
                                            <Area type="monotone" dataKey="lower_5" stroke="none" fill="rgba(30, 93, 241, 0.1)" />
                                            <Area type="monotone" dataKey="median" stroke="hsl(var(--primary))" strokeWidth={3} fill="none" />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Stats Bar */}
                    <div className="h-72 border-t border-border grid grid-cols-12 shrink-0 bg-background transition-colors">
                        <div className="col-span-12 xl:col-span-5 border-r border-border p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Historical Stress Overlay</h3>
                                <span className="text-[10px] text-destructive font-black tracking-tighter uppercase">
                                    {result ? `${result.max_drawdown.toFixed(1)}% MAX DD` : "-24.2% MAX DD"}
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

                        <div className="col-span-12 xl:col-span-7 bg-card/20 p-6">
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
