from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CatalogItemResponse(BaseModel):
    id: int
    uid: str
    external_id: str | None
    title: str
    price: str | None
    old_price: str | None
    discount: str | None
    brand: str | None
    image_url: str | None
    generation_status: str
    output_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CatalogItemListResponse(BaseModel):
    items: list[CatalogItemResponse]
    total: int
    page: int
    page_size: int
