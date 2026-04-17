from datetime import UTC

import pytest
from httpx import AsyncClient

from kartochka.models.user import User


@pytest.mark.asyncio
async def test_register_success(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "password123",
            "full_name": "New User",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "api_key" in data
    assert data["email"] == "newuser@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(
    async_client: AsyncClient, test_user: User
) -> None:
    resp = await async_client.post(
        "/api/auth/register", json={"email": test_user.email, "password": "password123"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_invalid_email(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/auth/register", json={"email": "not-an-email", "password": "password123"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/auth/register", json={"email": "valid@example.com", "password": "short"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, test_user: User) -> None:
    resp = await async_client.post(
        "/api/auth/login",
        json={"email": test_user.email, "password": "testpassword123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient, test_user: User) -> None:
    resp = await async_client.post(
        "/api/auth/login", json={"email": test_user.email, "password": "wrongpassword"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email(async_client: AsyncClient) -> None:
    resp = await async_client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "password123"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_token(
    async_client: AsyncClient, auth_headers: dict[str, str], test_user: User
) -> None:
    resp = await async_client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == test_user.email


@pytest.mark.asyncio
async def test_me_without_token(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_expired_token(async_client: AsyncClient) -> None:
    from datetime import datetime

    from jose import jwt

    from kartochka.config import settings

    expired_token = jwt.encode(
        {"sub": "999", "exp": datetime(2020, 1, 1, tzinfo=UTC)},
        settings.secret_key,
        algorithm="HS256",
    )
    resp = await async_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_regenerate_api_key(
    async_client: AsyncClient, auth_headers: dict[str, str], test_user: User
) -> None:
    old_key = test_user.api_key
    resp = await async_client.post("/api/auth/regenerate-api-key", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "api_key" in data
    assert data["api_key"] != old_key
