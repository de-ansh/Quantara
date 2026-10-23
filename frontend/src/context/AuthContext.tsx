import { createContext, useContext, useEffect, useState } from "react"
import type { AuthState, User } from "@/types"
import { useQueryClient } from "@tanstack/react-query"
import api, { refreshAccessToken, setAccessToken } from "@/lib/api"

const initialState: AuthState = {
    user: null,
    token: null,
    isLoading: true,
    login: () => null,
    logout: () => null,
}

export const AuthContext = createContext<AuthState>(initialState)

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const queryClient = useQueryClient()
    // The profile is cached for display; the session itself is the httpOnly refresh cookie.
    const [user, setUser] = useState<User | null>(() => {
        const storedUser = localStorage.getItem("quantara_user")
        if (!storedUser) return null
        try {
            return JSON.parse(storedUser)
        } catch (e) {
            console.error("Failed to parse stored user", e)
            localStorage.removeItem("quantara_user")
            return null
        }
    })
    const [token, setToken] = useState<string | null>(null)
    // Only a remembered user needs the cookie exchange before protected pages render
    const [isLoading, setIsLoading] = useState(user !== null)

    useEffect(() => {
        if (!isLoading) return
        refreshAccessToken()
            .then(setToken)
            .catch(() => {
                setUser(null)
                localStorage.removeItem("quantara_user")
            })
            .finally(() => setIsLoading(false))
    }, [isLoading])

    const login = (newToken: string, newUser: User) => {
        setAccessToken(newToken)
        setToken(newToken)
        setUser(newUser)
        localStorage.setItem("quantara_user", JSON.stringify(newUser))
    }

    const logout = () => {
        // Revokes all tokens server-side and clears the refresh cookie
        api.post("/auth/logout").catch(() => {})
        setAccessToken(null)
        setToken(null)
        setUser(null)
        localStorage.removeItem("quantara_user")
        // Don't leave this user's cached data for whoever signs in next
        queryClient.clear()
    }

    const value = {
        user,
        token,
        isLoading,
        login,
        logout,
    }

    return (
        <AuthContext.Provider value={value}>
            {children}
        </AuthContext.Provider>
    )
}

export const useAuth = () => {
    const context = useContext(AuthContext)
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider")
    }
    return context
}
