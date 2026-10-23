import { useState } from "react"
import { KeyRound, Loader2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import api, { apiErrorDetail } from "@/lib/api"
import { useAuth } from "@/context/AuthContext"

export default function ChangePasswordCard() {
    const { user, login } = useAuth()
    const [current, setCurrent] = useState("")
    const [next, setNext] = useState("")
    const [confirm, setConfirm] = useState("")
    const [saving, setSaving] = useState(false)
    const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null)

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (next !== confirm) {
            setMessage({ text: "New passwords do not match.", ok: false })
            return
        }
        setSaving(true)
        setMessage(null)
        try {
            const { data } = await api.post<{ access_token: string }>("/auth/change-password", {
                current_password: current,
                new_password: next,
            })
            // Every other session was revoked; keep this one on the fresh tokens
            if (user) login(data.access_token, user)
            setCurrent("")
            setNext("")
            setConfirm("")
            setMessage({ text: "Password changed. Other sessions were signed out.", ok: true })
        } catch (err) {
            setMessage({ text: apiErrorDetail(err) ?? "Could not change password.", ok: false })
        } finally {
            setSaving(false)
        }
    }

    const inputClass = "w-full bg-background border border-border text-sm px-3 py-2 rounded-sm text-foreground focus:border-primary outline-none"

    return (
        <Card className="bg-card border-border shadow-none">
            <CardHeader className="p-4 border-b border-border">
                <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-2">
                    <KeyRound className="size-4 text-primary" /> Change Password
                </CardTitle>
                <CardDescription className="text-[10px] uppercase font-bold">Signs out all other sessions</CardDescription>
            </CardHeader>
            <CardContent className="p-4">
                <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
                    <label className="space-y-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Current password</span>
                        <input type="password" autoComplete="current-password" required value={current}
                            onChange={e => setCurrent(e.target.value)} className={inputClass} />
                    </label>
                    <label className="space-y-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">New password</span>
                        <input type="password" autoComplete="new-password" required minLength={8} value={next}
                            onChange={e => setNext(e.target.value)} className={inputClass} />
                    </label>
                    <label className="space-y-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Confirm new password</span>
                        <input type="password" autoComplete="new-password" required minLength={8} value={confirm}
                            onChange={e => setConfirm(e.target.value)} className={inputClass} />
                    </label>
                    <div className="md:col-span-3 flex items-center justify-between gap-3">
                        <p role="status" className={message?.ok ? "text-xs text-green-400" : "text-xs text-red-400"}>
                            {message?.text}
                        </p>
                        <Button type="submit" disabled={saving} className="gap-2">
                            {saving && <Loader2 className="size-4 animate-spin" />} Update password
                        </Button>
                    </div>
                </form>
            </CardContent>
        </Card>
    )
}
