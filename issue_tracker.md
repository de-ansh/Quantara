# Quantara Engineering Issue Tracker

Structured issue registry for tracking, prioritizing, and resolving missing features, hardcoded mocks, and architectural gaps across Quantara.

---

## 📊 Summary Board

| Category | Open Issues | P0 (Critical) | P1 (High) | P2 (Medium) | P3 (Low) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Category | Open Issues | P0 (Critical) | P1 (High) | P2 (Medium) | P3 (Low) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Authentication & Routing (AUTH)** | 1 | 0 | 1 | 0 | 0 |
| **Recommendations Engine (REC)** | 0 | 0 | 0 | 0 | 0 |
| **Stock Research & Detail (STK)** | 0 | 0 | 0 | 0 | 0 |
| **Portfolio & Simulation (PORT)** | 0 | 0 | 0 | 0 | 0 |
| **Risk Analytics & Views (RSK)** | 2 | 0 | 1 | 1 | 0 |
| **Signal Engine & Ingestion (SIG)**| 3 | 0 | 2 | 1 | 0 |
| **Navigation & Explorer UX (NAV)** | 3 | 0 | 1 | 2 | 0 |
| **Qualitative Analysis / RAG (RAG)**| 2 | 0 | 1 | 1 | 0 |
| **Total** | **11** | **0** | **6** | **5** | **0** |

---

## 🔴 Priority 0 — Critical Path Blockers

### [QTR-AUTH-01] Implement Frontend Route Protection (`ProtectedRoute`) ✅
- **Category**: Auth & Routing
- **Component**: [`frontend/src/App.tsx`](frontend/src/App.tsx)
- **Description**: All routes currently allow unauthenticated navigation. Non-logged-in users can load private views (`/`, `/research`, `/risk`, `/simulation`, `/account`), triggering unhandled 401 exceptions.
- **Acceptance Criteria**:
  - [x] Add `ProtectedRoute` component checking `token` and `user` from `useAuth()`.
  - [x] Redirect unauthorized visits to `/login` with `from` location state.
  - [x] Wrap private routes (`/`, `/research`, `/explorer`, `/signals`, `/risk`, `/simulation`, `/account`, `/settings`).

### [QTR-REC-01] Wire User Risk Profile to Recommendations API ✅
- **Category**: Recommendations
- **Component**: [`backend/app/api/v1/recommendations.py`](backend/app/api/v1/recommendations.py)
- **Description**: Recommendations endpoint uses hardcoded profile (`user_risk_level = "Moderate"`, `user_volatility_tolerance = 60.0`), ignoring actual profile in DB.
- **Acceptance Criteria**:
  - [x] Extract user risk preferences directly from `current_user` (`risk_level`, `volatility_tolerance`).
  - [x] Provide sensible defaults only if user has not yet completed risk onboarding.

### [QTR-REC-02] Fetch Live Database Stocks for Recommendations ✅
- **Category**: Recommendations
- **Component**: [`backend/app/api/v1/recommendations.py`](backend/app/api/v1/recommendations.py)
- **Description**: API ranks a hardcoded 3-stock array (`AAPL`, `MSFT`, `JNJ`). Stock database entries are unused.
- **Acceptance Criteria**:
  - [x] Query active stocks and calculated scores (`risk_score`, `research_score`) from `stocks` table.
  - [x] Compute live signal score by aggregating recent active signals from `signals` table for each stock candidate.
  - [x] Pass dynamic dataset through `RecommendationEngine.rank_recommendations`.

### [QTR-STK-01] Eliminate Hardcoded NVIDIA Data in `StockDetail.tsx` ✅
- **Category**: Stock Research
- **Component**: [`frontend/src/pages/StockDetail.tsx`](frontend/src/pages/StockDetail.tsx)
- **Description**: Company name ("NVIDIA Corp."), Market Cap ("$2.5T"), Sector ("Technology / Semiconductors"), risk score (84), anti-thesis text, ownership numbers (92/2/6), and sparklines are static constants.
- **Acceptance Criteria**:
  - [x] Bind company header to `/stocks/{ticker}/research` and Yahoo market data.
  - [x] Dynamically compute and display risk score gauge from `/stocks/{ticker}/risk`.
  - [x] Render thesis and anti-thesis dynamically from `report.summary`, `report.key_insights`, and `report.weaknesses`.
  - [x] Bind Key Stats sidebar and price sparklines to real historical/current price data.

