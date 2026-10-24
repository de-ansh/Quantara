# Quantara Roadmap

Detailed tickets live in [issue_tracker.md](issue_tracker.md). This page is the high-level status.

---

## ✅ Delivered

### Phases 1–4 (original plan)
Database-backed auth and profiles, audit logging, live Yahoo/SEC data wiring, deterministic risk engine, background signal processing, research caching, and dynamic frontend views for Explorer, Risk, Simulation, Signals, Settings and Account.

### Hardening pass (Oct 2026)
- **Security:** OpenAI keys are stored only server-side (encrypted, with an optional dedicated `CREDENTIAL_ENCRYPTION_KEY`). Login, register and research generation are rate-limited through Redis. Refresh tokens are added, and logout revokes every outstanding token through `users.token_version`. Inactive users are blocked.
- **Data integrity:** The simulator uses real price history (volatility, correlation, beta, drawdown) with CAPM returns. Embeddings never mix vector spaces. Fabricated transcripts and placeholder UI values are removed. Prices are stored as numbers.
- **Operations:** Alembic owns the schema (frozen baseline, `alembic check` in CI). The signal job runs in a single worker through a Postgres advisory lock. Unused Celery and Pinecone config is removed.
- **Delivery:** GitHub Actions CI covers ruff, mypy, migrations, pytest, ESLint, the type check, the build and Playwright. Docker images exist for both backend and frontend.

### Usability (Oct 2026)
- **Portfolios page:** create, edit, delete, and open in Simulation. Simulation can save as new or update the loaded portfolio.
- **Watchlist:** star tickers in Explorer and Stock Detail. They appear on the Dashboard, first in the ticker chips, and in the command palette. Unknown tickers are verified against Yahoo before they're tracked.

---

### Follow-up (Oct 2026)
Change password, httpOnly cookie sessions, disclosed risk assumptions and correct D/E, verified portfolio tickers, data-freshness labels, watchlist alerts, account activity, Explorer pagination, stock comparison, and a route error boundary.

### Core features (Oct 2026)
Prices that refresh every 15 minutes, holdings with live P&L and sector allocation, and a price-history chart on Stock Detail.

### Compliance & reach (Oct 2026)
Daily fundamentals refresh, price alerts, personal-data export and account deletion, an investment-advice notice, and a phone layout.

---

## 🔜 Next

| Area | Item | Ticket |
| :--- | :--- | :--- |
| Accounts | Email-based password reset (needs an email provider) | QTR-AUTH-05 |
| Research | Real earnings-transcript source (only AAPL/NVDA/MSFT excerpts exist) | QTR-RAG-03 |
| Data | Licensed market-data vendor (Yahoo/yfinance is unofficial; not for commercial use) | — |
| Ops | Error monitoring (e.g. Sentry) and scheduled database backups | — |
