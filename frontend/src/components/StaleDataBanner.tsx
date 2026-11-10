import { useQuery } from "@tanstack/react-query"
import { AlertTriangle } from "lucide-react"
import apiClient from "@/lib/api"
import { timeAgo } from "@/lib/utils"

interface DataHealth {
    prices_updated_at: string | null
    prices_stale: boolean
    directory_updated_at: string | null
    directory_stale: boolean
}

/** Says so when a background job has stopped, instead of letting old prices pass for live ones. */
export default function StaleDataBanner() {
    const { data } = useQuery({
        queryKey: ["dataHealth"],
        queryFn: async () => (await apiClient.get<DataHealth>("/market/data-health")).data,
        refetchInterval: 5 * 60 * 1000,
    })
    if (!data?.prices_stale && !data?.directory_stale) return null
    return (
        <div role="alert" className="flex items-center gap-2 px-4 py-2 text-xs bg-amber-500/15 text-amber-600 dark:text-amber-400 border-b border-amber-500/30 shrink-0">
            <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
            <span>
                {data.prices_stale && data.prices_updated_at
                    ? `Prices last updated ${timeAgo(data.prices_updated_at)}: the price job has stopped, so prices, risk and verdicts may be out of date. Restart the backend.`
                    : "The stock list hasn't refreshed in over two days; new listings may be missing."}
            </span>
        </div>
    )
}
