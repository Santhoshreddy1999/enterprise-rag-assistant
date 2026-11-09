from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config
from app.core.config import Settings
from app.main import create_app


def test_configuration_rejects_unsafe_production_and_missing_provider_key() -> None:
    with pytest.raises(ValidationError, match="production requires"):
        Settings(_env_file=None, environment="production")

    with pytest.raises(ValidationError, match="RAG_OPENAI_API_KEY"):
        Settings(_env_file=None, answer_provider="openai")


def test_health_metrics_and_cors(client: TestClient) -> None:
    assert client.get("/api/v1/health/live").json() == {"status": "ok"}
    assert client.get("/api/v1/health/ready").json() == {"status": "ok"}

    metrics = client.get("/api/v1/metrics")
    assert metrics.status_code == 200
    assert "rag_http_requests_total" in metrics.text

    preflight = client.options(
        "/api/v1/documents",
        headers={
            "Origin": "http://frontend.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://frontend.test"
    assert preflight.headers["access-control-allow-credentials"] == "true"


def test_readiness_fails_before_schema_is_created(settings: Settings) -> None:
    settings.auto_create_schema = False
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready"}


def test_alembic_migration_upgrades_sqlite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setenv("RAG_DATABASE_URL", database_url)
    monkeypatch.setenv("RAG_ENVIRONMENT", "test")

    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert {
        "alembic_version",
        "users",
        "documents",
        "chunks",
        "conversations",
        "messages",
        "message_citations",
        "evaluation_runs",
    }.issubset(tables)
    engine.dispose()
