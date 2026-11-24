# Quantara

**Risk-Intelligent Investment Research Platform**

**Website:** https://de-ansh.github.io/Quantara/ (features, screenshots and how to run it)

A full-stack financial intelligence platform combining a React/TypeScript frontend with a production-grade Python/FastAPI backend.

## 📁 Project Structure

```
quantara/
├── frontend/          # React + TypeScript + Vite
│   ├── src/
│   ├── public/
│   └── package.json
│
└── backend/           # FastAPI + Python 3.11+
    ├── app/
    ├── alembic/
    ├── pyproject.toml
    └── docker-compose.yml
```

## 🚀 Quick Start

### Prerequisites

**Required:**
- Node.js 18+ and pnpm (for frontend)
- Python 3.11+ (for backend)
- Docker Desktop (for PostgreSQL and Redis)
- UV package manager (for backend dependencies)

**Install UV (if not already installed):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Step 1: Start Docker Services

**Start Docker Desktop first**, then:

```bash
cd backend

# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Verify services are running
docker ps
# You should see: quantara-postgres and quantara-redis

# Test PostgreSQL connection
docker exec -it quantara-postgres psql -U quantara -d quantara
# Type \q to exit
```

### Step 2: Setup Backend

```bash
cd backend

# Install dependencies
make install
# Or: uv sync

# Create environment file
cp .env.example .env

# Edit .env and add required values:
# - SECRET_KEY (generate with: openssl rand -hex 32)
# - OPENAI_API_KEY (your OpenAI API key)

# Run database migrations
make upgrade
# Or: uv run alembic upgrade head

# Start backend server
make dev
# Or: uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Backend will be running on:** `http://localhost:8000`

**API Documentation:** `http://localhost:8000/docs`

### Step 3: Setup Frontend

```bash
cd frontend

# Install dependencies
pnpm install

# Start development server
pnpm run dev
```

**Frontend will be running on:** `http://localhost:5173`

### Run it day to day (Docker)

For real use, run the whole app in Docker rather than the dev servers: every service restarts
on its own, and the backend runs without auto-reload (a hung reload once left an old process
holding the background-job locks, and prices silently stopped for two days).

```bash
cd backend
docker compose up -d            # postgres, redis, daily backups, backend :8000, frontend :3000
```

Open **http://localhost:3000**.

- **After pulling new code:** `docker compose up -d --build backend frontend` (migrations run on start).
- **Check it:** `docker compose ps` should show `quantara-backend` as `healthy`. If prices are more
  than two hours old the app shows a warning banner; `docker compose restart backend` fixes a stuck job.
- **Backups:** a dump lands in `backend/backups/` daily (14 kept). Restore one (replaces current data):
  `docker exec -i quantara-postgres pg_restore -U quantara -d quantara --clean --if-exists --no-owner < backups/<file>.dump`
- **Keep it running:** turn on Docker Desktop → Settings → General → *Start Docker Desktop when you
  sign in*. Nothing runs while the Mac sleeps; prices and signals catch up on wake.

### Alternative: Run Everything with Docker

If you prefer to run the backend in Docker as well:

```bash
cd backend

# Make sure .env file exists with required variables
cp .env.example .env
# Edit .env and add SECRET_KEY and OPENAI_API_KEY

# Start all services (PostgreSQL, Redis, Backend)
make docker-up
# Or: docker-compose up -d

# View logs
make docker-logs
# Or: docker-compose logs -f

# Stop all services
make docker-down
# Or: docker-compose down
```

### Verify Everything is Working

**1. Check Backend Health:**
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "app": "Quantara",
  "version": "0.1.0",
  "environment": "development"
}
```

**2. Test Authentication:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@quantara.com", "password": "password"}'
```

**3. Access API Documentation:**
Open `http://localhost:8000/docs` in your browser

**4. Access Frontend:**
Open `http://localhost:5173` in your browser

## 🏗️ Architecture

### Frontend
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui
- **State Management**: React Context

### Backend
- **Framework**: FastAPI (async)
- **Language**: Python 3.11+
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **AI**: OpenAI GPT-4o + LangGraph
- **Package Manager**: UV

## 🎯 Core Features

### Risk Engine
Deterministic Python-only risk scoring algorithm:
- Volatility analysis
- Beta calculation
- Leverage assessment
- Earnings stability
- Sector risk
- Valuation metrics

### Research Engine
Structured financial analysis pipeline:
- Data retrieval
- Metrics computation
- LLM-powered insights
- Schema validation
- Vector embeddings
- Qualitative context from the company's latest earnings press release (SEC 8-K, Exhibit 99.1); US listings only

### Recommendation Engine
Multi-component scoring system:
- Research quality (40%)
- Signal strength (30%)
- Risk alignment (20%)
- Macro fit (10%)

### Signal Detection
Real-time market signals:
- Earnings surprises
- Institutional buying
- Insider transactions
- Sentiment spikes

## 📚 Documentation

