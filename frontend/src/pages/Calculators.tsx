import { useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { CALCULATORS, calculate } from "@/lib/calculators"
import { cn } from "@/lib/utils"

export default function Calculators() {
    const [activeId, setActiveId] = useState(CALCULATORS[0].id)
    const [drafts, setDrafts] = useState<Record<string, string>>({})
    const calc = CALCULATORS.find(c => c.id === activeId) ?? CALCULATORS[0]

    const text = (key: string, initial: number) => drafts[`${calc.id}.${key}`] ?? String(initial)
    const values = Object.fromEntries(calc.fields.map(f => [f.key, text(f.key, f.initial).trim() === "" ? NaN : Number(text(f.key, f.initial))]))
    const results = calculate(calc, values)

    return (
        <div className="flex flex-col flex-1 p-6 bg-background space-y-6 overflow-y-auto custom-scrollbar">
            <header>
                <h1 className="text-2xl font-bold text-foreground">Calculators</h1>
                <p className="text-sm text-muted-foreground">Projections assume a constant rate; actual returns will vary. Tax results are estimates, not tax advice.</p>
            </header>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Calculator">
                {CALCULATORS.map(c => (
                    <button
                        key={c.id}
                        type="button"
                        aria-pressed={c.id === calc.id}
                        onClick={() => setActiveId(c.id)}
                        className={cn("px-3 py-1.5 text-sm rounded-sm border transition-colors", c.id === calc.id ? "bg-primary border-primary text-primary-foreground" : "border-border text-muted-foreground hover:bg-muted hover:text-foreground")}
                    >
                        {c.name}
                    </button>
                ))}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl">
                <Card className="bg-q-surface border-q-border shadow-none">
                    <CardContent className="p-5 space-y-4">
                        {calc.fields.map(f => (
                            <label key={f.key} className="flex flex-col gap-1 text-sm text-muted-foreground">
                                {f.label}
                                <input
                                    type="number"
                                    inputMode="decimal"
                                    min={0}
                                    step="any"
                                    value={text(f.key, f.initial)}
                                    onChange={e => setDrafts(d => ({ ...d, [`${calc.id}.${f.key}`]: e.target.value }))}
                                    className="h-9 px-3 bg-background border border-border rounded-sm text-sm text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                                />
                            </label>
                        ))}
                    </CardContent>
                </Card>
                <Card className="bg-q-surface border-q-border shadow-none">
                    <CardContent className="p-5 space-y-4" aria-live="polite">
                        {results ? results.map((r, i) => (
                            <div key={r.label}>
                                <p className="text-sm text-muted-foreground">{r.label}</p>
                                <p className={cn("font-mono font-bold text-foreground", i === 0 ? "text-3xl" : "text-lg")}>{r.value}</p>
                            </div>
                        )) : <p className="text-sm text-muted-foreground">Enter valid values to see the result.</p>}
                        {calc.note && <p className="text-xs text-muted-foreground border-t border-border pt-3">{calc.note}</p>}
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
