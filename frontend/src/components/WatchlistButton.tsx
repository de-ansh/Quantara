import { Star } from "lucide-react"
import { cn } from "@/lib/utils"
import { useToggleWatch, useWatchlist } from "@/hooks/useWatchlist"

export default function WatchlistButton({ ticker, className }: { ticker: string; className?: string }) {
    const { data: watchlist = [] } = useWatchlist()
    const toggle = useToggleWatch()
    const watched = watchlist.some(w => w.ticker === ticker.toUpperCase())
    const label = watched ? `Remove ${ticker} from watchlist` : `Add ${ticker} to watchlist`

    return (
        <button
            type="button"
            onClick={(e) => {
                e.stopPropagation()
                toggle.mutate({ ticker, watched })
            }}
            disabled={toggle.isPending}
            title={toggle.isError ? "Could not update watchlist" : label}
            aria-label={label}
            aria-pressed={watched}
            className={cn(
                "inline-flex items-center justify-center rounded-sm p-1 transition-colors disabled:opacity-50",
                watched ? "text-amber-400 hover:text-amber-300" : "text-muted-foreground hover:text-foreground",
                className
            )}
        >
            <Star className={cn("size-4", watched && "fill-current")} />
        </button>
    )
}
