from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.models.catalog_batch import CatalogBatch
from kartochka.models.template import Template
from kartochka.models.user import User
from kartochka.services.catalog_service import (
    detect_columns,
    guess_column_mapping,
    parse_csv,
)
from kartochka.utils.helpers import generate_uid


async def _create_batch(
    db: AsyncSession, user: User, template: Template
) -> CatalogBatch:
    batch = CatalogBatch(
        uid=generate_uid(),
        user_id=user.id,
        template_id=template.id,
        name="Test Batch",
        source="csv",
        marketplace="wildberries",
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return batch


class TestParseCsv:
    async def test_parse_basic_csv(
        self, test_db: AsyncSession, test_user: User, sample_template: Template
    ) -> None:
        batch = await _create_batch(test_db, test_user, sample_template)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["Название", "Цена", "Артикул"])
            writer.writerow(["Кроссовки Nike", "4990", "SKU001"])
            writer.writerow(["Толстовка Adidas", "2990", "SKU002"])
            tmp_path = Path(f.name)

        try:
            mapping = {"Название": "title", "Цена": "price", "Артикул": "external_id"}
            count = await parse_csv(tmp_path, mapping, test_user.id, batch.id, test_db)
            assert count == 2
        finally:
            tmp_path.unlink(missing_ok=True)

    async def test_parse_csv_skips_empty_rows(
        self, test_db: AsyncSession, test_user: User, sample_template: Template
    ) -> None:
        batch = await _create_batch(test_db, test_user, sample_template)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["title", "price"])
            writer.writerow(["Item 1", "100"])
            writer.writerow(["", ""])  # empty row
            writer.writerow(["Item 2", "200"])
            tmp_path = Path(f.name)

        try:
            mapping = {"title": "title", "price": "price"}
            count = await parse_csv(tmp_path, mapping, test_user.id, batch.id, test_db)
            assert count == 2
        finally:
            tmp_path.unlink(missing_ok=True)

    async def test_parse_csv_invalid_file(
        self, test_db: AsyncSession, test_user: User, sample_template: Template
    ) -> None:
        batch = await _create_batch(test_db, test_user, sample_template)
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"\xff\xfe invalid binary content \x00\x01")
            tmp_path = Path(f.name)
        try:
            with pytest.raises(ValueError, match="Failed to parse CSV"):
                await parse_csv(tmp_path, {}, test_user.id, batch.id, test_db)
        finally:
            tmp_path.unlink(missing_ok=True)


class TestDetectColumns:
    async def test_detect_csv_columns(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["Название", "Цена", "Артикул", "Бренд"])
            writer.writerow(["Item", "100", "SKU1", "Brand"])
            tmp_path = Path(f.name)

        try:
            cols = await detect_columns(tmp_path)
            assert "Название" in cols
            assert "Цена" in cols
        finally:
            tmp_path.unlink(missing_ok=True)

    async def test_detect_columns_nonexistent(self) -> None:
        cols = await detect_columns(Path("/nonexistent/file.csv"))
        assert cols == []


class TestGuessColumnMapping:
    def test_guess_basic_mapping(self) -> None:
        cols = ["Название", "Цена", "Артикул", "Бренд", "Фото", "Скидка"]
        mapping = guess_column_mapping(cols)
        assert mapping.get("Название") == "title"
        assert mapping.get("Цена") == "price"
        assert mapping.get("Артикул") == "external_id"
        assert mapping.get("Бренд") == "brand"

    def test_guess_english_columns(self) -> None:
        cols = ["name", "price", "sku", "brand", "image_url"]
        mapping = guess_column_mapping(cols)
        assert mapping.get("name") == "title"
        assert mapping.get("price") == "price"
        assert mapping.get("sku") == "external_id"
        assert mapping.get("brand") == "brand"

    def test_guess_no_duplicates(self) -> None:
        cols = ["title", "Title", "TITLE"]
        mapping = guess_column_mapping(cols)
        # Only one column should be mapped to 'title'
        mapped_to_title = [col for col, field in mapping.items() if field == "title"]
        assert len(mapped_to_title) == 1
