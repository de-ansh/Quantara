import { useState } from "react"
import { FileText, Loader2 } from "lucide-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import api, { apiErrorDetail } from "@/lib/api"
import { useRefreshResearch } from "@/hooks/useResearch"
import { timeAgo } from "@/lib/utils"

interface Filing {
    url: string | null
    updated_at: string | null
    chars: number
}

/** Link an earnings filing PDF (NSE/BSE announcement or company IR page) as research context. */
export default function FilingCard({ ticker }: { ticker: string }) {
    const queryClient = useQueryClient()
    const refreshReport = useRefreshResearch(ticker)
    const [url, setUrl] = useState("")
    const key = ["filing", ticker]

    const { data: filing } = useQuery({
        queryKey: key,
        queryFn: async () => (await api.get<Filing>(`/stocks/${ticker}/filing`)).data,
        enabled: !!ticker,
    })

    const onChanged = (data: Filing) => {
        queryClient.setQueryData(key, data)
        setUrl("")
        refreshReport.mutate()
    }
    const save = useMutation({
        mutationFn: async () => (await api.put<Filing>(`/stocks/${ticker}/filing`, { url })).data,
        onSuccess: onChanged,
    })
    const clear = useMutation({
        mutationFn: async () => {
            await api.delete(`/stocks/${ticker}/filing`)
            return { url: null, updated_at: null, chars: 0 }
        },
        onSuccess: onChanged,
    })

    return (
        <div className="bg-card border border-border shadow-lg">
            <div className="flex items-center gap-2 border-b border-border bg-muted/40 px-4 py-3">
                <FileText className="text-primary size-4" />
                <h3 className="text-xs font-bold uppercase tracking-widest text-foreground">Earnings Filing</h3>
            </div>
            <div className="p-4 space-y-3 text-xs">
                <p className="text-muted-foreground">
                    Research uses this filing as context. New NSE/BSE earnings-call transcripts are linked
                    automatically; paste a PDF link (transcript or results) to add or replace one yourself.
                </p>
                {filing?.url && (
                    <div className="space-y-1">
                        <a href={filing.url} target="_blank" rel="noreferrer" className="block truncate text-primary hover:underline">
                            {filing.url}
                        </a>
                        <div className="flex items-center justify-between text-muted-foreground">
                            <span>{filing.updated_at && `Added ${timeAgo(filing.updated_at)}`}</span>
                            <button
                                type="button"
                                onClick={() => clear.mutate()}
                                disabled={clear.isPending}
                                className="font-bold text-red-400 hover:underline disabled:opacity-50"
                            >
                                Remove
                            </button>
                        </div>
                    </div>
                )}
                <form
                    onSubmit={(e) => {
                        e.preventDefault()
                        save.mutate()
                    }}
                    className="flex gap-2"
                >
                    <label htmlFor="filing-url" className="sr-only">Filing PDF URL</label>
                    <input
                        id="filing-url"
                        type="url"
                        required
                        placeholder="https://…/transcript.pdf"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        className="min-w-0 flex-1 bg-background border border-border px-3 py-2 rounded-sm text-foreground focus:border-primary outline-none"
                    />
                    <Button type="submit" size="sm" disabled={save.isPending} className="gap-2">
                        {save.isPending && <Loader2 className="size-4 animate-spin" />} {filing?.url ? "Replace" : "Add"}
                    </Button>
                </form>
                <p role="status" className="text-muted-foreground">
                    {save.isError && <span className="text-red-400">{apiErrorDetail(save.error) ?? "Could not add that filing"}</span>}
                    {refreshReport.isPending && "Regenerating research with the filing…"}
                </p>
            </div>
        </div>
    )
}
