import { useQuery } from "@tanstack/react-query"
import { History } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import api from "@/lib/api"
import { parseUtc } from "@/lib/utils"

interface AuditLog {
    id: number
    action: string
    status: string
    timestamp: string
}

const ACTION_LABELS: Record<string, string> = {
    login: "Signed in",
    logout: "Signed out everywhere",
    register: "Account created",
    change_password: "Password change",
    update_credentials: "API credentials updated",
    update_profile: "Risk profile updated",
    export_data: "Data exported",
}

export default function RecentActivityCard() {
    const { data: logs = [], isLoading, isError } = useQuery({
        queryKey: ["auditLogs"],
        queryFn: async () => {
            const { data } = await api.get<{ logs: AuditLog[] }>("/audit/logs", { params: { limit: 20 } })
            return data.logs
        },
    })

    return (
        <Card className="bg-card border-border shadow-none">
            <CardHeader className="p-4 border-b border-border">
                <CardTitle className="text-xs font-bold uppercase tracking-wider flex items-center gap-2">
                    <History className="size-4 text-primary" /> Recent Activity
                </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
                {isLoading && <p className="p-4 text-xs text-muted-foreground">Loading...</p>}
                {isError && <p className="p-4 text-xs text-red-400">Could not load activity.</p>}
                {!isLoading && !isError && logs.length === 0 && (
                    <p className="p-4 text-xs text-muted-foreground">No activity recorded yet.</p>
                )}
                <ul className="divide-y divide-border">
                    {logs.map(log => (
                        <li key={log.id} className="px-4 py-2.5 flex items-center justify-between text-xs">
                            <span className="text-foreground">
                                {ACTION_LABELS[log.action] ?? log.action.replace(/_/g, " ")}
                                {log.status !== "success" && (
                                    <span className="ml-2 text-[10px] font-bold uppercase text-red-400">{log.status}</span>
                                )}
                            </span>
                            <time dateTime={log.timestamp} className="font-mono text-[11px] text-muted-foreground">
                                {parseUtc(log.timestamp).toLocaleString()}
                            </time>
                        </li>
                    ))}
                </ul>
            </CardContent>
        </Card>
    )
}
