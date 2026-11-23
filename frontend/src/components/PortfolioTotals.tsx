import { cn } from "@/lib/utils"
import { dayPct, money, pct, tone } from "@/lib/money"
import type { CurrencyTotals } from "@/hooks/usePortfolios"

/** Value now, today and gain or loss so far, each coloured up or down; one row per currency.
 *  "md" (cards) puts the value on its own line so narrow columns don't wrap the amounts. */
export default function PortfolioTotals({ totals, size = "md" }: { totals: CurrencyTotals[]; size?: "md" | "lg" }) {
    return (
        <div className="space-y-3">
            {totals.map(t => (
                <dl key={t.currency} className={cn("grid gap-3 [&_dd]:whitespace-nowrap", size === "lg" ? "grid-cols-3" : "grid-cols-2")}>
                    <div className={size === "md" ? "col-span-2" : undefined}>
                        <dt className="text-xs text-muted-foreground">Value now</dt>
                        <dd className={cn("font-semibold font-mono tabular-nums text-foreground", size === "lg" ? "text-2xl" : "text-lg")}>
                            {money(t.market_value, t.currency)}
                        </dd>
                    </div>
                    <div>
                        <dt className="text-xs text-muted-foreground">Today</dt>
                        <dd className={cn("font-mono tabular-nums", tone(t.day_change))}>
                            {money(t.day_change, t.currency, true)}
                            <span className="block text-xs">{pct(dayPct(t.market_value, t.day_change))}</span>
                        </dd>
                    </div>
                    <div>
                        <dt className="text-xs text-muted-foreground">Gain or loss so far</dt>
                        <dd className={cn("font-mono tabular-nums", tone(t.unrealized_pnl))}>
                            {money(t.unrealized_pnl, t.currency, true)}
                            <span className="block text-xs">{pct(t.unrealized_pnl_pct)}</span>
                        </dd>
                    </div>
                </dl>
            ))}
        </div>
    )
}
