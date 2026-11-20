import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

/** A titled section: the one card style pages use, so sections look and read alike. */
export default function Panel({ id, title, description, action, children, className }: {
    id: string // heading id, for aria-labelledby
    title: string
    description?: ReactNode
    action?: ReactNode
    children: ReactNode
    className?: string
}) {
    return (
        <section aria-labelledby={id} className={cn("rounded-lg border border-border bg-card", className)}>
            <div className="flex flex-wrap items-start justify-between gap-2 px-4 pt-3 pb-2 border-b border-border">
                <div className="min-w-0">
                    <h2 id={id} className="text-sm font-semibold text-foreground">{title}</h2>
                    {description && <p className="text-xs text-muted-foreground mt-0.5">{description}</p>}
                </div>
                {action}
            </div>
            {children}
        </section>
    )
}

/** Loading rows that keep the section's shape. */
export function PanelSkeleton({ rows = 3 }: { rows?: number }) {
    return (
        <div className="p-4 space-y-2" aria-busy="true" aria-label="Loading">
            {Array.from({ length: rows }).map((_, i) => <div key={i} className="h-8 rounded bg-muted animate-pulse" />)}
        </div>
    )
}

/** A short message in place of content: empty, or failed. */
export function PanelMessage({ children, alert = false }: { children: ReactNode; alert?: boolean }) {
    return <p role={alert ? "alert" : undefined} className={cn("px-4 py-4 text-sm", alert ? "text-q-risk-high" : "text-muted-foreground")}>{children}</p>
}
