import { Fragment, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react"
import { useLocation } from "react-router-dom"
import { MessageSquare, Send, X } from "lucide-react"
import { postStream } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface Message {
    role: "user" | "assistant"
    content: string
}

/** Ticker of the stock page the user is on (/research/:t or /risk/:t), if any. */
const tickerFromPath = (path: string) => path.match(/^\/(?:research|risk)\/([^/]+)/)?.[1]?.toUpperCase()

/** **bold** spans inside one line, as React nodes (no HTML injection). */
const inline = (text: string) =>
    text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
        part.startsWith("**") && part.endsWith("**")
            ? <strong key={i} className="font-semibold text-foreground">{part.slice(2, -2)}</strong>
            : <Fragment key={i}>{part}</Fragment>
    )

/** The assistant answers with paragraphs, "- " bullets and **bold** only (see the backend prompt). */
function Formatted({ text }: { text: string }) {
    const blocks: ReactNode[] = []
    let bullets: string[] = []
    const flush = () => {
        if (bullets.length) blocks.push(<ul key={blocks.length} className="list-disc pl-4 space-y-1">{bullets.map((b, i) => <li key={i}>{inline(b)}</li>)}</ul>)
        bullets = []
    }
    for (const raw of text.split("\n")) {
        const line = raw.trim()
        const bullet = line.match(/^(?:[-*•]|\d+\.)\s+(.*)/)
        if (bullet) { bullets.push(bullet[1]); continue }
        flush()
        if (line) blocks.push(<p key={blocks.length}>{inline(line.replace(/^#+\s*/, ""))}</p>)
    }
    flush()
    return <div className="space-y-2">{blocks}</div>
}

export default function ChatAssistant() {
    const [open, setOpen] = useState(false)
    const [messages, setMessages] = useState<Message[]>([])
    const [draft, setDraft] = useState("")
    const ticker = tickerFromPath(useLocation().pathname)
    const inputRef = useRef<HTMLTextAreaElement>(null)
    const endRef = useRef<HTMLDivElement>(null)
    const lastRef = useRef<HTMLDivElement>(null)

    const [pending, setPending] = useState(false)
    const [error, setError] = useState<string | null>(null)

    /** Stream the reply into a new assistant message as it is written. */
    const ask = async (history: Message[]) => {
        setPending(true)
        setError(null)
        let started = false
        try {
            // the server caps a conversation at 30 messages
            await postStream("/chat/stream", { messages: history.slice(-20), ticker }, chunk => {
                const first = !started // read now: the state updater below may run later
                started = true
                setMessages(m => first
                    ? [...m, { role: "assistant", content: chunk }]
                    : [...m.slice(0, -1), { role: "assistant", content: m[m.length - 1].content + chunk }])
            })
        } catch (e) {
            setError(e instanceof Error ? e.message : "The assistant couldn't answer.")
        } finally {
            setPending(false)
        }
    }

    useEffect(() => { if (open) inputRef.current?.focus() }, [open])
    // A new answer opens at its first line (once, not on every streamed chunk); anything else at the bottom
    const lastRole = messages.at(-1)?.role
    useEffect(() => {
        if (lastRole === "assistant") lastRef.current?.scrollIntoView({ block: "start" })
        else endRef.current?.scrollIntoView({ block: "end" })
    }, [messages.length, lastRole, pending])

    const send = (text: string) => {
        const content = text.trim()
        if (!content || pending) return
        const history = [...messages, { role: "user" as const, content }]
        setMessages(history)
        setDraft("")
        void ask(history)
    }
    const retry = () => {
        // A reply cut off mid-stream is dropped and asked for again
        const history = lastRole === "assistant" ? messages.slice(0, -1) : messages
        setMessages(history)
        void ask(history)
    }
    const onSubmit = (e: FormEvent) => { e.preventDefault(); send(draft) }

    const suggestions = ticker
        ? [`Should I buy ${ticker}?`, "Explain the charts on this page", `What are the biggest risks for ${ticker}?`]
        : ["How risky is my watchlist?", "Explain what the risk score measures", "Find me Tata Motors"]

    if (!open) {
        return (
            <Button
                onClick={() => setOpen(true)}
                aria-label="Open research assistant"
                className="fixed bottom-5 right-5 z-40 h-12 rounded-full px-4 shadow-lg gap-2"
            >
                <MessageSquare className="size-5" aria-hidden="true" />
                <span className="hidden sm:inline">Ask Quantara</span>
            </Button>
        )
    }

    return (
        <section
            role="dialog"
            aria-label="Research assistant"
            onKeyDown={e => e.key === "Escape" && setOpen(false)}
            className="fixed z-50 inset-0 sm:inset-auto sm:bottom-5 sm:right-5 sm:w-[400px] sm:h-[min(600px,calc(100dvh-2.5rem))] flex flex-col bg-card border border-border sm:rounded-lg shadow-2xl"
        >
            <header className="flex items-center justify-between gap-2 px-4 h-12 border-b border-border shrink-0">
                <div className="min-w-0">
                    <h2 className="text-sm font-semibold text-foreground">Research assistant</h2>
                    {ticker && <p className="text-[11px] text-muted-foreground truncate">Looking at {ticker}</p>}
                </div>
                <div className="flex items-center gap-1">
                    {messages.length > 0 && (
                        <Button variant="ghost" size="sm" className="h-8 text-xs" onClick={() => { setMessages([]); setError(null) }} disabled={pending}>
                            New chat
                        </Button>
                    )}
                    <Button variant="ghost" size="icon" className="size-8" onClick={() => setOpen(false)} aria-label="Close assistant">
                        <X className="size-4" />
                    </Button>
                </div>
            </header>

            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 text-sm leading-relaxed" aria-live="polite">
                {messages.length === 0 && (
                    <div className="space-y-3">
                        <p className="text-muted-foreground">
                            Ask about any chart, score or stock. Answers use Quantara's own data, and are research, not financial advice.
                        </p>
                        <div className="flex flex-col gap-2">
                            {suggestions.map(s => (
                                <button
                                    key={s}
                                    type="button"
                                    onClick={() => send(s)}
                                    className="text-left text-sm border border-border rounded-md px-3 py-2 hover:bg-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                >
                                    {s}
                                </button>
                            ))}
                        </div>
                    </div>
                )}
                {messages.map((m, i) => (
                    <div key={i} ref={i === messages.length - 1 ? lastRef : undefined} className={cn("flex scroll-mt-3", m.role === "user" ? "justify-end" : "justify-start")}>
                        <div className={cn(
                            "max-w-[88%] rounded-lg px-3 py-2",
                            m.role === "user" ? "bg-primary text-primary-foreground whitespace-pre-wrap" : "bg-muted/60 text-foreground/90"
                        )}>
                            {m.role === "user" ? m.content : <Formatted text={m.content} />}
                        </div>
                    </div>
                ))}
                {pending && lastRole === "user" && (
                    <p className="text-muted-foreground text-xs animate-pulse" role="status">Looking at the data…</p>
                )}
                {error && (
                    <div role="alert" className="text-xs text-destructive flex items-center gap-2">
                        <span>{error}</span>
                        <button type="button" className="underline" onClick={retry}>Retry</button>
                    </div>
                )}
                <div ref={endRef} />
            </div>

            <form onSubmit={onSubmit} className="border-t border-border p-3 flex items-end gap-2 shrink-0">
                <label htmlFor="assistant-input" className="sr-only">Message</label>
                <textarea
                    id="assistant-input"
                    ref={inputRef}
                    value={draft}
                    onChange={e => setDraft(e.target.value)}
                    onKeyDown={e => {
                        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(draft) }
                    }}
                    rows={1}
                    maxLength={4000}
                    placeholder={ticker ? `Ask about ${ticker}…` : "Ask about a stock or chart…"}
                    className="flex-1 resize-none max-h-32 bg-background border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                />
                <Button type="submit" size="icon" className="size-9 shrink-0" disabled={!draft.trim() || pending} aria-label="Send">
                    <Send className="size-4" />
                </Button>
            </form>
        </section>
    )
}
