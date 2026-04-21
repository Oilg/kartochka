from __future__ import annotations

from pydantic import BaseModel


class PlanFeature(BaseModel):
    name: str
    free: bool | str
    pro: bool | str


class PlanInfo(BaseModel):
    name: str
    price: int
    features: list[PlanFeature]


class PlansResponse(BaseModel):
    free: PlanInfo
    pro: PlanInfo


class CreatePaymentRequest(BaseModel):
    return_url: str


class CreatePaymentResponse(BaseModel):
    payment_id: str
    confirmation_url: str


class NotificationsUpdate(BaseModel):
    telegram_chat_id: str | None = None
    telegram_notifications: bool = False
