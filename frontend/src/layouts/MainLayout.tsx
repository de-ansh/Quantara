import { useState } from "react"
import { Link, useLocation } from "react-router-dom"
import {
    LayoutDashboard,
    BarChart3,
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
    AlertTriangle
} from "lucide-react"
import { useTheme } from "@/context/use-theme"
import { cn } from "@/lib/utils"
import type { NavItem } from "@/types"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Separator } from "@/components/ui/separator"
import { useAuth } from "@/context/AuthContext"

const PUBLIC_ROUTES = ["/login", "/register"]

const navigation: NavItem[] = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Stock Detail", href: "/research", icon: BarChart3 },
    { name: "Research Explorer", href: "/explorer", icon: Search },
    { name: "Signal Monitor", href: "/signals", icon: Activity },
    { name: "Risk Breakdown", href: "/risk", icon: AlertTriangle },
    { name: "Simulation", href: "/simulation", icon: TrendingUp },
]

const adminNavigation: NavItem[] = [
    { name: "Settings", href: "/settings", icon: Settings },
    { name: "Account", href: "/account", icon: User },
]

interface MainLayoutProps {
    children: React.ReactNode
}

export default function MainLayout({ children }: MainLayoutProps) {
    const { theme, setTheme } = useTheme()
    const { user } = useAuth()
    const location = useLocation()
    const [sidebarOpen, setSidebarOpen] = useState(true)

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

    return (
        <div className="min-h-screen bg-background text-foreground flex overflow-hidden">
            {/* Sidebar */}
            <aside
                className={cn(
                    "bg-card border-r border-border transition-all duration-300 flex flex-col shrink-0",
                    sidebarOpen ? "w-64" : "w-16"
                )}
            >
                <div className="h-16 flex items-center px-4 border-b border-border shrink-0">
                    <ShieldCheck className="h-6 w-6 text-primary shrink-0" />
                    {sidebarOpen && <span className="ml-3 font-bold text-lg tracking-tight">QUANTARA</span>}
                </div>

                <nav className="flex-1 overflow-y-auto py-4 custom-scrollbar">
                    <div className="px-2 space-y-1">
                        {navigation.map((item) => (
                            <Link
                                key={item.name}
                                to={item.href}
                                className={cn(
                                    "flex items-center px-2 py-2 text-sm font-medium rounded-md transition-colors",
                                    location.pathname === item.href
                                        ? "bg-primary/10 text-primary border-r-2 border-primary rounded-r-none"
                                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                                )}
                            >
                                <item.icon className={cn("h-5 w-5 shrink-0", sidebarOpen ? "mr-3" : "mx-auto")} />
                                {sidebarOpen && item.name}
                            </Link>
                        ))}
                    </div>

                    <div className="mt-8 px-4 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {sidebarOpen ? "System" : "—"}
                    </div>

                    <div className="px-2 space-y-1 mt-2">
                        {adminNavigation.map((item) => (
                            <Link
                                key={item.name}
                                to={item.href}
                                className={cn(
                                    "flex items-center px-2 py-2 text-sm font-medium rounded-md transition-colors",
                                    location.pathname === item.href
                                        ? "bg-primary/10 text-primary border-r-2 border-primary rounded-r-none"
                                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                                )}
                            >
                                <item.icon className={cn("h-5 w-5 shrink-0", sidebarOpen ? "mr-3" : "mx-auto")} />
                                {sidebarOpen && item.name}
                            </Link>
                        ))}
                    </div>
                </nav>

                <div className="p-4 border-t border-border bg-muted/50">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSidebarOpen(!sidebarOpen)}
                        className="w-full justify-start text-muted-foreground hover:text-foreground px-2"
                    >
                        {sidebarOpen ? <X className="h-5 w-5 mr-3" /> : <Menu className="h-5 w-5 mx-auto" />}
                        {sidebarOpen && "Collapse Sidebar"}
                    </Button>
                </div>
            </aside>

            {/* Main Content Area */}
            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                {/* Header */}
                <header className="h-16 bg-card border-b border-border flex items-center justify-between px-6 shrink-0 z-10 transition-colors">
                    <div className="flex-1 flex items-center">
                        <div className="relative w-full max-w-md group">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground group-focus-within:text-primary transition-colors" />
                            <input
                                type="text"
                                placeholder="Universal Research Search (Ctrl+K)"
                                className="w-full bg-muted/50 border border-border rounded-md pl-10 pr-4 py-1.5 text-[13px] focus:outline-none focus:ring-1 focus:ring-primary transition-all"
                            />
                        </div>
                    </div>

                    <div className="flex items-center space-x-4">
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                            className="text-muted-foreground hover:text-foreground transition-transform active:scale-95"
                            title="Toggle Theme"
                        >
                            {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                        </Button>
                        <Separator orientation="vertical" className="h-6" />
                        <div className="flex items-center space-x-3 group cursor-pointer">
                            <div className="flex flex-col items-end mr-1">
                                <span className="text-sm font-bold tracking-tight text-foreground">{user?.email?.split('@')[0] || "Trader"}</span>
                                <span className="text-[10px] text-muted-foreground uppercase font-black tracking-widest leading-none">Institutional Node</span>
                            </div>
                            <Avatar className="h-9 w-9 border border-primary/20 ring-2 ring-transparent group-hover:ring-primary/20 transition-all">
                                <AvatarFallback className="bg-primary/10 text-primary font-bold uppercase">
                                    {user?.email?.[0] || "U"}
                                </AvatarFallback>
                            </Avatar>
                        </div>
                    </div>
                </header>

                {/* Content Viewport */}
                <main className="flex-1 overflow-y-auto bg-background/50 relative flex flex-col custom-scrollbar">
                    <div className="flex-1">
                        {children}
                    </div>

                    <footer className="py-2.5 px-6 border-t border-border mt-auto bg-card/30 shrink-0">
                        <p className="text-[9px] text-muted-foreground uppercase tracking-[0.2em] font-medium text-center">
                            Institutional-grade financial intelligence. Disclaimer: This platform provides research insights, not financial advice.
                        </p>
                    </footer>
                </main>
            </div>
        </div>
    )
}
