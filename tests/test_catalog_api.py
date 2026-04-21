from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.models.catalog_batch import CatalogBatch
from kartochka.models.template import Template
from kartochka.models.user import User
from kartochka.utils.helpers import generate_uid


async def _create_test_batch(
    db: AsyncSession, user: User, template: Template, name: str = "Test"
) -> CatalogBatch:
    batch = CatalogBatch(
        uid=generate_uid(),
        user_id=user.id,
        template_id=template.id,
        name=name,
        source="csv",
        marketplace="wildberries",
        status="completed",
        total_items=5,
        processed_items=5,
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return batch


class TestCatalogBatchesEndpoints:
    async def test_list_batches_empty(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await async_client.get("/api/catalog/batches/", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    async def test_get_batch_not_found(
        self, async_client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        r = await async_client.get(
            "/api/catalog/batches/nonexistent-uid", headers=auth_headers
        )
        assert r.status_code == 404

    async def test_get_batch(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession,
        test_user: User,
        sample_template: Template,
        auth_headers: dict[str, str],
    ) -> None:
        batch = await _create_test_batch(test_db, test_user, sample_template)
        r = await async_client.get(
            f"/api/catalog/batches/{batch.uid}", headers=auth_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["uid"] == batch.uid

    async def test_list_batch_items(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession,
        test_user: User,
        sample_template: Template,
        auth_headers: dict[str, str],
    ) -> None:
        batch = await _create_test_batch(test_db, test_user, sample_template)
        r = await async_client.get(
            f"/api/catalog/batches/{batch.uid}/items", headers=auth_headers
        )
        assert r.status_code == 200

    async def test_delete_batch(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession,
        test_user: User,
        sample_template: Template,
        auth_headers: dict[str, str],
    ) -> None:
        batch = await _create_test_batch(
            test_db, test_user, sample_template, "Delete Me"
        )
        r = await async_client.delete(
            f"/api/catalog/batches/{batch.uid}", headers=auth_headers
        )
        assert r.status_code == 204

    async def test_download_requires_pro(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession,
        test_user: User,
        sample_template: Template,
        auth_headers: dict[str, str],
    ) -> None:
        batch = await _create_test_batch(test_db, test_user, sample_template)
        r = await async_client.get(
            f"/api/catalog/batches/{batch.uid}/download", headers=auth_headers
        )
        assert r.status_code == 403
        assert r.json()["code"] == "PLAN_UPGRADE_REQUIRED"

    async def test_upload_requires_pro(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
        sample_template: Template,
    ) -> None:
        csv_content = "title,price\nItem1,100\n"
        r = await async_client.post(
            "/api/catalog/upload",
            headers=auth_headers,
            files={"file": ("test.csv", csv_content.encode(), "text/csv")},
            data={
                "template_uid": sample_template.uid,
                "marketplace": "wildberries",
                "output_format": "png",
                "batch_name": "Test",
                "column_mapping": json.dumps({"title": "title", "price": "price"}),
            },
        )
        assert r.status_code == 403

    async def test_upload_pro_user(
        self,
        async_client: AsyncClient,
        pro_auth_headers: dict[str, str],
        pro_sample_template: Template,
    ) -> None:
        mock_task = MagicMock()
        mock_task.id = "mock-task-id"

        with patch(
            "kartochka.workers.tasks.process_batch.delay",
            return_value=mock_task,
        ):
            csv_content = "title,price\nItem1,100\nItem2,200\n"
            r = await async_client.post(
                "/api/catalog/upload",
                headers=pro_auth_headers,
                files={"file": ("test.csv", csv_content.encode(), "text/csv")},
                data={
                    "template_uid": pro_sample_template.uid,
                    "marketplace": "wildberries",
                    "output_format": "png",
                    "batch_name": "Pro Upload Test",
                    "column_mapping": json.dumps({"title": "title", "price": "price"}),
                },
            )
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Pro Upload Test"
        assert data["total_items"] == 2


class TestDetectColumns:
    async def test_detect_columns(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        csv_content = "Название,Цена,Артикул\nItem,100,SKU1\n"
        r = await async_client.post(
            "/api/catalog/detect-columns",
            headers=auth_headers,
            files={"file": ("test.csv", csv_content.encode(), "text/csv")},
        )
        assert r.status_code == 200
        data = r.json()
        assert "columns" in data
        assert "suggested_mapping" in data
        assert "Название" in data["columns"]
