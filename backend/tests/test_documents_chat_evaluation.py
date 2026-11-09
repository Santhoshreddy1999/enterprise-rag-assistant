from __future__ import annotations

from conftest import register
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _upload_text(
    client: TestClient,
    *,
    filename: str = "handbook.txt",
    text: str = (
        "Employees receive twenty five annual leave days each calendar year. "
        "Unused annual leave is subject to the carry-over policy. "
        "Health insurance enrollment begins on the first day of employment."
    ),
) -> dict[str, object]:
    response = client.post(
        "/api/v1/documents",
        files={"file": (filename, text.encode(), "text/plain")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_upload_chat_citations_history_and_evaluation(client: TestClient) -> None:
    register(client)
    document = _upload_text(client)
    assert document["status"] == "ready"
    assert document["chunk_count"] >= 1

    conversation_response = client.post(
        "/api/v1/conversations",
        json={"title": "Benefits handbook"},
    )
    assert conversation_response.status_code == 201
    conversation_id = conversation_response.json()["id"]

    answer = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "How many annual leave days are provided?", "top_k": 5},
    )
    assert answer.status_code == 201, answer.text
    payload = answer.json()
    assert payload["role"] == "assistant"
    assert "[1]" in payload["content"]
    assert payload["citations"][0]["document_id"] == document["id"]
    assert payload["citations"][0]["filename"] == "handbook.txt"
    assert "annual leave" in payload["citations"][0]["excerpt"].lower()

    history = client.get(f"/api/v1/conversations/{conversation_id}/messages")
    assert history.status_code == 200
    assert [message["role"] for message in history.json()] == ["user", "assistant"]
    assert history.json()[1]["citations"] == payload["citations"]

    evaluation = client.post(
        "/api/v1/evaluations/retrieval",
        json={
            "name": "benefits-smoke",
            "top_k": 5,
            "cases": [
                {
                    "query": "annual leave allowance",
                    "expected_document_ids": [document["id"]],
                }
            ],
        },
    )
    assert evaluation.status_code == 201, evaluation.text
    result = evaluation.json()
    assert result["hit_rate"] == 1.0
    assert result["mean_reciprocal_rank"] == 1.0
    assert result["cases"][0]["retrieved_document_ids"][0] == document["id"]


def test_owned_resources_are_not_visible_to_another_user(client: TestClient) -> None:
    register(client, email="owner@example.com")
    document = _upload_text(client)
    conversation = client.post(
        "/api/v1/conversations",
        json={"title": "Private"},
    ).json()
    client.post("/api/v1/auth/logout")

    register(client, email="other@example.com")
    assert client.get("/api/v1/documents").json() == []
    assert client.get("/api/v1/conversations").json() == []
    assert client.delete(f"/api/v1/documents/{document['id']}").status_code == 404
    assert client.get(f"/api/v1/conversations/{conversation['id']}/messages").status_code == 404
    evaluation = client.post(
        "/api/v1/evaluations/retrieval",
        json={
            "name": "ownership-check",
            "cases": [
                {
                    "query": "annual leave",
                    "expected_document_ids": [document["id"]],
                }
            ],
        },
    )
    assert evaluation.status_code == 404


def test_document_delete_and_no_context_answer(client: TestClient) -> None:
    register(client)
    document = _upload_text(client)
    response = client.delete(f"/api/v1/documents/{document['id']}")
    assert response.status_code == 204
    assert client.get("/api/v1/documents").json() == []

    conversation_id = client.post(
        "/api/v1/conversations",
        json={"title": "Empty workspace"},
    ).json()["id"]
    answer = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What is the leave allowance?"},
    )
    assert answer.status_code == 201
    assert answer.json()["citations"] == []
    assert "could not find" in answer.json()["content"].lower()


def test_upload_validation_and_size_limit(settings: Settings) -> None:
    settings.upload_max_bytes = 16
    with TestClient(create_app(settings)) as client:
        register(client)
        wrong_extension = client.post(
            "/api/v1/documents",
            files={"file": ("malware.exe", b"not executable", "text/plain")},
        )
        assert wrong_extension.status_code == 415

        wrong_media_type = client.post(
            "/api/v1/documents",
            files={"file": ("handbook.pdf", b"%PDF-invalid", "text/plain")},
        )
        assert wrong_media_type.status_code == 415

        empty = client.post(
            "/api/v1/documents",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert empty.status_code == 422

        oversized = client.post(
            "/api/v1/documents",
            files={"file": ("large.txt", b"x" * 17, "text/plain")},
        )
        assert oversized.status_code == 413