### [QTR-PORT-01] Implement Portfolio & Position DB Models and CRUD ✅
- **Category**: Portfolio Management
- **Component**: [`backend/app/models/portfolio.py`](backend/app/models/portfolio.py), [`backend/app/api/v1/portfolio.py`](backend/app/api/v1/portfolio.py)
- **Description**: Zero persistence exists for user portfolios. Users cannot save, name, or track actual portfolios or holdings.
- **Acceptance Criteria**:
  - [x] Create `Portfolio` model (`id`, `user_id`, `name`, `description`, `created_at`, `updated_at`).
  - [x] Create `PortfolioPosition` model (`id`, `portfolio_id`, `ticker`, `shares`, `cost_basis`, `weight`).
  - [x] Implement CRUD endpoints: `GET /portfolio/`, `POST /portfolio/`, `GET /portfolio/{id}`, `PUT /portfolio/{id}`, `DELETE /portfolio/{id}`.
  - [x] Write 100% test coverage in `test_portfolio_crud.py`.

---

## 🟡 Priority 1 — Core Features & Polish

### [QTR-AUTH-02] User Profile Menu & Logout Trigger in Layout ✅
- **Category**: Auth & Routing
- **Component**: [`frontend/src/layouts/MainLayout.tsx`](frontend/src/layouts/MainLayout.tsx)
- **Description**: Avatar and trader badge in top header are inert; no dropdown or logout button (`LogOut` icon imported but unused).
- **Acceptance Criteria**:
  - [x] Add dropdown menu on avatar click showing user email, risk tier, Account link, and Logout button.
  - [x] On logout, clear token, reset auth state, and route to `/login`.

### [QTR-AUTH-03] Server-Side User Credential & Preference Storage
- **Category**: Auth & Routing
- **Component**: [`frontend/src/pages/Settings.tsx`](frontend/src/pages/Settings.tsx), `backend/app/models/user.py`
- **Description**: `openai_api_key` and `sec_user_agent` persist only in browser `localStorage`.
- **Acceptance Criteria**:
  - [ ] Add encrypted/masked columns to `User` model for external credentials.
  - [ ] Add `PUT /users/credentials` endpoint to persist settings securely across sessions.

### [QTR-REC-03] Persist Recommendation Batches in `recommendations` Table ✅
- **Category**: Recommendations
- **Component**: [`backend/app/models/recommendation.py`](backend/app/models/recommendation.py), [`backend/app/api/v1/recommendations.py`](backend/app/api/v1/recommendations.py)
- **Description**: `recommendations` table exists with complete schema but is never populated or queried.
- **Acceptance Criteria**:
  - [x] Persist generated recommendations (`final_score`, `research_score`, `signal_score`, `risk_alignment_score`, `macro_fit_score`, `explanation_text`, `reasoning_metadata`) to DB.
  - [x] Cache user recommendations with `expires_at` timestamp.

### [QTR-STK-02] Implement Interactive Tab Switching in `StockDetail.tsx` ✅
- **Category**: Stock Research
- **Component**: [`frontend/src/pages/StockDetail.tsx`](frontend/src/pages/StockDetail.tsx)
- **Description**: Tabs ("Investment Thesis", "Financial Health", "Risk Breakdown", "Signal Intelligence", "Macro Exposure") do not switch views.
- **Acceptance Criteria**:
  - [x] Add active tab state (`thesis`, `financials`, `risk`, `signals`, `macro`).
  - [x] Implement view panels for Financial Health (income statement/balance sheet metrics from SEC), Risk Breakdown (risk components breakdown & alignment), and Signal Intelligence (insider/earnings signals for ticker).

