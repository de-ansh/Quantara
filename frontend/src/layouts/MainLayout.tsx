import { useState, useEffect } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import CommandPalette from "@/components/CommandPalette"
import ChatAssistant from "@/components/ChatAssistant"
import StaleDataBanner from "@/components/StaleDataBanner"
import AlertsBell from "@/components/AlertsBell"
import MarketTicker from "@/components/MarketTicker"
import {
    LayoutDashboard,
    Search,
    Activity,
    Settings,
    User,
    ShieldCheck,
    LogOut,
    Sun,
    Moon,
    Menu,
    X,
    TrendingUp,
    AlertTriangle,
    Briefcase,
    Columns3,
    Globe,
    CalendarDays,
    Calculator,
    Receipt,
    FileText,
    Mic,
    Handshake,
    Layers,
    MessagesSquare,
} from "lucide-react"
import { useTheme } from "@/context/use-theme"
import { cn } from "@/lib/utils"
import type { NavItem } from "@/types"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Separator } from "@/components/ui/separator"
import { useAuth } from "@/context/AuthContext"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

const PUBLIC_ROUTES = ["/login", "/register"]

// Grouped by what the user is doing: checking the market, researching a stock, or managing their money
const navigation: { group: string; items: NavItem[] }[] = [
    { group: "Overview", items: [
        { name: "Dashboard", href: "/", icon: LayoutDashboard },
        { name: "Markets", href: "/markets", icon: Globe },
        { name: "Events", href: "/events", icon: CalendarDays },
    ] },
    { group: "Research", items: [
        { name: "Find stocks", href: "/explorer", icon: Search },
        { name: "Compare", href: "/compare", icon: Columns3 },
        { name: "Risk breakdown", href: "/risk", icon: AlertTriangle },
        { name: "Signals", href: "/signals", icon: Activity },
        { name: "Indices & ETFs", href: "/indices", icon: Layers },
        { name: "Filings", href: "/filings", icon: FileText },
        { name: "Earnings calls", href: "/concalls", icon: Mic },
        { name: "Bulk & block deals", href: "/deals", icon: Handshake },
    ] },
    { group: "Your money", items: [
        { name: "Portfolios", href: "/portfolios", icon: Briefcase },
        { name: "Simulation", href: "/simulation", icon: TrendingUp },
        { name: "Tax harvesting", href: "/tax", icon: Receipt },
        { name: "Calculators", href: "/calculators", icon: Calculator },
    ] },
    { group: "Assistant", items: [
        { name: "Chats", href: "/gallery", icon: MessagesSquare },
    ] },
    { group: "Account", items: [
        { name: "Settings", href: "/settings", icon: Settings },
        { name: "Account", href: "/account", icon: User },
    ] },
]

interface MainLayoutProps {
    children: React.ReactNode
}

