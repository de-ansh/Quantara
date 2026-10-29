# Quantara Engineering Issue Tracker

Structured issue registry for tracking, prioritizing, and resolving missing features, hardcoded mocks, and architectural gaps across Quantara.

---

## 📊 Summary Board

| Category | Open Issues | P0 (Critical) | P1 (High) | P2 (Medium) | P3 (Low) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Authentication & Routing (AUTH)** | 1 | 0 | 0 | 1 | 0 |
| **Recommendations Engine (REC)** | 0 | 0 | 0 | 0 | 0 |
| **Stock Research & Detail (STK)** | 0 | 0 | 0 | 0 | 0 |
| **Portfolio & Simulation (PORT)** | 0 | 0 | 0 | 0 | 0 |
| **Risk Analytics & Views (RSK)** | 0 | 0 | 0 | 0 | 0 |
| **Signal Engine & Ingestion (SIG)**| 0 | 0 | 0 | 0 | 0 |
| **Navigation & Explorer UX (NAV)** | 0 | 0 | 0 | 0 | 0 |
| **Qualitative Analysis / RAG (RAG)**| 1 | 0 | 0 | 1 | 0 |
| **Product Usability (UX)** | 0 | 0 | 0 | 0 | 0 |
| **Total** | **2** | **0** | **0** | **2** | **0** |

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

### [QTR-AUTH-03] Server-Side User Credential & Preference Storage ✅
- **Category**: Auth & Routing
- **Component**: [`frontend/src/pages/Settings.tsx`](frontend/src/pages/Settings.tsx), [`backend/app/models/user.py`](backend/app/models/user.py), [`backend/app/core/security.py`](backend/app/core/security.py), [`backend/app/api/v1/users.py`](backend/app/api/v1/users.py)
- **Description**: `openai_api_key` and `sec_user_agent` persist only in browser `localStorage`.
- **Acceptance Criteria**:
  - [x] Add encrypted/masked columns to `User` model for external credentials.
  - [x] Implement AES-CBC Fernet credential encryption and masking utilities.
  - [x] Add `GET /users/credentials` and `PUT /users/credentials` endpoints to persist and preview settings securely across sessions.
  - [x] Connect `Settings.tsx` to hydrate, save, and reset server-side credentials with audit logging.
  - [x] 100% test coverage in `backend/app/tests/test_user_credentials.py`.

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

### [QTR-RSK-02] Dynamic Drawdown Curve in `Risk.tsx` ✅
- **Category**: Risk Analytics
- **Component**: [`frontend/src/pages/Risk.tsx`](frontend/src/pages/Risk.tsx), [`backend/app/services/risk_engine.py`](backend/app/services/risk_engine.py), [`backend/app/api/v1/risk.py`](backend/app/api/v1/risk.py)
- **Description**: Historical drawdown chart uses static 12-point dummy array.
- **Acceptance Criteria**:
  - [x] Feed historical drawdown series from Yahoo Finance historical calculations (`get_stock_risk_analysis`).
  - [x] Render actual drawdown curve in Recharts.
  - [x] Generate deterministic forward stressed shock simulation trajectory.
  - [x] Unit test coverage in `backend/app/tests/test_risk_engine.py`.

### [QTR-SIG-01] Wire Sentiment & Institutional Ingestion into Periodic Worker ✅
- **Category**: Signal Engine
- **Component**: [`backend/app/services/signal_engine.py`](backend/app/services/signal_engine.py)
- **Description**: Periodic background task only checks Form 4 insider transactions and company facts EPS; sentiment spike detection is never called.
- **Acceptance Criteria**:
  - [x] Schedule `detect_sentiment_spike` in background loop.
  - [x] Save detected sentiment signals to `signals` DB table.
  - [x] Schedule `detect_institutional_buying` accumulation in background loop.
  - [x] 100% test coverage in `backend/app/tests/test_signal_engine.py`.

### [QTR-SIG-02] Real SEC Form 13F Filing Ingestion for Institutional Buying ✅
- **Category**: Signal Engine
- **Component**: [`backend/app/providers/sec.py`](backend/app/providers/sec.py)
- **Description**: 13F institutional holdings parsing is missing; only Form 4 XML is implemented.
- **Acceptance Criteria**:
  - [x] Implement XML parser for SEC Form 13F filings.
  - [x] Detect significant quarter-over-quarter institutional accumulation.
  - [x] Support async Form 13F filing retrieval for institutional managers.
  - [x] 100% test coverage in `backend/app/tests/providers/test_sec_form13f.py`.

