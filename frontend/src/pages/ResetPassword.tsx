import { useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { KeyRound, Mail } from "lucide-react"
import { api, apiErrorDetail } from "@/lib/api"

const inputClass =
    "w-full bg-[#0A0E12] border border-[#282d39] text-white text-sm px-10 py-3 focus:border-[#1e5df1] focus:ring-0 outline-none placeholder:text-[#9ca5ba]/50"
const labelClass = "text-[11px] font-bold uppercase tracking-wider text-[#9ca5ba]"

// Without ?token= this requests a reset link (posted to Slack); with it, it sets the new password.
export default function ResetPassword() {
    const token = useSearchParams()[0].get("token")
    const [value, setValue] = useState("")
    const [confirm, setConfirm] = useState("")
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [done, setDone] = useState<string | null>(null)

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
                await api.post("/auth/reset-password", { token, new_password: value })
                setDone("Password updated. Every session has been signed out.")
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
        <div className="min-h-screen bg-[#f5f6f8] dark:bg-[#0A0E12] flex items-center justify-center p-4 font-inter antialiased">
            <div className="w-full max-w-[420px] bg-[#151B23] border border-[#282d39] shadow-2xl">
                <div className="p-6 border-b border-[#282d39] bg-[#0A0E12]/30">
                    <h2 className="text-xl font-bold text-white tracking-tight">
                        {token ? "Set a New Password" : "Reset Password"}
                    </h2>
                    <p className="text-[#9ca5ba] text-xs mt-1">
                        {token ? "The link works once and expires after 15 minutes." : "A reset link will be posted to the configured Slack channel."}
                    </p>
                </div>

                {done ? (
                    <div className="p-6 space-y-5">
                        <p className="text-sm text-white" role="status">{done}</p>
                        <Link to="/login" className="text-[10px] text-[#1e5df1] hover:underline font-bold uppercase">Back to sign in</Link>
                    </div>
                ) : (
                    <form onSubmit={handleSubmit} className="p-6 space-y-5">
                        <div className="space-y-1.5">
                            <label className={labelClass} htmlFor="reset-value">{token ? "New Password" : "Email"}</label>
                            <div className="relative">
                                {token
                                    ? <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9ca5ba] size-4" />
                                    : <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9ca5ba] size-4" />}
                                <input
                                    className={inputClass}
                                    id="reset-value"
                                    type={token ? "password" : "email"}
                                    autoComplete={token ? "new-password" : "email"}
                                    minLength={token ? 8 : undefined}
                                    value={value}
                                    onChange={(e) => setValue(e.target.value)}
                                    required
                                />
                            </div>
                        </div>

                        {token && (
                            <div className="space-y-1.5">
                                <label className={labelClass} htmlFor="reset-confirm">Confirm Password</label>
                                <div className="relative">
                                    <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9ca5ba] size-4" />
                                    <input
                                        className={inputClass}
                                        id="reset-confirm"
                                        type="password"
                                        autoComplete="new-password"
                                        value={confirm}
                                        onChange={(e) => setConfirm(e.target.value)}
                                        required
                                    />
                                </div>
                            </div>
                        )}

                        {error && (
                            <div role="alert" className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-[10px] font-bold uppercase tracking-wider">
                                {error}
                            </div>
                        )}

                        <button
                            className="w-full bg-[#1e5df1] hover:bg-[#1e5df1]/90 text-white font-bold py-3.5 uppercase tracking-widest text-xs transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            type="submit"
                            disabled={isLoading}
                        >
                            {isLoading ? "Working..." : token ? "Update Password" : "Send Reset Link"}
                        </button>

                        <div className="text-right">
                            <Link to="/login" className="text-[10px] text-[#1e5df1] hover:underline font-bold uppercase">Back to sign in</Link>
                        </div>
                    </form>
                )}
            </div>
        </div>
    )
}
