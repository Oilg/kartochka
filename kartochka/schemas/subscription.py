from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    id: int
    plan: str
    status: str
    started_at: datetime
    expires_at: datetime
    cancelled_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