- **Backend**: See [backend/README.md](backend/README.md)
- **API Docs**: http://localhost:8000/docs (when running)

## 🔐 Environment Setup

### Backend Environment

Copy `backend/.env.example` to `backend/.env` and configure:

```env
SECRET_KEY=your-secret-key-here
OPENAI_API_KEY=your-openai-api-key
DATABASE_URL=postgresql+asyncpg://quantara:quantara@localhost:5432/quantara
REDIS_URL=redis://localhost:6379/0
```

For production, also set `ENVIRONMENT=production` (which marks the session cookie `Secure`, so HTTPS is required) and a stable `CREDENTIAL_ENCRYPTION_KEY`.


To report backend errors to [Sentry](https://sentry.io), set `SENTRY_DSN`. Nothing is sent while it's unset, and requests are reported without personal data.

### Slack (optional)

With a Slack app connected, Quantara:

- **answers questions in Slack.** DM the bot, or @mention it in a channel, and it replies in a thread using the same assistant as the web chat, as your linked Quantara account (your risk profile, holdings and saved OpenAI key);
- **sends the daily digest** as a DM after 16:00 IST on weekdays: market close, plus news, signals and alerts on watched or held stocks. If Slack refuses it, the app retries every 10 minutes;
- **sends password-reset links** and a warning when two-factor login is turned off through a reset.

It uses Socket Mode, so no public URL is needed. Leave the Slack settings unset to turn all of this off.

**Set it up**

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From a manifest**, pick your workspace and paste [`backend/slack-app-manifest.yml`](backend/slack-app-manifest.yml).
2. **Basic Information → App-Level Tokens → Generate**, with the `connections:write` scope. Copy the `xapp-…` token.
3. **Install App → Install to Workspace**. Copy the **Bot User OAuth Token** (`xoxb-…`).
4. Find your Slack member ID: click your name in Slack → **Profile** → ⋮ → **Copy member ID** (it looks like `U0123ABCD`). The bot's **Home** tab also shows it.
5. Find your Quantara user ID:
   ```bash
   cd backend && docker compose exec postgres psql -U quantara -d quantara -c "select id, email from users;"
   ```
6. Add to `backend/.env`:
   ```env
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_APP_TOKEN=xapp-...
   SLACK_USERS=U0123ABCD:1          # SlackMemberID:QuantaraUserID, comma-separated for several people
   ```
7. Recreate the backend so it reads the new `.env`. `docker compose restart` does **not** reload it:
   ```bash
   cd backend && docker compose up -d --force-recreate backend
   docker compose logs backend | grep -i bolt     # expect "Bolt app is running!"
   ```
8. Open the Quantara app in Slack. The Home tab should say *You're linked*. Then send it a DM such as *is TCS a buy?*

Only Slack users listed in `SLACK_USERS` get answers. Anyone else is told their member ID and nothing more. Notifications go as DMs to every listed user, including password-reset links for any account, so list only people you trust with those.

**Webhook instead of the bot.** Without the bot tokens, notifications (but not chat) can go to a channel via an [incoming webhook](https://api.slack.com/messaging/webhooks): set `SLACK_WEBHOOK_URL`. When the bot is set up, it is used instead.

**If something's off**

| Symptom | Fix |
| --- | --- |
| Home tab spins forever | The backend isn't connected: check the tokens and the `Bolt app is running!` log line, then recreate the backend. |
| No **Messages** tab, or "sending messages to this app has been turned off" | **App Home → Show Tabs → Messages Tab** on, and tick *Allow users to send Slash commands and messages from the messages tab*. |
| DMs get no answer | Your member ID is missing from `SLACK_USERS`, or `message.im` / `im:history` are missing. After changing scopes or events, reinstall the app and copy the new bot token. |
| Reinstalling fails with a PKCE / redirect URL error | Use the **Reinstall to Workspace** button under **Install App**, not a custom redirect URL. |
| Webhook posts stop and Slack answers `no_service` | Reinstalling or removing the app revokes its webhooks. Use the bot, or create a new webhook. |
| `invalid_auth` / `not_authed` in the logs | The token is from a different app, or the app was uninstalled. Copy fresh tokens. Keep **token rotation off**: the bot can't refresh tokens. |

### Sessions & deployment

Sign-in keeps the access token in memory and the refresh token in an `HttpOnly; SameSite=Strict` cookie scoped to `/api/v1/auth`. The browser only sends that cookie when the UI and API are on the **same site** (the same registrable domain; ports may differ). Examples:

- ✅ `localhost:5173` → `localhost:8000`, or `app.example.com` → `api.example.com`
- ❌ `app.example.com` → `example-api.herokuapp.com` (users are signed out on every reload)

The UI's origin must also be listed in `CORS_ORIGINS`.

## 🧪 Testing

### Backend Tests

```bash
cd backend
make test
make test-cov
```

Tests run offline: `app/tests/conftest.py` replaces Yahoo with deterministic synthetic prices, makes SEC look unavailable, and fails any test that tries to reach a public host.

## 🛠️ Development

### Backend Development

```bash
cd backend

# Format code
make format

# Lint code
make lint

# Create migration
make migrate msg="description"

# Apply migrations
make upgrade
```

## 🐳 Docker

The backend includes a complete Docker setup:

```bash
cd backend
docker-compose up -d
```

Services:
- PostgreSQL (port 5432)
- Redis (port 6379)
- Backend API (port 8000)
- `db-backup`: a daily `pg_dump` into `backend/backups/`, keeping 14 days

Restore a backup (this replaces the current data):

```bash
cd backend
docker compose exec -T postgres pg_restore -U quantara -d quantara --clean --if-exists < backups/quantara-YYYYMMDD-HHMMSS.dump
```

Backups sit on the same machine as the database, so copy `backend/backups/` somewhere else (another disk or cloud storage) to survive a disk failure.

## 🔧 Common Commands

### Backend Commands

```bash
cd backend

# Development
make dev              # Start development server
make install          # Install dependencies
make test             # Run tests
make test-cov         # Run tests with coverage
make format           # Format code with black
make lint             # Lint code with ruff and mypy

# Database
make migrate msg="description"  # Create new migration
make upgrade                     # Apply migrations
make downgrade                   # Rollback one migration

# Docker
make docker-up        # Start all services
make docker-down      # Stop all services
make docker-logs      # View logs

# Manual commands
uv sync                                    # Install dependencies
uv run uvicorn app.main:app --reload      # Start server
uv run pytest                              # Run tests
uv run alembic upgrade head                # Run migrations
```

### Frontend Commands

```bash
cd frontend

pnpm install          # Install dependencies
pnpm run dev          # Start development server
pnpm run build        # Build for production
pnpm run preview      # Preview production build
pnpm run lint         # Lint code
```

### Docker Commands

```bash
cd backend

# Start specific services
docker-compose up -d postgres redis    # Only databases
docker-compose up -d                   # All services

# View logs
docker-compose logs -f                 # All services
docker-compose logs -f postgres        # PostgreSQL only
docker-compose logs -f backend         # Backend only

# Stop services
docker-compose down                    # Stop all
docker-compose down -v                 # Stop and remove volumes

# Access PostgreSQL
docker exec -it quantara-postgres psql -U quantara -d quantara

# Access Redis
docker exec -it quantara-redis redis-cli
```

## 🐛 Troubleshooting

### Docker Issues

**Problem: "Cannot connect to the Docker daemon"**
```bash
# Solution: Start Docker Desktop
# Open Docker Desktop application and wait for it to start
# Verify with:
docker --version
docker ps
```

**Problem: Port already in use (5432, 6379, or 8000)**
```bash
# Find what's using the port
lsof -i :5432  # For PostgreSQL
lsof -i :6379  # For Redis
lsof -i :8000  # For backend

# Stop the conflicting service or change ports in docker-compose.yml
```

**Problem: PostgreSQL container won't start**
```bash
# Remove old volumes and restart
docker-compose down -v
docker-compose up -d postgres redis
```

### Backend Issues

**Problem: "ModuleNotFoundError" or import errors**
```bash
cd backend
# Reinstall dependencies
uv sync
```

**Problem: Database connection errors**
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check connection string in .env
# Should be: DATABASE_URL=postgresql+asyncpg://quantara:quantara@localhost:5432/quantara

# Test connection
docker exec -it quantara-postgres psql -U quantara -d quantara
```

**Problem: Alembic migration errors**
```bash
cd backend
# Check current migration status
uv run alembic current

# Reset database (WARNING: destroys all data)
docker-compose down -v
docker-compose up -d postgres redis
uv run alembic upgrade head
```

**Problem: "SECRET_KEY" or "OPENAI_API_KEY" not found**
```bash
cd backend
# Make sure .env file exists
cp .env.example .env

# Generate SECRET_KEY
openssl rand -hex 32

# Add to .env file:
# SECRET_KEY=<generated-key>
# OPENAI_API_KEY=<your-openai-key>
```

### Frontend Issues

**Problem: Module not found errors**
```bash
cd frontend
# Clear node_modules and reinstall
rm -rf node_modules pnpm-lock.yaml
pnpm install
```

**Problem: Can't connect to backend**
```bash
# Verify backend is running
curl http://localhost:8000/health

# Check CORS settings in backend/.env
# CORS_ORIGINS should include http://localhost:5173
```

## 📊 Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Frontend | React + TypeScript + Vite |
| Backend | FastAPI + Python 3.11 |
| Database | PostgreSQL 15 |
| Cache | Redis 7 |
| AI/ML | OpenAI GPT-4o + LangGraph |
| Package Mgmt | pnpm (frontend), UV (backend) |
| Containerization | Docker + docker-compose |

## 🤝 Contributing

1. Follow existing code structure
2. Write tests for new features
3. Run linting before committing
4. Update documentation

## 📄 License

Proprietary - All rights reserved

---

**Built for intelligent, risk-aware investment research**
