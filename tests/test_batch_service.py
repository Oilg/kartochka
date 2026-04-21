from __future__ import annotations

import csv
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.models.catalog_batch import CatalogBatch
from kartochka.models.template import Template
from kartochka.models.user import User
from kartochka.services import batch_service
from kartochka.utils.helpers import generate_uid


class TestGetBatchProgress:
    async def test_progress_empty(self, test_db: AsyncSession) -> None:
        result = await batch_service.get_batch_progress("nonexistent-uid", test_db)
        assert result == {}

    async def test_progress_calculation(
        self, test_db: AsyncSession, test_user: User, sample_template: Template
    ) -> None:
        batch = CatalogBatch(
            uid=generate_uid(),
            user_id=test_user.id,
            template_id=sample_template.id,
            name="Progress Test",
            source="csv",
            marketplace="wildberries",
            total_items=10,
            processed_items=4,
            failed_items=1,
            status="processing",
        )
        test_db.add(batch)
        await test_db.commit()
        await test_db.refresh(batch)

        result = await batch_service.get_batch_progress(batch.uid, test_db)
        assert result["total"] == 10
        assert result["processed"] == 4
        assert result["percentage"] == 40
        assert result["status"] == "processing"

    async def test_progress_zero_total(
        self, test_db: AsyncSession, test_user: User, sample_template: Template
    ) -> None:
        batch = CatalogBatch(
            uid=generate_uid(),
            user_id=test_user.id,
            template_id=sample_template.id,
            name="Zero Test",
            source="csv",
            marketplace="wildberries",
            total_items=0,
            processed_items=0,
        )
        test_db.add(batch)
        await test_db.commit()
        await test_db.refresh(batch)

        result = await batch_service.get_batch_progress(batch.uid, test_db)
        assert result["percentage"] == 0


class TestCreateBatchFromCsv:
    async def test_create_batch_csv(
        self,
        test_db: AsyncSession,
        pro_user: User,
        pro_sample_template: Template,
    ) -> None:
        mock_task = MagicMock()
        mock_task.id = "test-task-id"

        with patch(
            "kartochka.workers.tasks.process_batch.delay",
            return_value=mock_task,
        ):
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False, encoding="utf-8"
            ) as f:
                writer = csv.writer(f)
                writer.writerow(["title", "price"])
                writer.writerow(["Product 1", "100"])
                writer.writerow(["Product 2", "200"])
                tmp_path = Path(f.name)

            try:
                batch = await batch_service.create_batch_from_csv(
                    file_path=tmp_path,
                    column_mapping={"title": "title", "price": "price"},
                    template_uid=pro_sample_template.uid,
                    marketplace="wildberries",
                    output_format="png",
                    batch_name="Test CSV Batch",
                    user=pro_user,
                    db=test_db,
                )
            finally:
                tmp_path.unlink(missing_ok=True)

        assert batch.total_items == 2
        assert batch.name == "Test CSV Batch"
        assert batch.celery_task_id == "test-task-id"

    async def test_create_batch_invalid_template(
        self, test_db: AsyncSession, pro_user: User
    ) -> None:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            tmp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Template not found"):
                await batch_service.create_batch_from_csv(
                    file_path=tmp_path,
                    column_mapping={},
                    template_uid="nonexistent-uid",
                    marketplace="wildberries",
                    output_format="png",
                    batch_name="Test",
                    user=pro_user,
                    db=test_db,
                )
        finally:
            tmp_path.unlink(missing_ok=True)


class TestCreateBatchZip:
    async def test_create_zip_empty(
        self, test_db: AsyncSession, test_user: User, sample_template: Template
    ) -> None:
        batch = CatalogBatch(
            uid=generate_uid(),
            user_id=test_user.id,
            template_id=sample_template.id,
            name="Zip Test",
            source="csv",
            marketplace="wildberries",
            output_format="png",
        )
        test_db.add(batch)
        await test_db.commit()
        await test_db.refresh(batch)

        zip_path = await batch_service.create_batch_zip(batch, test_db)
        assert zip_path.exists()
        zip_path.unlink(missing_ok=True)
        batch.zip_path = None
        await test_db.commit()