### [QTR-NAV-01] Universal Search & Command Palette (`Ctrl+K`) ✅
- **Category**: Navigation & Shell
- **Component**: [`frontend/src/layouts/MainLayout.tsx`](frontend/src/layouts/MainLayout.tsx), [`frontend/src/components/CommandPalette.tsx`](frontend/src/components/CommandPalette.tsx), [`frontend/src/components/ui/dialog.tsx`](frontend/src/components/ui/dialog.tsx)
- **Description**: Search input in top navigation has no event handlers or command palette modal.
- **Acceptance Criteria**:
  - [x] Open search modal / command palette on click or `Ctrl+K` / `Cmd+K`.
  - [x] Search stocks by ticker or company name via `/stocks/search` and route to `/research/:ticker` or `/risk/:ticker`.
  - [x] Support keyboard navigation (`ArrowUp`, `ArrowDown`, `Enter`, `Escape`).
  - [x] Include quick platform navigation shortcuts and popular market assets.
  - [x] Backend test coverage in `backend/app/tests/test_research_search.py`.

### [QTR-RAG-01] Earnings Call Transcript Ingestion & Vector Embeddings ✅
- **Category**: Qualitative Analysis
- **Component**: [`backend/app/services/llm_orchestrator.py`](backend/app/services/llm_orchestrator.py), [`backend/app/providers/transcript.py`](backend/app/providers/transcript.py)
- **Description**: Transcript retrieval is stubbed with empty array (`"transcripts": []`).
- **Acceptance Criteria**:
  - [x] Integrate transcript provider (`TranscriptProvider` for earnings calls & SEC MD&A).
  - [x] Generate chunk embeddings via OpenAI embeddings API with normalized deterministic fallback.
  - [x] Retrieve top-K relevant excerpts for LLM qualitative synthesis node.
  - [x] 100% test coverage in `backend/app/tests/test_transcript_rag.py`.

---

## 🟢 Priority 2 — Medium Improvements & Polish

### [QTR-RSK-03] Quantitative Scenario Stress Testing ✅
- **Category**: Risk Analytics
- **Component**: [`frontend/src/pages/Risk.tsx`](frontend/src/pages/Risk.tsx), [`backend/app/services/risk_engine.py`](backend/app/services/risk_engine.py), [`backend/app/api/v1/risk.py`](backend/app/api/v1/risk.py)
- **Description**: Macro stress scenarios (Fed pivot, Oil spike, Recession) use simple visual multipliers.
- **Acceptance Criteria**:
  - [x] Connect scenario modeling to historical factor beta sensitivities (`market_beta`, `interest_rate_beta`, `oil_beta`, `tech_momentum_beta`, `credit_spread_beta`).
  - [x] Implement multi-factor macroeconomic shock scenarios (`fed_pivot_50bps`, `global_recession`, `oil_spike_120`, `ai_infra_expansion`, `credit_spread_widening`, `usd_surge_10`).
  - [x] Expose `scenarios` and `factor_sensitivities` in `GET /stocks/{ticker}/risk` and dedicated `GET /stocks/{ticker}/scenarios`.
  - [x] Interactive UI in `frontend/src/pages/Risk.tsx` with dynamic scenario selection, driver details, and modal inspection dialog.
  - [x] 100% test coverage in `backend/app/tests/test_risk_engine.py`.

### [QTR-SIG-03] Live Intraday Sentiment Curve in `Signals.tsx` ✅
- **Category**: Signal Engine
- **Component**: [`frontend/src/pages/Signals.tsx`](frontend/src/pages/Signals.tsx), [`backend/app/api/v1/signals.py`](backend/app/api/v1/signals.py), [`backend/app/services/signal_engine.py`](backend/app/services/signal_engine.py)
- **Description**: Intraday social/news sentiment chart uses static 8-point dummy array.
- **Acceptance Criteria**:
  - [x] Implement `build_intraday_sentiment_curve` in `SignalEngine` aggregating time-bucketed social mention volumes and news polarity.
  - [x] Expose `GET /api/v1/signals/sentiment-curve` returning `points`, `current_social_score`, `current_news_score`, and `sentiment_trend`.
  - [x] Wire `Signals.tsx` to live sentiment curve endpoint with quick ticker chips (`ALL`, `NVDA`, `AAPL`, `MSFT`, `XLK`) and dynamic tooltips.
  - [x] 100% test coverage in `backend/app/tests/test_signal_engine.py`.

