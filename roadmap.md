# Quantara Development Roadmap & Issue Registry

This document outlines the current architectural issues, missing integrations, and hardcoded placeholders across the Quantara codebase, followed by a structured multi-phase roadmap to bring the platform to a production-ready, fully functional state.

---

## 🔍 Current System Audit & Issue Registry

### 1. Database & Authentication Mocks
*   **Static User Authentication**: In [auth.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/api/v1/auth.py) and [dependencies.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/core/dependencies.py), logins are matched against a hardcoded email and password, registrations do not write records, and authentication dependencies decode JWT payloads directly without database validation.
*   **Placeholder Profile Control**: In [users.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/api/v1/users.py), user details are returned as null values, and updating the risk profile only reflects in the response without updating any model.
*   **Mock Audit Logging**: In [audit.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/api/v1/audit.py), logging is simulated with a hardcoded login entry.

### 2. Disconnected Analytical Engines
*   **Dangling Yahoo Finance Integration**: In [yahoo.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/providers/yahoo.py), calculations for annualized volatility, max drawdown, and beta are functional but completely unused by any endpoint or engine.
*   **Dangling Signal Engine**: In [signal_engine.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/services/signal_engine.py), metrics for sentiment spikes, institutional buying, and insider purchases are defined but never executed or routed to the API.
*   **Mocked LangGraph Workflow Nodes**: In [llm_orchestrator.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/services/llm_orchestrator.py):
    *   `_compute_metrics` is a stub returning static zeros.
    *   `_risk_classification` bypasses calculations and defaults to a Moderate risk level (50.0).
    *   `_store_result` lacks database persistence logic.
*   **Expensive No-Cache Research Pipeline**: In [research.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/api/v1/research.py), there is no cache lookup layer, meaning the platform invokes the OpenAI model on every single ticker research request.

### 3. Static Frontend Components
*   **Unimplemented Configuration Pages**: In [App.tsx](file:///Users/ashishmishra/Developer/Projects/quantara/frontend/src/App.tsx), the Settings and Account components are inline shells.
*   **NVDA-Locked Risk View**: In [Risk.tsx](file:///Users/ashishmishra/Developer/Projects/quantara/frontend/src/pages/Risk.tsx), all variables, factor contributions, and scenario shocks are static client-side values.
*   **Simulated Portfolio Projections**: In [Simulation.tsx](file:///Users/ashishmishra/Developer/Projects/quantara/frontend/src/pages/Simulation.tsx), the Monte Carlo curve is a hardcoded SVG coordinate, metrics are static variables, and the simulation controls do not trigger API requests.
*   **Static Filtering & Discovery**: In [ResearchExplorer.tsx](file:///Users/ashishmishra/Developer/Projects/quantara/frontend/src/pages/ResearchExplorer.tsx), filters do not trigger searches, and the table lists a static array of 7 companies.
*   **Simulated Signals Feed**: In [Signals.tsx](file:///Users/ashishmishra/Developer/Projects/quantara/frontend/src/pages/Signals.tsx), 13F institutional accumulation, insider trading events, and sentiment charts are built on static mock datasets.

---

## 🗺️ Phase-by-Phase Integration Roadmap

### Phase 1: Database Persistence & Core Auth (Security & Users)
Establish the data layer foundation by connecting endpoints to PostgreSQL:
1.  **Database User Registration & Login**:
    *   Update [auth.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/api/v1/auth.py) to check for duplicate emails, write new user records using security helper hash values, and perform actual password validation.
    *   Update [dependencies.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/core/dependencies.py) to fetch the user from the database by ID retrieved from the decoded token.
2.  **Risk Profile Storage**:
    *   Implement user model updates in [users.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/api/v1/users.py) to save user preferences, risk tolerance, and sector weight limits in the database.
3.  **Database Audit Logging**:
    *   Implement database write triggers inside [audit.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/api/v1/audit.py) to record user logins, profile alterations, and report calculations.

### Phase 2: Engine Wiring & Ingestion (Data Pipeline)
Integrate the quantitative analytics components with external data APIs:
1.  **Yahoo Finance & SEC Data Flow**:
    *   Wire up [yahoo.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/providers/yahoo.py) to retrieve historical data for the calculated metrics.
    *   Update [llm_orchestrator.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/services/llm_orchestrator.py) to replace the static `_compute_metrics` stub with actual computations from yfinance/SEC EDGAR data.
2.  **Deterministic Risk Execution**:
    *   In [llm_orchestrator.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/services/llm_orchestrator.py), update the `_risk_classification` node to execute the deterministic calculations from [risk_engine.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/services/risk_engine.py).
3.  **Active Signal Processing**:
    *   Establish a cron scheduler or background task utilizing [signal_engine.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/services/signal_engine.py) to periodically run analysis on earnings surprises, institutional ownership changes, and insider Form 4 files (retrieved from [sec.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/providers/sec.py)).
    *   Save generated signals to the database so that [signals.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/api/v1/signals.py) returns real-time market data.
4.  **Research Report Caching & DB Persistence**:
    *   In [research.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/api/v1/research.py), implement check-and-cache lookups. Write generated reports to the PostgreSQL database in [llm_orchestrator.py](file:///Users/ashishmishra/Developer/Projects/quantara/backend/app/services/llm_orchestrator.py) under the `_store_result` node to prevent redundant LLM invocations.

### Phase 3: Frontend Dynamic Integration (Interactive UI)
Connect the React UI to the fully functional backend APIs:
1.  **Dynamic Stock Search & Explorer**:
    *   Update [ResearchExplorer.tsx](file:///Users/ashishmishra/Developer/Projects/quantara/frontend/src/pages/ResearchExplorer.tsx) to query a search endpoint with parameters (P/E limit, Beta, signals) instead of rendering static results.
2.  **Dynamic Ticker Risk Analysis**:
    *   Refactor [Risk.tsx](file:///Users/ashishmishra/Developer/Projects/quantara/frontend/src/pages/Risk.tsx) to fetch asset risk statistics dynamically based on the current active ticker (e.g. `/stocks/{ticker}/risk`), updating volatility metrics, factor attribution bar charts, and shock scenarios.
3.  **Dynamic Monte Carlo Simulation**:
    *   Update [Simulation.tsx](file:///Users/ashishmishra/Developer/Projects/quantara/frontend/src/pages/Simulation.tsx) to trigger a `POST` request to `/api/v1/portfolio/simulate` on clicking "Run Simulation".
    *   Render the resulting curve and standard deviations using Recharts (instead of the static SVG path).
4.  **Real-Time Signals & Inflow Monitoring**:
    *   Wire up the tables in [Signals.tsx](file:///Users/ashishmishra/Developer/Projects/quantara/frontend/src/pages/Signals.tsx) to consume live backend endpoints, exposing real 13F institutional changes and parsed SEC Form 4 insider transactions.

### Phase 4: Production Features & Polishing (UI Expansion)
Complete secondary dashboard views and institutional tools:
1.  **Settings and Security Panels**:
    *   Replace the inline shells in [App.tsx](file:///Users/ashishmishra/Developer/Projects/quantara/frontend/src/App.tsx) with fully styled components containing api-key configuration fields, visual theme controls, and account settings.
2.  **Real-Time Market VIX Feed**:
    *   Integrate a market utility script to supply live VIX metrics and macroeconomic alerts to the header and KPI blocks in [Dashboard.tsx](file:///Users/ashishmishra/Developer/Projects/quantara/frontend/src/Dashboard.tsx) and [Simulation.tsx](file:///Users/ashishmishra/Developer/Projects/quantara/frontend/src/Simulation.tsx).
