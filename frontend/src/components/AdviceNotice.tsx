import { Info } from "lucide-react"
import { cn } from "@/lib/utils"

/** Shown wherever the app ranks or analyses securities. */
export default function AdviceNotice({ className }: { className?: string }) {
    return (
        <p role="note" className={cn("flex items-start gap-1.5 text-[10px] leading-snug text-muted-foreground", className)}>
            <Info className="size-3 shrink-0 mt-px" aria-hidden="true" />
            <span>
                For research and information only, not investment advice. Scores and projections are model
                estimates from data that may be delayed or incomplete. Past performance does not predict future returns.
            </span>
        </p>
    )
}