export default function MainLayout({ children }: MainLayoutProps) {
    const { theme, setTheme } = useTheme()
    const { user, logout } = useAuth()
    const location = useLocation()
    const navigate = useNavigate()
    const [sidebarOpen, setSidebarOpen] = useState(true)
    // Phones get an off-canvas drawer instead; it closes whenever the route changes
    const [mobileNavOpen, setMobileNavOpen] = useState(false)
    const showLabels = sidebarOpen || mobileNavOpen
    const [navPath, setNavPath] = useState(location.pathname)
    if (navPath !== location.pathname) {
        setNavPath(location.pathname)
        setMobileNavOpen(false)
    }
    const [commandOpen, setCommandOpen] = useState(false)

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                e.preventDefault()
                setCommandOpen(prev => !prev)
            }
        }
        window.addEventListener("keydown", handleKeyDown)
        return () => window.removeEventListener("keydown", handleKeyDown)
    }, [])

    const isPublicRoute = PUBLIC_ROUTES.includes(location.pathname)

    if (isPublicRoute) {
        return (
            <div className="min-h-screen bg-background text-foreground flex flex-col font-sans">
                <main className="flex-1 overflow-y-auto bg-background relative flex flex-col custom-scrollbar">
                    <div className="flex-1 flex flex-col">
                        {children}
                    </div>
                </main>
            </div>
        )
    }

    // Viewport-height shell: sidebar and header stay put, only <main> scrolls
    return (
        <div className="h-dvh bg-background text-foreground flex overflow-hidden">
            {mobileNavOpen && (
                <div className="fixed inset-0 z-30 bg-black/60 md:hidden" onClick={() => setMobileNavOpen(false)} aria-hidden="true" />
            )}
            {/* Sidebar: drawer on phones, collapsible column from md up */}
            <aside
                className={cn(
                    "bg-card border-r border-border transition-all duration-300 flex flex-col shrink-0",
                    "fixed inset-y-0 left-0 z-40 w-64 md:static md:z-auto md:translate-x-0",
                    mobileNavOpen ? "translate-x-0" : "-translate-x-full",
                    sidebarOpen ? "md:w-64" : "md:w-16"
                )}
            >
                <div className="h-16 flex items-center px-4 border-b border-border shrink-0">
                    <ShieldCheck className="h-6 w-6 text-primary shrink-0" />
                    {showLabels && <span className="ml-3 font-semibold text-lg tracking-tight">Quantara</span>}
                </div>

                <nav className="flex-1 overflow-y-auto py-3 custom-scrollbar" aria-label="Main">
                    {navigation.map(({ group, items }) => (
                        <div key={group} className="mb-3">
                            {showLabels
                                ? <p className="px-4 pb-1 text-[11px] font-medium text-muted-foreground">{group}</p>
                                : <Separator className="mx-3 my-2 w-auto" />}
                            <ul className="px-2 space-y-0.5">
                                {items.map(item => {
                                    // A section is active on its own pages too (/portfolios/3, /risk/ITC.NS)
                                    const active = item.href === "/" ? location.pathname === "/" : location.pathname.startsWith(item.href)
                                    return (
                                        <li key={item.href}>
                                            <Link
                                                to={item.href}
                                                aria-current={active ? "page" : undefined}
                                                title={showLabels ? undefined : item.name}
                                                className={cn(
                                                    "flex items-center px-2 py-1.5 text-sm rounded-md transition-colors",
                                                    active ? "bg-primary/10 text-primary font-medium" : "text-muted-foreground hover:bg-muted hover:text-foreground",
                                                )}
                                            >
                                                <item.icon className={cn("h-4 w-4 shrink-0", showLabels ? "mr-3" : "mx-auto")} aria-hidden="true" />
                                                {showLabels ? item.name : <span className="sr-only">{item.name}</span>}
                                            </Link>
                                        </li>
                                    )
                                })}
                            </ul>
                        </div>
                    ))}
                </nav>

                <div className="p-4 border-t border-border bg-muted/50">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => (mobileNavOpen ? setMobileNavOpen(false) : setSidebarOpen(!sidebarOpen))}
                        className="w-full justify-start text-muted-foreground hover:text-foreground px-2"
                    >
                        {showLabels ? <X className="h-5 w-5 mr-3" /> : <Menu className="h-5 w-5 mx-auto" />}
                        {showLabels && (mobileNavOpen ? "Close menu" : "Collapse sidebar")}
                    </Button>
                </div>
            </aside>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                {/* Header */}
                <header className="h-16 bg-card border-b border-border flex items-center justify-between gap-2 px-3 md:px-6 shrink-0 z-10 transition-colors">
                    <div className="flex-1 flex items-center gap-2 min-w-0">
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setMobileNavOpen(true)}
                            className="md:hidden shrink-0 text-muted-foreground"
                            aria-label="Open navigation"
                        >
                            <Menu className="h-5 w-5" />
                        </Button>
                        <button
                            type="button"
                            onClick={() => setCommandOpen(true)}
                            className="relative w-full max-w-md group flex items-center justify-between bg-muted/50 hover:bg-muted/80 border border-border rounded-md px-3 py-1.5 text-[13px] text-muted-foreground transition-all cursor-pointer text-left focus:outline-none focus:ring-1 focus:ring-primary"
                        >
                            <div className="flex items-center min-w-0 mr-2">
                                <Search className="size-4 mr-2.5 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                                <span className="truncate">Search stocks and ETFs…</span>
                            </div>
                            <kbd className="hidden sm:inline-flex items-center gap-0.5 pointer-events-none h-5 select-none rounded border border-border bg-background px-1.5 font-mono text-[11px] font-bold text-muted-foreground">
                                <span className="text-xs">⌘</span>K
                            </kbd>
                        </button>
                    </div>

                    <div className="flex items-center gap-1 md:gap-4 shrink-0">
                        <MarketTicker />

                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                            className="hidden sm:inline-flex text-muted-foreground hover:text-foreground transition-transform active:scale-95"
                            title="Switch light/dark" aria-label="Switch light or dark theme"
                        >
                            {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                        </Button>
                        <AlertsBell />
                        <Separator orientation="vertical" className="h-6" />
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <button type="button" aria-label="Account menu" className="flex items-center space-x-3 group cursor-pointer rounded-md select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
                                    <div className="hidden sm:flex flex-col items-end mr-1">
                                        <span className="text-sm font-bold tracking-tight text-foreground">{user?.email?.split('@')[0] || "Trader"}</span>
                                    </div>
                                    <Avatar className="h-9 w-9 border border-primary/20 ring-2 ring-transparent group-hover:ring-primary/20 transition-all">
                                        <AvatarFallback className="bg-primary/10 text-primary font-bold uppercase">
                                            {user?.email?.[0] || "U"}
                                        </AvatarFallback>
                                    </Avatar>
                                </button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-56">
                                <DropdownMenuLabel className="font-normal">
                                    <div className="flex flex-col space-y-1">
                                        <p className="text-xs font-bold leading-none text-foreground">{user?.email || "Analyst Session"}</p>
                                        <p className="text-[11px] leading-none text-muted-foreground font-mono">
                                            {user?.risk_level ? `${user.risk_level} risk profile` : "Risk profile not set"}
                                        </p>
                                    </div>
                                </DropdownMenuLabel>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem onClick={() => navigate("/account")}>
                                    <User className="mr-2 h-4 w-4" />
                                    <span>Account</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => navigate("/settings")}>
                                    <Settings className="mr-2 h-4 w-4" />
                                    <span>Settings</span>
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                    onClick={() => {
                                        logout()
                                        navigate("/login")
                                    }}
                                    className="text-destructive focus:bg-destructive/10 focus:text-destructive"
                                >
                                    <LogOut className="mr-2 h-4 w-4" />
                                    <span>Sign out</span>
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>
                </header>

                <StaleDataBanner />

                {/* Content Viewport */}
                <main className="flex-1 overflow-y-auto bg-background/50 relative flex flex-col custom-scrollbar">
                    <div className="flex-1">
                        {children}
                    </div>

                    <footer className="py-2.5 px-6 border-t border-border mt-auto bg-card/30 shrink-0">
                        <p className="text-[11px] text-muted-foreground text-center">
                            Research to help you decide, not financial advice. Prices can be delayed.
                        </p>
                    </footer>
                </main>
            </div>
            <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
            <ChatAssistant />
        </div>
    )
}
