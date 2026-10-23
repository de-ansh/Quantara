// Response shapes of the backend API (mirrors the FastAPI response models).

export interface StockSearchItem {
    ticker: string
    name: string
    price: string
    cap: string
    risk: number
    signal: string
    alpha: string
    status: string
    updated_at: string | null
    sector: string | null
    pe: number | null
    beta: number | null
}

/** Signal metadata varies by signal type; these are the keys the UI reads. */
export interface SignalMetadata {
    ownership_change_pct?: number
    num_institutions?: number
    buy_volume?: number
    sell_volume?: number
    net_buying?: number
    num_insiders?: number
    [key: string]: unknown
}

export interface ApiSignal {
    id: number
    ticker: string
    signal_type: string
    strength: number
    confidence: number
    timestamp: string
    metadata: SignalMetadata
}

export interface RiskComponents {
    volatility_score: number
    beta_score: number
    leverage_score: number
    earnings_stability_score: number
    sector_risk_score: number
    valuation_risk_score: number
}

export interface StressScenario {
    id: string
    name: string
    type: string
    impact_pct: number
    status: string
    factor_breakdown: Record<string, number>
    narrative: string | null
}

export interface RiskAnalysis {
    ticker: string
    overall_risk_score: number
    risk_level: string
    risk_band: string
    components: RiskComponents
    explanation: string
    max_drawdown: number
    drawdown_series: { time: string; historical?: number | null; projected?: number | null; drawdown_pct?: number | null }[]
    scenarios: StressScenario[]
    factor_sensitivities: Record<string, number>
    assumed_inputs: string[]
}

export interface PeerCorrelation {
    ticker: string
    name: string
    sector: string
    correlation: number
    beta: number
    relationship: string
}

export interface StockCorrelation {
    ticker: string
    sector: string
    benchmark_ticker: string
    benchmark_correlation: number
    peers: PeerCorrelation[]
}
