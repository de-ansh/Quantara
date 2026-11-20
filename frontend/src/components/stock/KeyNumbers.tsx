import { Link } from "react-router-dom"
import Panel from "@/components/Panel"
import { riskWord } from "@/components/dashboard/riskWord"
import type { StockSearchItem } from "@/types/api"

const pctText = (v: number | null | undefined, digits = 1) => (v === null || v === undefined ? "—" : `${v.toFixed(digits)}%`)

/** The figures people check first, each with a line on what it means. */
export default function KeyNumbers({ ticker, stock, riskScore }: { ticker: string; stock: StockSearchItem | null | undefined; riskScore: number | null }) {
    const beta = stock?.beta ?? null
    const rows: [string, string, string][] = [
        ["Risk", riskScore === null ? "—" : `${riskWord(riskScore)} · ${Math.round(riskScore)}/100`, "Price swings, debt, earnings and valuation combined; higher is riskier"],
        ["P/E", stock?.pe ? `${stock.pe.toFixed(1)}×` : "—", "Price for each rupee of yearly profit"],
        ["Return on equity", pctText(stock?.roe_pct), "Profit made on shareholders' money each year"],
        ["Debt to equity", stock?.debt_to_equity != null ? stock.debt_to_equity.toFixed(2) : "—", "Borrowing compared with shareholders' money"],
        ["Dividend yield", pctText(stock?.dividend_yield_pct, 2), "Yearly dividend as a share of the price"],
        ["1-year return", pctText(stock?.return_1y_pct), "Price change over the last 12 months"],
        ["Beta", beta === null ? "—" : beta.toFixed(2), beta === null ? "How much it moves with the market"
            : Math.abs(beta) < 0.3 ? "Barely moves with the market"
            : `Moves about ${Math.abs(beta).toFixed(1)}× as much as the market${beta < 0 ? ", often the other way" : ""}`],
    ]
    return (
        <Panel id="key-numbers" title="Key numbers"
            action={<Link to={`/risk/${ticker}`} className="text-xs font-medium text-primary hover:underline">Full risk breakdown</Link>}>
            <dl className="divide-y divide-border">
                {rows.map(([label, value, help]) => (
                    <div key={label} className="px-4 py-2.5 flex items-start justify-between gap-4">
                        <div className="min-w-0">
                            <dt className="text-sm text-foreground">{label}</dt>
                            <dd className="text-xs text-muted-foreground">{help}</dd>
                        </div>
                        <dd className="text-sm font-mono tabular-nums font-medium text-foreground whitespace-nowrap">{value}</dd>
                    </div>
                ))}
            </dl>
        </Panel>
    )
}
