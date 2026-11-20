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

/** Link an earnings filing (PDF, call recording, or a company page listing them) as research context. */
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
        <section aria-labelledby="filing-heading" className="rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 border-b border-border px-4 pt-3 pb-2">
                <FileText className="text-muted-foreground size-4" aria-hidden="true" />
                <h2 id="filing-heading" className="text-sm font-semibold text-foreground">Earnings-call transcript</h2>
            </div>
            <div className="p-4 space-y-3 text-sm">
                <p className="text-muted-foreground">
                    The research reads the latest transcript. New NSE/BSE transcripts are added automatically; you can also paste a
                    PDF, an MP3 recording (transcribed in about a minute) or the company's transcript page.
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
                    <label htmlFor="filing-url" className="sr-only">Filing, recording or transcript page URL</label>
                    <input
                        id="filing-url"
                        type="url"
                        required
                        placeholder="https://…/transcript.pdf or .mp3"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        className="min-w-0 flex-1 bg-background border border-border px-3 py-2 rounded-md text-foreground focus:border-primary outline-none"
                    />
                    <Button type="submit" size="sm" disabled={save.isPending} className="gap-2">
                        {save.isPending && <Loader2 className="size-4 animate-spin" />} {filing?.url ? "Replace" : "Add"}
                    </Button>
                </form>
                <p role="status" className="text-muted-foreground">
                    {save.isError && <span className="text-red-400">{apiErrorDetail(save.error) ?? "Could not add that filing"}</span>}
                    {save.isPending && "Reading the filing (transcribing if it is a recording)…"}
                    {refreshReport.isPending && "Regenerating research with the filing…"}
                </p>
            </div>
        </section>
    )
}
