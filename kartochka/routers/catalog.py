from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.database import get_db
from kartochka.models.catalog_batch import CatalogBatch
from kartochka.models.catalog_item import CatalogItem
from kartochka.models.user import User
from kartochka.schemas.catalog_batch import (
    CatalogBatchListResponse,
    CatalogBatchResponse,
)
from kartochka.schemas.catalog_item import CatalogItemListResponse, CatalogItemResponse
from kartochka.services import batch_service, catalog_service
from kartochka.utils.dependencies import get_current_user
from kartochka.utils.plan_checks import require_pro

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _batch_to_response(batch: CatalogBatch) -> CatalogBatchResponse:
    pct = (
        int(batch.processed_items / batch.total_items * 100) if batch.total_items else 0
    )
    return CatalogBatchResponse(
        id=batch.id,
        uid=batch.uid,
        name=batch.name,
        source=batch.source,
        marketplace=batch.marketplace,
        status=batch.status,
        total_items=batch.total_items,
        processed_items=batch.processed_items,
        failed_items=batch.failed_items,
        output_format=batch.output_format,
        zip_path=batch.zip_path,
        publish_status=batch.publish_status,
        published_items=batch.published_items,
        publish_failed_items=batch.publish_failed_items,
        error_message=batch.error_message,
        created_at=batch.created_at,
        completed_at=batch.completed_at,
        percentage=pct,
    )


