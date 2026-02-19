import { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import {
    ShieldCheck,
    Mail,
    KeyRound,
    User,
    Lock,
    Globe,
    Monitor
} from "lucide-react"
import { api } from "@/lib/api"
import { useAuth } from "@/context/AuthContext"

export default function Register() {
    const navigate = useNavigate()
    const { login } = useAuth()
    const [formData, setFormData] = useState({
        fullName: "",
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

            const user = {
                id: "1", // Mock ID
                email: formData.email,
            }

            login(data.access_token, user)
            navigate("/")
        } catch (err: any) {
            setError(err.message || "Failed to register. Please try again.")
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
        <div className="min-h-screen bg-[#f5f6f8] dark:bg-[#0A0E12] text-[#F0F6FC] flex flex-col font-inter antialiased relative">
            <header className="flex items-center justify-between border-b border-[#282d39] px-6 py-3 bg-[#151B23]/50 backdrop-blur-sm fixed top-0 w-full z-50">
                <div className="flex items-center gap-2">
                    <div className="text-[#1e5df1]">
                        <ShieldCheck className="size-6" />
                    </div>
                    <Link to="/" className="text-white text-lg font-bold uppercase tracking-widest">Quantara</Link>
                    <span className="text-[10px] bg-[#1e5df1]/20 text-[#1e5df1] border border-[#1e5df1]/30 px-1.5 py-0.5 font-bold tracking-tighter">INSTITUTIONAL</span>
                </div>
                <div className="flex items-center gap-4">
                    <button className="flex items-center justify-center size-8 border border-[#282d39] hover:bg-[#282d39] transition-colors">
                        <Monitor className="text-sm size-4" />
                    </button>
                    <div className="h-4 w-px bg-[#282d39]"></div>
                    <div className="flex items-center gap-2 text-xs font-medium text-[#9ca5ba]">
                        <Globe className="size-3.5" />
                        EN-US
                    </div>
                </div>
            </header>

            <main className="flex-1 flex items-center justify-center p-4 pt-20 pb-20">
                <div className="w-full max-w-[420px] bg-[#151B23] border border-[#282d39] shadow-2xl overflow-hidden">
                    <div className="p-6 border-b border-[#282d39] bg-[#0A0E12]/30">
                        <div className="flex justify-between items-start mb-4">
                            <div>
                                <h2 className="text-xl font-bold text-white tracking-tight">Institutional Registration</h2>
                                <p className="text-[#9ca5ba] text-xs mt-1">Request access to Quantara's high-density financial intelligence platform.</p>
                            </div>
                            <div className="flex flex-col items-end gap-1">
                                <span className="text-[9px] font-bold text-[#1e5df1] uppercase tracking-widest border border-[#1e5df1] px-1.5 py-0.5">Level 3 Security</span>
                                <span className="text-[9px] text-[#9ca5ba] uppercase">Verified Node</span>
                            </div>
                        </div>
                    </div>

                    <form onSubmit={handleRegister} className="p-6 space-y-5">
                        <div className="space-y-1.5">
                            <label className="text-[11px] font-bold uppercase tracking-wider text-[#9ca5ba]" htmlFor="fullName">Full Name</label>
                            <div className="relative">
                                <User className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9ca5ba] size-4" />
                                <input
                                    className="w-full bg-[#0A0E12] border border-[#282d39] text-white text-sm px-10 py-3 focus:border-[#1e5df1] focus:ring-0 outline-none placeholder:text-[#9ca5ba]/50"
                                    id="fullName"
                                    placeholder="John Doe"
                                    type="text"
                                    value={formData.fullName}
                                    onChange={handleChange}
                                    required
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-[11px] font-bold uppercase tracking-wider text-[#9ca5ba]" htmlFor="email">Work Email</label>
                            <div className="relative">
                                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9ca5ba] size-4" />
                                <input
                                    className="w-full bg-[#0A0E12] border border-[#282d39] text-white text-sm px-10 py-3 focus:border-[#1e5df1] focus:ring-0 outline-none placeholder:text-[#9ca5ba]/50"
                                    id="email"
                                    placeholder="name@institution.com"
                                    type="email"
                                    value={formData.email}
                                    onChange={handleChange}
                                    required
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-[11px] font-bold uppercase tracking-wider text-[#9ca5ba]" htmlFor="password">Create Access Key</label>
                            <div className="relative">
                                <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9ca5ba] size-4" />
                                <input
                                    className="w-full bg-[#0A0E12] border border-[#282d39] text-white text-sm px-10 py-3 focus:border-[#1e5df1] focus:ring-0 outline-none placeholder:text-[#9ca5ba]/50"
                                    id="password"
                                    placeholder="••••••••••••"
                                    type="password"
                                    value={formData.password}
                                    onChange={handleChange}
                                    required
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-[11px] font-bold uppercase tracking-wider text-[#9ca5ba]" htmlFor="confirmPassword">Confirm Access Key</label>
                            <div className="relative">
                                <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9ca5ba] size-4" />
                                <input
                                    className="w-full bg-[#0A0E12] border border-[#282d39] text-white text-sm px-10 py-3 focus:border-[#1e5df1] focus:ring-0 outline-none placeholder:text-[#9ca5ba]/50"
                                    id="confirmPassword"
                                    placeholder="••••••••••••"
                                    type="password"
                                    value={formData.confirmPassword}
                                    onChange={handleChange}
                                    required
                                />
                            </div>
                        </div>

                        {error && (
                            <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-[10px] font-bold uppercase tracking-wider">
                                {error}
                            </div>
                        )}

                        <button
                            className="w-full bg-[#1e5df1] hover:bg-[#1e5df1]/90 text-white font-bold py-3.5 uppercase tracking-widest text-xs transition-colors border border-[#1e5df1]/50 shadow-lg shadow-[#1e5df1]/20 active:translate-y-[1px] disabled:opacity-50 disabled:cursor-not-allowed"
                            type="submit"
                            disabled={isLoading}
                        >
                            {isLoading ? "Processing Request..." : "Request Access"}
                        </button>

                        <div className="flex items-center justify-between text-[10px] text-[#9ca5ba] uppercase tracking-tighter">
                            <div className="flex items-center gap-1">
                                <Lock className="size-3 text-green-500" />
                                Secure Registration
                            </div>
                            <Link to="/login" className="text-[#1e5df1] hover:underline font-bold">Back to Login</Link>
                        </div>
                    </form>

                    <div className="h-1 bg-gradient-to-r from-[#1e5df1]/5 via-[#1e5df1] to-[#1e5df1]/5"></div>
                    <div className="aspect-[16/2] w-full bg-[#151B23] border-t border-[#282d39] overflow-hidden flex items-center justify-center opacity-20 grayscale">
                        <div className="flex gap-1">
                            <div className="w-8 h-1 bg-[#1e5df1]"></div>
                            <div className="w-4 h-1 bg-[#1e5df1]/50"></div>
                            <div className="w-12 h-1 bg-[#1e5df1]"></div>
                            <div className="w-2 h-1 bg-[#1e5df1]/20"></div>
                            <div className="w-16 h-1 bg-[#1e5df1]"></div>
                            <div className="w-6 h-1 bg-[#1e5df1]/40"></div>
                        </div>
                    </div>
                </div>
            </main>

            <footer className="fixed bottom-0 w-full border-t border-[#282d39] bg-[#151B23] px-6 py-2.5 flex flex-col md:flex-row items-center justify-between text-[10px] uppercase tracking-wider font-medium text-[#9ca5ba] z-50">
                <div className="flex items-center gap-4">
                    <span className="text-white font-bold">Quantara Terminal v4.12.0</span>
                    <span className="hidden md:inline text-[#282d39]">|</span>
                    <p>Institutional-grade financial intelligence. Not financial advice.</p>
                </div>
                <div className="flex items-center gap-6 mt-2 md:mt-0">
                    <a className="hover:text-[#1e5df1] transition-colors" href="#">Security Policy</a>
                    <a className="hover:text-[#1e5df1] transition-colors" href="#">Terms of Service</a>
                    <a className="hover:text-[#1e5df1] transition-colors" href="#">Compliance Hub</a>
                    <span className="text-white/50">© 2024 Quantara Systems</span>
                </div>
            </footer>

            <div className="fixed inset-0 pointer-events-none opacity-[0.03] z-[-1]" style={{ backgroundImage: "linear-gradient(#9ca5ba 1px, transparent 1px), linear-gradient(90deg, #9ca5ba 1px, transparent 1px)", backgroundSize: "40px 40px" }}>
            </div>
        </div>
    )
}
