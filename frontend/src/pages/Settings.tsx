import { useState, useEffect } from "react"
import { useTheme } from "@/context/use-theme"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Key, Globe, Eye, EyeOff, Save, RotateCcw, Settings as SettingsIcon, Sun, Moon } from "lucide-react"

export default function Settings() {
    const { theme, setTheme } = useTheme()
    const [openaiKey, setOpenaiKey] = useState("")
    const [secUserAgent, setSecUserAgent] = useState("")
    const [showKey, setShowKey] = useState(false)
    const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved">("idle")

    useEffect(() => {
        const storedKey = localStorage.getItem("openai_api_key") || ""
        const storedUA = localStorage.getItem("sec_user_agent") || ""
        setOpenaiKey(storedKey)
        setSecUserAgent(storedUA)
    }, [])

    const handleSave = () => {
        setSaveStatus("saving")
        setTimeout(() => {
            if (openaiKey.trim()) {
                localStorage.setItem("openai_api_key", openaiKey.trim())
            } else {
                localStorage.removeItem("openai_api_key")
            }

            if (secUserAgent.trim()) {
                localStorage.setItem("sec_user_agent", secUserAgent.trim())
            } else {
                localStorage.removeItem("sec_user_agent")
            }
            setSaveStatus("saved")
            setTimeout(() => setSaveStatus("idle"), 2000)
        }, 800)
    }

    const handleReset = () => {
        setOpenaiKey("")
        setSecUserAgent("")
        localStorage.removeItem("openai_api_key")
        localStorage.removeItem("sec_user_agent")
        setSaveStatus("saved")
        setTimeout(() => setSaveStatus("idle"), 2000)
    }

    return (
        <div className="p-6 max-w-4xl mx-auto space-y-6 bg-background min-h-screen text-foreground transition-colors">
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-border">
                <div>
                    <h1 className="text-2xl font-black uppercase tracking-tight flex items-center gap-2">
                        <SettingsIcon className="size-6 text-primary" />
                        System Settings
                    </h1>
                    <p className="text-[10px] text-muted-foreground uppercase font-bold tracking-widest mt-1">
                        Configure visual aesthetics and security credentials
                    </p>
                </div>
                <Badge variant="outline" className="font-mono text-[9px] font-black uppercase tracking-widest px-2 py-0.5 border-primary/20 bg-primary/5 text-primary">
                    Node Configuration
                </Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Visual Settings */}
                <Card className="bg-card border-border shadow-none">
                    <CardHeader className="p-4 pb-2 border-b border-border/50">
                        <CardTitle className="text-xs font-bold uppercase tracking-wider text-foreground">Visual Theme</CardTitle>
                        <CardDescription className="text-[10px] text-muted-foreground uppercase font-bold">
                            Select terminal theme mode
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="p-6 space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <button
                                onClick={() => setTheme("dark")}
                                className={`flex flex-col items-center justify-center p-4 border rounded-sm transition-all ${
                                    theme === "dark"
                                        ? "border-primary bg-primary/5 text-foreground ring-1 ring-primary"
                                        : "border-border bg-muted/20 text-muted-foreground hover:bg-muted"
                                }`}
                            >
                                <Moon className="size-6 mb-2" />
                                <span className="text-[10px] font-black uppercase tracking-widest">Institutional Dark</span>
                            </button>
                            <button
                                onClick={() => setTheme("light")}
                                className={`flex flex-col items-center justify-center p-4 border rounded-sm transition-all ${
                                    theme === "light"
                                        ? "border-primary bg-primary/5 text-foreground ring-1 ring-primary"
                                        : "border-border bg-muted/20 text-muted-foreground hover:bg-muted"
                                }`}
                            >
                                <Sun className="size-6 mb-2" />
                                <span className="text-[10px] font-black uppercase tracking-widest">Aero Light</span>
                            </button>
                        </div>
                        <p className="text-[10px] text-muted-foreground uppercase font-bold text-center leading-relaxed">
                            Current visual theme: <span className="text-primary font-black">{theme.toUpperCase()}</span>
                        </p>
                    </CardContent>
                </Card>

                {/* API Credentials */}
                <Card className="bg-card border-border shadow-none">
                    <CardHeader className="p-4 pb-2 border-b border-border/50">
                        <CardTitle className="text-xs font-bold uppercase tracking-wider text-foreground">API Credentials & Overrides</CardTitle>
                        <CardDescription className="text-[10px] text-muted-foreground uppercase font-bold">
                            These credentials override environment configurations and are stored locally
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="p-6 space-y-4">
                        {/* OpenAI API Key */}
                        <div className="space-y-1.5">
                            <label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                                <Key className="size-3.5 text-primary" />
                                OpenAI API Key
                            </label>
                            <div className="relative">
                                <input
                                    type={showKey ? "text" : "password"}
                                    value={openaiKey}
                                    onChange={(e) => setOpenaiKey(e.target.value)}
                                    placeholder="sk-proj-..."
                                    className="w-full bg-[#0A0E12] border border-[#282d39] text-white text-sm pl-4 pr-10 py-2.5 focus:border-[#1e5df1] focus:ring-0 outline-none placeholder:text-[#9ca5ba]/50 font-mono"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowKey(!showKey)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                                >
                                    {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                                </button>
                            </div>
                        </div>

                        {/* SEC User Agent */}
                        <div className="space-y-1.5">
                            <label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                                <Globe className="size-3.5 text-primary" />
                                SEC User-Agent
                            </label>
                            <input
                                type="text"
                                value={secUserAgent}
                                onChange={(e) => setSecUserAgent(e.target.value)}
                                placeholder="Company AdminName admin@company.com"
                                className="w-full bg-[#0A0E12] border border-[#282d39] text-white text-sm px-4 py-2.5 focus:border-[#1e5df1] focus:ring-0 outline-none placeholder:text-[#9ca5ba]/50 font-mono"
                            />
                            <p className="text-[9px] text-muted-foreground font-bold uppercase tracking-wide">
                                SEC EDGAR requests require a valid User-Agent containing name and email.
                            </p>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-border bg-card/20 p-4 rounded-sm">
                <Button
                    variant="outline"
                    onClick={handleReset}
                    className="flex items-center gap-2 border-border text-muted-foreground hover:text-foreground h-10 px-4 text-xs font-bold uppercase"
                >
                    <RotateCcw className="size-4" />
                    Reset local variables
                </Button>
                <Button
                    onClick={handleSave}
                    disabled={saveStatus === "saving"}
                    className="flex items-center gap-2 bg-primary text-white hover:bg-primary/90 h-10 px-6 text-xs font-black uppercase"
                >
                    <Save className="size-4" />
                    {saveStatus === "saving" ? "Saving..." : saveStatus === "saved" ? "Values Updated" : "Save Changes"}
                </Button>
            </div>
        </div>
    )
}
