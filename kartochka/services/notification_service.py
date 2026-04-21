from __future__ import annotations

from typing import TYPE_CHECKING

from kartochka.config import settings
from kartochka.utils.logging import logger

if TYPE_CHECKING:
    from kartochka.models.catalog_batch import CatalogBatch


async def send_batch_completed(telegram_chat_id: str, batch: CatalogBatch) -> None:
    if not settings.telegram_bot_token:
        return
    try:
        import httpx

        text = (
            f"\u2705 \u041f\u0430\u043a\u0435\u0442 \u00ab{batch.name}\u00bb \u0433\u043e\u0442\u043e\u0432!\n"
            f"\u041e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d\u043e: {batch.processed_items}/{batch.total_items}\n"
            f"\u041e\u0448\u0438\u0431\u043e\u043a: {batch.failed_items}\n"
            f"\u0421\u043a\u0430\u0447\u0430\u0442\u044c: {settings.base_url}/catalog/batches/{batch.uid}"
        )
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": telegram_chat_id, "text": text},
            )
    except Exception as exc:
        logger.warning("telegram_notification_failed: %s", exc)
