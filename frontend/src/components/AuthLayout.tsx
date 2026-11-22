import type { InputHTMLAttributes, ReactNode } from "react"
import { ShieldCheck } from "lucide-react"

/** The shell for sign in, register and password reset: the app's name, one card, theme colours. */
export default function AuthLayout({ title, description, children }: { title: string; description: ReactNode; children: ReactNode }) {
    return (
        <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center gap-6 p-4">
            <div className="flex items-center gap-2 text-lg font-semibold">
                <ShieldCheck className="size-6 text-primary" aria-hidden="true" /> Quantara
            </div>
            <main className="w-full max-w-sm rounded-lg border border-border bg-card">
                <div className="p-6 pb-4 space-y-1">
                    <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
                    <p className="text-sm text-muted-foreground">{description}</p>
                </div>
                <div className="px-6 pb-6">{children}</div>
            </main>
            <p className="text-xs text-muted-foreground">Research to help you decide, not financial advice.</p>
        </div>
    )
}

/** A labelled input for the auth forms. */
export function AuthField({ id, label, aside, hint, ...input }: InputHTMLAttributes<HTMLInputElement> & { id: string; label: string; aside?: ReactNode; hint?: ReactNode }) {
    return (
        <div className="space-y-1.5">
            <div className="flex items-baseline justify-between">
                <label htmlFor={id} className="text-sm font-medium">{label}</label>
                {aside}
            </div>
            <input id={id} {...input}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary placeholder:text-muted-foreground/60" />
            {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
        </div>
    )
}

export function AuthError({ children }: { children: ReactNode }) {
    return <p role="alert" className="rounded-md border border-q-risk-high/30 bg-q-risk-high/10 px-3 py-2 text-sm text-q-risk-high">{children}</p>
}
