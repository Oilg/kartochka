from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.models.catalog_item import CatalogItem
from kartochka.utils.helpers import generate_uid
from kartochka.utils.logging import logger


async def parse_csv(
    file_path: Path,
    column_mapping: dict[str, str],
    user_id: int,
    batch_id: int,
    db: AsyncSession,
) -> int:
    import pandas as pd

    try:
        raw = file_path.read_bytes()
        # Reject files with null bytes — binary content, not CSV
        if b"\x00" in raw:
            raise ValueError("Failed to parse CSV: file contains binary content")
        try:
            df = pd.read_csv(file_path, encoding="utf-8", sep=None, engine="python")
        except UnicodeDecodeError:
            df = pd.read_csv(
                file_path, encoding="windows-1251", sep=None, engine="python"
            )
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Failed to parse CSV: {exc}") from exc
    return await _create_items_from_df(df, column_mapping, user_id, batch_id, db)


async def parse_xlsx(
    file_path: Path,
    column_mapping: dict[str, str],
    user_id: int,
    batch_id: int,
    db: AsyncSession,
) -> int:
    import pandas as pd

    try:
        df = pd.read_excel(file_path, engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Failed to parse XLSX: {exc}") from exc
    return await _create_items_from_df(df, column_mapping, user_id, batch_id, db)


async def _create_items_from_df(
    df: Any,
    column_mapping: dict[str, str],
    user_id: int,
    batch_id: int,
    db: AsyncSession,
) -> int:
    # column_mapping: {csv_column_name: kartochka_field_name}
    reverse: dict[str, str] = {
        v: k for k, v in column_mapping.items()
    }  # field -> csv_col

    def get_field(row: Any, field: str) -> str | None:
        col = reverse.get(field)
        if col is None:
            return None
        import pandas as pd

        val = getattr(row, col, None)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        s = str(val).strip()
        return s if s and s.lower() != "nan" else None

    count = 0

    for _, row in df.iterrows():
        # Skip fully empty rows
        non_empty = [
            str(v).strip()
            for v in row.values
            if str(v).strip() and str(v).strip().lower() != "nan"
        ]
        if not non_empty:
            continue

        title = get_field(row, "title") or ""
        item = CatalogItem(
            uid=generate_uid(),
            user_id=user_id,
            catalog_batch_id=batch_id,
            title=title,
            external_id=get_field(row, "external_id"),
            price=get_field(row, "price"),
            old_price=get_field(row, "old_price"),
            discount=get_field(row, "discount"),
            brand=get_field(row, "brand"),
            image_url=get_field(row, "image_url"),
        )
        db.add(item)
        count += 1

    if count:
        await db.commit()
    return count


async def detect_columns(file_path: Path) -> list[str]:
    import pandas as pd

    try:
        if file_path.suffix.lower() == ".xlsx":
            df = pd.read_excel(file_path, engine="openpyxl", nrows=0)
        else:
            try:
                df = pd.read_csv(
                    file_path, encoding="utf-8", sep=None, engine="python", nrows=0
                )
            except UnicodeDecodeError:
                df = pd.read_csv(
                    file_path,
                    encoding="windows-1251",
                    sep=None,
                    engine="python",
                    nrows=0,
                )
        return [str(c) for c in df.columns.tolist()]
    except Exception as exc:
        logger.warning("detect_columns_failed: %s", exc)
        return []


def guess_column_mapping(columns: list[str]) -> dict[str, str]:
    """Auto-map CSV column names to kartochka field names."""
    mapping: dict[str, str] = {}
    field_keywords: dict[str, list[str]] = {
        "title": [
            "название",
            "наименование",
            "товар",
            "продукт",
            "name",
            "title",
            "product",
        ],
        "price": ["цена", "стоимость", "price", "цена руб"],
        "old_price": ["старая цена", "цена до", "old_price", "прежняя цена"],
        "discount": ["скидка", "discount", "акция"],
        "brand": ["бренд", "brand", "марка", "производитель"],
        "image_url": ["фото", "photo", "image", "img", "url", "ссылка", "картинка"],
        "external_id": ["артикул", "sku", "id", "external_id", "код товара", "арт"],
    }
    used_fields: set[str] = set()
    for col in columns:
        col_lower = col.lower()
        for field, keywords in field_keywords.items():
            if field not in used_fields and any(kw in col_lower for kw in keywords):
                mapping[col] = field
                used_fields.add(field)
                break
    return mapping
