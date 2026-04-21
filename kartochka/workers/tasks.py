from __future__ import annotations

import asyncio
import time
from collections.abc import Coroutine
from datetime import UTC
from typing import Any

from celery import Task

from kartochka.utils.logging import logger
from kartochka.workers.celery_app import celery_app


def _get_sync_db() -> Any:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from kartochka.config import settings

    url = settings.database_url.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    ).replace("sqlite+aiosqlite:///", "sqlite:///")
    engine = create_engine(url)
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def _run(coro: Coroutine[Any, Any, Any]) -> Any:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(bind=True, max_retries=3)  # type: ignore[untyped-decorator]
def process_batch(self: Task, batch_uid: str) -> dict[str, object]:
    import json as _json
    from datetime import datetime
    from pathlib import Path

    from sqlalchemy import select as sel

    from kartochka.config import settings
    from kartochka.models.catalog_batch import CatalogBatch
    from kartochka.models.catalog_item import CatalogItem
    from kartochka.models.marketplace_credential import MarketplaceCredential
    from kartochka.models.template import Template
    from kartochka.models.user import User
    from kartochka.services.image_service import generate_image
    from kartochka.utils.helpers import generate_uid

    db = _get_sync_db()
    try:
        batch = db.execute(
            sel(CatalogBatch).where(CatalogBatch.uid == batch_uid)
        ).scalar_one_or_none()
        if not batch:
            return {"error": "batch_not_found"}

        batch.status = "processing"
        db.commit()

        template = db.execute(
            sel(Template).where(Template.id == batch.template_id)
        ).scalar_one()
        user = db.execute(sel(User).where(User.id == batch.user_id)).scalar_one()
        variables_data = _json.loads(template.variables)
        default_vars = {
            v["name"]: v.get("default", "")
            for v in variables_data
            if isinstance(v, dict)
        }

        items = (
            db.execute(
                sel(CatalogItem).where(
                    CatalogItem.catalog_batch_id == batch.id,
                    CatalogItem.generation_status == "pending",
                )
            )
            .scalars()
            .all()
        )

        output_dir = Path(settings.storage_path) / "generated"
        output_dir.mkdir(parents=True, exist_ok=True)

        field_map: dict[str, list[str]] = {
            "title": ["title", "Название", "Заголовок", "name"],
            "price": ["price", "Цена"],
            "brand": ["brand", "Бренд"],
            "discount": ["discount", "Скидка"],
        }

        for item in items:
            try:
                item.generation_status = "processing"
                db.commit()

                input_vars = dict(default_vars)
                item_vals = {
                    "title": item.title,
                    "price": item.price or "",
                    "brand": item.brand or "",
                    "discount": item.discount or "",
                }
                for field, val in item_vals.items():
                    for key in field_map.get(field, []):
                        if key in input_vars:
                            input_vars[key] = val

                out_uid = generate_uid()
                output_path = output_dir / f"{out_uid}.{batch.output_format}"

                _run(
                    generate_image(
                        canvas_json=template.canvas_json,
                        input_data=input_vars,
                        output_format=batch.output_format,
                        canvas_width=template.canvas_width,
                        canvas_height=template.canvas_height,
                        output_width=None,
                        output_height=None,
                        user_plan=user.plan,
                        output_path=output_path,
                        is_preview=False,
                    )
                )

                item.generation_status = "completed"
                item.output_path = str(output_path)
                batch.processed_items += 1
            except Exception as exc:
                logger.exception(
                    "item_generation_failed item_uid=%s: %s", item.uid, exc
                )
                item.generation_status = "failed"
                batch.failed_items += 1
            db.commit()

        # Create ZIP
        _create_zip(batch, db)

        batch.status = (
            "completed" if batch.failed_items == 0 else "completed_with_errors"
        )
        batch.completed_at = datetime.now(UTC)
        db.commit()

        # Auto-publish check
        cred = db.execute(
            sel(MarketplaceCredential).where(
                MarketplaceCredential.user_id == batch.user_id,
                MarketplaceCredential.marketplace == batch.marketplace,
            )
        ).scalar_one_or_none()
        if cred and cred.publish_mode == "auto":
            task = publish_batch.delay(batch_uid, batch.marketplace)
            batch.publish_task_id = task.id
            batch.publish_status = "publishing"
            db.commit()

        # Telegram notification
        if (
            user.telegram_notifications
            and user.telegram_chat_id
            and settings.telegram_bot_token
        ):
            _run(_notify(user.telegram_chat_id, batch))

        return {
            "batch_uid": batch_uid,
            "processed": batch.processed_items,
            "failed": batch.failed_items,
        }

    except Exception as exc:
        logger.exception("process_batch_failed batch_uid=%s", batch_uid)
        try:
            b = db.execute(
                sel(CatalogBatch).where(CatalogBatch.uid == batch_uid)
            ).scalar_one_or_none()
            if b:
                b.status = "failed"
                b.error_message = str(exc)
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60) from exc
    finally:
        db.close()


