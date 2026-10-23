import { Component, type ErrorInfo, type ReactNode } from "react"
import { useLocation } from "react-router-dom"

interface State {
    error: Error | null
}

class Boundary extends Component<{ children: ReactNode }, State> {
    state: State = { error: null }

    static getDerivedStateFromError(error: Error): State {
        return { error }
    }

    componentDidCatch(error: Error, info: ErrorInfo) {
        console.error("Page crashed:", error, info.componentStack)
    }

    render() {
        if (!this.state.error) return this.props.children
        return (
            <div role="alert" className="flex-1 flex flex-col items-center justify-center gap-3 p-10 text-center">
                <p className="text-sm font-bold text-foreground">This page hit an unexpected error.</p>
                <p className="text-xs text-muted-foreground max-w-md">{this.state.error.message}</p>
                <button
                    type="button"
                    onClick={() => window.location.reload()}
                    className="text-xs font-bold text-primary hover:underline"
                >
                    Reload
                </button>
            </div>
        )
    }
}

/** Contains a page crash to that page (navigation keeps working) and resets on route change. */
export default function RouteErrorBoundary({ children }: { children: ReactNode }) {
    const { pathname } = useLocation()
    return <Boundary key={pathname}>{children}</Boundary>
}
