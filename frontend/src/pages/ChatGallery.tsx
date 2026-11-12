import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import apiClient from "@/lib/api"
import { cleanTickerDisplay } from "@/lib/currency"

interface GalleryItem { token: string; question: string; tickers: string[]; messages: number; created_at: string }

/** Research chats other users chose to list when sharing, newest first. No author is shown. */
export default function ChatGallery() {
    const { data, isLoading, isError } = useQuery({
        queryKey: ["chatGallery"],
        queryFn: async () => (await apiClient.get<GalleryItem[]>("/chat/gallery")).data,
        refetchInterval: 5 * 60_000,
    })
    return (
        <div className="flex flex-col flex-1 p-6 bg-background space-y-4 overflow-y-auto custom-scrollbar">
            <header>
                <h1 className="text-2xl font-bold text-foreground">Chat gallery</h1>
                <p className="text-sm text-muted-foreground">
                    Research chats Quantara users chose to list when sharing. AI-generated, not financial advice. To add yours, share a chat from the assistant and tick "Also list in the gallery".
                </p>
            </header>
            {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
            {isError && <p role="alert" className="text-sm text-muted-foreground">Couldn't load the gallery.</p>}
            {data && data.length === 0 && <p className="text-sm text-muted-foreground">No chats listed yet.</p>}
            {data && data.length > 0 && (
                <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {data.map(c => (
                        <li key={c.token}>
                            <Link to={`/shared/${c.token}`} className="block h-full rounded-lg border border-q-border bg-q-surface p-4 hover:border-primary/50">
                                <p className="text-sm font-semibold text-foreground line-clamp-3">{c.question}</p>
                                <p className="mt-2 text-xs text-muted-foreground">
                                    {c.tickers.length > 0 && <span className="font-mono">{c.tickers.map(cleanTickerDisplay).join(" · ")} · </span>}
                                    {c.messages} messages · {new Date(c.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}
                                </p>
                            </Link>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    )
}
