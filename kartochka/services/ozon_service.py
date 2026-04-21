from __future__ import annotations

from pathlib import Path

import httpx

from kartochka.utils.logging import logger

BASE_URL = "https://api-seller.ozon.ru"


class OzonService:
    def _headers(self, client_id: str, api_key: str) -> dict[str, str]:
        return {
            "Client-Id": client_id,
            "Api-Key": api_key,
            "Content-Type": "application/json",
        }

    async def verify_credentials(self, client_id: str, api_key: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"{BASE_URL}/v1/category/tree",
                    headers=self._headers(client_id, api_key),
                    json={"language": "RU"},
                )
                return r.status_code == 200
        except Exception:
            return False

    async def fetch_catalog(
        self, client_id: str, api_key: str, page: int = 1, page_size: int = 100
    ) -> list[dict[str, str]]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(
                    f"{BASE_URL}/v2/product/list",
                    headers=self._headers(client_id, api_key),
                    json={"page": page, "page_size": page_size},
                )
                if r.status_code != 200:
                    return []
                items = r.json().get("result", {}).get("items", [])
                ids = [item["product_id"] for item in items]
                if not ids:
                    return []
                dr = await client.post(
                    f"{BASE_URL}/v2/product/info/list",
                    headers=self._headers(client_id, api_key),
                    json={"product_id": ids},
                )
                details: list[dict[str, object]] = (
                    dr.json().get("result", {}).get("items", [])
                    if dr.status_code == 200
                    else []
                )
                return [self._map_ozon_item_to_catalog(d) for d in details]
        except Exception as exc:
            logger.warning("ozon_fetch_catalog_failed: %s", exc)
            return []

    async def upload_photo(
        self, client_id: str, api_key: str, product_id: str, image_path: Path
    ) -> bool:
        try:
            import base64

            with open(image_path, "rb") as f:
                content = base64.b64encode(f.read()).decode()
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    f"{BASE_URL}/v1/product/pictures/import",
                    headers=self._headers(client_id, api_key),
                    json={"product_id": int(product_id), "images": [content]},
                )
                return r.status_code == 200
        except Exception as exc:
            logger.warning(
                "ozon_upload_photo_failed product_id=%s: %s", product_id, exc
            )
            return False

    def _map_ozon_item_to_catalog(self, item: dict[str, object]) -> dict[str, str]:
        images = item.get("images") or []
        image_url = images[0] if isinstance(images, list) and images else ""
        return {
            "external_id": str(item.get("id", "")),
            "title": str(item.get("name", "")),
            "brand": "",
            "price": str(item.get("price", "")),
            "old_price": str(item.get("old_price", "")),
            "image_url": str(image_url),
        }


ozon_service = OzonService()
