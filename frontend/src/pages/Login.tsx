import { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import AuthLayout, { AuthError, AuthField } from "@/components/AuthLayout"
import { Button } from "@/components/ui/button"
import { api, apiErrorDetail } from "@/lib/api"
import { useAuth } from "@/context/AuthContext"
import type { User } from "@/types"

export default function Login() {
    const navigate = useNavigate()
    const { login } = useAuth()
    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    // Shown once the server says this account needs a two-factor code
    const [needsCode, setNeedsCode] = useState(false)
    const [totpCode, setTotpCode] = useState("")
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault()
        setIsLoading(true)
        setError(null)

        try {
            const { data } = await api.post<{ access_token: string }>("/auth/login", {
                email,
                password,
                ...(needsCode ? { totp_code: totpCode } : {}),
            })

            // Token isn't stored yet, so pass it explicitly to fetch the real profile
            const { data: profile } = await api.get<User & { id: number }>("/users/me", {
                headers: { Authorization: `Bearer ${data.access_token}` },
            })
            const user: User = { ...profile, id: String(profile.id) }

            login(data.access_token, user)
            navigate("/")
        } catch (err) {
            if (apiErrorDetail(err) === "two_factor_required") {
                setNeedsCode(true)
                return
            }
            setError(apiErrorDetail(err) ?? ((err instanceof Error && err.message) || "Couldn't sign in. Check your email and password."))
        } finally {
            setIsLoading(false)
        }
    }

    return (
        <AuthLayout title="Sign in" description="Your stock research, portfolios and alerts.">
            <form onSubmit={handleLogin} className="space-y-4">
                <AuthField id="email" label="Email" type="email" autoComplete="email" placeholder="you@example.com"
                    value={email} onChange={e => setEmail(e.target.value)} required />
                <AuthField id="password" label="Password" type="password" autoComplete="current-password"
                    aside={<Link className="text-xs text-primary hover:underline" to="/reset-password">Forgot password?</Link>}
                    value={password} onChange={e => setPassword(e.target.value)} required />
                {needsCode && (
                    <AuthField id="totp-code" label="Two-factor code" autoComplete="one-time-code" inputMode="numeric" placeholder="123456" autoFocus
                        hint={<>The 6-digit code from your authenticator app, or a recovery code. <Link to="/reset-password" className="text-primary hover:underline">Lost both?</Link></>}
                        value={totpCode} onChange={e => setTotpCode(e.target.value)} required />
                )}
                {error && <AuthError>{error}</AuthError>}
                <Button type="submit" className="w-full" disabled={isLoading}>{isLoading ? "Signing in…" : "Sign in"}</Button>
                <p className="text-center text-sm text-muted-foreground">
                    New here? <Link to="/register" className="text-primary hover:underline">Create an account</Link>
                </p>
            </form>
        </AuthLayout>
    )
}
