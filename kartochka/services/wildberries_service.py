from __future__ import annotations

from pathlib import Path

import httpx

from kartochka.utils.logging import logger

BASE_URL = "https://suppliers-api.wildberries.ru"


class WildberriesService:
    async def verify_credentials(self, api_key: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{BASE_URL}/ping", headers={"Authorization": api_key}
                )
                return r.status_code == 200
        except Exception:
            return False

    async def fetch_catalog(
        self, api_key: str, limit: int = 100, offset: int = 0
    ) -> list[dict[str, str]]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{BASE_URL}/content/v2/get/cards/list",
                    headers={"Authorization": api_key},
                    json={
                        "settings": {
                            "cursor": {"limit": limit},
                            "filter": {"withPhoto": -1},
                        }
                    },
                )
                if r.status_code != 200:
                    return []
                return [
                    self._map_wb_item_to_catalog(item)
                    for item in r.json().get("cards", [])
                ]
        except Exception as exc:
            logger.warning("wb_fetch_catalog_failed: %s", exc)
            return []

    async def upload_photo(self, api_key: str, nm_id: int, image_path: Path) -> bool:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                with open(image_path, "rb") as f:
                    r = await client.post(
                        f"{BASE_URL}/content/v3/media/save",
                        headers={"Authorization": api_key},
                        params={"nmId": nm_id, "photoNumber": 1},
                        content=f.read(),
                    )
                return r.status_code in (200, 201)
        except Exception as exc:
            logger.warning("wb_upload_photo_failed nm_id=%s: %s", nm_id, exc)
            return False

    def _map_wb_item_to_catalog(self, item: dict[str, object]) -> dict[str, str]:
        photos = item.get("photos", [])
        photo_url = ""
        if isinstance(photos, list) and photos:
            first = photos[0]
            if isinstance(first, dict):
                photo_url = str(first.get("big", ""))
        return {
            "external_id": str(item.get("nmID", "")),
            "title": str(item.get("title", "")),
            "brand": str(item.get("brand", "")),
            "image_url": photo_url,
            "price": "",
        }


wildberries_service = WildberriesService()
