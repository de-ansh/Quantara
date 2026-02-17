import {
    BarChart3,
    AlertTriangle,
    Zap,
    Download,
    Droplets,
    Globe,
    Cpu,
    Monitor,
    Database,
    Cloud,
    Network,
    Info,
} from "lucide-react"
import { cn } from "@/lib/utils"
import {
    ResponsiveContainer,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    LineChart,
    Line
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"

interface KPIData {
    label: string
    value: string
    trend: string
    status: "danger" | "success" | "warning"
    fill?: string
    isSpark?: boolean
    isDots?: boolean
    sub?: string
}

interface FactorData {
    name: string
    val: string
    width: string
    opacity: string
    offset?: string
}

interface ScenarioData {
    name: string
    type: string
    impact: string
    status: "danger" | "success"
    icon: React.ComponentType<{ className?: string }>
    active?: boolean
}

interface MatrixData {
    label: string
    val: string
    color: string
    icon?: React.ComponentType<{ className?: string }>
}

interface DrawdownPoint {
    time: string
    historical: number
    projected?: number
}

const kpis: KPIData[] = [
    { label: "Beta (5Y Trailing)", value: "1.42", trend: "+2.1% ↑", status: "danger", fill: "w-3/4" },
    { label: "Annualized Volatility", value: "32.4%", trend: "-0.5% ↓", status: "danger", isSpark: true },
    { label: "Liquidity Score", value: "88/100", trend: "+0.2% ↑", status: "success", isDots: true },
    { label: "VaR 95% (Daily)", value: "$12,450.00", trend: "-1.1% ↓", status: "danger", sub: "CONFIDENCE: 95%" },
]

const factors: FactorData[] = [
    { name: "MARKET SYSTEMIC RISK", val: "+42.5%", width: "42.5%", opacity: "bg-primary/40" },
    { name: "SECTOR (SEMI) SPECIFIC", val: "+28.2%", width: "28.2%", opacity: "bg-primary/30", offset: "left-[42.5%]" },
    { name: "MACRO (INTEREST RATES)", val: "+15.3%", width: "15.3%", opacity: "bg-primary/20", offset: "left-[70.7%]" },
    { name: "CURRENCY VOLATILITY", val: "+4.0%", width: "4%", opacity: "bg-primary/10", offset: "left-[86%]" },
]

const scenarios: ScenarioData[] = [
    { name: "Fed Pivot +50bps", type: "Interest Rate Spike", impact: "-12.4%", status: "danger", icon: BarChart3 },
    { name: "Global Recession (Bear)", type: "Consumer Confidence Drop", impact: "-24.8%", status: "danger", icon: Globe },
    { name: "Oil Spike to $120", type: "Supply Chain Shock", impact: "-6.2%", status: "danger", icon: Droplets },
    { name: "AI Infrastructure Expansion", type: "Catalyst Event", impact: "+18.5%", status: "success", icon: Zap, active: true },
]

const matrix: MatrixData[] = [
    { label: "CPU TECH", val: "0.82", color: "bg-q-risk-high/90", icon: Cpu },
    { label: "GPU CLOUD", val: "0.71", color: "bg-q-risk-high/70", icon: Cloud },
    { label: "NETWORKING", val: "0.45", color: "bg-q-risk-high/40", icon: Network },
    { label: "AUTO AI", val: "0.22", color: "bg-q-risk-low/40", icon: Monitor },
    { label: "GAMING", val: "0.15", color: "bg-q-risk-low/60", icon: Monitor },
    { label: "DATA CENTER", val: "0.78", color: "bg-q-risk-high/80", icon: Database },
    { label: "AI INFRA", val: "0.55", color: "bg-q-risk-high/50", icon: Monitor },
    { label: "RESEARCH", val: "0.28", color: "bg-q-risk-low/30", icon: Monitor },
    { label: "OMNIVERSE", val: "0.12", color: "bg-q-risk-low/70", icon: Monitor },
    { label: "EDGE COMP", val: "0.08", color: "bg-q-risk-low/80", icon: Monitor },
]

const drawdownData: DrawdownPoint[] = [
    { time: "0", historical: 100 },
    { time: "1", historical: 95 },
    { time: "2", historical: 98 },
    { time: "3", historical: 85 },
    { time: "4", historical: 88 },
    { time: "5", historical: 70 },
    { time: "6", historical: 75 },
    { time: "7", historical: 60 },
    { time: "8", historical: 65, projected: 65 },
    { time: "9", historical: 65, projected: 55 },
    { time: "10", historical: 65, projected: 58 },
    { time: "11", historical: 65, projected: 45 },
]

export default function Risk() {
    return (
        <div className="flex flex-col flex-1 p-6 bg-background space-y-6 overflow-y-auto custom-scrollbar">
            {/* Risk Context Header */}
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-q-border pb-6 shrink-0">
                <div className="space-y-1">
                    <div className="flex items-center gap-3">
                        <span className="text-primary font-mono text-[10px] font-black uppercase tracking-widest">Equity Intelligence</span>
                        <div className="size-1 rounded-full bg-q-border" />
                        <span className="text-muted-foreground font-mono text-[10px] font-black uppercase tracking-widest leading-none">Live Data: NASDAQ</span>
                    </div>
                    <h2 className="text-3xl font-black tracking-tighter uppercase text-foreground leading-none">Asset: NVDA | <span className="text-q-risk-high">Risk: Aggressive</span></h2>
                    <p className="text-muted-foreground text-[11px] max-w-2xl font-bold uppercase tracking-tight">
                        NVIDIA Corp. risk decomposition based on 252-day trailing variance. Model: GARCH(1,1) with institutional factor overlays.
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <Button variant="outline" size="sm" className="bg-q-surface border-q-border text-[10px] font-black uppercase tracking-[0.15em] hover:bg-muted h-9 px-4">
                        <Download className="mr-2 size-3.5" />
                        Export Data
                    </Button>
                    <Button size="sm" className="bg-primary hover:brightness-110 text-primary-foreground text-[10px] font-black uppercase tracking-[0.15em] h-9 px-4">
                        Recalculate Model
                    </Button>
                </div>
            </header>

            {/* KPI Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 shrink-0">
                {kpis.map((stat, i) => (
                    <Card key={i} className="bg-q-surface border-q-border shadow-none overflow-hidden group">
                        <CardHeader className="p-5 pb-2 flex-row items-start justify-between space-y-0">
                            <CardTitle className="text-[10px] font-black text-muted-foreground uppercase tracking-[0.2em] leading-none">{stat.label}</CardTitle>
                            <Badge variant="outline" className={cn("text-[8px] font-black bg-transparent border-none p-0 leading-none", stat.status === "danger" ? "text-q-risk-high" : "text-q-risk-low")}>{stat.trend}</Badge>
                        </CardHeader>
                        <CardContent className="p-5 pt-0">
                            <div className="text-2xl font-black tabular-nums tracking-tighter text-foreground leading-none mb-4">{stat.value}</div>

                            {stat.fill && (
                                <div className="h-2 w-full bg-q-border/30 rounded-full overflow-hidden">
                                    <div className={cn("h-full bg-primary shadow-[0_0_8px_rgba(var(--primary),0.4)] transition-all duration-1000", stat.fill)} />
                                </div>
                            )}

                            {stat.isSpark && (
                                <div className="h-8 w-full flex items-end gap-1 opacity-60 group-hover:opacity-100 transition-opacity">
                                    {[4, 6, 10, 8, 5].map((h, idx) => (
                                        <div key={idx} className={cn("flex-1 bg-q-border rounded-t-sm", idx === 2 ? "bg-primary" : "")} style={{ height: `${h * 10}%` }} />
                                    ))}
                                </div>
                            )}

                            {stat.isDots && (
                                <div className="grid grid-cols-10 gap-1.5 h-2">
                                    {[...Array(10)].map((_, idx) => (
                                        <div key={idx} className={cn("rounded-full", idx < 8 ? "bg-q-risk-low shadow-[0_0_5px_rgba(var(--q-risk-low),0.5)]" : "bg-q-border")} />
                                    ))}
                                </div>
                            )}

                            {stat.sub && (
                                <div className="flex items-center justify-between border-t border-q-border/30 pt-3 mt-1">
                                    <span className="text-[8px] font-black font-mono text-muted-foreground uppercase tracking-widest">{stat.sub}</span>
                                    <span className="text-[8px] font-black font-mono text-muted-foreground uppercase tracking-widest">Horizon: 1D</span>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0 flex-1">
                {/* Attribution */}
                <Card className="lg:col-span-8 bg-q-surface border-q-border shadow-none flex flex-col">
                    <CardHeader className="p-6 border-b border-q-border flex-row items-center justify-between space-y-0 bg-background/20">
                        <div>
                            <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-foreground">Factor Risk Attribution</CardTitle>
                            <p className="text-[9px] text-muted-foreground font-black uppercase tracking-widest mt-0.5">Marginal contribution to total portfolio risk</p>
                        </div>
                        <Badge variant="outline" className="text-[9px] font-black font-mono text-muted-foreground border-q-border rounded-sm h-6">MODEL: MULTI-FACTOR</Badge>
                    </CardHeader>
                    <CardContent className="p-6 space-y-6 flex-1 overflow-auto custom-scrollbar">
                        {factors.map((f, i) => (
                            <div key={i} className="space-y-2">
                                <div className="flex justify-between text-[10px] font-black uppercase tracking-widest font-mono">
                                    <span className="text-muted-foreground">{f.name}</span>
                                    <span className="text-foreground">{f.val}</span>
                                </div>
                                <div className="h-6 bg-background border border-q-border relative overflow-hidden group cursor-help rounded-sm">
                                    <div className={cn("absolute inset-y-0 bg-primary/30 border-r-2 border-primary transition-all duration-1000", f.width, f.offset || "left-0")} />
                                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full group-hover:animate-shimmer" />
                                </div>
                            </div>
                        ))}
                    </CardContent>
                    <div className="p-6 pt-0 mt-auto">
                        <Separator className="bg-q-border mb-4" />
                        <div className="flex justify-end">
                            <div className="text-right">
                                <p className="text-[10px] text-muted-foreground font-black uppercase tracking-[0.2em] mb-1">Total Attributed Risk</p>
                                <div className="flex items-baseline justify-end gap-3 text-3xl font-black tabular-nums tracking-tighter text-foreground leading-none">
                                    90.0%
                                    <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest">Residual: 10%</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </Card>

                {/* Scenarios */}
                <Card className="lg:col-span-4 bg-q-surface border-q-border shadow-none flex flex-col">
                    <CardHeader className="p-6 border-b border-q-border bg-background/20">
                        <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-foreground">Scenario Analysis (Shock Engine)</CardTitle>
                        <p className="text-[9px] text-muted-foreground font-black uppercase tracking-widest mt-0.5">Projected % impact under market shocks</p>
                    </CardHeader>
                    <CardContent className="p-4 space-y-2 flex-1 overflow-auto custom-scrollbar">
                        {scenarios.map((s, i) => (
                            <div
                                key={i}
                                className={cn(
                                    "p-3 rounded-md bg-background/50 border transition-all cursor-pointer group flex items-center justify-between",
                                    s.active ? "border-primary bg-primary/5 ring-1 ring-primary/20" : "border-q-border/50 hover:border-q-border hover:bg-background"
                                )}
                            >
                                <div className="flex items-center gap-3">
                                    <div className={cn("p-2 rounded bg-background border border-q-border group-hover:scale-110 transition-transform", s.status === "danger" ? "text-q-risk-high" : "text-q-risk-low")}>
                                        <s.icon className="size-4" />
                                    </div>
                                    <div>
                                        <p className="text-[10px] font-black uppercase tracking-tight text-foreground">{s.name}</p>
                                        <p className="text-[8px] text-muted-foreground font-black uppercase font-mono tracking-widest">{s.type}</p>
                                    </div>
                                </div>
                                <span className={cn("font-mono font-black text-sm", s.status === "danger" ? "text-q-risk-high" : "text-q-risk-low")}>{s.impact}</span>
                            </div>
                        ))}
                    </CardContent>
                    <div className="p-4">
                        <Button variant="secondary" className="w-full text-[10px] font-black uppercase tracking-[0.2em] h-10 border border-q-border/50">
                            Load Advanced Scenarios
                        </Button>
                    </div>
                </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 shrink-0">
                {/* Drawdown */}
                <Card className="bg-q-surface border-q-border shadow-none overflow-hidden">
                    <CardHeader className="p-6 border-b border-q-border bg-background/20 flex-row items-center justify-between space-y-0">
                        <div>
                            <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-foreground">Historical Max Drawdown</CardTitle>
                            <p className="text-[9px] text-muted-foreground font-black uppercase tracking-widest mt-0.5">Historical vs. Projected Stressed Performance</p>
                        </div>
                        <div className="flex items-center gap-4 text-[9px] font-black font-mono tracking-widest">
                            <div className="flex items-center gap-1.5 text-primary"><div className="size-2 bg-primary rounded-full" /> HIST</div>
                            <div className="flex items-center gap-1.5 text-q-risk-high"><div className="size-2 bg-q-risk-high rounded-full" /> PROJ</div>
                        </div>
                    </CardHeader>
                    <CardContent className="p-6">
                        <div className="h-64 relative">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={drawdownData}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--q-border))" opacity={0.3} />
                                    <XAxis hide />
                                    <YAxis
                                        domain={[0, 100]}
                                        axisLine={false}
                                        tickLine={false}
                                        tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))', fontWeight: 'bold' }}
                                        tickFormatter={(v) => `${v}%`}
                                    />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: 'hsl(var(--q-surface))',
                                            borderColor: 'hsl(var(--q-border))',
                                            fontSize: '10px',
                                            fontWeight: 'bold',
                                            textTransform: 'uppercase'
                                        }}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="historical"
                                        stroke="hsl(var(--primary))"
                                        strokeWidth={3}
                                        dot={false}
                                        animationDuration={2000}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="projected"
                                        stroke="hsl(var(--q-risk-high))"
                                        strokeWidth={3}
                                        strokeDasharray="5 5"
                                        dot={false}
                                        animationDuration={2500}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                            <div className="absolute top-2 left-10 text-[9px] font-black font-mono text-muted-foreground bg-background/50 px-1">0% PEAK</div>
                            <div className="absolute bottom-2 left-10 text-[9px] font-black font-mono text-q-risk-high bg-q-risk-high/10 px-1 border border-q-risk-high/20">-45% MAX DRAWDOWN PROJECTION</div>
                        </div>
                    </CardContent>
                </Card>

                {/* Heatmap */}
                <Card className="bg-q-surface border-q-border shadow-none overflow-hidden">
                    <CardHeader className="p-6 border-b border-q-border bg-background/20">
                        <CardTitle className="text-xs font-black uppercase tracking-[0.2em] text-foreground">Risk Concentration Matrix</CardTitle>
                        <p className="text-[9px] text-muted-foreground font-black uppercase tracking-widest mt-0.5">Attribution across asset sub-segments</p>
                    </CardHeader>
                    <CardContent className="p-4 bg-background/5 border-b border-q-border/30">
                        <div className="grid grid-cols-5 gap-1.5 h-64">
                            {matrix.map((m, i) => (
                                <div key={i} className={cn("p-2 text-[9px] font-black flex flex-col justify-between transition-all hover:scale-105 hover:z-10 cursor-crosshair border border-white/5 text-white rounded-sm group shadow-lg", m.color)}>
                                    <div className="flex justify-between items-start">
                                        <span className="leading-tight uppercase tracking-tighter opacity-90 group-hover:opacity-100">{m.label}</span>
                                        {m.icon && <m.icon className="size-3 opacity-40 group-hover:opacity-100 transition-opacity" />}
                                    </div>
                                    <span className="text-right font-mono font-black scale-90 group-hover:scale-100 transition-transform">{m.val}</span>
                                </div>
                            ))}
                            {[...Array(10)].map((_, i) => (
                                <div key={i + 10} className="bg-q-risk-low/5 p-2 text-[9px] font-black flex flex-col justify-between opacity-30 border border-q-border/20 rounded-sm">
                                    <span className="uppercase tracking-tighter text-muted-foreground">OTHER</span>
                                    <span className="text-right font-mono text-muted-foreground">0.02</span>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                    <div className="p-4 px-6 bg-q-surface flex justify-between items-center text-[9px] font-black font-mono text-muted-foreground uppercase tracking-[0.2em]">
                        <span className="flex items-center gap-2"><div className="size-2 bg-q-risk-low rounded-full" /> Min Risk</span>
                        <div className="flex-grow mx-8 h-1.5 bg-gradient-to-r from-q-risk-low via-primary to-q-risk-high rounded-full opacity-60" />
                        <span className="flex items-center gap-2"><div className="size-2 bg-q-risk-high rounded-full" /> Max Risk</span>
                    </div>
                </Card>
            </div>
        </div>
    )
}
