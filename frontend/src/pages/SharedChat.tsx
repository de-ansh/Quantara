import { Link, useParams } from "react-router-dom"
import { ArrowLeft } from "lucide-react"
import PageHeader from "@/components/PageHeader"
import { PanelSkeleton } from "@/components/Panel"
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
        <div className="p-4 md:p-6">
            <div className="mx-auto max-w-2xl space-y-4">
                <Link to="/gallery" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" /> All chats</Link>
                <PageHeader title="Research chat"
                    description={data ? `AI-generated research from ${new Date(data.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}. Not financial advice.` : "AI-generated research. Not financial advice."} />
                {isLoading && <PanelSkeleton rows={4} />}
                {isError && <p role="alert" className="text-sm text-muted-foreground">This chat doesn't exist, was removed, or isn't shared with you.</p>}
                {data?.messages.map((m, i) => (
                    <div key={i} className={cn("rounded-lg border border-border p-3 text-sm text-foreground", m.role === "user" ? "bg-primary/10" : "bg-card")}>
                        <p className="mb-1 text-xs font-medium text-muted-foreground">{m.role === "user" ? "Question" : "Quantara"}</p>
                        <Formatted text={m.content} />
                        {/* Named, not charted: a saved chat is a record, the stock pages have the live charts */}
                        {m.tickers && m.tickers.length > 0 && <p className="mt-2 text-xs text-muted-foreground">Looked up: {m.tickers.join(", ")}</p>}
                    </div>
                ))}
            </div>
        </div>
    )
}
