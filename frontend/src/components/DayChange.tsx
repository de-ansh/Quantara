import { cn } from "@/lib/utils"

/** Day change badge, e.g. "+1.24%"; renders nothing when unknown. */
export default function DayChange({ pct, className }: { pct: number | null | undefined; className?: string }) {
    if (pct === null || pct === undefined) return null
    return (
        <span className={cn("font-mono font-bold", pct > 0 ? "text-q-risk-low" : pct < 0 ? "text-q-risk-high" : "text-muted-foreground", className)}>
            {pct > 0 ? "+" : ""}{pct.toFixed(2)}%
        </span>
    )
}
