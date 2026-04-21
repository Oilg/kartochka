from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.config import settings
from kartochka.models.catalog_batch import CatalogBatch
from kartochka.models.catalog_item import CatalogItem
from kartochka.models.template import Template
from kartochka.utils.helpers import generate_uid
from kartochka.utils.logging import logger

if TYPE_CHECKING:
    from kartochka.models.user import User


async def create_batch_from_csv(
    file_path: Path,
    column_mapping: dict[str, str],
    template_uid: str,
    marketplace: str,
    output_format: str,
    batch_name: str,
    user: User,
    db: AsyncSession,
) -> CatalogBatch:
    template = (
        await db.execute(
            select(Template).where(
                Template.uid == template_uid, Template.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if template is None:
        raise ValueError("Template not found")

    batch = CatalogBatch(
        uid=generate_uid(),
        user_id=user.id,
        template_id=template.id,
        name=batch_name,
        source="xlsx" if file_path.suffix.lower() == ".xlsx" else "csv",
        marketplace=marketplace,
        output_format=output_format,
        column_mapping=json.dumps(column_mapping),
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    from kartochka.services import catalog_service

    if file_path.suffix.lower() == ".xlsx":
        count = await catalog_service.parse_xlsx(
            file_path, column_mapping, user.id, batch.id, db
        )
    else:
        count = await catalog_service.parse_csv(
            file_path, column_mapping, user.id, batch.id, db
        )

    batch.total_items = count
    await db.commit()

    # Launch Celery task
    from kartochka.workers.tasks import process_batch

    task = process_batch.delay(batch.uid)
    batch.celery_task_id = task.id
    await db.commit()
    return batch


async def create_batch_from_marketplace(
    marketplace: str,
    template_uid: str,
    output_format: str,
    batch_name: str,
    user: User,
    db: AsyncSession,
) -> CatalogBatch:
    from kartochka.models.marketplace_credential import MarketplaceCredential
    from kartochka.services.encryption_service import encryption_service

    cred = (
        await db.execute(
            select(MarketplaceCredential).where(
                MarketplaceCredential.user_id == user.id,
                MarketplaceCredential.marketplace == marketplace,
            )
        )
    ).scalar_one_or_none()
    if cred is None:
        raise ValueError(f"No credentials for {marketplace}")

    template = (
        await db.execute(
            select(Template).where(
                Template.uid == template_uid, Template.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if template is None:
        raise ValueError("Template not found")

    api_key = encryption_service.decrypt(cred.encrypted_api_key)
    items_data: list[dict[str, str]]
    if marketplace == "wildberries":
        from kartochka.services.wildberries_service import wildberries_service

        items_data = await wildberries_service.fetch_catalog(api_key)
    else:
        client_id = encryption_service.decrypt(cred.encrypted_client_id or "")
        from kartochka.services.ozon_service import ozon_service

        items_data = await ozon_service.fetch_catalog(client_id, api_key)

    batch = CatalogBatch(
        uid=generate_uid(),
        user_id=user.id,
        template_id=template.id,
        name=batch_name,
        source=f"{marketplace}_api",
        marketplace=marketplace,
        output_format=output_format,
        total_items=len(items_data),
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    for item_data in items_data:
        item = CatalogItem(
            uid=generate_uid(),
            user_id=user.id,
            catalog_batch_id=batch.id,
            external_id=item_data.get("external_id"),
            title=item_data.get("title", ""),
            brand=item_data.get("brand"),
            price=item_data.get("price"),
            old_price=item_data.get("old_price"),
            image_url=item_data.get("image_url"),
        )
        db.add(item)
    await db.commit()

    from kartochka.workers.tasks import process_batch

    task = process_batch.delay(batch.uid)
    batch.celery_task_id = task.id
    await db.commit()
    return batch


async def get_batch_progress(batch_uid: str, db: AsyncSession) -> dict[str, object]:
    batch = (
        await db.execute(select(CatalogBatch).where(CatalogBatch.uid == batch_uid))
    ).scalar_one_or_none()
    if not batch:
        return {}
    pct = (
        int(batch.processed_items / batch.total_items * 100) if batch.total_items else 0
    )
    return {
        "uid": batch.uid,
        "status": batch.status,
        "total": batch.total_items,
        "processed": batch.processed_items,
        "failed": batch.failed_items,
        "percentage": pct,
    }


async def create_batch_zip(batch: CatalogBatch, db: AsyncSession) -> Path:
    items = (
        (
            await db.execute(
                select(CatalogItem).where(
                    CatalogItem.catalog_batch_id == batch.id,
                    CatalogItem.generation_status == "completed",
                )
            )
        )
        .scalars()
        .all()
    )

    zip_dir = Path(settings.storage_path) / "zips"
    zip_dir.mkdir(parents=True, exist_ok=True)
    zip_path = zip_dir / f"{batch.uid}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, item in enumerate(items):
            if not item.output_path:
                continue
            src = Path(item.output_path)
            if not src.exists():
                continue
            fname = (
                f"{item.external_id}.{batch.output_format}"
                if item.external_id
                else f"{idx + 1:04d}.{batch.output_format}"
            )
            zf.write(src, fname)

    batch.zip_path = str(zip_path)
    await db.commit()
    logger.info("batch_zip_created batch_uid=%s path=%s", batch.uid, zip_path)
    return zip_path
