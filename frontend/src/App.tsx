import { lazy, Suspense } from "react"
import { BrowserRouter as Router, Routes, Route } from "react-router-dom"
import { ThemeProvider } from "@/context/ThemeProvider"
import { AuthProvider } from "@/context/AuthContext"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import TickerGate from "@/components/TickerGate"
import MainLayout from "@/layouts/MainLayout"
import ProtectedRoute from "@/components/ProtectedRoute"
import RouteErrorBoundary from "@/components/ErrorBoundary"

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
const Portfolios = lazy(() => import("@/pages/Portfolios"))
const PortfolioDetail = lazy(() => import("@/pages/PortfolioDetail"))
const Compare = lazy(() => import("@/pages/Compare"))
const Login = lazy(() => import("@/pages/Login"))
const Register = lazy(() => import("@/pages/Register"))
const ResetPassword = lazy(() => import("@/pages/ResetPassword"))

const Markets = lazy(() => import("@/pages/Markets"))
const Filings = lazy(() => import("@/pages/Filings"))
const IndicesEtfs = lazy(() => import("@/pages/IndicesEtfs"))
const Concalls = lazy(() => import("@/pages/Concalls"))
const Deals = lazy(() => import("@/pages/Deals"))
const Events = lazy(() => import("@/pages/Events"))
const Calculators = lazy(() => import("@/pages/Calculators"))
const SharedChat = lazy(() => import("@/pages/SharedChat"))
const Settings = lazy(() => import("@/pages/Settings"))
const Account = lazy(() => import("@/pages/Account"))

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="dark" storageKey="quantara-ui-theme">
        <AuthProvider>
          <Router>
            <MainLayout>
              <RouteErrorBoundary>
              <Suspense fallback={<div className="flex-1 flex items-center justify-center bg-background text-muted-foreground font-mono text-xs">LOADING_RESOURCES...</div>}>
                <Routes>
                  <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                  <Route path="/research" element={<ProtectedRoute><StockDetail /></ProtectedRoute>} />
                  <Route path="/research/:ticker" element={<ProtectedRoute><TickerGate><StockDetail /></TickerGate></ProtectedRoute>} />
                  <Route path="/explorer" element={<ProtectedRoute><ResearchExplorer /></ProtectedRoute>} />
                  <Route path="/signals" element={<ProtectedRoute><Signals /></ProtectedRoute>} />
                  <Route path="/risk" element={<ProtectedRoute><Risk /></ProtectedRoute>} />
                  <Route path="/risk/:ticker" element={<ProtectedRoute><TickerGate><Risk /></TickerGate></ProtectedRoute>} />
                  <Route path="/simulation" element={<ProtectedRoute><Simulation /></ProtectedRoute>} />
                  <Route path="/portfolios" element={<ProtectedRoute><Portfolios /></ProtectedRoute>} />
                  <Route path="/portfolios/:id" element={<ProtectedRoute><PortfolioDetail /></ProtectedRoute>} />
                  <Route path="/compare" element={<ProtectedRoute><Compare /></ProtectedRoute>} />
                  <Route path="/markets" element={<ProtectedRoute><Markets /></ProtectedRoute>} />
                  <Route path="/events" element={<ProtectedRoute><Events /></ProtectedRoute>} />
                  <Route path="/filings" element={<ProtectedRoute><Filings /></ProtectedRoute>} />
                  <Route path="/indices" element={<ProtectedRoute><IndicesEtfs /></ProtectedRoute>} />
                  <Route path="/concalls" element={<ProtectedRoute><Concalls /></ProtectedRoute>} />
                  <Route path="/deals" element={<ProtectedRoute><Deals /></ProtectedRoute>} />
                  <Route path="/calculators" element={<ProtectedRoute><Calculators /></ProtectedRoute>} />
                  <Route path="/shared/:token" element={<SharedChat />} />
                  <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
                  <Route path="/account" element={<ProtectedRoute><Account /></ProtectedRoute>} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/register" element={<Register />} />
                  <Route path="/reset-password" element={<ResetPassword />} />
                </Routes>
              </Suspense>
              </RouteErrorBoundary>
            </MainLayout>
          </Router>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}

export default App
