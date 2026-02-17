# Quantara Backend

**Risk-Intelligent Investment Research System**

A production-grade FastAPI backend for financial intelligence and investment research, featuring deterministic risk scoring, LLM-powered analysis, and personalized recommendations.

## 🏗️ Architecture

### Tech Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI (async)
- **ORM**: SQLAlchemy (async)
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **AI**: OpenAI GPT-4o + LangGraph
- **Package Manager**: UV (not pip/poetry)
- **Migrations**: Alembic
- **Testing**: pytest + pytest-asyncio
- **Containerization**: Docker + docker-compose

### Core Components

1. **Risk Engine** - Deterministic Python-only risk scoring (0-100 scale)
2. **Research Engine** - Structured financial analysis pipeline
3. **LLM Orchestrator** - LangGraph state machine with strict schema validation
4. **Signal Engine** - Market signal detection (earnings, institutional buying, etc.)
5. **Recommendation Engine** - Multi-component scoring and ranking

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker & docker-compose
- UV package manager
- OpenAI API key

### Installation

```bash
# Install UV if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
make install

# Copy environment template
cp .env.example .env

# Edit .env and add your API keys
# Required: SECRET_KEY, OPENAI_API_KEY, DATABASE_URL
```

### Running with Docker (Recommended)

```bash
# Start all services (PostgreSQL, Redis, Backend)
make docker-up

# View logs
make docker-logs

# Stop services
make docker-down
```

The API will be available at `http://localhost:8000`

### Running Locally

```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Run migrations
make upgrade

# Start development server
make dev
```

## 📚 API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

#### Authentication
- `POST /api/v1/auth/login` - Login and get JWT token
- `POST /api/v1/auth/register` - Register new user

#### User Management
- `GET /api/v1/users/me` - Get current user profile
- `POST /api/v1/users/risk-profile` - Update risk profile

#### Research & Analysis
- `GET /api/v1/stocks/{ticker}/research` - Get research report
- `GET /api/v1/stocks/{ticker}/risk` - Get risk analysis

#### Recommendations
- `GET /api/v1/recommendations` - Get personalized recommendations

#### Signals
- `GET /api/v1/signals` - Get market signals

#### Portfolio
- `POST /api/v1/portfolio/simulate` - Run portfolio simulation

#### Audit
- `GET /api/v1/audit/logs` - Get audit logs

## 🧪 Testing

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
uv run pytest app/tests/test_risk_engine.py -v
```

## 🔧 Development

### Code Quality

```bash
# Format code
make format

# Lint code
make lint
```

### Database Migrations

```bash
# Create new migration
make migrate msg="description of changes"

# Apply migrations
make upgrade

# Rollback one migration
make downgrade
```

### Project Structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── core/                   # Core configuration
│   │   ├── config.py          # Settings
│   │   ├── security.py        # Auth & security
│   │   ├── logging.py         # Structured logging
│   │   ├── database.py        # DB connection
│   │   └── dependencies.py    # FastAPI dependencies
│   ├── api/v1/                # API endpoints
│   │   ├── auth.py
│   │   ├── users.py
│   │   ├── research.py
│   │   ├── risk.py
│   │   ├── recommendations.py
│   │   ├── signals.py
│   │   ├── portfolio.py
│   │   └── audit.py
│   ├── services/              # Business logic
│   │   ├── risk_engine.py
│   │   ├── research_engine.py
│   │   ├── llm_orchestrator.py
│   │   ├── signal_engine.py
│   │   └── recommendation_engine.py
│   ├── models/                # SQLAlchemy models
│   ├── schemas/               # Pydantic schemas
│   ├── repositories/          # Data access layer
│   └── tests/                 # Test suite
├── alembic/                   # Database migrations
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml            # UV dependencies
└── Makefile
```

## 🔐 Security

- JWT authentication with bcrypt password hashing
- Role-based access control
- Rate limiting
- Prompt injection mitigation
- Full AI reasoning logging in audit logs
- Secure environment variable management

## 🎯 Risk Engine

The risk engine uses a deterministic algorithm:

```
Risk Score = (0.2 × volatility) +
             (0.15 × beta) +
             (0.2 × leverage) +
             (0.15 × earnings_stability) +
             (0.1 × sector_risk) +
             (0.2 × valuation_risk)
```

**Risk Levels:**
- Conservative: 0-33
- Moderate: 34-66
- Aggressive: 67-100

## 🤖 LLM Orchestration

Uses LangGraph state machine with:
- Strict system prompts
- JSON-only output
- Schema validation with retry logic
- Timeout protection
- Comprehensive logging
- No hallucinated numeric data

## 📊 Recommendation Algorithm

```
Final Score = (0.4 × Research Score) +
              (0.3 × Signal Score) +
              (0.2 × Risk Alignment) +
              (0.1 × Macro Fit)
```

Filters stocks by user risk band and ranks top N.

## 🔄 Background Tasks

- Nightly risk recomputation
- Research refresh
- Signal ingestion
- Embedding updates

## 📝 Environment Variables

See `.env.example` for all required variables:

- `SECRET_KEY` - JWT secret (required)
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `OPENAI_API_KEY` - OpenAI API key (required)
- `CORS_ORIGINS` - Allowed CORS origins

## 🐳 Docker

The Docker setup includes:
- **PostgreSQL 15** - Main database
- **Redis 7** - Caching and Celery broker
- **Backend** - FastAPI application

All services include health checks and automatic restarts.

## 📈 Monitoring

- Structured JSON logging (production)
- Pretty console logging (development)
- Request/response logging
- AI reasoning audit trail

## 🤝 Contributing

1. Follow existing code structure
2. Write tests for new features
3. Run linting and formatting before committing
4. Update documentation as needed

## 📄 License

Proprietary - All rights reserved

## 🆘 Support

For issues or questions, please contact the development team.

---

**Built with ❤️ for intelligent investment research**
