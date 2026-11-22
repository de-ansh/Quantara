import { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import AuthLayout, { AuthError, AuthField } from "@/components/AuthLayout"
import { Button } from "@/components/ui/button"
import { api, apiErrorDetail } from "@/lib/api"
import { useAuth } from "@/context/AuthContext"
import type { User as AuthUser } from "@/types"

export default function Register() {
    const navigate = useNavigate()
    const { login } = useAuth()
    const [formData, setFormData] = useState({
        email: "",
        password: "",
        confirmPassword: ""
    })
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault()

        if (formData.password !== formData.confirmPassword) {
            setError("Passwords do not match.")
            return
        }

        setIsLoading(true)
        setError(null)

        try {
            const { data } = await api.post<{ access_token: string }>("/auth/register", {
                email: formData.email,
                password: formData.password
            })

            // Token isn't stored yet, so pass it explicitly to fetch the real profile
            const { data: profile } = await api.get<AuthUser & { id: number }>("/users/me", {
                headers: { Authorization: `Bearer ${data.access_token}` },
            })
            const user: AuthUser = { ...profile, id: String(profile.id) }

            login(data.access_token, user)
            navigate("/")
        } catch (err) {
            setError(apiErrorDetail(err) ?? ((err instanceof Error && err.message) || "Failed to register. Please try again."))
        } finally {
            setIsLoading(false)
        }
    }

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({
            ...formData,
            [e.target.id]: e.target.value
        })
    }

    return (
        <AuthLayout title="Create an account" description="Everything you save stays private to your account.">
            <form onSubmit={handleRegister} className="space-y-4">
                <AuthField id="email" name="email" label="Email" type="email" autoComplete="email" placeholder="you@example.com"
                    value={formData.email} onChange={handleChange} required />
                <AuthField id="password" name="password" label="Password" type="password" autoComplete="new-password" minLength={8}
                    hint="At least 8 characters." value={formData.password} onChange={handleChange} required />
                <AuthField id="confirmPassword" name="confirmPassword" label="Confirm password" type="password" autoComplete="new-password"
                    value={formData.confirmPassword} onChange={handleChange} required />
                {error && <AuthError>{error}</AuthError>}
                <Button type="submit" className="w-full" disabled={isLoading}>{isLoading ? "Creating account…" : "Create account"}</Button>
                <p className="text-center text-sm text-muted-foreground">
                    Already have an account? <Link to="/login" className="text-primary hover:underline">Sign in</Link>
                </p>
            </form>
        </AuthLayout>
    )
}
