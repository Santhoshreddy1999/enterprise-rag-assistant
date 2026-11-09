from __future__ import annotations

from conftest import TEST_PASSWORD, register
from fastapi.testclient import TestClient


def test_register_sets_http_only_cookie_and_authenticates(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "Engineer@Example.com", "password": TEST_PASSWORD},
    )

    assert response.status_code == 201
    assert response.json()["email"] == "engineer@example.com"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/api/v1" in cookie

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json() == response.json()


def test_login_errors_are_generic_and_logout_clears_cookie(client: TestClient) -> None:
    register(client)
    duplicate = client.post(
        "/api/v1/auth/register",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    assert duplicate.status_code == 409

    client.post("/api/v1/auth/logout")
    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "wrong password value"},
    )
    missing_user = client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "wrong password value"},
    )
    assert wrong_password.status_code == 401
    assert missing_user.status_code == 401
    assert wrong_password.json() == missing_user.json()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_validation_response_does_not_echo_password(client: TestClient) -> None:
    secret = "too-short"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "engineer@example.com", "password": secret},
    )

    assert response.status_code == 422
    assert secret not in response.text


def test_authentication_is_required(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/documents").status_code == 401
    assert client.get("/api/v1/conversations").status_code == 401
