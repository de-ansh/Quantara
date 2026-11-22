import { useState, useEffect } from "react"
import { useTheme } from "@/context/use-theme"
import apiClient, { apiErrorDetail } from "@/lib/api"
import { cn } from "@/lib/utils"
import PageHeader from "@/components/PageHeader"
import Panel from "@/components/Panel"
import { Button } from "@/components/ui/button"
import { Eye, EyeOff, Moon, Save, Sun, Trash2 } from "lucide-react"

interface Credentials { has_openai_key: boolean; openai_key_masked: string | null; sec_user_agent: string | null }
type Status = { kind: "idle" | "saving" } | { kind: "done" | "error"; text: string }

export default function Settings() {
    const { theme, setTheme } = useTheme()
    const [openaiKey, setOpenaiKey] = useState("")
    const [secUserAgent, setSecUserAgent] = useState("")
    const [hasServerKey, setHasServerKey] = useState(false)
    const [serverConfiguredKey, setServerConfiguredKey] = useState<string | null>(null)
    const [showKey, setShowKey] = useState(false)
    const [status, setStatus] = useState<Status>({ kind: "idle" })
    const [confirmRemove, setConfirmRemove] = useState(false)

    useEffect(() => {
        // Credentials live encrypted on the server; scrub copies older builds left in the browser.
        localStorage.removeItem("openai_api_key")
        localStorage.removeItem("sec_user_agent")

        // Hydrate from server-side credentials storage
        apiClient.get<Credentials>("/users/credentials")
            .then(res => {
                if (res.data) {
                    if (res.data.has_openai_key) {
                        setHasServerKey(true)
                        setServerConfiguredKey(res.data.openai_key_masked)
                    }
                    if (res.data.sec_user_agent) {
                        setSecUserAgent(res.data.sec_user_agent)
                    }
                }
            })
            .catch(() => {
                // Leave fields empty if the server is unreachable
            })
    }, [])

    const handleSave = async () => {
        setStatus({ kind: "saving" })
        try {
            const payload: { openai_api_key?: string; sec_user_agent?: string } = {}
            if (openaiKey.trim()) payload.openai_api_key = openaiKey.trim()
            if (secUserAgent.trim()) payload.sec_user_agent = secUserAgent.trim()
            const res = await apiClient.put<Credentials>("/users/credentials", payload)
            setHasServerKey(res.data.has_openai_key)
            setServerConfiguredKey(res.data.openai_key_masked)
            setOpenaiKey("")
            setStatus({ kind: "done", text: "Saved." })
        } catch (err) {
            setStatus({ kind: "error", text: apiErrorDetail(err) ?? "Couldn't save. Please try again." })
        }
    }

    const handleRemove = async () => {
        setStatus({ kind: "saving" })
        try {
            await apiClient.put("/users/credentials", { openai_api_key: "", sec_user_agent: "" })
            setOpenaiKey("")
            setSecUserAgent("")
            setHasServerKey(false)
            setServerConfiguredKey(null)
            setConfirmRemove(false)
            setStatus({ kind: "done", text: "Your keys were removed." })
        } catch (err) {
            setStatus({ kind: "error", text: apiErrorDetail(err) ?? "Couldn't remove your keys. Please try again." })
        }
    }

    const inputClass = "w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary placeholder:text-muted-foreground/60"

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-4xl mx-auto">
            <PageHeader title="Settings" description="How the app looks, and the keys it uses for AI answers and US filings." />

            <Panel id="theme" title="Theme">
                <div role="group" aria-label="Theme" className="p-4 grid grid-cols-2 gap-3 max-w-md">
                    {([["dark", "Dark", Moon], ["light", "Light", Sun]] as const).map(([value, label, Icon]) => (
                        <button key={value} type="button" aria-pressed={theme === value} onClick={() => setTheme(value)}
                            className={cn("flex items-center justify-center gap-2 rounded-md border p-3 text-sm",
                                theme === value ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>
                            <Icon className="size-4" aria-hidden="true" /> {label}
                        </button>
                    ))}
                </div>
            </Panel>

            <Panel id="keys" title="Keys" description="Stored encrypted on your server, never in the browser.">
                <div className="p-4 space-y-5">
                    <div className="space-y-1.5">
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                            <label htmlFor="openai-key" className="text-sm font-medium">OpenAI API key</label>
                            <span className="text-xs text-muted-foreground">
                                {serverConfiguredKey ? <>In use: <span className="font-mono">{serverConfiguredKey}</span></> : "None saved; the server's key is used if it has one"}
                            </span>
                        </div>
                        <div className="relative">
                            <input id="openai-key" type={showKey ? "text" : "password"} value={openaiKey} onChange={e => setOpenaiKey(e.target.value)}
                                autoComplete="off" placeholder={hasServerKey ? "Leave blank to keep the saved key" : "sk-proj-…"} className={cn(inputClass, "pr-10 font-mono")} />
                            <button type="button" onClick={() => setShowKey(!showKey)} aria-label={showKey ? "Hide key" : "Show key"}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                                {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                            </button>
                        </div>
                        <p className="text-xs text-muted-foreground">Used for research reports, chat and earnings-call summaries.</p>
                    </div>

                    <div className="space-y-1.5">
                        <label htmlFor="sec-agent" className="text-sm font-medium">SEC contact (for US filings)</label>
                        <input id="sec-agent" type="text" value={secUserAgent} onChange={e => setSecUserAgent(e.target.value)}
                            placeholder="Your name you@example.com" className={inputClass} />
                        <p className="text-xs text-muted-foreground">The SEC asks every automated request for a name and email. Only needed for US stocks.</p>
                    </div>

                    {status.kind === "done" && <p role="status" className="text-sm text-q-risk-low">{status.text}</p>}
                    {status.kind === "error" && <p role="alert" className="text-sm text-q-risk-high">{status.text}</p>}

                    <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-border">
                        {confirmRemove ? (
                            <span className="flex items-center gap-2 text-sm">
                                Remove both saved keys?
                                <Button variant="outline" size="sm" className="text-q-risk-high" disabled={status.kind === "saving"} onClick={handleRemove}>Remove</Button>
                                <Button variant="ghost" size="sm" onClick={() => setConfirmRemove(false)}>Cancel</Button>
                            </span>
                        ) : (
                            <Button variant="ghost" size="sm" className="gap-1.5 text-muted-foreground" disabled={!hasServerKey && !secUserAgent} onClick={() => setConfirmRemove(true)}>
                                <Trash2 className="size-4" /> Remove saved keys
                            </Button>
                        )}
                        <Button onClick={handleSave} disabled={status.kind === "saving"} className="gap-1.5">
                            <Save className="size-4" /> {status.kind === "saving" ? "Saving…" : "Save"}
                        </Button>
                    </div>
                </div>
            </Panel>
        </div>
    )
}
