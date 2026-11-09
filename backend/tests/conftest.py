from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

TEST_PASSWORD = "correct horse battery staple"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
        auto_create_schema=True,
        jwt_secret="test-secret-with-at-least-thirty-two-characters",
        cors_origins=["http://frontend.test"],
        chunk_size_chars=240,
        chunk_overlap_chars=30,
        log_level="ERROR",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def register(
    client: TestClient,
    *,
    email: str = "engineer@example.com",
    password: str = TEST_PASSWORD,
) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()
