import type { ReactNode } from "react"

/** Every page opens the same way: one title, one line on what it's for, and its main actions. */
export default function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
    return (
        <header className="flex flex-wrap items-end justify-between gap-3">
            <div className="min-w-0 space-y-1">
                <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
                {description && <p className="text-sm text-muted-foreground max-w-3xl">{description}</p>}
            </div>
            {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
    )
}
