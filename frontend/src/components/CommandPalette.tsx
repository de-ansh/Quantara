import React, { useState, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import apiClient from "@/lib/api"
import {
    Search,
    BarChart3,
    AlertTriangle,
    LayoutDashboard,
    Activity,
    TrendingUp,
    Settings,
    User,
    ArrowRight,
    Sparkles,
    ShieldAlert,
    X,
    Loader2
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"

interface StockItem {
    ticker: string
    name: string
    price: string
    cap: string
    risk: number
    signal: string
    alpha: string
    status: string
}

interface CommandPaletteProps {
    open: boolean
    onOpenChange: (open: boolean) => void
}

const SYSTEM_PAGES = [
    { name: "Portfolio Dashboard", href: "/", icon: LayoutDashboard, category: "Platform" },
    { name: "Research Explorer", href: "/explorer", icon: Search, category: "Platform" },
    { name: "Signal Intelligence", href: "/signals", icon: Activity, category: "Intelligence" },
    { name: "Risk & Correlation Engine", href: "/risk", icon: AlertTriangle, category: "Risk" },
    { name: "Simulation & MPT Studio", href: "/simulation", icon: TrendingUp, category: "Portfolio" },
    { name: "Account Profile", href: "/account", icon: User, category: "Account" },
    { name: "System Settings & Keys", href: "/settings", icon: Settings, category: "Account" },
]

const CORE_ASSETS = [
    { ticker: "NVDA", name: "NVIDIA Corp.", sector: "Semiconductors" },
    { ticker: "AAPL", name: "Apple Inc.", sector: "Consumer Tech" },
    { ticker: "MSFT", name: "Microsoft Corp.", sector: "Enterprise Software" },
    { ticker: "TSLA", name: "Tesla Inc.", sector: "Automotive / Clean Energy" },
    { ticker: "RELIANCE.NS", name: "Reliance Industries Ltd", sector: "Energy & Conglomerate (NSE)" },
    { ticker: "TCS.NS", name: "Tata Consultancy Services", sector: "IT Services (NSE)" },
    { ticker: "HDFCBANK.NS", name: "HDFC Bank Ltd", sector: "Financial Services (NSE)" },
    { ticker: "INFY.NS", name: "Infosys Ltd", sector: "IT Consulting (NSE)" },
    { ticker: "GOOGL", name: "Alphabet Inc.", sector: "Digital Advertising" },
    { ticker: "AMZN", name: "Amazon.com Inc.", sector: "E-Commerce / Cloud" },
    { ticker: "TLT", name: "iShares 20+ Year Treasury Bond", sector: "Macro Hedge (Rates)" },
    { ticker: "GLD", name: "SPDR Gold Shares", sector: "Commodity Hedge" },
]

export default function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
    const navigate = useNavigate()
    const [query, setQuery] = useState("")
    const [selectedIndex, setSelectedIndex] = useState(0)
    const inputRef = useRef<HTMLInputElement>(null)

    // Reset selection and query when opening
    useEffect(() => {
        if (open) {
            setQuery("")
            setSelectedIndex(0)
            setTimeout(() => inputRef.current?.focus(), 50)
        }
    }, [open])

    // Query backend for stocks
    const { data, isLoading } = useQuery({
        queryKey: ["commandSearch", query],
        queryFn: async () => {
            if (!query.trim()) return []
            const res = await apiClient.get<{ stocks: StockItem[] }>("/stocks/search", {
                params: { query: query.trim() }
            })
            return res.data.stocks || []
        },
        enabled: open && query.trim().length > 0,
        staleTime: 30000,
    })

    const stockResults: StockItem[] = data || []
    const trimmed = query.trim().toUpperCase()

    // Build selectable actions list
    type ActionItem = {
        id: string
        type: "stock-research" | "stock-risk" | "direct-research" | "direct-risk" | "page" | "core"
        title: string
        subtitle?: string
        badge?: string
        href: string
        icon: React.ComponentType<{ className?: string }>
    }

    const selectableItems: ActionItem[] = []

    if (trimmed.length > 0) {
        // Direct jump options for typed ticker
        selectableItems.push({
            id: `direct-res-${trimmed}`,
            type: "direct-research",
            title: `Research Thesis: ${trimmed}`,
            subtitle: `Deep dive into SEC fundamentals, thesis & sentiment for ${trimmed}`,
            badge: "STOCK DETAIL",
            href: `/research/${trimmed}`,
            icon: BarChart3
        })
        selectableItems.push({
            id: `direct-risk-${trimmed}`,
            type: "direct-risk",
            title: `Risk Analysis: ${trimmed}`,
            subtitle: `Factor decomposition, peer correlation & drawdown for ${trimmed}`,
            badge: "RISK MODEL",
            href: `/risk/${trimmed}`,
            icon: ShieldAlert
        })

        // Matched stock database results
        stockResults.forEach((s) => {
            selectableItems.push({
                id: `stock-res-${s.ticker}`,
                type: "stock-research",
                title: `${s.ticker} — ${s.name}`,
                subtitle: `Price: ${s.price} | Cap: ${s.cap} | Risk: ${s.risk.toFixed(1)}/100`,
                badge: s.signal,
                href: `/research/${s.ticker}`,
                icon: BarChart3
            })
        })

        // Filter system pages by query
        SYSTEM_PAGES.filter(p => p.name.toLowerCase().includes(query.toLowerCase())).forEach(p => {
            selectableItems.push({
                id: `page-${p.href}`,
                type: "page",
                title: p.name,
                subtitle: `Navigate to ${p.name}`,
                badge: p.category,
                href: p.href,
                icon: p.icon
            })
        })
    } else {
        // Default when query is empty: Core Assets
        CORE_ASSETS.forEach(a => {
            selectableItems.push({
                id: `core-${a.ticker}`,
                type: "core",
                title: `${a.ticker} — ${a.name}`,
                subtitle: `${a.sector} · Quick Asset Inspection`,
                badge: "QUICK TICKER",
                href: `/research/${a.ticker}`,
                icon: BarChart3
            })
        })

        // Default navigation
        SYSTEM_PAGES.forEach(p => {
            selectableItems.push({
                id: `page-${p.href}`,
                type: "page",
                title: p.name,
                subtitle: `Jump to platform view`,
                badge: p.category,
                href: p.href,
                icon: p.icon
            })
        })
    }

    // Keep selectedIndex in bounds
    useEffect(() => {
        setSelectedIndex(0)
    }, [query, stockResults.length])

    const handleNavigate = (href: string) => {
        onOpenChange(false)
        navigate(href)
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "ArrowDown") {
            e.preventDefault()
            setSelectedIndex(prev => (selectableItems.length > 0 ? (prev + 1) % selectableItems.length : 0))
        } else if (e.key === "ArrowUp") {
            e.preventDefault()
            setSelectedIndex(prev => (selectableItems.length > 0 ? (prev - 1 + selectableItems.length) % selectableItems.length : 0))
        } else if (e.key === "Enter") {
            e.preventDefault()
            if (selectableItems[selectedIndex]) {
                handleNavigate(selectableItems[selectedIndex].href)
            }
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl p-0 gap-0 overflow-hidden bg-card border border-border shadow-2xl rounded-lg">
                <DialogTitle className="sr-only">Universal Research Search</DialogTitle>
                <DialogDescription className="sr-only">
                    Search stocks, tickers, financial models, and system routes across Quantara
                </DialogDescription>

                {/* Search Input Bar */}
                <div className="flex items-center px-4 border-b border-border bg-background/50 h-14 shrink-0">
                    {isLoading ? (
                        <Loader2 className="size-4 text-primary animate-spin mr-3 shrink-0" />
                    ) : (
                        <Search className="size-4 text-muted-foreground mr-3 shrink-0" />
                    )}
                    <input
                        ref={inputRef}
                        type="text"
                        placeholder="Search tickers (e.g. NVDA, TLT), company names, or views..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={handleKeyDown}
                        className="flex-1 bg-transparent border-none outline-none text-sm font-sans placeholder:text-muted-foreground text-foreground h-full"
                    />
                    {query && (
                        <button
                            onClick={() => setQuery("")}
                            className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground mr-2"
                        >
                            <X className="size-3.5" />
                        </button>
                    )}
                    <Badge variant="outline" className="text-[10px] font-mono font-bold tracking-widest text-muted-foreground border-border px-1.5 py-0.5">
                        ESC
                    </Badge>
                </div>

                {/* Results Container */}
                <div className="max-h-[380px] overflow-y-auto p-2 space-y-1 custom-scrollbar">
                    {selectableItems.length === 0 ? (
                        <div className="py-12 text-center text-xs text-muted-foreground font-mono uppercase tracking-widest">
                            No assets or commands matching "{query}"
                        </div>
                    ) : (
                        selectableItems.map((item, idx) => {
                            const isSelected = idx === selectedIndex
                            const IconComponent = item.icon
                            return (
                                <div
                                    key={item.id}
                                    onClick={() => handleNavigate(item.href)}
                                    onMouseEnter={() => setSelectedIndex(idx)}
                                    className={cn(
                                        "flex items-center justify-between px-3 py-2.5 rounded-md cursor-pointer transition-colors group",
                                        isSelected
                                            ? "bg-primary text-primary-foreground shadow-sm"
                                            : "hover:bg-muted/70 text-foreground"
                                    )}
                                >
                                    <div className="flex items-center gap-3 min-w-0">
                                        <div
                                            className={cn(
                                                "p-1.5 rounded shrink-0 transition-colors",
                                                isSelected
                                                    ? "bg-primary-foreground/20 text-primary-foreground"
                                                    : "bg-muted text-muted-foreground group-hover:text-foreground"
                                            )}
                                        >
                                            <IconComponent className="size-4" />
                                        </div>
                                        <div className="min-w-0">
                                            <div className="flex items-center gap-2">
                                                <span className="text-xs font-bold font-mono tracking-tight truncate">
                                                    {item.title}
                                                </span>
                                            </div>
                                            {item.subtitle && (
                                                <p
                                                    className={cn(
                                                        "text-[10px] truncate font-medium",
                                                        isSelected ? "text-primary-foreground/80" : "text-muted-foreground"
                                                    )}
                                                >
                                                    {item.subtitle}
                                                </p>
                                            )}
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-2 shrink-0 ml-3">
                                        {item.badge && (
                                            <span
                                                className={cn(
                                                    "text-[9px] font-black font-mono tracking-wider px-1.5 py-0.5 rounded uppercase border",
                                                    isSelected
                                                        ? "border-primary-foreground/30 bg-primary-foreground/10 text-primary-foreground"
                                                        : "border-border bg-background text-muted-foreground"
                                                )}
                                            >
                                                {item.badge}
                                            </span>
                                        )}
                                        <ArrowRight
                                            className={cn(
                                                "size-3.5 transition-transform",
                                                isSelected ? "translate-x-0.5 opacity-100" : "opacity-0 group-hover:opacity-60"
                                            )}
                                        />
                                    </div>
                                </div>
                            )
                        })
                    )}
                </div>

                {/* Command Palette Footer */}
                <div className="px-4 py-2 border-t border-border bg-muted/40 flex items-center justify-between text-[10px] font-mono text-muted-foreground font-bold uppercase tracking-wider shrink-0">
                    <div className="flex items-center gap-3">
                        <span><kbd className="bg-background px-1 py-0.5 border border-border rounded">↑</kbd> <kbd className="bg-background px-1 py-0.5 border border-border rounded">↓</kbd> Navigate</span>
                        <span><kbd className="bg-background px-1 py-0.5 border border-border rounded">↵</kbd> Select</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-primary font-black">
                        <Sparkles className="size-3" />
                        <span>Quantara Omnibar</span>
                    </div>
                </div>
            </DialogContent>
        </Dialog>
    )
}
