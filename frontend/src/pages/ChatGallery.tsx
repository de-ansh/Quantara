import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Trash2 } from "lucide-react"
import apiClient from "@/lib/api"
import { cleanTickerDisplay } from "@/lib/currency"
import PageHeader from "@/components/PageHeader"
import Panel, { PanelMessage, PanelSkeleton } from "@/components/Panel"

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
            <Link to={`/shared/${c.token}`} className="block h-full rounded-md border border-border bg-background p-4 pr-10 hover:border-primary/50">
                <p className="text-sm font-semibold text-foreground line-clamp-3">{c.question}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                    {c.mine && <span className="font-medium text-foreground">{c.listed ? "Shared" : "Private"} · </span>}
                    {c.tickers.length > 0 && <span>{c.tickers.map(cleanTickerDisplay).join(" · ")} · </span>}
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
        <div className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto">
            <PageHeader title="Chats" description="Every chat with the assistant is saved here. Yours are private; share one from the assistant to let other signed-in users read it. AI-generated, not financial advice." />
            {isLoading && <Panel id="my-chats-loading" title="Your chats"><PanelSkeleton rows={3} /></Panel>}
            {isError && <Panel id="my-chats-error" title="Your chats"><PanelMessage alert>Couldn't load your chats.</PanelMessage></Panel>}
            {remove.isError && <p role="alert" className="text-sm text-q-risk-high">Couldn't delete that chat. Please try again.</p>}
            {data && (
                <>
                    <Panel id="my-chats" title="Your chats">
                        {mine.length === 0 ? (
                            <PanelMessage>No chats yet. Ask Quantara something and it will appear here.</PanelMessage>
                        ) : (
                            <ul className="p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                                {mine.map(c => <ChatCard key={c.token} c={c} onDelete={() => remove.mutate(c.token)} />)}
                            </ul>
                        )}
                    </Panel>
                    {others.length > 0 && (
                        <Panel id="shared-chats" title="Shared by other users">
                            <ul className="p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                                {others.map(c => <ChatCard key={c.token} c={c} />)}
                            </ul>
                        </Panel>
                    )}
                </>
            )}
        </div>
    )
}
