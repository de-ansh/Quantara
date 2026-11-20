import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Trash2 } from "lucide-react"
import apiClient from "@/lib/api"
import { cleanTickerDisplay } from "@/lib/currency"

interface GalleryItem {
    token: string
    mine: boolean
    listed: boolean
    question: string
    tickers: string[]
    messages: number
    created_at: string
}

function ChatCard({ c, onDelete }: { c: GalleryItem; onDelete?: () => void }) {
    return (
        <li className="relative">
            <Link to={`/shared/${c.token}`} className="block h-full rounded-lg border border-q-border bg-q-surface p-4 pr-10 hover:border-primary/50">
                <p className="text-sm font-semibold text-foreground line-clamp-3">{c.question}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                    {c.mine && <span className="font-bold">{c.listed ? "Shared" : "Private"} · </span>}
                    {c.tickers.length > 0 && <span className="font-mono">{c.tickers.map(cleanTickerDisplay).join(" · ")} · </span>}
                    {c.messages} messages · {new Date(c.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                </p>
            </Link>
            {onDelete && (
                <button type="button" onClick={onDelete} aria-label={`Delete chat: ${c.question}`}
                    className="absolute top-3 right-3 p-1 text-muted-foreground hover:text-q-risk-high">
                    <Trash2 className="size-4" />
                </button>
            )}
        </li>
    )
}

/** Every chat the viewer has had (saved automatically, private unless shared), then chats other users shared. */
export default function ChatGallery() {
    const queryClient = useQueryClient()
    const { data, isLoading, isError } = useQuery({
        queryKey: ["chatGallery"],
        queryFn: async () => (await apiClient.get<GalleryItem[]>("/chat/gallery")).data,
        refetchInterval: 5 * 60_000,
    })
    const remove = useMutation({
        mutationFn: async (token: string) => { await apiClient.delete(`/chat/shared/${token}`) },
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chatGallery"] }),
    })
    const mine = data?.filter(c => c.mine) ?? []
    const others = data?.filter(c => !c.mine) ?? []

    return (
        <div className="flex flex-col flex-1 p-6 bg-background space-y-6 overflow-y-auto custom-scrollbar">
            <header>
                <h1 className="text-2xl font-bold text-foreground">Chat gallery</h1>
                <p className="text-sm text-muted-foreground">
                    Every chat with the assistant is saved here. Yours are private; share one from the assistant to let other
                    signed-in Quantara users read it. Nothing here is visible without signing in. AI-generated, not financial advice.
                </p>
            </header>
            {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
            {isError && <p role="alert" className="text-sm text-muted-foreground">Couldn't load the gallery.</p>}
            {remove.isError && <p role="alert" className="text-sm text-q-risk-high">Couldn't delete that chat. Please try again.</p>}
            {data && (
                <>
                    <section aria-labelledby="my-chats" className="space-y-3">
                        <h2 id="my-chats" className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Your chats</h2>
                        {mine.length === 0 ? (
                            <p className="text-sm text-muted-foreground">No chats yet. Ask Quantara something and it will appear here.</p>
                        ) : (
                            <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {mine.map(c => <ChatCard key={c.token} c={c} onDelete={() => remove.mutate(c.token)} />)}
                            </ul>
                        )}
                    </section>
                    {others.length > 0 && (
                        <section aria-labelledby="shared-chats" className="space-y-3">
                            <h2 id="shared-chats" className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Shared by other users</h2>
                            <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {others.map(c => <ChatCard key={c.token} c={c} />)}
                            </ul>
                        </section>
                    )}
                </>
            )}
        </div>
    )
}
