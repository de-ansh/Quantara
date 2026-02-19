import { createContext, useContext, useEffect, useState } from "react"
import type { AuthState, User } from "@/types"

const initialState: AuthState = {
    user: null,
    token: null,
    isLoading: true,
    login: () => null,
    logout: () => null,
}

export const AuthContext = createContext<AuthState>(initialState)

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null)
    const [token, setToken] = useState<string | null>(null)
    const [isLoading, setIsLoading] = useState(true)

    useEffect(() => {
        const storedToken = localStorage.getItem("quantara_token")
        const storedUser = localStorage.getItem("quantara_user")

        if (storedToken && storedUser) {
            setToken(storedToken)
            try {
                setUser(JSON.parse(storedUser))
            } catch (e) {
                console.error("Failed to parse stored user", e)
                localStorage.removeItem("quantara_token")
                localStorage.removeItem("quantara_user")
            }
        }
        setIsLoading(false)
    }, [])

    const login = (newToken: string, newUser: User) => {
        setToken(newToken)
        setUser(newUser)
        localStorage.setItem("quantara_token", newToken)
        localStorage.setItem("quantara_user", JSON.stringify(newUser))
    }

    const logout = () => {
        setToken(null)
        setUser(null)
        localStorage.removeItem("quantara_token")
        localStorage.removeItem("quantara_user")
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
