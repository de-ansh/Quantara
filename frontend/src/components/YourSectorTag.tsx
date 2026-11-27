import { usePreferredSectors } from "@/hooks/useUserProfile"

/** A small "your sector" tag when the stock's sector is one the user prefers; nothing otherwise. */
export default function YourSectorTag({ sector }: { sector: string | null | undefined }) {
    const preferred = usePreferredSectors()
    if (!sector || !preferred.has(sector)) return null
    return <span className="ml-1.5 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">your sector</span>
}
