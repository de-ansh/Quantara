import { useState, type FormEvent } from "react"
import { Link } from "react-router-dom"
import { AlertTriangle, CheckCircle2 } from "lucide-react"
import AdviceNotice from "@/components/AdviceNotice"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"
import { Button } from "@/components/ui/button"
import { usePortfolioBalance, useSaveTargetMix, type PortfolioBalance, type TargetMix } from "@/hooks/usePortfolios"
import { apiErrorDetail } from "@/lib/api"
import { money } from "@/lib/money"

const CLASSES = ["equity", "debt", "cash", "gold"] as const
const BAR = { equity: "bg-primary", debt: "bg-sky-500", cash: "bg-emerald-500", gold: "bg-amber-500" }
const WHERE = { equity: "stocks or an equity fund", debt: "a debt fund or bond ETF", cash: "a liquid fund or liquid ETF", gold: "a gold ETF or gold fund" }
const INPUT = "w-16 bg-background border border-border rounded-sm px-2 py-1 font-mono text-right text-foreground outline-none focus:border-primary"

/** Your mix against your target, what looks lopsided, and what to sell and add to get back on target. */
export default function BalanceCheck({ id }: { id: number }) {
    const [newMoney, setNewMoney] = useState(0)
    const [draft, setDraft] = useState("")
    const [editing, setEditing] = useState(false)
    const { data, isLoading, isError } = usePortfolioBalance(id, newMoney)
    const ok = data?.flags && data.mix && data.target && data.plan
    return (
        <Panel id="balance" title="Balance check"
            description="Your mix against your target, single companies and sectors over your limits, Avoid ratings, and stocks you also hold elsewhere."
            action={ok && !editing ? <Button variant="outline" size="sm" className="h-7" onClick={() => setEditing(true)}>Change target</Button> : undefined}>
            {isLoading ? <PanelSkeleton rows={2} />
                : isError || !ok ? <PanelMessage alert>Couldn't check this portfolio's balance.</PanelMessage>
                : (
                    <div className="p-4 space-y-5">
                        {editing ? <TargetForm target={data.target} onDone={() => setEditing(false)} /> : <Mix data={data} />}
                        <Flags data={data} />
                        <div className="space-y-3 pt-4 border-t border-border">
                            <div className="flex flex-wrap items-baseline justify-between gap-2">
                                <h3 className="text-sm font-semibold text-foreground">Rebalancing plan</h3>
                                <form className="flex items-center gap-2 text-sm text-muted-foreground"
                                    onSubmit={e => { e.preventDefault(); setNewMoney(Math.max(0, Number(draft) || 0)) }}>
                                    <label htmlFor="new-money">Adding new money?</label>
                                    <span className="relative">
                                        <span className="absolute left-2 top-1/2 -translate-y-1/2" aria-hidden="true">₹</span>
                                        <input id="new-money" type="number" min={0} step="any" value={draft} placeholder="0"
                                            onChange={e => setDraft(e.target.value)} className={`${INPUT} w-28 pl-5`} />
                                    </span>
                                    <Button type="submit" size="sm" variant="outline" className="h-7">Update plan</Button>
                                </form>
                            </div>
                            <Plan data={data} newMoney={newMoney} />
                        </div>
                        <AdviceNotice />
                    </div>
                )}
        </Panel>
    )
}

function Mix({ data }: { data: PortfolioBalance }) {
    const t = data.target
    return (
        <div className="space-y-3">
            {Object.entries(data.mix).map(([currency, mix]) => (
                <div key={currency} className="space-y-1.5">
                    {Object.keys(data.mix).length > 1 && <p className="text-xs text-muted-foreground">{currency}</p>}
                    <div className="flex h-2 rounded-full overflow-hidden bg-muted" aria-hidden="true">
                        {CLASSES.filter(c => mix[c]).map(c => <div key={c} className={BAR[c]} style={{ width: `${mix[c]}%` }} />)}
                    </div>
                    <dl className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
                        {CLASSES.map(c => (
                            <div key={c}>
                                <dt className="flex items-center gap-1.5 text-xs text-muted-foreground capitalize">
                                    <span className={`size-2 rounded-full ${BAR[c]}`} aria-hidden="true" />{c}
                                </dt>
                                <dd className="font-mono tabular-nums">{Math.round(mix[c] ?? 0)}% <span className="text-xs text-muted-foreground">target {t[c]}%</span></dd>
                            </div>
                        ))}
                    </dl>
                </div>
            ))}
            <p className="text-xs text-muted-foreground">
                {t.is_default
                    ? <>Target is the starting point for a {data.risk_level ?? "Moderate"} investor; change it to your own. </>
                    : "Your saved target, used for every portfolio. "}
                Limits: one company {t.max_stock}%, one sector {t.max_sector}%.
                {!data.risk_level && <> Set your risk profile on the <Link to="/account" className="underline">Account</Link> page to also check Avoid ratings.</>}
            </p>
        </div>
    )
}

