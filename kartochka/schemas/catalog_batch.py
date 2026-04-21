from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CatalogBatchResponse(BaseModel):
    id: int
    uid: str
    name: str
    source: str
    marketplace: str
    status: str
    total_items: int
    processed_items: int
    failed_items: int
    output_format: str
    zip_path: str | None
    publish_status: str | None
    published_items: int
    publish_failed_items: int
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    percentage: int = 0

    model_config = {"from_attributes": True}


class CatalogBatchListResponse(BaseModel):
    items: list[CatalogBatchResponse]
    total: int
    page: int
    page_size: int
