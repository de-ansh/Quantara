import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Download, Loader2, Trash2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import api, { apiErrorDetail } from "@/lib/api"
import { useAuth } from "@/context/AuthContext"

export default function YourDataCard() {
    const { logout } = useAuth()
    const navigate = useNavigate()
    const [exporting, setExporting] = useState(false)
    const [confirming, setConfirming] = useState(false)
    const [password, setPassword] = useState("")
    const [understood, setUnderstood] = useState(false)
    const [deleting, setDeleting] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const handleExport = async () => {
        setExporting(true)
        setError(null)
        try {
            const { data } = await api.get("/users/me/export")
            const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }))
            const a = document.createElement("a")
            a.href = url
            a.download = "quantara-my-data.json"
            a.click()
            URL.revokeObjectURL(url)
        } catch (err) {
            setError(apiErrorDetail(err) ?? "Could not export your data.")
        } finally {
            setExporting(false)
        }
    }

    const handleDelete = async (e: React.FormEvent) => {
        e.preventDefault()
        setDeleting(true)
        setError(null)
        try {
            await api.delete("/users/me", { data: { password } })
            logout()
            navigate("/login", { replace: true })
        } catch (err) {
            setError(apiErrorDetail(err) ?? "Could not delete your account.")
            setDeleting(false)
        }
    }

    return (
        <Card className="bg-card border-border shadow-none">
            <CardHeader className="p-4 border-b border-border">
                <CardTitle className="text-xs font-bold uppercase tracking-wider">Your Data</CardTitle>
                <CardDescription className="text-[10px] uppercase font-bold">Download or permanently delete everything we store</CardDescription>
            </CardHeader>
            <CardContent className="p-4 space-y-4">
                <div className="flex flex-wrap gap-2">
                    <Button variant="outline" onClick={handleExport} disabled={exporting} className="gap-2">
                        {exporting ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
                        Download my data
                    </Button>
                    {!confirming && (
                        <Button variant="outline" onClick={() => setConfirming(true)} className="gap-2 text-red-400 border-red-500/40 hover:bg-red-500/10">
                            <Trash2 className="size-4" /> Delete account
                        </Button>
                    )}
                </div>

                {confirming && (
                    <form onSubmit={handleDelete} className="space-y-3 border border-red-500/30 bg-red-500/5 p-4 rounded-sm">
                        <p className="text-xs text-foreground">
                            This permanently deletes your account, portfolios, watchlist, alerts and activity history. It cannot be undone.
                        </p>
                        <label className="block space-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Confirm with your password</span>
                            <input type="password" autoComplete="current-password" required value={password}
                                onChange={e => setPassword(e.target.value)}
                                className="w-full max-w-sm bg-background border border-border text-sm px-3 py-2 rounded-sm text-foreground outline-none focus:border-red-400" />
                        </label>
                        <label className="flex items-center gap-2 text-xs text-foreground">
                            <input type="checkbox" checked={understood} onChange={e => setUnderstood(e.target.checked)} />
                            I understand this cannot be undone
                        </label>
                        <div className="flex gap-2">
                            <Button type="submit" disabled={!understood || !password || deleting} className="bg-red-600 hover:bg-red-700 text-white gap-2">
                                {deleting && <Loader2 className="size-4 animate-spin" />} Permanently delete
                            </Button>
                            <Button type="button" variant="ghost" onClick={() => { setConfirming(false); setPassword(""); setUnderstood(false) }}>
                                Cancel
                            </Button>
                        </div>
                    </form>
                )}
                {error && <p role="alert" className="text-xs text-red-400">{error}</p>}
            </CardContent>
        </Card>
    )
}
