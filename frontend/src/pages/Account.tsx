import { useState, useEffect } from "react"
import { useQueryClient } from "@tanstack/react-query"
import apiClient, { apiErrorDetail } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import PageHeader from "@/components/PageHeader"
import Panel, { PanelSkeleton } from "@/components/Panel"
import ChangePasswordCard from "@/components/ChangePasswordCard"
import TwoFactorCard from "@/components/TwoFactorCard"
import RecentActivityCard from "@/components/RecentActivityCard"
import YourDataCard from "@/components/YourDataCard"
import { Save } from "lucide-react"
import type { UserProfile } from "@/hooks/useUserProfile"

// The sectors stocks are filed under (Yahoo's names)
const SECTORS = ["Communication Services", "Consumer Discretionary", "Consumer Staples", "Energy", "Financials", "Healthcare",
    "Industrials", "Materials", "Real Estate", "Technology", "Utilities"]

export default function Account() {
    const [user, setUser] = useState<UserProfile | null>(null)
    const [loading, setLoading] = useState(true)
    const [updating, setUpdating] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState(false)

    const [riskLevel, setRiskLevel] = useState("Moderate")
    const [volatilityTolerance, setVolatilityTolerance] = useState(50)
    const [horizon, setHorizon] = useState(12)
    const [sectors, setSectors] = useState<Set<string>>(new Set())
    const queryClient = useQueryClient()

    useEffect(() => {
        const fetchProfile = async () => {
            try {
                const res = await apiClient.get<UserProfile>("/users/me")
                const data = res.data
                setUser(data)
                setRiskLevel(data.risk_level || "Moderate")
                setVolatilityTolerance(data.volatility_tolerance ?? 50)
                setHorizon(data.investment_horizon ?? 12)
                setSectors(new Set(Object.entries(data.sector_preferences ?? {}).filter(([, v]) => v > 0).map(([k]) => k)))
            } catch {
                setError("Couldn't load your profile. Try signing in again.")
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
                volatility_tolerance: volatilityTolerance,
                investment_horizon: horizon,
                sector_preferences: Object.fromEntries([...sectors].map(s => [s, 1])),
            }

            const res = await apiClient.post<UserProfile>("/users/risk-profile", payload)
            setUser(res.data)
            queryClient.invalidateQueries({ queryKey: ["userProfile"] })
            queryClient.invalidateQueries({ queryKey: ["portfolioBalance"] })
            setSuccess(true)
            setTimeout(() => setSuccess(false), 3000)
        } catch (err) {
            setError(apiErrorDetail(err) ?? "Couldn't save. Please try again.")
        } finally {
            setUpdating(false)
        }
    }

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-4xl mx-auto">
            <PageHeader title="Account" description={user ? <>Signed in as <span className="text-foreground">{user.email}</span>.</> : "Your risk profile, password, sign-in security and data."} />

            {loading ? <Panel id="risk-profile" title="Risk profile"><PanelSkeleton rows={3} /></Panel> : (
                <Panel id="risk-profile" title="Risk profile"
                    description="Verdicts, ideas and portfolio updates are judged against this: a stock riskier than your level counts against it.">
                    <form onSubmit={handleSave} className="p-4 space-y-5">
                        <div className="space-y-1.5">
                            <span id="risk-level-label" className="text-sm font-medium">Risk level</span>
                            <div role="group" aria-labelledby="risk-level-label" className="grid grid-cols-3 gap-2 max-w-md">
                                {["Conservative", "Moderate", "Aggressive"].map(level => (
                                    <button key={level} type="button" aria-pressed={riskLevel === level} onClick={() => setRiskLevel(level)}
                                        className={cn("rounded-md border px-2 py-2 text-sm", riskLevel === level ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>
                                        {level}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <div className="space-y-1.5 max-w-md">
                            <div className="flex justify-between text-sm">
                                <label htmlFor="volatility" className="font-medium">How much price swing you accept</label>
                                <span className="font-mono tabular-nums">{volatilityTolerance}</span>
                            </div>
                            <input id="volatility" type="range" min={0} max={100} step={1} value={volatilityTolerance}
                                onChange={e => setVolatilityTolerance(Number(e.target.value))} className="w-full accent-primary" />
                            <p className="text-xs text-muted-foreground">0 avoids volatile stocks; 100 doesn't mind them. Weighs how ideas are ranked.</p>
                        </div>
                        <div className="space-y-1.5 max-w-md">
                            <label htmlFor="horizon" className="text-sm font-medium">When you'll need the money</label>
                            <div className="flex items-center gap-2">
                                <input id="horizon" type="number" min={1} max={600} step={1} value={horizon}
                                    onChange={e => setHorizon(Math.max(1, Math.round(Number(e.target.value) || 1)))}
                                    className="w-24 rounded-md border border-border bg-background px-2 py-1.5 text-sm font-mono tabular-nums" />
                                <span className="text-sm text-muted-foreground">months from now</span>
                            </div>
                            <p className="text-xs text-muted-foreground">Under 36 months, the balance check's starting mix is one step more cautious than your risk level. A mix you've saved isn't changed.</p>
                        </div>
                        <fieldset className="space-y-1.5">
                            <legend className="text-sm font-medium">Sectors you prefer</legend>
                            <div className="flex flex-wrap gap-2">
                                {SECTORS.map(sector => (
                                    <button key={sector} type="button" aria-pressed={sectors.has(sector)}
                                        onClick={() => setSectors(prev => {
                                            const next = new Set(prev)
                                            if (next.has(sector)) next.delete(sector); else next.add(sector)
                                            return next
                                        })}
                                        className={cn("rounded-md border px-2 py-1 text-xs", sectors.has(sector) ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground")}>
                                        {sector}
                                    </button>
                                ))}
                            </div>
                            <p className="text-xs text-muted-foreground">Marked "your sector" in Ideas and Find stocks. It doesn't change any scores.</p>
                        </fieldset>
                        {error && <p role="alert" className="text-sm text-q-risk-high">{error}</p>}
                        {success && <p role="status" className="text-sm text-q-risk-low">Saved.</p>}
                        <Button type="submit" disabled={updating || !user} className="gap-1.5">
                            <Save className="size-4" /> {updating ? "Saving…" : "Save risk profile"}
                        </Button>
                    </form>
                </Panel>
            )}

            <ChangePasswordCard />
            <TwoFactorCard />
            <RecentActivityCard />
            <YourDataCard />
        </div>
    )
}
