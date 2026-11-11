import { useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import apiClient from "@/lib/api"
import { Formatted } from "@/components/ChatAssistant"
import { cn } from "@/lib/utils"

interface Shared { messages: { role: "user" | "assistant"; content: string }[]; created_at: string }

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
                <h1 className="text-xl font-bold text-foreground">Shared research chat</h1>
                <p className="text-xs text-muted-foreground">AI-generated research shared by a Quantara user. Not financial advice.</p>
                {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
                {isError && <p role="alert" className="text-sm text-muted-foreground">This shared chat doesn't exist or was removed.</p>}
                {data?.messages.map((m, i) => (
                    <div key={i} className={cn("rounded-lg border border-border p-3 text-sm text-foreground", m.role === "user" ? "bg-primary/10" : "bg-card")}>
                        <p className="mb-1 text-[11px] text-muted-foreground">{m.role === "user" ? "Question" : "Quantara"}</p>
                        <Formatted text={m.content} />
                    </div>
                ))}
            </div>
        </div>
    )
}
