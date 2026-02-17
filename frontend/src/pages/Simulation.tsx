import { useState } from "react"
import {
    BarChart3,
    TrendingUp,
    TrendingDown,
    Play,
    Download,
    Settings,
    Bell,
    User,
    Activity,
    ChevronDown,
    Info,
    Clock,
    ShieldCheck,
    Zap,
    SlidersHorizontal,
    LineChart as LineChartIcon
} from "lucide-react"
import { cn } from "@/lib/utils"

const initialAllocation = [
    { label: "Equities", val: 60 },
    { label: "Fixed Income", val: 25 },
    { label: "Alternatives", val: 10 },
    { label: "Cash", val: 5 },
]

const metrics = [
    { label: "Forward Sharpe", value: "1.84", sub: "CI: 1.6 - 2.1", color: "text-green-400" },
    { label: "Portfolio Beta", value: "0.92", sub: "Rel. to S&P 500" },
    { label: "Est. Alpha (BPS)", value: "+145", sub: "Top 15% Percentile", color: "text-green-500" },
    { label: "Volatility (Std Dev)", value: "12.4%", sub: "Annualized" },
    { label: "Prob. of Success", value: "88.2%", sub: "Goal: $4M Target", color: "text-[#1e5df1]" },
    { label: "Value at Risk (95%)", value: "-$1.2M", sub: "1-Year Horizon", color: "text-red-500" },
]

export default function Simulation() {
    const [allocation, setAllocation] = useState(initialAllocation)

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
                            <h3 className="text-[9px] font-bold uppercase text-[#484f58] mb-3 tracking-tighter">Target Allocation (%)</h3>
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
                                <button className="py-2 text-[9px] font-bold uppercase hover:bg-muted transition-colors">Cons.</button>
                                <button className="py-2 text-[9px] font-bold uppercase bg-primary text-white">Base</button>
                                <button className="py-2 text-[9px] font-bold uppercase hover:bg-muted transition-colors border-l border-border">Aggr.</button>
                            </div>
                        </section>

                        <section className="space-y-3">
                            <h3 className="text-[9px] font-bold uppercase text-muted-foreground/60 tracking-tighter">Parameters</h3>
                            <div className="flex items-center justify-between">
                                <span className="text-[11px] text-muted-foreground">Time Horizon</span>
                                <select className="bg-background border border-border text-[10px] py-1 px-2 focus:ring-0 rounded-sm text-foreground">
                                    <option>10 Years</option>
                                    <option>20 Years</option>
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

                        <button className="w-full bg-primary hover:bg-primary/90 text-white text-[10px] font-black uppercase py-3 mt-4 transition-colors flex items-center justify-center gap-2 shadow-lg shadow-primary/20">
                            <Play className="size-3.5 fill-current" />
                            Run Simulation
                        </button>
                    </div>
                </aside>

                {/* Workspace */}
                <div className="flex-1 flex flex-col min-w-0">
                    <div className="flex-1 p-6 flex flex-col">
                        <div className="flex items-center justify-between mb-6">
                            <div>
                                <h2 className="text-2xl font-black tracking-tight uppercase text-foreground">Monte Carlo Simulation</h2>
                                <p className="text-[10px] text-muted-foreground font-bold uppercase tracking-widest">Projected Portfolio Value Distribution | Base Case</p>
                            </div>
                            <div className="flex gap-2">
                                <div className="flex items-center gap-2 px-3 py-1.5 border border-border bg-card text-[9px] font-bold uppercase tracking-widest text-foreground/80">
                                    <div className="size-2 bg-primary/20 border border-primary" />
                                    95th Percentile
                                </div>
                                <div className="flex items-center gap-2 px-3 py-1.5 border border-border bg-card text-[9px] font-bold uppercase tracking-widest text-foreground/80">
                                    <div className="size-2 bg-primary" />
                                    Median Outcome
                                </div>
                            </div>
                        </div>

                        <div className="flex-1 relative border border-border bg-card/30 overflow-hidden shadow-inner">
                            <div className="absolute inset-x-12 bottom-12 top-10 pointer-events-none">
                                <svg className="size-full" preserveAspectRatio="none" viewBox="0 0 1000 400">
                                    <g className="stroke-[#30363d]/30" strokeWidth="1" strokeDasharray="2">
                                        {[80, 160, 240, 320].map(y => <line key={y} x1="0" x2="1000" y1={y} y2={y} />)}
                                    </g>
                                    <path d="M0,300 Q250,280 500,200 Q750,120 1000,50 L1000,380 Q750,390 500,385 Q250,380 0,300 Z" fill="rgba(30, 93, 241, 0.05)" />
                                    <path d="M0,300 Q250,290 500,240 Q750,190 1000,120 L1000,340 Q750,360 500,355 Q250,350 0,300 Z" fill="rgba(30, 93, 241, 0.1)" />
                                    <path d="M0,300 Q250,295 500,270 Q750,240 1000,220" fill="none" stroke="currentColor" className="text-primary" strokeWidth="3" />
                                    <circle cx="0" cy="300" fill="currentColor" r="5" className="text-primary animate-pulse" />
                                </svg>
                                <div className="absolute -left-12 inset-y-0 flex flex-col justify-between text-[9px] font-mono text-muted-foreground font-bold pr-4">
                                    <span>$10.0M</span>
                                    <span>$7.5M</span>
                                    <span>$5.0M</span>
                                    <span>$2.5M</span>
                                    <span>$0.0M</span>
                                </div>
                                <div className="absolute inset-x-0 -bottom-8 flex justify-between text-[9px] font-mono text-muted-foreground font-bold">
                                    <span>2024 (START)</span>
                                    <span>2029</span>
                                    <span>2034 (END)</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Stats Bar */}
                    <div className="h-72 border-t border-border grid grid-cols-12 shrink-0 bg-background transition-colors">
                        <div className="col-span-12 xl:col-span-5 border-r border-border p-6">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Historical Stress Overlay</h3>
                                <span className="text-[10px] text-destructive font-black tracking-tighter uppercase">-24.2% MAX DD</span>
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
