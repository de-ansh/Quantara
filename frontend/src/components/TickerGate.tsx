import type { ReactNode } from "react"
import { Navigate, useLocation, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { resolveTicker } from "@/lib/api"

/**
 * Pages keyed by `/:ticker` see the listing the user meant: `/research/ITC` becomes `/research/ITC.NS`
 * before the page loads, so it never analyses (or pays for a report on) an unrelated US symbol.
 */
export default function TickerGate({ children }: { children: ReactNode }) {
    const { ticker = "" } = useParams()
    const { pathname } = useLocation()
    const { data: resolved, isPending } = useQuery({
        queryKey: ["resolveTicker", ticker.toUpperCase()],
        queryFn: () => resolveTicker(ticker),
        staleTime: Infinity,
        enabled: !!ticker,
    })

    if (ticker && isPending) {
        return <p role="status" className="p-6 text-sm text-muted-foreground">Finding the listing for {ticker.toUpperCase()}…</p>
    }
    if (resolved && resolved !== ticker.toUpperCase()) {
        return <Navigate replace to={pathname.replace(/[^/]+$/, encodeURIComponent(resolved))} />
    }
    return <>{children}</>
}