function Flags({ data }: { data: PortfolioBalance }) {
    if (data.flags.length === 0) return (
        <p className="flex items-center gap-2 text-sm text-q-risk-low">
            <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" /> Nothing stands out: this portfolio is on target.
        </p>
    )
    return (
        <ul className="space-y-3">
            {data.flags.map((f, i) => (
                <li key={i} className="flex gap-2 text-sm">
                    <AlertTriangle className="size-4 shrink-0 mt-0.5 text-amber-500" aria-hidden="true" />
                    <div className="min-w-0">
                        <p className="font-medium text-foreground">
                            {f.ticker ? <Link to={`/research/${f.ticker}`} className="hover:underline">{f.title}</Link> : f.title}
                        </p>
                        <p className="text-muted-foreground">
                            {f.detail}
                            {f.amount ? <> <span className="font-mono tabular-nums text-foreground whitespace-nowrap">About {money(f.amount, f.currency)}</span>.</> : null}
                        </p>
                    </div>
                </li>
            ))}
        </ul>
    )
}

function Plan({ data, newMoney }: { data: PortfolioBalance; newMoney: number }) {
    const sells = data.plan.filter(t => t.action === "sell")
    const adds = data.plan.filter(t => t.action === "add")
    if (!data.plan.length) return (
        <p className="text-sm text-muted-foreground">
            Nothing to move: every part of the mix is within 5 points of your target. Enter new money above to see where it should go.
        </p>
    )
    const gain = sells.reduce((s, t) => s + (t.gain ?? 0), 0)
    return (
        <div className="space-y-3 text-sm">
            {sells.length > 0 && (
                <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">Sell</p>
                    <ul className="divide-y divide-border">
                        {sells.map(t => (
                            <li key={t.ticker} className="flex flex-wrap justify-between gap-x-4 py-1.5">
                                <span className="min-w-0">
                                    <Link to={`/research/${t.ticker}`} className="font-medium text-foreground hover:underline">{t.name}</Link>
                                    <span className="text-muted-foreground"> · {t.reason}</span>
                                </span>
                                <span className="font-mono tabular-nums whitespace-nowrap">
                                    {money(t.amount, t.currency)}
                                    {t.gain !== null && <span className="text-xs text-muted-foreground"> ({t.gain < 0 ? "loss" : "gain"} {money(Math.abs(t.gain), t.currency)})</span>}
                                </span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
            <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">
                    Add{newMoney > 0 ? ` (your ${money(newMoney, "INR")}${sells.length ? " plus what you sell" : ""})` : ""}
                </p>
                <ul className="divide-y divide-border">
                    {adds.map(t => (
                        <li key={t.asset_class} className="flex flex-wrap justify-between gap-x-4 py-1.5">
                            <span><span className="font-medium text-foreground capitalize">{t.asset_class}</span>
                                <span className="text-muted-foreground"> · {WHERE[t.asset_class as keyof typeof WHERE] ?? ""}</span></span>
                            <span className="font-mono tabular-nums whitespace-nowrap">{money(t.amount, t.currency)}</span>
                        </li>
                    ))}
                </ul>
            </div>
            {sells.length > 0 && (
                <p className="text-xs text-muted-foreground">
                    Selling realises about {money(Math.abs(gain), "INR")} of {gain < 0 ? "losses" : "gains"} before tax. Short-term gains (held under a year)
                    are taxed at 20%; long-term gains above ₹1.25 lakh a year at 12.5%. The app doesn't know your buy dates, so check them before selling.
                </p>
            )}
        </div>
    )
}

function TargetForm({ target, onDone }: { target: TargetMix; onDone: () => void }) {
    const [form, setForm] = useState<TargetMix>(target)
    const save = useSaveTargetMix()
    const sum = CLASSES.reduce((s, c) => s + (Number(form[c]) || 0), 0)
    const set = (key: keyof TargetMix) => (e: React.ChangeEvent<HTMLInputElement>) => setForm(f => ({ ...f, [key]: e.target.value === "" ? 0 : Number(e.target.value) }))
    const submit = (e: FormEvent) => {
        e.preventDefault()
        save.mutate({ ...form, is_default: undefined }, { onSuccess: onDone })
    }
    return (
        <form onSubmit={submit} className="space-y-3" aria-label="Target mix">
            <p className="text-sm text-foreground">Your target, used for every portfolio</p>
            <div className="flex flex-wrap gap-4 text-sm">
                {CLASSES.map(c => (
                    <label key={c} className="flex items-center gap-1.5 capitalize">
                        {c}<input type="number" min={0} max={100} step="any" value={form[c]} onChange={set(c)} className={INPUT} />%
                    </label>
                ))}
                <span className={sum === 100 ? "text-muted-foreground" : "text-q-risk-high"} aria-live="polite">Total {sum}%</span>
            </div>
            <div className="flex flex-wrap gap-4 text-sm">
                <label className="flex items-center gap-1.5">Max in one company<input type="number" min={5} max={100} step="any" value={form.max_stock} onChange={set("max_stock")} className={INPUT} />%</label>
                <label className="flex items-center gap-1.5">Max in one sector<input type="number" min={10} max={100} step="any" value={form.max_sector} onChange={set("max_sector")} className={INPUT} />%</label>
            </div>
            {save.isError && <p role="alert" className="text-sm text-q-risk-high">{apiErrorDetail(save.error) ?? "Couldn't save the target."}</p>}
            <div className="flex flex-wrap gap-2">
                <Button type="submit" size="sm" disabled={sum !== 100 || save.isPending}>Save target</Button>
                <Button type="button" size="sm" variant="outline" onClick={onDone}>Cancel</Button>
                {!target.is_default && (
                    <Button type="button" size="sm" variant="ghost" disabled={save.isPending} onClick={() => save.mutate(null, { onSuccess: onDone })}>
                        Reset to risk profile default
                    </Button>
                )}
            </div>
        </form>
    )
}
