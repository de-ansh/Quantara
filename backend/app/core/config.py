"""Core configuration using Pydantic Settings."""


from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Quantara"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Security
    secret_key: str = Field(..., min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    # Fernet key for stored user credentials. Unset: derived from secret_key (rotating
    # secret_key would then make stored credentials unreadable, so set this in production).
    credential_encryption_key: str | None = None

    # Database
    database_url: str = Field(..., description="PostgreSQL connection string")
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis
    redis_url: str = Field(..., description="Redis connection string")

    # OpenAI
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = "gpt-4o"
    openai_max_tokens: int = 4096
    openai_temperature: float = 0.1

    # SEC EDGAR
    sec_user_agent: str = Field(
        "Quantara admin@example.com", description="SEC EDGAR User-Agent string"
    )

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Rate Limiting
    login_rate_limit_per_minute: int = 10
    research_generation_limit_per_hour: int = 20

    # Research reports older than this are regenerated on next request
    research_cache_max_age_hours: int = 24

    # Background Tasks
    enable_background_tasks: bool = True

    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, v: str) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in v.split(",")]

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"


# Global settings instance
settings = Settings()
