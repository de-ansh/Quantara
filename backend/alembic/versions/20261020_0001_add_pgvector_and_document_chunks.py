"""baseline schema: pgvector extension and all model tables

Revision ID: 20261020_0001
Revises:
Create Date: 2026-10-20 12:45:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261020_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Explicit snapshot of the schema at this revision. Never derive it from Base.metadata:
# later model changes must arrive through their own migrations.
def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.create_table('stocks',
    sa.Column('ticker', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('sector', sa.String(length=100), nullable=True),
    sa.Column('risk_score', sa.Float(), nullable=True, comment='Risk score 0-100'),
    sa.Column('research_score', sa.Float(), nullable=True, comment='Research quality score 0-100'),
    sa.Column('pe_ratio', sa.Float(), nullable=True, comment='Price-to-earnings ratio'),
    sa.Column('beta', sa.Float(), nullable=True, comment='Beta vs market'),
    sa.Column('market_cap', sa.String(length=50), nullable=True, comment='Market cap formatted'),
    sa.Column('price', sa.String(length=50), nullable=True, comment='Current price formatted'),
    sa.Column('alpha_projection', sa.String(length=50), nullable=True, comment='Alpha projection percentage formatted'),
    sa.Column('status', sa.String(length=20), nullable=True, comment='Signal trend status (up/down/neutral)'),
    sa.Column('last_updated', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('ticker')
    )
    op.create_index('idx_research_score', 'stocks', ['research_score'], unique=False)
    op.create_index('idx_sector_risk', 'stocks', ['sector', 'risk_score'], unique=False)
    op.create_index(op.f('ix_stocks_sector'), 'stocks', ['sector'], unique=False)
    op.create_index(op.f('ix_stocks_ticker'), 'stocks', ['ticker'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('risk_level', sa.String(length=50), nullable=True, comment='Conservative, Moderate, Aggressive'),
    sa.Column('volatility_tolerance', sa.Float(), nullable=True, comment='0-100 scale'),
    sa.Column('investment_horizon', sa.Integer(), nullable=True, comment='Investment horizon in months'),
    sa.Column('sector_preferences', sa.JSON(), nullable=True, comment='Preferred sectors and weights'),
    sa.Column('openai_api_key', sa.String(length=512), nullable=True, comment='Encrypted external OpenAI API key'),
    sa.Column('sec_user_agent', sa.String(length=255), nullable=True, comment='Custom SEC User-Agent header'),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_table('audit_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=100), nullable=False, comment='Action type: login, update_profile, generate_recommendation, etc.'),
    sa.Column('entity', sa.String(length=50), nullable=True, comment='Entity type affected'),
    sa.Column('entity_id', sa.String(length=255), nullable=True, comment='ID of affected entity'),
    sa.Column('reasoning_snapshot', sa.JSON(), nullable=True, comment='AI reasoning, prompts, and outputs'),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('user_agent', sa.Text(), nullable=True),
    sa.Column('data', sa.JSON(), nullable=True, comment='Additional context and data'),
    sa.Column('status', sa.String(length=20), nullable=False, comment='success, failure, error'),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_entity', 'audit_logs', ['entity', 'entity_id'], unique=False)
    op.create_index('idx_status_time', 'audit_logs', ['status', 'timestamp'], unique=False)
    op.create_index('idx_user_action_time', 'audit_logs', ['user_id', 'action', 'timestamp'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    op.create_table('document_chunks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ticker', sa.String(length=20), nullable=False),
    sa.Column('document_type', sa.String(length=50), nullable=False, comment='earnings_call, sec_10k, sec_10q, sec_8k, news'),
    sa.Column('period', sa.String(length=20), nullable=True, comment='e.g. Q4 2023, FY 2023'),
    sa.Column('chunk_index', sa.Integer(), nullable=False, comment='Sequential chunk index'),
    sa.Column('chunk_text', sa.Text(), nullable=False, comment='Raw text content of the chunk'),
    sa.Column('embedding', Vector(1536), nullable=False, comment='1536-dimensional OpenAI vector embedding'),
    sa.Column('token_count', sa.Integer(), nullable=True, comment='Estimated token count in chunk'),
    sa.Column('data', sa.JSON(), nullable=True, comment='Additional chunk-specific metadata'),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_doc_chunk_embedding', 'document_chunks', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index('idx_doc_chunk_ticker_doc_type', 'document_chunks', ['ticker', 'document_type'], unique=False)
    op.create_index('idx_doc_chunk_ticker_period', 'document_chunks', ['ticker', 'period'], unique=False)
    op.create_index(op.f('ix_document_chunks_created_at'), 'document_chunks', ['created_at'], unique=False)
    op.create_index(op.f('ix_document_chunks_document_type'), 'document_chunks', ['document_type'], unique=False)
    op.create_index(op.f('ix_document_chunks_id'), 'document_chunks', ['id'], unique=False)
    op.create_index(op.f('ix_document_chunks_ticker'), 'document_chunks', ['ticker'], unique=False)
    op.create_table('portfolios',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('initial_investment', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_portfolios_id'), 'portfolios', ['id'], unique=False)
    op.create_index(op.f('ix_portfolios_user_id'), 'portfolios', ['user_id'], unique=False)
    op.create_table('recommendations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('ticker', sa.String(length=10), nullable=False),
    sa.Column('final_score', sa.Float(), nullable=False, comment='Final recommendation score 0-100'),
    sa.Column('research_score', sa.Float(), nullable=False, comment='Research component score'),
    sa.Column('signal_score', sa.Float(), nullable=False, comment='Signal component score'),
    sa.Column('risk_alignment_score', sa.Float(), nullable=False, comment='Risk alignment with user profile'),
    sa.Column('macro_fit_score', sa.Float(), nullable=False, comment='Macro environment fit score'),
    sa.Column('explanation_text', sa.Text(), nullable=False, comment='Human-readable explanation'),
    sa.Column('reasoning_metadata', sa.JSON(), nullable=False, comment='Detailed reasoning breakdown and factors'),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=True, comment='When this recommendation expires'),
    sa.Column('is_active', sa.Boolean(), nullable=False, comment='Whether recommendation is still valid'),
    sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ticker_score', 'recommendations', ['ticker', 'final_score'], unique=False)
    op.create_index('idx_user_active_score', 'recommendations', ['user_id', 'is_active', 'final_score'], unique=False)
    op.create_index(op.f('ix_recommendations_created_at'), 'recommendations', ['created_at'], unique=False)
    op.create_index(op.f('ix_recommendations_id'), 'recommendations', ['id'], unique=False)
    op.create_index(op.f('ix_recommendations_ticker'), 'recommendations', ['ticker'], unique=False)
    op.create_index(op.f('ix_recommendations_user_id'), 'recommendations', ['user_id'], unique=False)
    op.create_table('research_reports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ticker', sa.String(length=20), nullable=False),
    sa.Column('structured_json', sa.JSON(), nullable=False, comment='Structured research data validated by schema'),
    sa.Column('vector_embedding_id', sa.String(length=255), nullable=True, comment='Reference to vector DB embedding'),
    sa.Column('confidence_score', sa.Float(), nullable=False, comment='Confidence in analysis 0-100'),
    sa.Column('summary', sa.Text(), nullable=True, comment='Human-readable summary'),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False, comment='Report version number'),
    sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_reports_created_at'), 'research_reports', ['created_at'], unique=False)
    op.create_index(op.f('ix_research_reports_id'), 'research_reports', ['id'], unique=False)
    op.create_index(op.f('ix_research_reports_ticker'), 'research_reports', ['ticker'], unique=False)
    op.create_table('signals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ticker', sa.String(length=20), nullable=False),
    sa.Column('signal_type', sa.String(length=50), nullable=False, comment='earnings_surprise, institutional_buying, insider_buying, sentiment_spike'),
    sa.Column('strength', sa.Float(), nullable=False, comment='Signal strength 0-100'),
    sa.Column('confidence', sa.Float(), nullable=False, comment='Confidence score 0-100'),
    sa.Column('data', sa.JSON(), nullable=True, comment='Additional signal-specific data'),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_strength', 'signals', ['strength'], unique=False)
    op.create_index('idx_ticker_type_time', 'signals', ['ticker', 'signal_type', 'timestamp'], unique=False)
    op.create_index(op.f('ix_signals_id'), 'signals', ['id'], unique=False)
    op.create_index(op.f('ix_signals_signal_type'), 'signals', ['signal_type'], unique=False)
    op.create_index(op.f('ix_signals_ticker'), 'signals', ['ticker'], unique=False)
    op.create_index(op.f('ix_signals_timestamp'), 'signals', ['timestamp'], unique=False)
    op.create_table('portfolio_positions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('portfolio_id', sa.Integer(), nullable=False),
    sa.Column('ticker', sa.String(length=20), nullable=False),
    sa.Column('shares', sa.Float(), nullable=False),
    sa.Column('cost_basis', sa.Float(), nullable=False),
    sa.Column('weight', sa.Float(), nullable=False, comment='Target portfolio weight (0.0 - 1.0)'),
    sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ),
    sa.ForeignKeyConstraint(['ticker'], ['stocks.ticker'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_portfolio_positions_id'), 'portfolio_positions', ['id'], unique=False)
    op.create_index(op.f('ix_portfolio_positions_portfolio_id'), 'portfolio_positions', ['portfolio_id'], unique=False)
    op.create_index(op.f('ix_portfolio_positions_ticker'), 'portfolio_positions', ['ticker'], unique=False)


def downgrade() -> None:
    op.drop_table("portfolio_positions")
    op.drop_table("signals")
    op.drop_table("research_reports")
    op.drop_table("recommendations")
    op.drop_table("portfolios")
    op.drop_table("document_chunks")
    op.drop_table("audit_logs")
    op.drop_table("users")
    op.drop_table("stocks")
    op.execute("DROP EXTENSION IF EXISTS vector CASCADE;")
