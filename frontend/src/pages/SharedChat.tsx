import { useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import apiClient from "@/lib/api"
import { Formatted } from "@/components/ChatAssistant"
import { cn } from "@/lib/utils"

interface Shared { messages: { role: "user" | "assistant"; content: string; tickers?: string[] }[]; created_at: string }

export default function SharedChat() {
    const { token = "" } = useParams()
    const { data, isLoading, isError } = useQuery({
        queryKey: ["sharedChat", token],
        queryFn: async () => (await apiClient.get<Shared>(`/chat/shared/${encodeURIComponent(token)}`)).data,
        retry: false,
    })
    return (
        <div className="flex-1 overflow-y-auto bg-background p-6">
            <div className="mx-auto max-w-2xl space-y-3">
                <h1 className="text-xl font-bold text-foreground">Research chat</h1>
                <p className="text-xs text-muted-foreground">AI-generated research. Not financial advice.</p>
                {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
                {isError && <p role="alert" className="text-sm text-muted-foreground">This chat doesn't exist, was removed, or isn't shared with you.</p>}
                {data?.messages.map((m, i) => (
                    <div key={i} className={cn("rounded-lg border border-border p-3 text-sm text-foreground", m.role === "user" ? "bg-primary/10" : "bg-card")}>
                        <p className="mb-1 text-[11px] text-muted-foreground">{m.role === "user" ? "Question" : "Quantara"}</p>
                        <Formatted text={m.content} />
                        {/* Named, not charted: a saved chat is a record, the stock pages have the live charts */}
                        {m.tickers && m.tickers.length > 0 && <p className="mt-2 text-[11px] text-muted-foreground">Looked up: {m.tickers.join(", ")}</p>}
                    </div>
                ))}
            </div>
        </div>
    )
}
