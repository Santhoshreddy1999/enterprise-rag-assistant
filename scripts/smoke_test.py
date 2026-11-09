"""Exercise the deployed MVP through its public HTTP contract."""

from __future__ import annotations

import json
import os
import uuid

import httpx

API_BASE = os.getenv("RAG_SMOKE_API_URL", "http://localhost:8000/api/v1").rstrip("/")
FRONTEND_URL = os.getenv("RAG_SMOKE_FRONTEND_URL", "http://localhost:3000").rstrip("/")
PASSWORD = "local smoke test passphrase"
TIMEOUT = 30.0


def require(response: httpx.Response, expected: int) -> dict[str, object]:
    if response.status_code != expected:
        raise AssertionError(
            f"{response.request.method} {response.request.url} returned "
            f"{response.status_code}, expected {expected}: {response.text[:500]}"
        )
    if response.status_code == 204:
        return {}
    payload = response.json()
    if not isinstance(payload, dict):
        raise AssertionError(f"Expected an object response from {response.request.url}")
    return payload


def main() -> None:
    run_id = uuid.uuid4().hex[:12]
    owner_email = f"smoke-owner-{run_id}@example.com"
    other_email = f"smoke-other-{run_id}@example.com"
    document_text = (
        "The Northstar employee handbook provides twenty-five annual leave days "
        "per calendar year. Employees may carry over five unused days."
    )

    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as browser:
        frontend = browser.get(FRONTEND_URL)
        frontend.raise_for_status()
        if "Northstar" not in frontend.text:
            raise AssertionError("Frontend response did not contain the application title")

    with httpx.Client(timeout=TIMEOUT) as owner:
        user = require(
            owner.post(
                f"{API_BASE}/auth/register",
                json={"email": owner_email, "password": PASSWORD},
            ),
            201,
        )
        if "rag_access" not in owner.cookies:
            raise AssertionError("Registration did not set the authentication cookie")

        document = require(
            owner.post(
                f"{API_BASE}/documents",
                files={
                    "file": (
                        "employee-handbook.txt",
                        document_text.encode("utf-8"),
                        "text/plain",
                    )
                },
            ),
            201,
        )
        if document.get("status") != "ready" or int(document.get("chunk_count", 0)) < 1:
            raise AssertionError("Document did not reach ready state with stored chunks")

        conversation = require(
            owner.post(
                f"{API_BASE}/conversations",
                json={"title": "Leave policy"},
            ),
            201,
        )
        answer = require(
            owner.post(
                f"{API_BASE}/conversations/{conversation['id']}/messages",
                json={
                    "content": "How many annual leave days are provided?",
                    "top_k": 5,
                },
            ),
            201,
        )
        citations = answer.get("citations")
        if not isinstance(citations, list) or not citations:
            raise AssertionError("Grounded answer did not include a citation")
        first_citation = citations[0]
        if not isinstance(first_citation, dict):
            raise AssertionError("Citation response has an invalid shape")
        if first_citation.get("document_id") != document.get("id"):
            raise AssertionError("Citation did not reference the uploaded document")
        if "[1]" not in str(answer.get("content", "")):
            raise AssertionError("Answer did not include the expected citation marker")

        history = owner.get(f"{API_BASE}/conversations/{conversation['id']}/messages")
        history.raise_for_status()
        history_payload = history.json()
        if [message["role"] for message in history_payload] != ["user", "assistant"]:
            raise AssertionError("Conversation history did not persist both messages")

        evaluation = require(
            owner.post(
                f"{API_BASE}/evaluations/retrieval",
                json={
                    "name": f"smoke-{run_id}",
                    "top_k": 5,
                    "cases": [
                        {
                            "query": "annual leave allowance",
                            "expected_document_ids": [document["id"]],
                        }
                    ],
                },
            ),
            201,
        )
        if evaluation.get("hit_rate") != 1.0:
            raise AssertionError("Retrieval evaluation did not find the expected document")

    with httpx.Client(timeout=TIMEOUT) as other:
        require(
            other.post(
                f"{API_BASE}/auth/register",
                json={"email": other_email, "password": PASSWORD},
            ),
            201,
        )
        documents = other.get(f"{API_BASE}/documents")
        documents.raise_for_status()
        if documents.json() != []:
            raise AssertionError("A second user could see another user's documents")
        inaccessible = other.delete(f"{API_BASE}/documents/{document['id']}")
        if inaccessible.status_code != 404:
            raise AssertionError("A second user could address another user's document")

    print(
        json.dumps(
            {
                "status": "passed",
                "frontend": FRONTEND_URL,
                "api": API_BASE,
                "owner_id": user["id"],
                "document_id": document["id"],
                "citation_count": len(citations),
                "retrieval_hit_rate": evaluation["hit_rate"],
                "ownership_isolation": "passed",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
