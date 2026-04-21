from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MarketplaceCredentialCreate(BaseModel):
    marketplace: str
    api_key: str
    client_id: str | None = None
    publish_mode: str = "manual"


class MarketplaceCredentialUpdate(BaseModel):
    api_key: str | None = None
    client_id: str | None = None
    publish_mode: str | None = None


class MarketplaceCredentialResponse(BaseModel):
    id: int
    marketplace: str
    is_valid: bool
    publish_mode: str
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
