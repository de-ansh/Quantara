import { useState } from "react"
import PageHeader from "@/components/PageHeader"
import Panel from "@/components/Panel"
import { CALCULATORS, calculate } from "@/lib/calculators"
import { chipClass, cn } from "@/lib/utils"

export default function Calculators() {
    const [activeId, setActiveId] = useState(CALCULATORS[0].id)
    const [drafts, setDrafts] = useState<Record<string, string>>({})
    const calc = CALCULATORS.find(c => c.id === activeId) ?? CALCULATORS[0]

    const text = (key: string, initial: number) => drafts[`${calc.id}.${key}`] ?? String(initial)
    const values = Object.fromEntries(calc.fields.map(f => [f.key, text(f.key, f.initial).trim() === "" ? NaN : Number(text(f.key, f.initial))]))
    const results = calculate(calc, values)

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto">
            <PageHeader title="Calculators" description="SIP, lump sum, retirement and tax. Projections assume a constant rate; actual returns will vary. Tax results are estimates, not tax advice." />
            <div className="flex flex-wrap gap-1.5" role="group" aria-label="Calculator">
                {CALCULATORS.map(c => (
                    <button
                        key={c.id}
                        type="button"
                        aria-pressed={c.id === calc.id}
                        onClick={() => setActiveId(c.id)}
                        className={chipClass(c.id === calc.id)}
                    >
                        {c.name}
                    </button>
                ))}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl">
                <Panel id="calc-inputs" title={calc.name}>
                    <div className="p-4 space-y-4">
                        {calc.fields.map(f => (
                            <label key={f.key} className="flex flex-col gap-1 text-sm font-medium text-foreground">
                                {f.label}
                                <input
                                    type="number"
                                    inputMode="decimal"
                                    min={0}
                                    step="any"
                                    value={text(f.key, f.initial)}
                                    onChange={e => setDrafts(d => ({ ...d, [`${calc.id}.${f.key}`]: e.target.value }))}
                                    className="h-9 px-3 bg-background border border-border rounded-md text-sm font-normal text-foreground font-mono tabular-nums outline-none focus:border-primary"
                                />
                            </label>
                        ))}
                    </div>
                </Panel>
                <Panel id="calc-result" title="Result">
                    <div className="p-4 space-y-4" aria-live="polite">
                        {results ? results.map((r, i) => (
                            <div key={r.label}>
                                <p className="text-sm text-muted-foreground">{r.label}</p>
                                <p className={cn("font-mono tabular-nums font-semibold text-foreground", i === 0 ? "text-3xl" : "text-lg")}>{r.value}</p>
                            </div>
                        )) : <p className="text-sm text-muted-foreground">Enter valid values to see the result.</p>}
                        {calc.note && <p className="text-xs text-muted-foreground border-t border-border pt-3">{calc.note}</p>}
                    </div>
                </Panel>
            </div>
        </div>
    )
}