@router.post("/upload")
async def upload_catalog(
    file: UploadFile = File(...),
    template_uid: str = Form(...),
    marketplace: str = Form(...),
    output_format: str = Form("png"),
    batch_name: str = Form(""),
    column_mapping: str = Form("{}"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CatalogBatchResponse:
    require_pro(user, "Пакетная генерация")

    suffix = Path(file.filename or "file.csv").suffix.lower()
    if suffix not in (".csv", ".xlsx"):
        raise HTTPException(400, detail="Unsupported file type. Use CSV or XLSX.")

    try:
        mapping: dict[str, str] = json.loads(column_mapping)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, detail="Invalid column_mapping JSON") from exc

    name = batch_name or (file.filename or "batch")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        batch = await batch_service.create_batch_from_csv(
            file_path=tmp_path,
            column_mapping=mapping,
            template_uid=template_uid,
            marketplace=marketplace,
            output_format=output_format,
            batch_name=name,
            user=user,
            db=db,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    return _batch_to_response(batch)


@router.post("/detect-columns")
async def detect_columns(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    suffix = Path(file.filename or "file.csv").suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        columns = await catalog_service.detect_columns(tmp_path)
        mapping = catalog_service.guess_column_mapping(columns)
    finally:
        tmp_path.unlink(missing_ok=True)

    return {"columns": columns, "suggested_mapping": mapping}


@router.post("/import-from-marketplace")
async def import_from_marketplace(
    marketplace: str = Form(...),
    template_uid: str = Form(...),
    output_format: str = Form("png"),
    batch_name: str = Form(""),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CatalogBatchResponse:
    require_pro(user, "Импорт из маркетплейса")

    name = batch_name or f"Импорт {marketplace}"
    try:
        batch = await batch_service.create_batch_from_marketplace(
            marketplace=marketplace,
            template_uid=template_uid,
            output_format=output_format,
            batch_name=name,
            user=user,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(400, detail=str(e)) from e

    return _batch_to_response(batch)


@router.get("/batches/", response_model=CatalogBatchListResponse)
async def list_batches(
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CatalogBatchListResponse:
    offset = (page - 1) * page_size
    total_result = await db.execute(
        select(func.count())
        .select_from(CatalogBatch)
        .where(CatalogBatch.user_id == user.id)
    )
    total = total_result.scalar() or 0

    batches_result = await db.execute(
        select(CatalogBatch)
        .where(CatalogBatch.user_id == user.id)
        .order_by(CatalogBatch.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    batches = list(batches_result.scalars().all())

    return CatalogBatchListResponse(
        items=[_batch_to_response(b) for b in batches],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/batches/{uid}", response_model=CatalogBatchResponse)
async def get_batch(
    uid: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CatalogBatchResponse:
    batch = (
        await db.execute(
            select(CatalogBatch).where(
                CatalogBatch.uid == uid, CatalogBatch.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not batch:
        raise HTTPException(404, detail="Batch not found")
    return _batch_to_response(batch)


@router.get("/batches/{uid}/items", response_model=CatalogItemListResponse)
async def list_batch_items(
    uid: str,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CatalogItemListResponse:
    batch = (
        await db.execute(
            select(CatalogBatch).where(
                CatalogBatch.uid == uid, CatalogBatch.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not batch:
        raise HTTPException(404, detail="Batch not found")

    base_q = select(CatalogItem).where(CatalogItem.catalog_batch_id == batch.id)
    if status:
        base_q = base_q.where(CatalogItem.generation_status == status)

    total_result = await db.execute(
        select(func.count())
        .select_from(CatalogItem)
        .where(
            CatalogItem.catalog_batch_id == batch.id,
            *([CatalogItem.generation_status == status] if status else []),
        )
    )
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    items_result = await db.execute(
        base_q.order_by(CatalogItem.id).offset(offset).limit(page_size)
    )
    items = list(items_result.scalars().all())

    return CatalogItemListResponse(
        items=[CatalogItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/batches/{uid}/download")
async def download_batch(
    uid: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    require_pro(user, "Скачивание ZIP")

    batch = (
        await db.execute(
            select(CatalogBatch).where(
                CatalogBatch.uid == uid, CatalogBatch.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not batch:
        raise HTTPException(404, detail="Batch not found")

    if batch.zip_path and Path(batch.zip_path).exists():
        zip_path = Path(batch.zip_path)
    else:
        zip_path = await batch_service.create_batch_zip(batch, db)

    return FileResponse(
        str(zip_path),
        media_type="application/zip",
        filename=f"batch_{uid}.zip",
    )


@router.post("/batches/{uid}/retry-failed")
async def retry_failed_items(
    uid: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    batch = (
        await db.execute(
            select(CatalogBatch).where(
                CatalogBatch.uid == uid, CatalogBatch.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not batch:
        raise HTTPException(404, detail="Batch not found")

    failed_items = (
        (
            await db.execute(
                select(CatalogItem).where(
                    CatalogItem.catalog_batch_id == batch.id,
                    CatalogItem.generation_status == "failed",
                )
            )
        )
        .scalars()
        .all()
    )

    for item in failed_items:
        item.generation_status = "pending"

    batch.failed_items = 0
    batch.status = "pending"
    await db.commit()

    from kartochka.workers.tasks import process_batch

    task = process_batch.delay(batch.uid)
    batch.celery_task_id = task.id
    await db.commit()

    return {"retried": len(failed_items), "task_id": task.id}


@router.post("/batches/{uid}/publish-to-marketplace")
async def publish_to_marketplace(
    uid: str,
    marketplace: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    require_pro(user, "Публикация в маркетплейсы")

    batch = (
        await db.execute(
            select(CatalogBatch).where(
                CatalogBatch.uid == uid, CatalogBatch.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not batch:
        raise HTTPException(404, detail="Batch not found")

    from kartochka.workers.tasks import publish_batch

    task = publish_batch.delay(uid, marketplace)
    batch.publish_task_id = task.id
    batch.publish_status = "publishing"
    await db.commit()

    return {"task_id": task.id, "publish_status": "publishing"}


@router.get("/batches/{uid}/publish-status")
async def get_publish_status(
    uid: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    batch = (
        await db.execute(
            select(CatalogBatch).where(
                CatalogBatch.uid == uid, CatalogBatch.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not batch:
        raise HTTPException(404, detail="Batch not found")

    return {
        "uid": batch.uid,
        "publish_status": batch.publish_status,
        "published_items": batch.published_items,
        "publish_failed_items": batch.publish_failed_items,
        "total_items": batch.total_items,
    }


@router.delete("/batches/{uid}", status_code=204)
async def delete_batch(
    uid: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    batch = (
        await db.execute(
            select(CatalogBatch).where(
                CatalogBatch.uid == uid, CatalogBatch.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not batch:
        raise HTTPException(404, detail="Batch not found")

    # Delete generated files
    items_result = await db.execute(
        select(CatalogItem).where(CatalogItem.catalog_batch_id == batch.id)
    )
    for item in items_result.scalars().all():
        if item.output_path:
            Path(item.output_path).unlink(missing_ok=True)

    # Delete zip
    if batch.zip_path:
        Path(batch.zip_path).unlink(missing_ok=True)

    await db.delete(batch)
    await db.commit()
    return Response(status_code=204)
