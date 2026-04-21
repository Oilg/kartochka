from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.config import settings
from kartochka.models.subscription import Subscription
from kartochka.utils.logging import logger

if TYPE_CHECKING:
    from kartochka.models.user import User


class PaymentService:
    def _configure(self) -> None:
        if settings.yookassa_shop_id and settings.yookassa_secret_key:
            from yookassa import Configuration

            Configuration.configure(
                settings.yookassa_shop_id, settings.yookassa_secret_key
            )

    async def create_payment(self, user: User, return_url: str) -> dict[str, str]:
        if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
            from fastapi import HTTPException

            raise HTTPException(503, detail="Payment service not configured")
        self._configure()
        import uuid

        from yookassa import Payment

        payment = Payment.create(
            {
                "amount": {
                    "value": f"{settings.pro_plan_price_rub}.00",
                    "currency": "RUB",
                },
                "confirmation": {"type": "redirect", "return_url": return_url},
                "capture": True,
                "description": f"Подписка Карточка Pro — {user.email}",
                "metadata": {"user_id": str(user.id)},
                "save_payment_method": True,
            },
            str(uuid.uuid4()),
        )
        return {
            "payment_id": payment.id,
            "confirmation_url": payment.confirmation.confirmation_url,
        }

    async def handle_webhook(self, body: dict[str, object], db: AsyncSession) -> None:
        event = body.get("event", "")
        obj = body.get("object", {})
        if not isinstance(obj, dict):
            obj = {}
        if event == "payment.succeeded":
            metadata = obj.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            user_id_str = str(metadata.get("user_id", "0"))
            user_id = int(user_id_str) if user_id_str.isdigit() else 0
            if user_id:
                await self._activate_pro(user_id, str(obj.get("id", "")), db)
        elif event == "payment.canceled":
            logger.info("payment_canceled payment_id=%s", obj.get("id"))
        elif event == "refund.succeeded":
            logger.info("refund_succeeded refund_id=%s", obj.get("id"))

    async def _activate_pro(
        self, user_id: int, payment_id: str, db: AsyncSession
    ) -> None:
        from kartochka.models.user import User

        user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if not user:
            return
        sub = Subscription(
            user_id=user_id,
            plan="pro",
            status="active",
            yookassa_payment_id=payment_id,
            expires_at=datetime.now(UTC) + timedelta(days=31),
        )
        db.add(sub)
        user.plan = "pro"
        await db.commit()
        logger.info("pro_activated user_id=%s payment_id=%s", user_id, payment_id)

    async def cancel_subscription(
        self, user: User, db: AsyncSession
    ) -> Subscription | None:
        sub = (
            await db.execute(
                select(Subscription)
                .where(Subscription.user_id == user.id, Subscription.status == "active")
                .order_by(Subscription.created_at.desc())
            )
        ).scalar_one_or_none()
        if sub:
            sub.status = "cancelled"
            sub.cancelled_at = datetime.now(UTC)
            await db.commit()
        return sub

    async def check_expired_subscriptions(self, db: AsyncSession) -> int:
        from kartochka.models.user import User

        now = datetime.now(UTC)
        subs = (
            (
                await db.execute(
                    select(Subscription).where(
                        Subscription.status == "active", Subscription.expires_at < now
                    )
                )
            )
            .scalars()
            .all()
        )
        count = 0
        for sub in subs:
            sub.status = "expired"
            user = (
                await db.execute(select(User).where(User.id == sub.user_id))
            ).scalar_one_or_none()
            if user:
                user.plan = "free"
            count += 1
        if count:
            await db.commit()
        return count


payment_service = PaymentService()
