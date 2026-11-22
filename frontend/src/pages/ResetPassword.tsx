import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import AuthLayout, { AuthError, AuthField } from "@/components/AuthLayout"
import { Button } from "@/components/ui/button"
import { api, apiErrorDetail } from "@/lib/api"

// Without ?token= this requests a reset link (posted to Slack); with it, it sets the new password.
export default function ResetPassword() {
    const token = useSearchParams()[0].get("token")
    const [value, setValue] = useState("")
    const [confirm, setConfirm] = useState("")
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [done, setDone] = useState<string | null>(null)
    const [disableTwoFactor, setDisableTwoFactor] = useState(false)

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setError(null)
        if (token && value !== confirm) {
            setError("Passwords do not match")
            return
        }
        setIsLoading(true)
        try {
            if (token) {
                await api.post("/auth/reset-password", { token, new_password: value, disable_two_factor: disableTwoFactor })
                setDone(
                    disableTwoFactor
                        ? "Password updated and two-factor login turned off. Turn it back on from your Account page."
                        : "Password updated. Every session has been signed out."
                )
            } else {
                const { data } = await api.post<{ detail: string }>("/auth/forgot-password", { email: value })
                setDone(data.detail)
            }
        } catch (err) {
            setError(apiErrorDetail(err) ?? "Something went wrong. Please try again.")
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <AuthLayout title={token ? "Set a new password" : "Reset your password"}
            description={token ? "The link works once and expires after 15 minutes." : "A reset link will be posted to the configured Slack channel."}>
            {done ? (
                <div className="space-y-4">
                    <p className="text-sm" role="status">{done}</p>
                    <Link to="/login" className="text-sm text-primary hover:underline">Back to sign in</Link>
                </div>
            ) : (
                <form onSubmit={handleSubmit} className="space-y-4">
                    <AuthField id="reset-value" label={token ? "New password" : "Email"} type={token ? "password" : "email"}
                        autoComplete={token ? "new-password" : "email"} minLength={token ? 8 : undefined}
                        value={value} onChange={e => setValue(e.target.value)} required />
                    {token && (
                        <AuthField id="reset-confirm" label="Confirm password" type="password" autoComplete="new-password"
                            value={confirm} onChange={e => setConfirm(e.target.value)} required />
                    )}
                    {token && (
                        <label className="flex items-start gap-2 text-sm text-muted-foreground">
                            <input type="checkbox" checked={disableTwoFactor} onChange={e => setDisableTwoFactor(e.target.checked)} className="mt-1 accent-primary" />
                            <span>I lost my authenticator app and my recovery codes: also turn off two-factor login.</span>
                        </label>
                    )}
                    {error && <AuthError>{error}</AuthError>}
                    <Button type="submit" className="w-full" disabled={isLoading}>
                        {isLoading ? "Working…" : token ? "Update password" : "Send reset link"}
                    </Button>
                    <p className="text-center text-sm"><Link to="/login" className="text-primary hover:underline">Back to sign in</Link></p>
                </form>
            )}
        </AuthLayout>
    )
}
