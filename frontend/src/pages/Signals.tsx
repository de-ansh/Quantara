import {
    MessageSquare,
    Download,
    Maximize2,
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"

interface AccumulationData {
    fund: string
    shares: string
    change: string
    value: string
    date: string
    type: "buy" | "sell"
}

interface InsiderData {
    person: string
    role: string
    type: string
    shares: string
    price: string
    date: string
}

interface SentimentPoint {
    time: string
    social: number
    news: number
}

const accumulationData: AccumulationData[] = [
    { fund: "Vanguard Group Inc.", shares: "284,541,200", change: "+4.2%", value: "$342.1B", date: "Q4 2023", type: "buy" },
    { fund: "BlackRock Inc.", shares: "245,120,450", change: "+1.8%", value: "$295.4B", date: "Q4 2023", type: "buy" },
    { fund: "FMR LLC", shares: "112,450,100", change: "-2.1%", value: "$135.2B", date: "Q4 2023", type: "sell" },
    { fund: "State Street Corp", shares: "98,120,400", change: "+0.5%", value: "$118.1B", date: "Q4 2023", type: "buy" },
    { fund: "Price (T.Rowe) Assoc", shares: "85,450,200", change: "+12.4%", value: "$102.8B", date: "Q4 2023", type: "buy" },
]

const insiderData: InsiderData[] = [
    { person: "Huang Jen Hsun", role: "CEO", type: "Option Exercise", shares: "120,000", price: "$450.22", date: "2024-01-15" },
    { person: "Kress Colette", role: "CFO", type: "Automatic Sell", shares: "15,400", price: "$520.10", date: "2024-01-12" },
    { person: "Puri Ajay K", role: "Director", type: "Open Market Buy", shares: "2,500", price: "$490.45", date: "2024-01-10" },
    { person: "Debesh Chowdry", role: "VP", type: "Stock Award", shares: "8,200", price: "$0.00", date: "2024-01-08" },
    { person: "Stevens Mark A", role: "Director", type: "Automatic Sell", shares: "25,000", price: "$510.00", date: "2024-01-05" },
]

const sentimentData: SentimentPoint[] = [
    { time: "09:00", social: 45, news: 30 },
    { time: "10:00", social: 52, news: 35 },
    { time: "11:00", social: 48, news: 42 },
    { time: "12:00", social: 65, news: 55 },
    { time: "13:00", social: 70, news: 60 },
    { time: "14:00", social: 55, news: 65 },
    { time: "15:00", social: 60, news: 58 },
    { time: "16:00", social: 75, news: 62 },
]

export default function Signals() {
    return (
        <div className="flex flex-col h-full bg-background overflow-hidden">
            {/* Header Info */}
            <div className="flex items-center justify-between px-6 py-3 border-b border-q-border bg-q-surface/50 shrink-0">
                <div className="flex items-center gap-6">
                    <div className="flex flex-col">
                        <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Market Context</span>
                        <div className="flex items-center gap-2">
                            <span className="text-sm font-black text-foreground uppercase tracking-tight">Tech Sector (XLK)</span>
                            <Badge variant="secondary" className="bg-q-risk-low/10 text-q-risk-low border-none h-4 px-1.5 text-[9px] font-black font-mono">STRONG OVERWEIGHT</Badge>
                        </div>
                    </div>
                    <div className="h-8 w-px bg-q-border hidden sm:block" />
                    <div className="flex flex-col hidden sm:flex font-mono">
                        <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Signal Confidence</span>
                        <span className="text-sm font-black text-primary">94.2% [HIGH]</span>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <span className="text-[9px] font-bold text-muted-foreground uppercase tracking-widest mr-2 animate-pulse flex items-center gap-1.5">
                        <div className="size-1.5 rounded-full bg-q-risk-low" /> Processing Live Feeds
                    </span>
                    <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground">
                        <Download className="size-4" />
                    </Button>
                </div>
            </div>

            <main className="flex-1 p-4 grid grid-cols-12 gap-4 overflow-y-auto custom-scrollbar">
                {/* Accumulation */}
                <Card className="col-span-12 lg:col-span-6 flex flex-col bg-q-surface border-q-border overflow-hidden shadow-none">
                    <CardHeader className="p-4 border-b border-q-border bg-background/30 shrink-0">
                        <CardTitle className="text-[10px] font-black uppercase tracking-[0.15em] flex items-center gap-2 text-foreground">
                            <div className="size-1.5 rounded-full bg-primary" />
                            Top 13F Institutional Accumulation
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0 flex-1 overflow-auto custom-scrollbar">
                        <Table>
                            <TableHeader className="bg-q-surface font-mono sticky top-0 z-10 border-b border-q-border">
                                <TableRow className="hover:bg-transparent">
                                    <TableHead className="text-[9px] font-black uppercase h-8 px-4 text-muted-foreground">Institution / Fund</TableHead>
                                    <TableHead className="text-[9px] font-black uppercase h-8 text-right text-muted-foreground">Shares</TableHead>
                                    <TableHead className="text-[9px] font-black uppercase h-8 text-right text-muted-foreground">Change</TableHead>
                                    <TableHead className="text-[9px] font-black uppercase h-8 text-right pr-4 text-muted-foreground">Value</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody className="text-[11px] font-mono">
                                {accumulationData.map((row) => (
                                    <TableRow key={row.fund} className="border-q-border hover:bg-primary/5 transition-colors cursor-crosshair">
                                        <TableCell className="px-4 py-2 font-bold text-foreground uppercase tracking-tight">{row.fund}</TableCell>
                                        <TableCell className="px-4 py-2 text-right text-foreground">{row.shares}</TableCell>
                                        <TableCell className={cn("px-4 py-2 text-right font-black", row.type === "buy" ? "text-q-risk-low" : "text-q-risk-high")}>
                                            {row.change}
                                        </TableCell>
                                        <TableCell className="px-4 py-2 text-right font-black pr-4 text-foreground">{row.value}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>

                {/* Insiders */}
                <Card className="col-span-12 lg:col-span-6 flex flex-col bg-q-surface border-q-border overflow-hidden shadow-none">
                    <CardHeader className="p-4 border-b border-q-border bg-background/30 shrink-0">
                        <CardTitle className="text-[10px] font-black uppercase tracking-[0.15em] flex items-center gap-2 text-foreground">
                            <div className="size-1.5 rounded-full bg-amber-500" />
                            Recent Insider Buying Activity
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="p-0 flex-1 overflow-auto custom-scrollbar">
                        <Table>
                            <TableHeader className="bg-q-surface font-mono sticky top-0 z-10 border-b border-q-border">
                                <TableRow className="hover:bg-transparent">
                                    <TableHead className="text-[9px] font-black uppercase h-8 px-4 text-muted-foreground">Relationship / Name</TableHead>
                                    <TableHead className="text-[9px] font-black uppercase h-8 text-center text-muted-foreground">Trans Type</TableHead>
                                    <TableHead className="text-[9px] font-black uppercase h-8 text-right text-muted-foreground">Shares</TableHead>
                                    <TableHead className="text-[9px] font-black uppercase h-8 text-right pr-4 text-muted-foreground">Price</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody className="text-[11px] font-mono">
                                {insiderData.map((row, i) => (
                                    <TableRow key={i} className="border-q-border hover:bg-primary/5 transition-colors cursor-crosshair">
                                        <TableCell className="px-4 py-2">
                                            <div className="font-bold text-foreground uppercase leading-none">{row.person}</div>
                                            <div className="text-[9px] text-muted-foreground uppercase font-black mt-0.5">{row.role}</div>
                                        </TableCell>
                                        <TableCell className="px-4 py-2 text-center">
                                            <Badge variant="outline" className="text-[8px] font-black px-1.5 py-0 border-q-border uppercase tracking-widest text-muted-foreground leading-none">{row.type}</Badge>
                                        </TableCell>
                                        <TableCell className="px-4 py-2 text-right font-black text-foreground">{row.shares}</TableCell>
                                        <TableCell className="px-4 py-2 text-right font-black pr-4 text-foreground">{row.price}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>

                {/* Sentiment Analysis */}
                <Card className="col-span-12 flex flex-col bg-q-surface border-q-border overflow-hidden min-h-[400px] shadow-none">
                    <CardHeader className="px-4 py-2 border-b border-q-border bg-background/30 shrink-0 flex-row items-center justify-between space-y-0">
                        <div className="flex items-center gap-6">
                            <CardTitle className="text-[10px] font-black uppercase tracking-[0.2em] flex items-center gap-2 text-foreground">
                                <MessageSquare className="size-3.5 text-primary" />
                                Quantitative Sentiment Analysis
                            </CardTitle>
                            <div className="flex items-center gap-4 text-[9px] font-black font-mono tracking-widest text-muted-foreground">
                                <div className="flex items-center gap-1.5"><div className="size-2 bg-primary" /> SOCIAL INDEX</div>
                                <div className="flex items-center gap-1.5"><div className="size-2 bg-q-risk-low" /> NEWS AGGREGATE</div>
                            </div>
                        </div>
                        <div className="flex items-center gap-1">
                            <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground">
                                <Maximize2 className="size-3.5" />
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent className="flex flex-col xl:flex-row flex-1 p-0 min-h-0">
                        <div className="flex-1 p-6 relative min-h-[300px]">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={sentimentData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                    <defs>
                                        <linearGradient id="colorSocial" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                                        </linearGradient>
                                        <linearGradient id="colorNews" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="hsl(var(--q-risk-low))" stopOpacity={0.2} />
                                            <stop offset="95%" stopColor="hsl(var(--q-risk-low))" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--q-border))" opacity={0.3} />
                                    <XAxis
                                        dataKey="time"
                                        axisLine={false}
                                        tickLine={false}
                                        tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))', fontWeight: 'bold' }}
                                        dy={10}
                                    />
                                    <YAxis hide />
                                    <Tooltip
                                        contentStyle={{
                                            backgroundColor: 'hsl(var(--q-surface))',
                                            borderColor: 'hsl(var(--q-border))',
                                            fontSize: '10px',
                                            fontWeight: 'bold',
                                            textTransform: 'uppercase'
                                        }}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="social"
                                        stroke="hsl(var(--primary))"
                                        fillOpacity={1}
                                        fill="url(#colorSocial)"
                                        strokeWidth={2}
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="news"
                                        stroke="hsl(var(--q-risk-low))"
                                        fillOpacity={1}
                                        fill="url(#colorNews)"
                                        strokeWidth={1.5}
                                        strokeDasharray="4 2"
                                    />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                        <div className="w-full xl:w-72 border-l border-q-border bg-background/20 overflow-hidden flex flex-col">
                            <div className="p-3 border-b border-q-border bg-q-surface shrink-0">
                                <h4 className="text-[9px] font-black uppercase tracking-widest text-muted-foreground">Sentiment Ticker Scores</h4>
                            </div>
                            <div className="flex-1 overflow-auto custom-scrollbar">
                                <table className="w-full text-[10px] font-mono border-collapse">
                                    <tbody className="divide-y divide-q-border/50">
                                        {[
                                            { t: "NVDA", s: "88", v: "+2.4%" },
                                            { t: "TSMC", s: "82", v: "+1.1%" },
                                            { t: "AMD", s: "45", v: "-4.2%" },
                                            { t: "INTC", s: "12", v: "-8.1%" },
                                            { t: "ARM", s: "77", v: "+5.1%" },
                                            { t: "AVGO", s: "60", v: "+0.5%" },
                                        ].map((item, idx) => (
                                            <tr key={idx} className="hover:bg-primary/5 transition-colors">
                                                <td className="px-3 py-2 font-black text-foreground">{item.t}</td>
                                                <td className="px-3 py-2 text-right">
                                                    <span className={cn(
                                                        "px-1 py-0.5 rounded-sm",
                                                        parseInt(item.s) > 70 ? "bg-q-risk-low/20 text-q-risk-low" :
                                                            parseInt(item.s) < 30 ? "bg-q-risk-high/20 text-q-risk-high" : "bg-muted text-muted-foreground"
                                                    )}>{item.s}</span>
                                                </td>
                                                <td className={cn("px-3 py-2 text-right font-black", item.v.startsWith("+") ? "text-q-risk-low" : "text-q-risk-high")}>{item.v}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </main>

            {/* Compliance Footer */}
            <footer className="bg-background border-t border-q-border py-2.5 px-6 flex flex-col md:flex-row justify-between items-center gap-2 shrink-0">
                <div className="flex items-center gap-4 text-[9px] font-black tracking-widest text-muted-foreground uppercase">
                    <span className="flex items-center gap-1.5"><div className="size-1.5 rounded-full bg-q-risk-low" /> NLP Model: LLAMA-3-70B</span>
                    <span className="flex items-center gap-1.5"><div className="size-1.5 rounded-full bg-q-risk-low" /> Latency: 42ms</span>
                </div>
                <span className="text-[9px] font-black tracking-widest text-muted-foreground uppercase">Last Global Scan: <span className="text-foreground">2024-02-17 12:45:01 UTC</span></span>
            </footer>
        </div>
    );
}