def _create_zip(batch: Any, db: Any) -> None:
    import zipfile
    from pathlib import Path

    from sqlalchemy import select as sel

    from kartochka.config import settings
    from kartochka.models.catalog_item import CatalogItem

    items = (
        db.execute(
            sel(CatalogItem).where(
                CatalogItem.catalog_batch_id == batch.id,
                CatalogItem.generation_status == "completed",
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
            if src.exists():
                fname = (
                    f"{item.external_id}.{batch.output_format}"
                    if item.external_id
                    else f"{idx + 1:04d}.{batch.output_format}"
                )
                zf.write(src, fname)

    batch.zip_path = str(zip_path)
    db.commit()


async def _notify(chat_id: str, batch: Any) -> None:
    from kartochka.services.notification_service import send_batch_completed

    await send_batch_completed(chat_id, batch)


@celery_app.task(bind=True, max_retries=5)  # type: ignore[untyped-decorator]
def publish_batch(self: Task, batch_uid: str, marketplace: str) -> dict[str, object]:
    from pathlib import Path

    from sqlalchemy import select as sel

    from kartochka.config import settings
    from kartochka.models.catalog_batch import CatalogBatch
    from kartochka.models.catalog_item import CatalogItem
    from kartochka.models.marketplace_credential import MarketplaceCredential
    from kartochka.services.encryption_service import encryption_service

    db = _get_sync_db()
    try:
        batch = db.execute(
            sel(CatalogBatch).where(CatalogBatch.uid == batch_uid)
        ).scalar_one_or_none()
        if not batch:
            return {"error": "batch_not_found"}

        batch.publish_status = "publishing"
        db.commit()

        cred = db.execute(
            sel(MarketplaceCredential).where(
                MarketplaceCredential.user_id == batch.user_id,
                MarketplaceCredential.marketplace == marketplace,
            )
        ).scalar_one_or_none()
        if not cred:
            batch.publish_status = "publish_failed"
            db.commit()
            return {"error": "no_credentials"}

        api_key = encryption_service.decrypt(cred.encrypted_api_key)
        client_id = (
            encryption_service.decrypt(cred.encrypted_client_id)
            if cred.encrypted_client_id
            else ""
        )

        items = (
            db.execute(
                sel(CatalogItem).where(
                    CatalogItem.catalog_batch_id == batch.id,
                    CatalogItem.generation_status == "completed",
                )
            )
            .scalars()
            .all()
        )

        chunk_size = settings.publish_chunk_size
        items_list = list(items)
        chunks = [
            items_list[i : i + chunk_size]
            for i in range(0, len(items_list), chunk_size)
        ]

        for chunk in chunks:
            for item in chunk:
                if not item.output_path:
                    continue
                path = Path(item.output_path)
                try:
                    if marketplace == "wildberries":
                        from kartochka.services.wildberries_service import (
                            wildberries_service,
                        )

                        ok = _run(
                            wildberries_service.upload_photo(
                                api_key, int(item.external_id or "0"), path
                            )
                        )
                    else:
                        from kartochka.services.ozon_service import ozon_service

                        ok = _run(
                            ozon_service.upload_photo(
                                client_id, api_key, item.external_id or "", path
                            )
                        )
                    if ok:
                        batch.published_items += 1
                    else:
                        batch.publish_failed_items += 1
                except Exception as exc:
                    if "429" in str(exc):
                        db.commit()
                        raise self.retry(exc=exc, countdown=60) from exc
                    logger.warning("publish_item_failed item=%s: %s", item.uid, exc)
                    batch.publish_failed_items += 1
            db.commit()
            time.sleep(settings.publish_chunk_delay)

        batch.publish_status = (
            "published" if batch.publish_failed_items == 0 else "publish_failed"
        )
        db.commit()
        return {
            "published": batch.published_items,
            "failed": batch.publish_failed_items,
        }

    except Exception as exc:
        logger.exception("publish_batch_failed batch_uid=%s", batch_uid)
        try:
            b = db.execute(
                sel(CatalogBatch).where(CatalogBatch.uid == batch_uid)
            ).scalar_one_or_none()
            if b:
                b.publish_status = "publish_failed"
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60) from exc
    finally:
        db.close()


@celery_app.task  # type: ignore[untyped-decorator]
def check_expired_subscriptions() -> dict[str, int]:
    from datetime import datetime

    from sqlalchemy import select as sel

    from kartochka.models.subscription import Subscription
    from kartochka.models.user import User

    db = _get_sync_db()
    try:
        now = datetime.now(UTC)
        subs = (
            db.execute(
                sel(Subscription).where(
                    Subscription.status == "active", Subscription.expires_at < now
                )
            )
            .scalars()
            .all()
        )
        count = 0
        for sub in subs:
            sub.status = "expired"
            user = db.execute(
                sel(User).where(User.id == sub.user_id)
            ).scalar_one_or_none()
            if user:
                user.plan = "free"
            count += 1
        if count:
            db.commit()
        return {"expired": count}
    finally:
        db.close()
