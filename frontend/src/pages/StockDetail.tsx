import {
    TrendingUp,
    TrendingDown,
    CheckCircle2,
    AlertTriangle,
    ShieldCheck,
    Info,
    BadgeInfo,
    BarChart3,
    Radar,
    Activity,
    User,
    Zap,
    ChevronRight,
    ShieldAlert
} from "lucide-react"
import { cn } from "@/lib/utils"

const stats = [
    { label: "P/E Ratio (GAAP)", value: "72.4x" },
    { label: "Forward P/E", value: "34.2x" },
    { label: "Div Yield", value: "0.02%" },
    { label: "Beta (5Y Monthly)", value: "1.68" },
    { label: "Free Cash Flow", value: "$27.1B" },
]

export default function StockDetail() {
    return (
        <div className="flex flex-col flex-1 p-6 bg-background overflow-y-auto custom-scrollbar transition-colors">
            <section className="mb-6 flex flex-wrap items-end justify-between gap-6 border-b border-border pb-6">
                <div className="flex flex-col gap-1">
                    <div className="flex items-baseline gap-4">
                        <h2 className="text-6xl font-black tracking-tighter text-foreground">NVDA</h2>
                        <div className="flex items-center gap-2 px-3 py-1 bg-q-risk-low/10 text-q-risk-low text-sm font-bold border border-q-risk-low/20 uppercase tracking-widest shadow-sm shadow-q-risk-low/10">
                            <TrendingUp className="size-4" />
                            <span>+2.45%</span>
                        </div>
                    </div>
                    <div className="flex items-center gap-3 text-muted-foreground text-sm font-medium">
                        <span className="text-foreground uppercase tracking-wider">NVIDIA Corp.</span>
                        <div className="size-1 rounded-full bg-border" />
                        <span>Technology / Semiconductors</span>
                        <div className="size-1 rounded-full bg-border" />
                        <span>MCap: $2.5T</span>
                        <div className="size-1 rounded-full bg-border" />
                        <span className="text-primary font-mono font-bold">NASDAQ: NVDA</span>
                    </div>
                </div>

                <div className="flex items-center gap-4 bg-card border border-border p-4 px-6 shadow-xl shadow-background/10 transition-colors">
                    <div className="flex flex-col items-end">
                        <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Institutional Risk Score</span>
                        <span className="text-3xl font-black text-foreground leading-none">84<span className="text-lg text-muted-foreground font-medium ml-1">/100</span></span>
                    </div>
                    <div className="size-12 flex items-center justify-center relative">
                        <svg className="size-full -rotate-90">
                            <circle cx="24" cy="24" r="20" fill="transparent" stroke="currentColor" className="text-border" strokeWidth="4" />
                            <circle cx="24" cy="24" r="20" fill="transparent" stroke="currentColor" className="text-primary" strokeWidth="4" strokeDasharray="125.6" strokeDashoffset="20" />
                        </svg>
                        <ShieldCheck className="absolute text-primary size-5" />
                    </div>
                </div>
            </section>

            <section className="mb-6 flex gap-1 border-b border-border overflow-x-auto no-scrollbar">
                {["Investment Thesis", "Financial Health", "Risk Breakdown", "Signal Intelligence", "Macro Exposure"].map((tab, i) => (
                    <button
                        key={tab}
                        className={cn(
                            "px-6 py-3 text-xs font-bold uppercase tracking-widest transition-all",
                            i === 0
                                ? "border-b-2 border-primary bg-primary/10 text-primary"
                                : "border-b-2 border-transparent text-muted-foreground hover:text-foreground"
                        )}
                    >
                        {tab}
                    </button>
                ))}
            </section>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
                <div className="lg:col-span-8 space-y-6">
                    <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                        {/* Thesis */}
                        <div className="flex flex-col bg-card border border-border shadow-lg transition-colors">
                            <div className="flex items-center gap-2 border-b border-border bg-muted/40 px-4 py-3">
                                <Zap className="text-primary size-4" />
                                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground">Investment Thesis</h3>
                                <span className="ml-auto flex items-center gap-1 rounded bg-primary/20 px-2 py-0.5 text-[10px] font-bold text-primary border border-primary/20">BULLISH</span>
                            </div>
                            <div className="p-6">
                                <p className="text-sm leading-relaxed text-muted-foreground mb-4 font-medium">
                                    NVIDIA occupies a dominant, near-monopoly position in the high-performance AI accelerator market. Our quantitative models suggest H100 lifecycle remains robust with a visibility runway extending into FY2026.
                                </p>
                                <ul className="space-y-3">
                                    {/* ... */}
                                    {[
                                        "Structural data center demand continues to outpace foundry supply limits.",
                                        "Superior software moat (CUDA) prevents rapid displacement by commodity silicon.",
                                        "Aggressive Blackwell roadmap maintains 12-18 month lead."
                                    ].map((item, i) => (
                                        <li key={i} className="flex items-start gap-3 group">
                                            <CheckCircle2 className="text-primary size-4 mt-0.5 group-hover:scale-110 transition-transform" />
                                            <span className="text-sm text-foreground/90 font-medium">{item}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </div>

                        {/* Anti-Thesis */}
                        <div className="flex flex-col bg-card border border-border shadow-lg transition-colors">
                            <div className="flex items-center gap-2 border-b border-border bg-muted/40 px-4 py-3">
                                <AlertTriangle className="text-q-warning size-4" />
                                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground">Anti-Thesis</h3>
                                <span className="ml-auto flex items-center gap-1 rounded bg-q-warning/20 px-2 py-0.5 text-[10px] font-bold text-q-warning border border-q-warning/20">BEARISH</span>
                            </div>
                            <div className="p-6">
                                <p className="text-sm leading-relaxed text-muted-foreground mb-4 font-medium">
                                    Concentration risk among major hyperscalers presents a potential air-pocket in future CapEx cycles. Geopolitical friction remains the primary tail-risk.
                                </p>
                                <ul className="space-y-3">
                                    {/* ... */}
                                    {[
                                        "Export restrictions on specialized chips to China may widen in Q3.",
                                        "Valuation premiums sit 2.5 standard deviations above historical means.",
                                        "Supply chain bottlenecks in CoWoS packaging could cap short-term upside."
                                    ].map((item, i) => (
                                        <li key={i} className="flex items-start gap-3 group">
                                            <ShieldAlert className="text-q-warning size-4 mt-0.5 group-hover:scale-110 transition-transform" />
                                            <span className="text-sm text-foreground/90 font-medium">{item}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    </div>

                    {/* Alignment Viz */}
                    <div className="bg-card border border-border shadow-lg transition-colors">
                        <div className="flex items-center justify-between border-b border-border bg-muted/40 px-4 py-3">
                            <div className="flex items-center gap-2">
                                <Radar className="text-primary size-4" />
                                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground">Risk Alignment Visualization</h3>
                            </div>
                            <div className="flex items-center gap-4 text-[10px] font-bold uppercase tracking-widest">
                                <div className="flex items-center gap-1.5"><div className="size-2 bg-primary" /> User Band</div>
                                <div className="flex items-center gap-1.5"><div className="size-2 bg-muted-foreground" /> Asset Band</div>
                            </div>
                        </div>
                        <div className="flex flex-col items-center justify-center p-10 md:flex-row md:gap-16">
                            <div className="relative size-48">
                                <div className="absolute inset-0 rounded-full border-[10px] border-border" />
                                <div className="absolute inset-0 rounded-full border-[10px] border-primary" style={{ clipPath: "polygon(50% 50%, 0 0, 100% 0, 100% 50%)" }} />
                                <div className="absolute inset-0 flex flex-col items-center justify-center">
                                    <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Alignment</span>
                                    <span className="text-4xl font-black text-foreground">92%</span>
                                </div>
                            </div>
                            <div className="mt-8 grid flex-1 grid-cols-1 gap-6 md:mt-0 md:grid-cols-2">
                                <div className="flex flex-col gap-3 rounded border border-border bg-muted/40 p-4">
                                    <div className="flex items-center justify-between">
                                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">User Risk Profile</span>
                                        <User className="size-3.5 text-primary" />
                                    </div>
                                    <span className="text-lg font-bold text-foreground uppercase tracking-tight">Moderate-Aggressive</span>
                                    <div className="h-1.5 w-full bg-border">
                                        <div className="h-full bg-primary" style={{ width: "75%" }} />
                                    </div>
                                </div>
                                <div className="flex flex-col gap-3 rounded border border-border bg-muted/40 p-4">
                                    <div className="flex items-center justify-between">
                                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Asset Risk Profile</span>
                                        <TrendingUp className="size-3.5 text-q-warning" />
                                    </div>
                                    <span className="text-lg font-bold text-foreground uppercase tracking-tight">High Growth / High Vol</span>
                                    <div className="h-1.5 w-full bg-border">
                                        <div className="h-full bg-q-warning" style={{ width: "85%" }} />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <aside className="lg:col-span-4 space-y-6">
                    {/* Key Stats */}
                    <div className="bg-card border border-border shadow-lg transition-colors">
                        <div className="border-b border-border bg-muted/40 px-4 py-3">
                            <h3 className="text-xs font-bold uppercase tracking-widest text-foreground">Key Stats</h3>
                        </div>
                        <div className="divide-y divide-border">
                            {stats.map((row) => (
                                <div key={row.label} className="flex items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors">
                                    <span className="text-xs text-muted-foreground uppercase tracking-wider">{row.label}</span>
                                    <span className="text-sm font-mono font-bold text-foreground tracking-tighter">{row.value}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Ownership */}
                    <div className="bg-card border border-border shadow-lg transition-colors">
                        <div className="border-b border-border bg-muted/40 px-4 py-3">
                            <h3 className="text-xs font-bold uppercase tracking-widest text-foreground">Institutional Ownership</h3>
                        </div>
                        <div className="p-4">
                            <div className="flex h-4 w-full mb-6 border border-border/50 shadow-inner">
                                <div className="h-full bg-primary shadow-[inset_0_0_10px_rgba(30,93,241,0.5)]" style={{ width: "92%" }} />
                                <div className="h-full bg-blue-400" style={{ width: "2%" }} />
                                <div className="h-full bg-border" style={{ width: "6%" }} />
                            </div>
                            <div className="space-y-3">
                                {[
                                    { label: "Institutional", value: "92.0%", color: "bg-primary" },
                                    { label: "Insider", value: "2.0%", color: "bg-blue-400" },
                                    { label: "Retail / Other", value: "6.0%", color: "bg-border" }
                                ].map((item) => (
                                    <div key={item.label} className="flex items-center justify-between text-[11px] font-bold tracking-widest uppercase">
                                        <div className="flex items-center gap-2">
                                            <div className={cn("size-2", item.color)} />
                                            <span className="text-muted-foreground">{item.label}</span>
                                        </div>
                                        <span className="text-foreground">{item.value}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Price Action Sparklines */}
                    <div className="bg-card border border-border shadow-lg transition-colors">
                        <div className="border-b border-border bg-muted/40 px-4 py-3">
                            <h3 className="text-xs font-bold uppercase tracking-widest text-foreground">Price Action</h3>
                        </div>
                        <div className="p-4 space-y-6">
                            {[
                                { label: "5D", valColor: "text-q-risk-low", val: "+5.2%", fill: "h-1/2" },
                                { label: "1M", valColor: "text-q-risk-low", val: "+12.8%", fill: "h-2/3" },
                                { label: "YTD", valColor: "text-q-risk-low", val: "+114.5%", fill: "h-full" },
                            ].map((item) => (
                                <div key={item.label} className="flex items-center justify-between group cursor-help">
                                    <div className="flex flex-col">
                                        <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">{item.label}</span>
                                        <span className={cn("text-lg font-bold tracking-tighter", item.valColor)}>{item.val}</span>
                                    </div>
                                    <div className="h-10 w-32 bg-q-risk-low/5 border-l border-q-risk-low/30 relative overflow-hidden group-hover:bg-q-risk-low/10 transition-colors">
                                        <div className={cn("absolute bottom-0 left-0 w-full bg-gradient-to-t from-q-risk-low/20 to-transparent transition-all duration-500", item.fill)} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </aside>
            </div>
        </div>
    )
}