### [QTR-STK-03] Dynamic SEC CIK Company Lookup ✅
- **Category**: Stock Research / Data Providers
- **Component**: [`backend/app/providers/sec.py`](backend/app/providers/sec.py)
- **Description**: Hardcoded `CIK_MAPPING` supports only 8 tickers; any other stock fails SEC fact retrieval.
- **Acceptance Criteria**:
  - [x] Fetch and cache `https://www.sec.gov/files/company_tickers.json` to resolve any US ticker to its CIK.
  - [x] Fall back to static map if SEC directory fetch fails.
  - [x] Provide async `get_cik_async(ticker: str)` while keeping synchronous `get_cik(ticker: str)` fallback for backward compatibility.
  - [x] 100% test coverage in `backend/app/tests/providers/test_sec.py`.

### [QTR-PORT-02] Covariance Matrix & Asset Correlation in Portfolio Simulation ✅
- **Category**: Portfolio Management
- **Component**: [`backend/app/api/v1/portfolio.py`](backend/app/api/v1/portfolio.py), [`backend/app/services/portfolio_analytics.py`](backend/app/services/portfolio_analytics.py)
- **Description**: Portfolio volatility is currently estimated assuming zero covariance between assets.
- **Acceptance Criteria**:
  - [x] Model cross-asset correlation and covariance matrix across portfolio components (`PortfolioAnalyticsEngine`).
  - [x] Use $w^T \Sigma w$ for true portfolio variance in Monte Carlo trajectory generation.
  - [x] Return correlation matrix, covariance matrix, individual asset volatilities, and diversification benefit in simulation response.
  - [x] 100% test coverage in `backend/app/tests/test_portfolio_simulation.py`.

### [QTR-PORT-03] Dynamic Stock Allocation & Volatility Mode in `Simulation.tsx` ✅
- **Category**: Portfolio Management
- **Component**: [`frontend/src/pages/Simulation.tsx`](frontend/src/pages/Simulation.tsx), [`backend/app/api/v1/portfolio.py`](backend/app/api/v1/portfolio.py)
- **Description**: Stocks locked to 4 preset asset buckets (`AAPL`, `TLT`, `GLD`, `BIL`); volatility mode selector ("Cons.", "Base", "Aggr.") ignored.
- **Acceptance Criteria**:
  - [x] Allow users to add custom tickers from DB/quick chips and adjust weight sliders.
  - [x] Add weight normalization to 100% and remove asset capability.
  - [x] Send `volatility_mode` ("conservative", "base", "aggressive") and `initial_investment` to `/portfolio/simulate`.
  - [x] Render dynamic diversification benefit badge and correlation matrix view tab.

### [QTR-RSK-01] Dynamic Correlation & Segment Matrix in `Risk.tsx` ✅
- **Category**: Risk Analytics
- **Component**: [`frontend/src/pages/Risk.tsx`](frontend/src/pages/Risk.tsx), [`backend/app/api/v1/risk.py`](backend/app/api/v1/risk.py)
- **Description**: Correlation matrix displays hardcoded semiconductor segments ("CPU TECH", "GPU CLOUD") for all stocks.
- **Acceptance Criteria**:
  - [x] Provide backend endpoint `GET /api/v1/stocks/{ticker}/correlation` returning sector peer correlations and benchmark exposure.
  - [x] Render dynamic correlation matrix and risk badges in `Risk.tsx` for any selected stock.
  - [x] Unit test coverage in `backend/app/tests/test_risk_engine.py`.

### [QTR-RSK-02] Dynamic Drawdown Curve in `Risk.tsx`
- **Category**: Risk Analytics
- **Component**: [`frontend/src/pages/Risk.tsx`](frontend/src/pages/Risk.tsx)
- **Description**: Historical drawdown chart uses static 12-point dummy array.
- **Acceptance Criteria**:
  - [ ] Feed historical drawdown series from Yahoo Finance historical calculations (`get_stock_risk_analysis`).
  - [ ] Render actual drawdown curve in Recharts.

### [QTR-SIG-01] Wire Sentiment & Institutional Ingestion into Periodic Worker
- **Category**: Signal Engine
- **Component**: [`backend/app/services/signal_engine.py`](backend/app/services/signal_engine.py)
- **Description**: Periodic background task only checks Form 4 insider transactions and company facts EPS; sentiment spike detection is never called.
- **Acceptance Criteria**:
  - [ ] Schedule `detect_sentiment_spike` in background loop.
  - [ ] Save detected sentiment signals to `signals` DB table.

