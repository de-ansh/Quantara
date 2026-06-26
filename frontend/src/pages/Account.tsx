import { useState, useEffect } from "react"
import apiClient from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { User, ShieldCheck, AlertTriangle, Save, Loader2, Sliders, CheckCircle2 } from "lucide-react"

const AVAILABLE_SECTORS = ["Technology", "Consumer Discretionary", "Financials", "Healthcare", "Energy"]

export default function Account() {
    const [user, setUser] = useState<any>(null)
    const [loading, setLoading] = useState(true)
    const [updating, setUpdating] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState(false)

    // Form states
    const [riskLevel, setRiskLevel] = useState("Moderate")
    const [volatilityTolerance, setVolatilityTolerance] = useState(50.0)
    const [investmentHorizon, setInvestmentHorizon] = useState(12)
    const [sectorPrefs, setSectorPrefs] = useState<Record<string, number>>({})

    useEffect(() => {
        const fetchProfile = async () => {
            try {
                const res = await apiClient.get("/users/me")
                const data = res.data
                setUser(data)
                setRiskLevel(data.risk_level || "Moderate")
                setVolatilityTolerance(data.volatility_tolerance ?? 50.0)
                setInvestmentHorizon(data.investment_horizon || 12)
                
                // Initialize sector preferences if empty
                const initialSectors: Record<string, number> = {}
                AVAILABLE_SECTORS.forEach(sec => {
                    initialSectors[sec] = data.sector_preferences?.[sec] ?? 30.0
                })
                setSectorPrefs(initialSectors)
            } catch (err: any) {
                console.error("Failed to load user profile:", err)
                setError("Failed to load institutional profile. Please authenticate again.")
            } finally {
                setLoading(false)
            }
        }
        fetchProfile()
    }, [])

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault()
        setUpdating(true)
        setError(null)
        setSuccess(false)

        try {
            const payload = {
                risk_level: riskLevel,
                volatility_tolerance: parseFloat(volatilityTolerance.toString()),
                investment_horizon: parseInt(investmentHorizon.toString(), 10),
                sector_preferences: sectorPrefs
            }

            const res = await apiClient.post("/users/risk-profile", payload)
            setUser(res.data)
            setSuccess(true)
            setTimeout(() => setSuccess(false), 3000)
        } catch (err: any) {
            console.error("Failed to save risk profile:", err)
            setError(err.response?.data?.detail || "Network error: Failed to persist risk parameters.")
        } finally {
            setUpdating(false)
        }
    }

    const handleSectorChange = (sector: string, val: number) => {
        setSectorPrefs(prev => ({
            ...prev,
            [sector]: val
        }))
    }

    if (loading) {
        return (
            <div className="flex-1 flex flex-col items-center justify-center min-h-[400px] font-mono text-xs text-muted-foreground uppercase tracking-widest animate-pulse">
                <Loader2 className="size-6 animate-spin mb-4 text-primary" />
                Retrieving_Credentials...
            </div>
        )
    }

    return (
        <div className="p-6 max-w-4xl mx-auto space-y-6 bg-background text-foreground transition-colors">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-border">
                <div>
                    <h1 className="text-2xl font-black uppercase tracking-tight flex items-center gap-2">
                        <User className="size-6 text-primary" />
                        Account & Risk Control
                    </h1>
                    <p className="text-[10px] text-muted-foreground uppercase font-bold tracking-widest mt-1">
                        Manage institutional Node Access and database-backed Risk Limits
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Badge variant="outline" className="font-mono text-[9px] font-black uppercase tracking-widest px-2 py-0.5 border-primary/20 bg-primary/5 text-primary">
                        UID: #{user?.id || "N/A"}
                    </Badge>
                </div>
            </div>

            {error && (
                <div className="p-3 border border-red-500/20 bg-red-500/10 text-red-400 text-xs font-bold uppercase tracking-wide flex items-center gap-2">
                    <AlertTriangle className="size-4 shrink-0" />
                    {error}
                </div>
            )}

            {success && (
                <div className="p-3 border border-green-500/20 bg-green-500/10 text-green-400 text-xs font-bold uppercase tracking-wide flex items-center gap-2">
                    <CheckCircle2 className="size-4 shrink-0" />
                    Database updated successfully. Risk parameters synchronized.
                </div>
            )}

            <form onSubmit={handleSave} className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Node Details Card */}
                <div className="space-y-6">
                    <Card className="bg-card border-border shadow-none">
                        <CardHeader className="p-4 pb-2 border-b border-border/55">
                            <CardTitle className="text-xs font-bold uppercase tracking-wider text-foreground">Node Metadata</CardTitle>
                            <CardDescription className="text-[10px] text-muted-foreground uppercase font-bold">
                                Authenticated Trader Details
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="p-6 space-y-4 font-mono text-[11px] uppercase">
                            <div className="flex justify-between py-1 border-b border-border/30">
                                <span className="text-muted-foreground">Access ID:</span>
                                <span className="text-foreground font-bold">{user?.id}</span>
                            </div>
                            <div className="flex justify-between py-1 border-b border-border/30">
                                <span className="text-muted-foreground">Registered Email:</span>
                                <span className="text-foreground font-bold font-sans normal-case">{user?.email}</span>
                            </div>
                            <div className="flex justify-between py-1 border-b border-border/30">
                                <span className="text-muted-foreground">Access Clearance:</span>
                                <span className="text-primary font-black tracking-wider">Institutional Node</span>
                            </div>
                            <div className="flex justify-between py-1">
                                <span className="text-muted-foreground">Security State:</span>
                                <span className="text-green-400 font-bold flex items-center gap-1">
                                    <ShieldCheck className="size-3.5" /> SECURE_CONN
                                </span>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Risk Tolerance Card */}
                    <Card className="bg-card border-border shadow-none">
                        <CardHeader className="p-4 pb-2 border-b border-border/55">
                            <CardTitle className="text-xs font-bold uppercase tracking-wider text-foreground">Risk Classification</CardTitle>
                            <CardDescription className="text-[10px] text-muted-foreground uppercase font-bold">
                                Core investment constraint classification
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="p-6 space-y-5">
                            {/* Risk Level Selector */}
                            <div className="space-y-1.5">
                                <label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Risk Level</label>
                                <div className="grid grid-cols-3 border border-border overflow-hidden rounded-sm">
                                    {["Conservative", "Moderate", "Aggressive"].map((level) => (
                                        <button
                                            key={level}
                                            type="button"
                                            onClick={() => setRiskLevel(level)}
                                            className={`py-2.5 text-[9px] font-black uppercase transition-all ${
                                                riskLevel === level ? "bg-primary text-white" : "bg-background text-muted-foreground hover:bg-muted"
                                            }`}
                                        >
                                            {level}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Volatility Tolerance Slider */}
                            <div className="space-y-2">
                                <div className="flex justify-between text-[11px] font-bold uppercase">
                                    <span className="text-muted-foreground">Volatility Tolerance</span>
                                    <span className="font-mono text-foreground font-bold">{volatilityTolerance}%</span>
                                </div>
                                <input
                                    type="range"
                                    min="0"
                                    max="100"
                                    step="0.5"
                                    value={volatilityTolerance}
                                    onChange={(e) => setVolatilityTolerance(parseFloat(e.target.value))}
                                    className="w-full h-[2px] bg-border appearance-none cursor-pointer accent-primary"
                                />
                            </div>

                            {/* Investment Horizon */}
                            <div className="space-y-1.5">
                                <label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground" htmlFor="horizon">
                                    Investment Horizon (Months)
                                </label>
                                <input
                                    id="horizon"
                                    type="number"
                                    min="1"
                                    max="600"
                                    value={investmentHorizon}
                                    onChange={(e) => setInvestmentHorizon(parseInt(e.target.value) || 1)}
                                    className="w-full bg-[#0A0E12] border border-[#282d39] text-white text-sm px-4 py-2.5 focus:border-[#1e5df1] focus:ring-0 outline-none font-mono"
                                />
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Sector Preferences limits */}
                <Card className="bg-card border-border shadow-none flex flex-col justify-between">
                    <div>
                        <CardHeader className="p-4 pb-2 border-b border-border/55">
                            <CardTitle className="text-xs font-bold uppercase tracking-wider text-foreground">Sector Allocation Caps</CardTitle>
                            <CardDescription className="text-[10px] text-muted-foreground uppercase font-bold">
                                Define maximum weight limits (%) per industry sector
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="p-6 space-y-6">
                            {AVAILABLE_SECTORS.map((sector) => {
                                const capVal = sectorPrefs[sector] ?? 30.0
                                return (
                                    <div key={sector} className="space-y-2">
                                        <div className="flex justify-between text-[11px] font-bold">
                                            <span className="text-muted-foreground uppercase">{sector} Limit</span>
                                            <span className="font-mono text-foreground font-bold">{capVal.toFixed(1)}%</span>
                                        </div>
                                        <input
                                            type="range"
                                            min="5"
                                            max="100"
                                            step="1"
                                            value={capVal}
                                            onChange={(e) => handleSectorChange(sector, parseFloat(e.target.value))}
                                            className="w-full h-[2px] bg-border appearance-none cursor-pointer accent-primary"
                                        />
                                    </div>
                                )
                            })}
                        </CardContent>
                    </div>

                    <div className="p-6 border-t border-border bg-card/10 flex items-center justify-between">
                        <div className="flex items-center gap-1 text-[10px] text-muted-foreground font-bold uppercase">
                            <Sliders className="size-3.5 text-primary" /> Sector Constraints Enabled
                        </div>
                        <Button
                            type="submit"
                            disabled={updating}
                            className="bg-primary text-white hover:bg-primary/90 h-10 px-6 text-xs font-black uppercase flex items-center gap-2"
                        >
                            {updating ? (
                                <>
                                    <Loader2 className="size-4 animate-spin" />
                                    Synchronizing...
                                </>
                            ) : (
                                <>
                                    <Save className="size-4" />
                                    Sync Risk Profile
                                </>
                            )}
                        </Button>
                    </div>
                </Card>
            </form>
        </div>
    )
}