### [QTR-NAV-02] Research Explorer Grid View & Bulk Actions ✅
- **Category**: Navigation & Explorer
- **Component**: [`frontend/src/pages/ResearchExplorer.tsx`](frontend/src/pages/ResearchExplorer.tsx)
- **Description**: Grid view toggle button changes state but renders the table; checkboxes do nothing.
- **Acceptance Criteria**:
  - [x] Implement responsive card-based Grid layout when `view === "grid"`.
  - [x] Add multi-asset selection state, master select-all toggle, and bulk actions bar ("Export Selected", "Compare in Simulation", "Clear Selection").
  - [x] Render actionable asset cards with risk badges, signals, prices, and direct research/risk navigation.

### [QTR-NAV-03] Export Handlers (CSV / PDF) across Tables and Simulations ✅
- **Category**: Navigation & Explorer
- **Component**: [`frontend/src/lib/export.ts`](frontend/src/lib/export.ts), [`frontend/src/pages/ResearchExplorer.tsx`](frontend/src/pages/ResearchExplorer.tsx), [`frontend/src/pages/Simulation.tsx`](frontend/src/pages/Simulation.tsx), [`frontend/src/pages/Signals.tsx`](frontend/src/pages/Signals.tsx)
- **Description**: Download / export buttons exist without click actions.
- **Acceptance Criteria**:
  - [x] Create modular RFC 4180 compliant client-side CSV download utility in `frontend/src/lib/export.ts`.
  - [x] Wire export button in `ResearchExplorer.tsx` to download discovery and filtered stock results.
  - [x] Wire export button in `Simulation.tsx` to download Monte Carlo trajectory percentiles and risk statistics.
  - [x] Wire download button in `Signals.tsx` to download live institutional 13F and insider Form 4 streams.

### [QTR-RAG-02] PostgreSQL Vector Store Integration (`pgvector`) ✅
- **Category**: Qualitative Analysis
- **Component**: [`backend/app/models/document_chunk.py`](backend/app/models/document_chunk.py), [`backend/alembic/versions/20261020_0001_add_pgvector_and_document_chunks.py`](backend/alembic/versions/20261020_0001_add_pgvector_and_document_chunks.py), [`backend/app/providers/transcript.py`](backend/app/providers/transcript.py)
- **Description**: No vector schema or extension configured in Alembic / PostgreSQL.
- **Acceptance Criteria**:
  - [x] Compile and enable `pgvector` extension in PostgreSQL container.
  - [x] Create `DocumentChunk` model with 1536-dimensional `Vector(1536)` column and HNSW cosine distance index.
  - [x] Generate Alembic migration script for pgvector and document chunks table.
  - [x] Implement async vector storage (`store_chunks`) and cosine similarity search (`search_similar_chunks`) with <=> operator.
  - [x] 100% test coverage in `backend/app/tests/test_vector_store.py`.

---

## 🛡️ Hardening & Usability Pass (Oct 2026) — Completed

| ID | Summary |
| :--- | :--- |
| QTR-SEC-01 ✅ | OpenAI key read only from encrypted server storage; removed from `localStorage` and request headers |
| QTR-SEC-02 ✅ | Redis rate limits on login, register and research generation; minimum password length 8 |
| QTR-SEC-03 ✅ | Inactive users blocked; refresh tokens; `POST /auth/logout` revokes all tokens through `users.token_version` |
| QTR-SEC-04 ✅ | `CREDENTIAL_ENCRYPTION_KEY` (MultiFernet keeps legacy values readable); `debug` off by default |
| QTR-RAG-04 ✅ | Query and chunks embedded in the same vector space; stored chunks tagged with their embedding model; no synthesized transcripts |
| QTR-PORT-05 ✅ | Simulation uses real 1Y returns (vol, correlation, beta, drawdown) with CAPM; weights must sum to 1; estimated tickers flagged |
| QTR-PORT-06 ✅ | Portfolios page (CRUD) and save/load in Simulation |
| QTR-NAV-05 ✅ | Watchlist API and UI (Explorer/Stock Detail stars, Dashboard strip, watchlist-first ticker chips, command palette) |
| QTR-STK-04 ✅ | Prices and market caps stored numerically and formatted per listing currency; search returns sector/P/E/beta |
| QTR-RSK-05 ✅ | Risk page bound to the real scenario schema; placeholder KPIs, trends and scenarios removed |
| QTR-OPS-01 ✅ | Alembic owns the schema (frozen baseline, `alembic check`); single-worker signal job through advisory lock |
| QTR-OPS-02 ✅ | CI: ruff, mypy, migrations, pytest, ESLint, tsc, build, Playwright; frontend Dockerfile and compose service |

---

## ✅ Follow-up Pass (Oct 2026) — Completed

