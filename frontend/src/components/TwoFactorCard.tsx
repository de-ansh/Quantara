import { useState } from "react"
import { Loader2, Smartphone } from "lucide-react"
import { QRCodeSVG } from "qrcode.react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import api, { apiErrorDetail } from "@/lib/api"

interface TwoFactorStatus {
    two_factor_enabled: boolean
    recovery_codes_left: number
}

export default function TwoFactorCard() {
    const queryClient = useQueryClient()
    const { data: status } = useQuery({
        queryKey: ["two-factor"],
        queryFn: async () => (await api.get<TwoFactorStatus>("/users/me")).data,
    })
    const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null)
    const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null)
    const [code, setCode] = useState("")
    const [password, setPassword] = useState("")
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const run = async (action: () => Promise<void>) => {
        setBusy(true)
        setError(null)
        try {
            await action()
        } catch (err) {
            setError(apiErrorDetail(err) ?? "Something went wrong. Please try again.")
        } finally {
            setBusy(false)
        }
    }
    const refreshStatus = () => queryClient.invalidateQueries({ queryKey: ["two-factor"] })

    const start = () => run(async () => {
        setSetup((await api.post<{ secret: string; otpauth_uri: string }>("/auth/2fa/setup")).data)
    })
    const enable = (e: React.FormEvent) => {
        e.preventDefault()
        run(async () => {
            const { data } = await api.post<{ recovery_codes: string[] }>("/auth/2fa/enable", { code })
            setRecoveryCodes(data.recovery_codes)
            setSetup(null)
            setCode("")
            await refreshStatus()
        })
    }
    const regenerate = () => run(async () => {
        const { data } = await api.post<{ recovery_codes: string[] }>("/auth/2fa/recovery-codes", { password, code })
        setRecoveryCodes(data.recovery_codes)
        setPassword("")
        setCode("")
        await refreshStatus()
    })
    const disable = (e: React.FormEvent) => {
        e.preventDefault()
        run(async () => {
            await api.post("/auth/2fa/disable", { password, code })
            setPassword("")
            setCode("")
            await refreshStatus()
        })
    }

    const inputClass = "w-full bg-background border border-border text-sm px-3 py-2 rounded-sm text-foreground focus:border-primary outline-none"
    const labelClass = "text-[10px] font-bold uppercase tracking-wider text-muted-foreground"

    return (
        <Card className="bg-card border-border shadow-none">
            <CardHeader className="p-4 border-b border-border">
                <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-2">
                    <Smartphone className="size-4 text-primary" /> Two-Factor Login
                </CardTitle>
                <CardDescription className="text-[10px] uppercase font-bold">
                    {status?.two_factor_enabled
                        ? `On · ${status.recovery_codes_left} recovery codes left`
                        : "Off · asks for an authenticator-app code at sign-in"}
                </CardDescription>
            </CardHeader>
            <CardContent className="p-4 space-y-4 text-sm">
                {recoveryCodes && (
                    <div className="space-y-2" role="status">
                        <p className="font-bold text-foreground">Save these recovery codes now.</p>
                        <p className="text-xs text-muted-foreground">
                            Each works once if you lose your phone. They won't be shown again, and any older codes no longer work.
                        </p>
                        <ul className="grid grid-cols-2 gap-2 font-mono text-xs bg-muted/40 p-3 rounded-sm">
                            {recoveryCodes.map((c) => <li key={c}>{c}</li>)}
                        </ul>
                        <Button size="sm" onClick={() => setRecoveryCodes(null)}>I've saved them</Button>
                    </div>
                )}

                {!recoveryCodes && !status?.two_factor_enabled && !setup && (
                    <Button onClick={start} disabled={busy || !status} className="gap-2">
                        {busy && <Loader2 className="size-4 animate-spin" />} Turn on
                    </Button>
                )}

                {setup && (
                    <form onSubmit={enable} className="space-y-3">
                        <p className="text-xs text-muted-foreground">
                            Scan this with an authenticator app (Google Authenticator, 1Password, Authy…), then enter the code it shows.
                        </p>
                        <div className="inline-block bg-white p-2 rounded-sm">
                            <QRCodeSVG value={setup.otpauth_uri} size={168} title="Two-factor setup QR code" />
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Can't scan? Enter this key: <code className="font-mono text-foreground break-all">{setup.secret}</code>
                        </p>
                        <label className="block space-y-1 max-w-xs">
                            <span className={labelClass}>Code from the app</span>
                            <input inputMode="numeric" autoComplete="one-time-code" required value={code}
                                onChange={(e) => setCode(e.target.value)} className={inputClass} />
                        </label>
                        <div className="flex gap-2">
                            <Button type="submit" disabled={busy} className="gap-2">
                                {busy && <Loader2 className="size-4 animate-spin" />} Confirm and turn on
                            </Button>
                            <Button type="button" variant="outline" onClick={() => setSetup(null)}>Cancel</Button>
                        </div>
                    </form>
                )}

                {!recoveryCodes && status?.two_factor_enabled && (
                    <form onSubmit={disable} className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
                        <label className="space-y-1">
                            <span className={labelClass}>Password</span>
                            <input type="password" autoComplete="current-password" required value={password}
                                onChange={(e) => setPassword(e.target.value)} className={inputClass} />
                        </label>
                        <label className="space-y-1">
                            <span className={labelClass}>App or recovery code</span>
                            <input autoComplete="one-time-code" required value={code}
                                onChange={(e) => setCode(e.target.value)} className={inputClass} />
                        </label>
                        <div className="flex gap-2">
                            <Button type="button" disabled={busy || !password || !code} onClick={regenerate} className="gap-2">
                                {busy && <Loader2 className="size-4 animate-spin" />} New recovery codes
                            </Button>
                            <Button type="submit" variant="outline" disabled={busy}>Turn off</Button>
                        </div>
                        <p className="md:col-span-3 text-xs text-muted-foreground">
                            Enter your password and a code, then get a fresh set of recovery codes or turn two-factor off.
                        </p>
                    </form>
                )}

                {error && <p role="alert" className="text-xs text-red-400">{error}</p>}
            </CardContent>
        </Card>
    )
}
