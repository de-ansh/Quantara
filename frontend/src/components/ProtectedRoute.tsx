import { Navigate, useLocation } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"

interface ProtectedRouteProps {
    children: React.ReactNode
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
    const { token, user, isLoading } = useAuth()
    const location = useLocation()

    if (isLoading) {
        return (
            <div className="flex-1 flex items-center justify-center min-h-[50vh] text-muted-foreground font-mono text-xs">
                VERIFYING_AUTHORIZATION...
            </div>
        )
    }

    if (!token || !user) {
        return <Navigate to="/login" state={{ from: location }} replace />
    }

    return <>{children}</>
}
