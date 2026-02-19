import { lazy, Suspense } from "react"
import { BrowserRouter as Router, Routes, Route } from "react-router-dom"
import { ThemeProvider } from "@/context/ThemeProvider"
import { AuthProvider } from "@/context/AuthContext"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import MainLayout from "@/layouts/MainLayout"

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
const Login = lazy(() => import("./pages/Login"))
const Register = lazy(() => import("./pages/Register"))

const Settings = () => <div className="p-8"><h1>Settings</h1></div>
const Account = () => <div className="p-8"><h1>Account & Security</h1></div>

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="dark" storageKey="quantara-ui-theme">
        <AuthProvider>
          <Router>
            <MainLayout>
              <Suspense fallback={<div className="flex-1 flex items-center justify-center bg-background text-muted-foreground font-mono text-xs">LOADING_RESOURCES...</div>}>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/research" element={<StockDetail />} />
                  <Route path="/research/:ticker" element={<StockDetail />} />
                  <Route path="/explorer" element={<ResearchExplorer />} />
                  <Route path="/signals" element={<Signals />} />
                  <Route path="/risk" element={<Risk />} />
                  <Route path="/simulation" element={<Simulation />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="/account" element={<Account />} />
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
