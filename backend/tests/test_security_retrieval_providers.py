from __future__ import annotations

import math
import uuid

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.security import (
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.domain.retrieval import SearchHit, reciprocal_rank_fusion
from app.infrastructure.embeddings import DeterministicEmbedding, cosine_similarity
from app.infrastructure.providers import LocalExtractiveProvider, OpenAIProvider


def _hit(chunk_id: int, score: float, text: str = "source sentence") -> SearchHit:
    return SearchHit(
        chunk_id=uuid.UUID(int=chunk_id),
        document_id=uuid.UUID(int=100 + chunk_id),
        filename=f"source-{chunk_id}.txt",
        page=None,
        text=text,
        score=score,
    )


def test_password_hashing_and_signed_access_tokens(settings: Settings) -> None:
    encoded = hash_password("correct horse battery staple")
    assert encoded.startswith("$argon2")
    assert verify_password("correct horse battery staple", encoded)[0] is True
    assert verify_password("incorrect password", encoded)[0] is False

    user_id = uuid.uuid4()
    token = create_access_token(user_id, settings)
    assert decode_access_token(token, settings) == user_id
    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(token + "tampered", settings)


def test_deterministic_embedding_is_normalized() -> None:
    provider = DeterministicEmbedding(64)
    first = provider.embed("Annual LEAVE leave")
    second = provider.embed("annual leave leave")
    assert first == second
    assert math.isclose(math.sqrt(sum(value * value for value in first)), 1.0)
    assert cosine_similarity(first, second) == pytest.approx(1.0)
    assert provider.embed("") == [0.0] * 64


def test_reciprocal_rank_fusion_rewards_cross_ranking_hits() -> None:
    first = [_hit(1, 0.9), _hit(2, 0.8)]
    second = [_hit(2, 10.0), _hit(3, 9.0)]
    fused = reciprocal_rank_fusion([first, second], limit=3, constant=60)

    assert [hit.chunk_id for hit in fused][0] == uuid.UUID(int=2)
    assert len(fused) == 3


def test_local_provider_is_extractive_and_cited() -> None:
    context = _hit(
        1,
        1.0,
        "The office is closed on Fridays. Employees receive 25 annual leave days.",
    )
    answer = LocalExtractiveProvider().answer(
        "How many annual leave days are provided?",
        [context],
    )
    assert answer.content == "Employees receive 25 annual leave days. [1]"
    assert answer.citation_indices == [1]


def test_openai_adapter_uses_http_api_and_repairs_missing_marker(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.openai_api_key = SecretStr("test-provider-key")
    settings.answer_provider = "openai"
    original_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-provider-key"
        assert request.url.path == "/v1/chat/completions"
        assert b"UNTRUSTED_SOURCES" in request.content
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Employees receive 25 leave days."}}]},
        )

    transport = httpx.MockTransport(handler)

    def client_factory(*, timeout: float) -> httpx.Client:
        return original_client(timeout=timeout, transport=transport)

    monkeypatch.setattr(httpx, "Client", client_factory)
    result = OpenAIProvider(settings).answer("How much leave?", [_hit(1, 1.0)])
    assert result.content.endswith("[1]")
    assert result.citation_indices == [1]
