import { Link } from "react-router-dom"
import Panel from "@/components/Panel"
import PortfolioTotals from "@/components/PortfolioTotals"
import { usePortfolioUpdates } from "@/hooks/usePortfolios"
import { money, sumTotals } from "@/lib/money"

/** On a stock's page: how much of it you hold across portfolios, and whether it is up or down. Hidden if you hold none. */
export default function YourPosition({ ticker }: { ticker: string }) {
    const { data } = usePortfolioUpdates()
    const held = (data ?? []).flatMap(p =>
        p.performance.holdings
            .filter(h => h.kind === "stock" && h.ticker.toUpperCase() === ticker && h.shares > 0)
            .map(h => ({ portfolio: p, h })),
    )
    if (!held.length) return null
    const currency = held[0].h.currency
    const shares = held.reduce((s, x) => s + x.h.shares, 0)
    const cost = held.reduce((s, x) => s + x.h.cost_value, 0)
    // Each holding as a one-line total so sumTotals adds them and recomputes the gain %
    const totals = sumTotals(held.map(({ h }) => [{
        currency: h.currency,
        market_value: h.market_value ?? 0,
        cost_value: h.cost_value,
        unrealized_pnl: h.unrealized_pnl ?? 0,
        unrealized_pnl_pct: null,
        day_change: h.day_change ?? 0,
        sector_allocation: {},
    }]))
    return (
        <Panel id="your-position" title="Your position" description={
            `${shares.toLocaleString(undefined, { maximumFractionDigits: 4 })} shares at ${money(shares ? cost / shares : null, currency)} average cost`
        }>
            <div className="p-4 space-y-3">
                <PortfolioTotals totals={totals} />
                <p className="text-xs text-muted-foreground">
                    In {held.map(({ portfolio }, i) => (
                        <span key={portfolio.portfolio_id}>
                            {i > 0 && ", "}
                            <Link to={`/portfolios/${portfolio.portfolio_id}`} className="underline hover:text-foreground">{portfolio.name}</Link>
                        </span>
                    ))}
                </p>
            </div>
        </Panel>
    )
}
