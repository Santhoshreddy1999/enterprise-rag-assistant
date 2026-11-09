from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEVELOPMENT_SECRET = "development-only-secret-change-me-000000000000"


class Settings(BaseSettings):
    """Validated process configuration loaded exclusively from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="RAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Enterprise RAG Assistant"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite+pysqlite:///./rag.db"
    auto_create_schema: bool = True

    jwt_secret: SecretStr = SecretStr(_DEVELOPMENT_SECRET)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_issuer: str = "enterprise-rag-assistant"
    jwt_audience: str = "enterprise-rag-assistant-api"
    jwt_ttl_minutes: int = Field(default=30, ge=5, le=1440)
    auth_cookie_name: str = "rag_access"
    cookie_secure: bool = False

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    upload_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=50 * 1024 * 1024)
    parsed_content_max_chars: int = Field(default=2_000_000, ge=1_000, le=10_000_000)
    chunk_size_chars: int = Field(default=900, ge=200, le=4_000)
    chunk_overlap_chars: int = Field(default=120, ge=0, le=1_000)
    embedding_dimension: int = Field(default=384, ge=64, le=2_048)
    retrieval_candidate_limit: int = Field(default=50, ge=10, le=500)
    rrf_constant: int = Field(default=60, ge=1, le=1_000)

    answer_provider: Literal["local", "openai", "anthropic"] = "local"
    provider_timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-3-5-haiku-latest"
    anthropic_base_url: str = "https://api.anthropic.com/v1"

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        normalized: list[str] = []
        for origin in origins:
            clean = origin.strip().rstrip("/")
            if clean == "*" or not clean.startswith(("http://", "https://")):
                raise ValueError("CORS origins must be explicit HTTP(S) origins")
            normalized.append(clean)
        if not normalized:
            raise ValueError("at least one CORS origin is required")
        return list(dict.fromkeys(normalized))

    @field_validator("openai_base_url", "anthropic_base_url")
    @classmethod
    def validate_provider_url(cls, value: str) -> str:
        clean = value.strip().rstrip("/")
        if not clean.startswith("https://"):
            raise ValueError("provider base URLs must use HTTPS")
        return clean

    @model_validator(mode="after")
    def validate_deployment(self) -> Settings:
        secret = self.jwt_secret.get_secret_value()
        if len(secret) < 32:
            raise ValueError("RAG_JWT_SECRET must contain at least 32 characters")
        if self.chunk_overlap_chars >= self.chunk_size_chars:
            raise ValueError("chunk overlap must be smaller than chunk size")
        if self.embedding_dimension != 384:
            raise ValueError("embedding dimension must remain 384 for the current schema")

        if self.answer_provider == "openai" and self.openai_api_key is None:
            raise ValueError("RAG_OPENAI_API_KEY is required for the OpenAI provider")
        if self.answer_provider == "anthropic" and self.anthropic_api_key is None:
            raise ValueError("RAG_ANTHROPIC_API_KEY is required for the Anthropic provider")

        if self.environment == "production":
            if secret == _DEVELOPMENT_SECRET:
                raise ValueError("production requires a unique RAG_JWT_SECRET")
            if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                raise ValueError("production requires PostgreSQL")
            if not self.cookie_secure:
                raise ValueError("production requires secure authentication cookies")
            if self.auto_create_schema:
                raise ValueError("production schema changes must be applied with Alembic")
        return self
