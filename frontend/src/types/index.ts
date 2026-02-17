export type Theme = "dark" | "light" | "system"

export interface ThemeProviderProps {
    children: React.ReactNode
    defaultTheme?: Theme
    storageKey?: string
}

export interface ThemeProviderState {
    theme: Theme
    setTheme: (theme: Theme) => void
}

export interface NavItem {
    name: string
    href: string
    icon: React.ComponentType<{ className?: string }>
}

export interface PortfolioStat {
    label: string
    value: string
    trend?: string
    trendStatus?: "up" | "down" | "neutral"
    subtext?: string
    isGauge?: boolean
    isBadge?: boolean
    isSparkline?: boolean
    isVol?: boolean
}

export interface Opportunity {
    ticker: string
    name: string
    risk: string
    research: number
    signal: "up" | "up-right" | "right" | "down"
    return: string
    alignment: string
}

export interface SignalEvent {
    time: string
    type: "BULLISH" | "BEARISH" | "NEUTRAL" | "VOLATILITY"
    text: string
}
