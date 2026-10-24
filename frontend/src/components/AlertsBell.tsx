import { useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Bell } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn, timeAgo } from "@/lib/utils"
import api from "@/lib/api"
import { useAuth } from "@/context/AuthContext"

interface WatchlistAlert {
    id: number
    kind: "signal" | "price"
    message: string | null
    ticker: string
    signal_type: string
    strength: number
    detected_at: string
    unread: boolean
}

const KEY = ["watchlistAlerts"]

export default function AlertsBell() {
    const queryClient = useQueryClient()
    const { token } = useAuth()
    const { data } = useQuery({
        enabled: !!token,
        queryKey: KEY,
        queryFn: async () => {
            const res = await api.get<{ alerts: WatchlistAlert[]; unread_count: number }>("/watchlist/alerts")
            return res.data
        },
        refetchInterval: 60_000,
    })
    // Tolerate partial responses: a header widget must never take the page down
    const alerts = data?.alerts ?? []
    const unread = data?.unread_count ?? 0

    const handleOpenChange = (open: boolean) => {
        if (!open || unread === 0) return
        // Mark read on the server; the open list keeps its highlights until the next refetch
        api.post("/watchlist/alerts/seen")
            .then(() => queryClient.setQueryData(KEY, { alerts, unread_count: 0 }))
            .catch(() => {})
    }

    return (
        <DropdownMenu onOpenChange={handleOpenChange}>
            <DropdownMenuTrigger asChild>
                <Button
                    variant="ghost"
                    size="icon"
                    className="relative text-muted-foreground hover:text-foreground"
                    aria-label={unread ? `Watchlist alerts, ${unread} unread` : "Watchlist alerts"}
                >
                    <Bell className="h-5 w-5" />
                    {unread > 0 && (
                        <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full bg-q-risk-high text-white text-[9px] font-bold flex items-center justify-center">
                            {unread > 9 ? "9+" : unread}
                        </span>
                    )}
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-80">
                <DropdownMenuLabel className="text-xs uppercase tracking-wider">Alerts · 7 days</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {alerts.length === 0 ? (
                    <p className="px-3 py-4 text-xs text-muted-foreground">
                        No signals for watched tickers and no price alerts triggered.
                    </p>
                ) : (
                    <ul className="max-h-80 overflow-y-auto">
                        {alerts.map(a => (
                            <li key={`${a.kind}-${a.id}`}>
                                <Link
                                    to={`/research/${a.ticker}`}
                                    className={cn("flex items-start justify-between gap-2 px-3 py-2 text-xs hover:bg-muted", a.unread && "bg-primary/5")}
                                >
                                    <span>
                                        <span className="font-bold font-mono text-foreground">{a.ticker}</span>{" "}
                                        <span className="text-muted-foreground">
                                            {a.kind === "price"
                                                ? a.message ?? a.signal_type.replace(/_/g, " ")
                                                : `${a.signal_type.replace(/_/g, " ")} · strength ${Math.round(a.strength)}`}
                                        </span>
                                    </span>
                                    <span className="shrink-0 text-[10px] text-muted-foreground font-mono">
                                        {a.unread && <span className="mr-1 inline-block size-1.5 rounded-full bg-primary align-middle" />}
                                        {timeAgo(a.detected_at)}
                                    </span>
                                </Link>
                            </li>
                        ))}
                    </ul>
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    )
}