### [QTR-SIG-02] Real SEC Form 13F Filing Ingestion for Institutional Buying
- **Category**: Signal Engine
- **Component**: [`backend/app/providers/sec.py`](backend/app/providers/sec.py)
- **Description**: 13F institutional holdings parsing is missing; only Form 4 XML is implemented.
- **Acceptance Criteria**:
  - [ ] Implement XML parser for SEC Form 13F filings.
  - [ ] Detect significant quarter-over-quarter institutional accumulation.

### [QTR-NAV-01] Universal Search & Command Palette (`Ctrl+K`)
- **Category**: Navigation & Shell
- **Component**: [`frontend/src/layouts/MainLayout.tsx`](frontend/src/layouts/MainLayout.tsx)
- **Description**: Search input in top navigation has no event handlers or command palette modal.
- **Acceptance Criteria**:
  - [ ] Open search modal / command palette on click or `Ctrl+K` / `Cmd+K`.
  - [ ] Search stocks by ticker or company name via `/stocks/search` and route to `/research/:ticker` or `/risk/:ticker`.

### [QTR-RAG-01] Earnings Call Transcript Ingestion & Vector Embeddings
- **Category**: Qualitative Analysis
- **Component**: [`backend/app/services/llm_orchestrator.py`](backend/app/services/llm_orchestrator.py)
- **Description**: Transcript retrieval is stubbed with empty array (`"transcripts": []`).
- **Acceptance Criteria**:
  - [ ] Integrate transcript provider (e.g. FMP / SEC 8-K exhibits).
  - [ ] Generate chunk embeddings via OpenAI embeddings API.
  - [ ] Retrieve top-K relevant excerpts for LLM qualitative synthesis node.

---

## 🟢 Priority 2 — Medium Improvements & Polish

### [QTR-RSK-03] Quantitative Scenario Stress Testing
- **Category**: Risk Analytics
- **Component**: [`frontend/src/pages/Risk.tsx`](frontend/src/pages/Risk.tsx)
- **Description**: Macro stress scenarios (Fed pivot, Oil spike, Recession) use simple visual multipliers.
- **Acceptance Criteria**:
  - [ ] Connect scenario modeling to historical factor beta sensitivities.

### [QTR-SIG-03] Live Intraday Sentiment Curve in `Signals.tsx`
- **Category**: Signal Engine
- **Component**: [`frontend/src/pages/Signals.tsx`](frontend/src/pages/Signals.tsx)
- **Description**: Intraday social/news sentiment chart uses static 8-point dummy array.
- **Acceptance Criteria**:
  - [ ] Feed chart with time-bucketed sentiment signals from backend.

### [QTR-NAV-02] Research Explorer Grid View & Bulk Actions
- **Category**: Navigation & Explorer
- **Component**: [`frontend/src/pages/ResearchExplorer.tsx`](frontend/src/pages/ResearchExplorer.tsx)
- **Description**: Grid view toggle button changes state but renders the table; checkboxes do nothing.
- **Acceptance Criteria**:
  - [ ] Implement responsive card-based Grid layout when `view === "grid"`.
  - [ ] Add batch actions (e.g. "Add to Watchlist", "Compare").

### [QTR-NAV-03] Export Handlers (CSV / PDF) across Tables and Simulations
- **Category**: Navigation & Explorer
- **Component**: `frontend/src/pages/ResearchExplorer.tsx`, `frontend/src/pages/Simulation.tsx`, `frontend/src/pages/Signals.tsx`
- **Description**: Download / export buttons exist without click actions.
- **Acceptance Criteria**:
  - [ ] Add client-side CSV download handlers for displayed tabular data.

### [QTR-RAG-02] PostgreSQL Vector Store Integration (`pgvector`)
- **Category**: Qualitative Analysis
- **Component**: `backend/app/models/`
- **Description**: No vector schema or extension configured in Alembic / PostgreSQL.
- **Acceptance Criteria**:
  - [ ] Add `pgvector` extension migration and `DocumentChunk` embedding table.
