from __future__ import annotations

import ipaddress
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.config import settings
from kartochka.database import get_db
from kartochka.models.subscription import Subscription
from kartochka.models.user import User
from kartochka.schemas.billing import (
    CreatePaymentRequest,
    CreatePaymentResponse,
    PlanFeature,
    PlanInfo,
    PlansResponse,
)
from kartochka.schemas.subscription import SubscriptionResponse
from kartochka.services.payment_service import payment_service
from kartochka.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/billing", tags=["billing"])

# YooKassa allowed IP ranges
_YOOKASSA_ALLOWED = [
    ipaddress.ip_network("185.71.76.0/27"),
    ipaddress.ip_network("185.71.77.0/27"),
    ipaddress.ip_network("77.75.153.0/25"),
    ipaddress.ip_network("77.75.156.11/32"),
    ipaddress.ip_network("77.75.156.35/32"),
]


def _is_yookassa_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in net for net in _YOOKASSA_ALLOWED)
    except ValueError:
        return False


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.get("/plans", response_model=PlansResponse)
async def get_plans() -> PlansResponse:
    features = [
        PlanFeature(name="Шаблоны", free="до 3", pro="без ограничений"),
        PlanFeature(name="Генерации в день", free="10", pro="без ограничений"),
        PlanFeature(name="Пакетная генерация", free=False, pro=True),
        PlanFeature(name="Импорт из маркетплейсов", free=False, pro=True),
        PlanFeature(name="Скачивание ZIP", free=False, pro=True),
        PlanFeature(name="Публикация в маркетплейсы", free=False, pro=True),
        PlanFeature(name="Уведомления Telegram", free=False, pro=True),
        PlanFeature(name="Приоритетная поддержка", free=False, pro=True),
    ]
    return PlansResponse(
        free=PlanInfo(name="Free", price=0, features=features),
        pro=PlanInfo(name="Pro", price=settings.pro_plan_price_rub, features=features),
    )


@router.post("/subscribe", response_model=CreatePaymentResponse)
async def subscribe(
    data: CreatePaymentRequest,
    user: User = Depends(get_current_user),
) -> CreatePaymentResponse:
    result = await payment_service.create_payment(user, data.return_url)
    return CreatePaymentResponse(
        payment_id=result["payment_id"],
        confirmation_url=result["confirmation_url"],
    )


@router.post("/webhook")
async def yookassa_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    client_ip = _get_client_ip(request)
    if not _is_yookassa_ip(client_ip):
        raise HTTPException(403, detail="Forbidden: IP not in YooKassa allowed range")

    body: Any = await request.json()
    await payment_service.handle_webhook(body, db)
    return {"status": "ok"}


@router.get("/subscription", response_model=SubscriptionResponse | None)
async def get_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Subscription | None:
    return (
        await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id, Subscription.status == "active")
            .order_by(Subscription.created_at.desc())
        )
    ).scalar_one_or_none()


@router.post("/cancel", response_model=SubscriptionResponse | None)
async def cancel_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Subscription | None:
    return await payment_service.cancel_subscription(user, db)
