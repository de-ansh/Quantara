import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}

/** Parse an API timestamp; naive ISO strings from the backend are UTC. */
export function parseUtc(iso: string): Date {
    return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`)
}

/** "just now", "5m ago", "3h ago", "2d ago". */
export function timeAgo(iso: string, now: number = Date.now()): string {
    const minutes = Math.max(0, Math.round((now - parseUtc(iso).getTime()) / 60000))
    if (minutes < 1) return "just now"
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.round(minutes / 60)
    if (hours < 48) return `${hours}h ago`
    return `${Math.round(hours / 24)}d ago`
}
