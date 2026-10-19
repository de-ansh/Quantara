import { lazy, Suspense } from "react"
import { BrowserRouter as Router, Routes, Route } from "react-router-dom"
import { ThemeProvider } from "@/context/ThemeProvider"
import { AuthProvider } from "@/context/AuthContext"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import MainLayout from "@/layouts/MainLayout"
import ProtectedRoute from "@/components/ProtectedRoute"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

const Dashboard = lazy(() => import("@/pages/Dashboard"))
const ResearchExplorer = lazy(() => import("@/pages/ResearchExplorer"))
const StockDetail = lazy(() => import("@/pages/StockDetail"))
const Signals = lazy(() => import("@/pages/Signals"))
const Risk = lazy(() => import("@/pages/Risk"))
const Simulation = lazy(() => import("@/pages/Simulation"))
const Login = lazy(() => import("@/pages/Login"))
const Register = lazy(() => import("@/pages/Register"))

const Settings = lazy(() => import("@/pages/Settings"))
const Account = lazy(() => import("@/pages/Account"))

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="dark" storageKey="quantara-ui-theme">
        <AuthProvider>
          <Router>
            <MainLayout>
              <Suspense fallback={<div className="flex-1 flex items-center justify-center bg-background text-muted-foreground font-mono text-xs">LOADING_RESOURCES...</div>}>
                <Routes>
                  <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                  <Route path="/research" element={<ProtectedRoute><StockDetail /></ProtectedRoute>} />
                  <Route path="/research/:ticker" element={<ProtectedRoute><StockDetail /></ProtectedRoute>} />
                  <Route path="/explorer" element={<ProtectedRoute><ResearchExplorer /></ProtectedRoute>} />
                  <Route path="/signals" element={<ProtectedRoute><Signals /></ProtectedRoute>} />
                  <Route path="/risk" element={<ProtectedRoute><Risk /></ProtectedRoute>} />
                  <Route path="/risk/:ticker" element={<ProtectedRoute><Risk /></ProtectedRoute>} />
                  <Route path="/simulation" element={<ProtectedRoute><Simulation /></ProtectedRoute>} />
                  <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
                  <Route path="/account" element={<ProtectedRoute><Account /></ProtectedRoute>} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/register" element={<Register />} />
                </Routes>
              </Suspense>
            </MainLayout>
          </Router>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

export default App
