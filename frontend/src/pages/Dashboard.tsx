import { Link } from "react-router-dom"
import PageHeader from "@/components/PageHeader"
import MarketToday from "@/components/dashboard/MarketToday"
import WatchlistPanel from "@/components/dashboard/WatchlistPanel"
import SignalsPanel from "@/components/dashboard/SignalsPanel"
import IdeasPanel from "@/components/dashboard/IdeasPanel"
import { useUserProfile } from "@/hooks/useUserProfile"
import PortfolioUpdatesCard from "@/components/PortfolioUpdatesCard"
import TrackRecordCard from "@/components/TrackRecordCard"

const today = () => new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })

/** Answers, in order: how is the market, how is my money, what's moving in what I follow, what could I look at. */
export default function Dashboard() {
    const { data: profile } = useUserProfile()
    const riskLevel = profile?.risk_level ?? "Moderate"

    return (
        <div className="p-4 md:p-6 space-y-6 max-w-[1400px] mx-auto">
            <PageHeader title="Dashboard" description={today()} />

            {profile && !profile.risk_level && (
                <p role="note" className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-2.5 text-sm text-foreground">
                    Verdicts and ideas assume a moderate risk profile.{" "}
                    <Link to="/account" className="font-medium text-primary hover:underline">Set your own</Link> to tailor them.
                </p>
            )}

            <MarketToday />
            <PortfolioUpdatesCard />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                <WatchlistPanel />
                <SignalsPanel />
            </div>

            <IdeasPanel riskLevel={riskLevel} />
            <TrackRecordCard />
        </div>
    )
}
