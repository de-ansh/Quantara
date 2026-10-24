import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { BellPlus, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { getCurrencySymbol } from "@/lib/currency"
import { timeAgo } from "@/lib/utils"
import api, { apiErrorDetail } from "@/lib/api"

interface PriceAlert {
    id: number
    ticker: string
    direction: "above" | "below"
    target_price: number
    triggered_at: string | null
    triggered_price: number | null
}

export default function PriceAlertForm({ ticker }: { ticker: string }) {
    const queryClient = useQueryClient()
    const key = ["priceAlerts", ticker]
    const [direction, setDirection] = useState<"above" | "below">("below")
    const [target, setTarget] = useState("")
    const sym = getCurrencySymbol(ticker)

    const { data: alerts = [] } = useQuery({
        queryKey: key,
        queryFn: async () => (await api.get<PriceAlert[]>("/alerts/price/", { params: { ticker } })).data,
        enabled: !!ticker,
    })
    const create = useMutation({
        mutationFn: async () =>
            (await api.post<PriceAlert>("/alerts/price/", { ticker, direction, target_price: Number(target) })).data,
        onSuccess: () => {
            setTarget("")
            queryClient.invalidateQueries({ queryKey: key })
        },
    })
    const remove = useMutation({
        mutationFn: async (id: number) => api.delete(`/alerts/price/${id}`),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
    })

    return (
        <div className="space-y-2">
            <form
                onSubmit={(e) => { e.preventDefault(); if (Number(target) > 0) create.mutate() }}
                className="flex flex-wrap items-center gap-2 text-xs"
            >
                <BellPlus className="size-4 text-primary" aria-hidden="true" />
                <span className="text-muted-foreground">Alert me when price goes</span>
                <select value={direction} onChange={e => setDirection(e.target.value as "above" | "below")} aria-label="Direction"
                    className="bg-background border border-border rounded-sm px-2 py-1 text-foreground">
                    <option value="below">below</option>
                    <option value="above">above</option>
                </select>
                <span className="relative">
                    <span className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground">{sym}</span>
                    <input type="number" min={0} step="any" required value={target} onChange={e => setTarget(e.target.value)}
                        aria-label="Target price" placeholder="0.00"
                        className="w-28 bg-background border border-border rounded-sm pl-5 pr-2 py-1 font-mono text-foreground outline-none focus:border-primary" />
                </span>
                <Button type="submit" size="sm" className="h-7" disabled={create.isPending}>Set alert</Button>
                {create.isError && <span role="alert" className="text-red-400">{apiErrorDetail(create.error) ?? "Could not set alert"}</span>}
            </form>
            {alerts.length > 0 && (
                <ul className="flex flex-wrap gap-2 text-[11px]">
                    {alerts.map(a => (
                        <li key={a.id} className="flex items-center gap-1 border border-border rounded-sm px-2 py-0.5 font-mono">
                            <span className={a.triggered_at ? "text-muted-foreground line-through" : "text-foreground"}>
                                {a.direction} {sym}{a.target_price.toLocaleString()}
                            </span>
                            {a.triggered_at && (
                                <span className="text-amber-400 no-underline">
                                    hit {sym}{a.triggered_price?.toLocaleString()} {timeAgo(a.triggered_at)}
                                </span>
                            )}
                            <button type="button" onClick={() => remove.mutate(a.id)} aria-label={`Delete alert ${a.direction} ${a.target_price}`}
                                className="text-muted-foreground hover:text-foreground">
                                <X className="size-3" />
                            </button>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    )
}
