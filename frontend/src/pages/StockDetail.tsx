import { Link, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import apiClient from "@/lib/api"
import { timeAgo } from "@/lib/utils"
import { cleanTickerDisplay, getMarketLabel, isIndianAsset } from "@/lib/currency"
import type { RiskAnalysis, StockSearchItem } from "@/types/api"
import DayChange from "@/components/DayChange"
import WatchlistButton from "@/components/WatchlistButton"
import VerdictCard from "@/components/VerdictCard"
import PriceChart from "@/components/PriceChart"
import PriceAlertForm from "@/components/PriceAlertForm"
import TechnicalsCard from "@/components/TechnicalsCard"
import ShareholdingCard from "@/components/ShareholdingCard"
import FilingCard from "@/components/FilingCard"
import Panel from "@/components/Panel"
import KeyNumbers from "@/components/stock/KeyNumbers"
import ResearchReport from "@/components/stock/ResearchReport"
import { useResearch } from "@/hooks/useResearch"

/** One stock: what it is and costs, the call, how risky it is, how it has moved, and the research behind it. */
export default function StockDetail() {
    const ticker = (useParams().ticker || "").toUpperCase()
    const { data: report } = useResearch(ticker)

    const { data: stock, isLoading } = useQuery({
        queryKey: ["stockMetadata", ticker],
        queryFn: async () => {
            // track: opening a listed-but-untracked stock starts its price and risk jobs
            const res = await apiClient.get<{ stocks: StockSearchItem[] }>("/stocks/search", { params: { query: ticker, track: true } })
            return res.data.stocks?.find(s => s.ticker.toUpperCase() === ticker) ?? null
        },
        enabled: !!ticker,
    })
    const { data: risk } = useQuery({
        queryKey: ["stockRisk", ticker],
        queryFn: async () => (await apiClient.get<RiskAnalysis>(`/stocks/${ticker}/risk`)).data,
        enabled: !!ticker,
    })

    if (!ticker) {
        return (
            <div className="p-6">
                <p className="text-sm text-muted-foreground">Search for a stock with the bar at the top, or browse <Link to="/explorer" className="text-primary hover:underline">Find stocks</Link>.</p>
            </div>
        )
    }

    // Without price history the live analysis runs on defaults; prefer the stored score then
    const riskIsGuess = risk?.assumed_inputs?.includes("price_history")
    const riskScore = (riskIsGuess ? undefined : risk?.overall_risk_score) ?? stock?.risk ?? null

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto">
            <header className="flex flex-wrap items-end justify-between gap-4">
                <div className="min-w-0 space-y-1">
                    <p className="text-xs text-muted-foreground">
                        {cleanTickerDisplay(ticker)} · {isIndianAsset(ticker) ? getMarketLabel(ticker) : "US"}{stock?.sector ? ` · ${stock.sector}` : ""}
                    </p>
                    <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-foreground">
                        {isLoading ? ticker : stock?.name || ticker}
                        <WatchlistButton ticker={ticker} className="[&_svg]:size-5" />
                    </h1>
                    <p className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                        <span className="text-2xl font-semibold font-mono tabular-nums text-foreground">{stock?.price ?? "—"}</span>
                        <DayChange pct={stock?.change_pct} className="text-sm" />
                        <span className="text-sm text-muted-foreground">Market cap {stock?.cap && stock.cap !== "N/A" ? stock.cap : "—"}</span>
                        {stock?.price_updated_at && <span className="text-xs text-muted-foreground">Price from {timeAgo(stock.price_updated_at)}</span>}
                    </p>
                </div>
                <div className="flex flex-wrap gap-2 text-sm">
                    <Link to={`/compare?tickers=${encodeURIComponent(ticker)}`} className="rounded-md border border-border px-3 py-1.5 hover:bg-muted">Compare</Link>
                    <Link to={`/risk/${ticker}`} className="rounded-md border border-border px-3 py-1.5 hover:bg-muted">Risk breakdown</Link>
                </div>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
                <div className="lg:col-span-2 space-y-6">
                    <VerdictCard ticker={ticker} version={`${report?.generated_at ?? ""}|${stock?.risk ?? ""}`} />
                    <PriceChart ticker={ticker} />
                </div>
                <div className="space-y-6">
                    <KeyNumbers ticker={ticker} stock={stock} riskScore={riskScore} />
                    <Panel id="price-alert" title="Price alert" description="Get notified in the bell when the price crosses a level">
                        <div className="p-4"><PriceAlertForm ticker={ticker} /></div>
                    </Panel>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                <TechnicalsCard ticker={ticker} />
                <ShareholdingCard ticker={ticker} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
                <div className="lg:col-span-2"><ResearchReport ticker={ticker} risk={risk} /></div>
                <FilingCard ticker={ticker} />
            </div>
        </div>
    )
}