| ID | Summary |
| :--- | :--- |
| QTR-AUTH-03 ✅ (partial) | `POST /auth/change-password` (revokes other sessions) and an Account page form. The email reset flow is still open below. |
| QTR-AUTH-04 ✅ | Refresh token in an `HttpOnly; SameSite=Strict` cookie scoped to `/api/v1/auth`; access token in memory only; logout clears the cookie; query cache cleared on logout |
| QTR-RSK-04 ✅ | Risk API returns `assumed_inputs` and drops factor sensitivities derived from assumed values; Risk page warns |
| QTR-RSK-06 ✅ | D/E computed from reported debt / stockholders' equity (was debt / (assets − debt), and 0 when unknown); SEC `LongTermDebt`/`StockholdersEquity` tags added |
| QTR-PORT-04 ✅ | Portfolio tickers verified against Yahoo (shared `stock_lookup` service); duplicates rejected; nothing written on failure |
| QTR-UX-01 ✅ | Report "generated N ago" with Refresh (`?refresh=true`), "Data as of" on Stock Detail, UTC-safe timestamp parsing |
| QTR-UX-02 ✅ | In-app watchlist alerts: `GET /watchlist/alerts`, `POST /watchlist/alerts/seen`, header bell with unread count |
| QTR-UX-03 ✅ | Recent Activity card on Account (audit log) |
| QTR-UX-04 ✅ | `/compare` page: risk metrics side by side plus a real 1Y correlation matrix; Explorer "Compare (2–4)" |
| QTR-NAV-04 ✅ | `/stocks/search` `limit`/`offset` with a true `total_count`; Explorer pagination |
| QTR-NAV-06 ✅ | Explorer "Simulate Selected" now opens Simulation with those tickers (`?tickers=` was ignored) |
| QTR-OPS-03 ✅ | Route-level error boundary so one page crash no longer blanks the app |

---

## ✅ Core Features Pass (Oct 2026) — Completed

| ID | Summary |
| :--- | :--- |
| QTR-STK-05 ✅ | Prices refresh every 15 min (batched Yahoo download, single worker through an advisory lock); `previous_close`/`price_updated_at` columns; day change shown in Explorer, Dashboard watchlist and Stock Detail; research runs no longer blank a known price |
| QTR-PORT-07 ✅ | Holdings: shares and average cost per position, `GET /portfolio/{id}/performance` (value, unrealized and day P&L, sector allocation, totals per currency, stale quotes refreshed on view), `/portfolios/:id` page; weights derived from shares when omitted |
| QTR-STK-06 ✅ | Price history chart on Stock Detail (`GET /stocks/{ticker}/history`, 1M/6M/1Y/5Y, 15-min cache) |

---

## ✅ Compliance & Reach Pass (Oct 2026) — Completed

| ID | Summary |
| :--- | :--- |
| QTR-STK-07 ✅ | Daily fundamentals refresh (market cap, P/E, beta, name, sector) inside the 15-min job; Yahoo sectors mapped to app names; missing fields never erase known ones |
| QTR-STK-08 ✅ | Seed uses `TMCV.NS`; migration 0007 removes unreferenced delisted `TATAMOTORS.NS` |
| QTR-UX-05 ✅ | One-shot price alerts (`/alerts/price`), checked after every price refresh, delivered through the header bell; form on Stock Detail |
| QTR-SEC-05 ✅ | `GET /users/me/export` (JSON, no secrets) and `DELETE /users/me` (password-confirmed, removes all owned rows, anonymous erasure record); "Your Data" card on Account |
| QTR-UX-06 ✅ | "Not investment advice" notice on Dashboard recommendations and Stock Detail analysis |
| QTR-UX-07 ✅ | Phone layout: off-canvas navigation drawer, stacked Explorer filters and Simulation controls, compact header; no clipping on any page at 390px |
| QTR-UX-08 ✅ | Simulation's hardcoded "Market Open" badge now shows the real US/NSE session |

---

## 📋 Open Tickets

### [QTR-AUTH-05] Email Password Reset (P3, deferred: personal use; notifications use Slack)
- **Description**: Users who are signed in can change their password; a forgotten password still can't be recovered.
- **Acceptance Criteria**:
  - [ ] Choose an email provider; single-use, time-limited reset tokens; bump `token_version` on reset.

### [QTR-RAG-03] Real Earnings Transcript Source (P2, done for US listings)
- **Description**: Only hardcoded AAPL/NVDA/MSFT excerpts existed; other tickers got no qualitative RAG context.
- **Acceptance Criteria**:
  - [x] Use the latest SEC 8-K earnings press release (Exhibit 99.1) for any US ticker, falling back to the bundled excerpts.
  - [ ] NSE/BSE listings: no free equivalent wired in yet.
  - [ ] Full call transcripts would need a paid provider.
