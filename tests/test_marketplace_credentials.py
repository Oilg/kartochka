from __future__ import annotations

from httpx import AsyncClient

from kartochka.services.encryption_service import EncryptionService


class TestEncryptionService:
    def test_encrypt_decrypt_no_key(self) -> None:
        svc = EncryptionService.__new__(EncryptionService)
        svc._fernet = None
        plain = "my-api-key"
        assert svc.encrypt(plain) == plain
        assert svc.decrypt(plain) == plain

    def test_encrypt_decrypt_with_key(self) -> None:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        svc = EncryptionService.__new__(EncryptionService)
        svc._fernet = Fernet(key.encode())
        plain = "secret-api-key-123"
        encrypted = svc.encrypt(plain)
        assert encrypted != plain
        assert svc.decrypt(encrypted) == plain


class TestMarketplaceCredentialsAPI:
    async def test_list_credentials_empty(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await async_client.get(
            "/api/marketplace-credentials/", headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json() == []

    async def test_create_credential_wb(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        mocker: object,
    ) -> None:
        mocker.patch(  # type: ignore[attr-defined]
            "kartochka.services.wildberries_service.WildberriesService.verify_credentials",
            return_value=True,
        )
        r = await async_client.post(
            "/api/marketplace-credentials/",
            json={
                "marketplace": "wildberries",
                "api_key": "test-key-123",
                "publish_mode": "manual",
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["marketplace"] == "wildberries"
        assert data["is_valid"] is True
        assert data["publish_mode"] == "manual"

    async def test_create_credential_ozon(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        mocker: object,
    ) -> None:
        mocker.patch(  # type: ignore[attr-defined]
            "kartochka.services.ozon_service.OzonService.verify_credentials",
            return_value=False,
        )
        r = await async_client.post(
            "/api/marketplace-credentials/",
            json={
                "marketplace": "ozon",
                "api_key": "ozon-key",
                "client_id": "12345",
                "publish_mode": "auto",
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["marketplace"] == "ozon"
        assert data["is_valid"] is False

    async def test_delete_credential(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        mocker: object,
    ) -> None:
        mocker.patch(  # type: ignore[attr-defined]
            "kartochka.services.wildberries_service.WildberriesService.verify_credentials",
            return_value=True,
        )
        await async_client.post(
            "/api/marketplace-credentials/",
            json={"marketplace": "wildberries", "api_key": "del-key"},
            headers=auth_headers,
        )
        r = await async_client.delete(
            "/api/marketplace-credentials/wildberries", headers=auth_headers
        )
        assert r.status_code == 204

    async def test_delete_nonexistent(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await async_client.delete(
            "/api/marketplace-credentials/nonexistent", headers=auth_headers
        )
        assert r.status_code == 404

    async def test_verify_endpoint(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        mocker: object,
    ) -> None:
        mocker.patch(  # type: ignore[attr-defined]
            "kartochka.services.wildberries_service.WildberriesService.verify_credentials",
            return_value=True,
        )
        # Create first
        await async_client.post(
            "/api/marketplace-credentials/",
            json={"marketplace": "wildberries", "api_key": "verify-key"},
            headers=auth_headers,
        )
        r = await async_client.post(
            "/api/marketplace-credentials/wildberries/verify", headers=auth_headers
        )
        assert r.status_code == 200
        assert r.json()["is_valid"] is True
