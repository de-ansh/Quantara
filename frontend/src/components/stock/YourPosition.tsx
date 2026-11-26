import { Link } from "react-router-dom"
import Panel from "@/components/Panel"
import PortfolioTotals from "@/components/PortfolioTotals"
import { usePortfolioUpdates, useStockExposure } from "@/hooks/usePortfolios"
import { fundName, shortDay } from "@/lib/format"
import { money, sumTotals } from "@/lib/money"

/** On a stock's page: how much of it you hold across portfolios and through your funds. Hidden if you hold none. */
export default function YourPosition({ ticker }: { ticker: string }) {
    const { data } = usePortfolioUpdates()
    const { data: exposure } = useStockExposure(ticker)
    const held = (data ?? []).flatMap(p =>
        p.performance.holdings
            .filter(h => h.kind === "stock" && h.ticker.toUpperCase() === ticker && h.shares > 0)
            .map(h => ({ portfolio: p, h })),
    )
    const funds = Array.isArray(exposure?.funds) ? exposure.funds : []
    if (!held.length && !funds.length) return null
    const currency = held[0]?.h.currency ?? "INR"
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
    const description = held.length
        ? `${shares.toLocaleString(undefined, { maximumFractionDigits: 4 })} shares at ${money(shares ? cost / shares : null, currency)} average cost`
        : "You don't hold it directly, only through your funds"
    return (
        <Panel id="your-position" title="Your position" description={description}>
            <div className="p-4 space-y-3">
                {held.length > 0 && <>
                    <PortfolioTotals totals={totals} />
                    <p className="text-xs text-muted-foreground">
                        In {held.map(({ portfolio }, i) => (
                            <span key={portfolio.portfolio_id}>
                                {i > 0 && ", "}
                                <Link to={`/portfolios/${portfolio.portfolio_id}`} className="underline hover:text-foreground">{portfolio.name}</Link>
                            </span>
                        ))}
                    </p>
                </>}
                {funds.length > 0 && (
                    <div className="text-sm">
                        <p>
                            Through your funds: <span className="font-mono tabular-nums">{money(exposure?.via_funds ?? 0, "INR")}</span>
                        </p>
                        <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                            {funds.map(f => (
                                <li key={f.name}>
                                    {fundName(f.name)}: <span className="font-mono tabular-nums">{money(f.amount, "INR")}</span> ({f.weight}% of the fund)
                                </li>
                            ))}
                        </ul>
                        {exposure?.holdings_as_of && (
                            <p className="mt-1 text-xs text-muted-foreground">From fund portfolios published for {shortDay(exposure.holdings_as_of)}.</p>
                        )}
                    </div>
                )}
            </div>
        </Panel>
    )
}
