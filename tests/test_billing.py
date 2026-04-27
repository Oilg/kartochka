from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.models.subscription import Subscription
from kartochka.models.user import User
from kartochka.routers.billing import _is_yookassa_ip
from kartochka.services.payment_service import payment_service
from kartochka.utils.plan_checks import require_pro


class TestYookassaIpCheck:
    def test_valid_yookassa_ip(self) -> None:
        assert _is_yookassa_ip("185.71.76.1") is True
        assert _is_yookassa_ip("185.71.77.1") is True
        assert _is_yookassa_ip("77.75.153.1") is True
        assert _is_yookassa_ip("77.75.156.11") is True
        assert _is_yookassa_ip("77.75.156.35") is True

    def test_invalid_ip(self) -> None:
        assert _is_yookassa_ip("1.2.3.4") is False
        assert _is_yookassa_ip("192.168.1.1") is False
        assert _is_yookassa_ip("127.0.0.1") is False

    def test_invalid_ip_format(self) -> None:
        assert _is_yookassa_ip("not-an-ip") is False


class TestPlansEndpoint:
    async def test_get_plans(self, async_client: AsyncClient) -> None:
        r = await async_client.get("/api/billing/plans")
        assert r.status_code == 200
        data = r.json()
        assert "free" in data
        assert "pro" in data
        assert data["free"]["price"] == 0
        assert data["pro"]["price"] > 0
        assert len(data["free"]["features"]) > 0


class TestWebhookIpCheck:
    async def test_webhook_forbidden_ip(self, async_client: AsyncClient) -> None:
        r = await async_client.post(
            "/api/billing/webhook",
            json={"event": "payment.succeeded", "object": {}},
            headers={"X-Forwarded-For": "1.2.3.4"},
        )
        assert r.status_code == 403

    async def test_webhook_allowed_ip(self, async_client: AsyncClient) -> None:
        with patch(
            "kartochka.services.payment_service.PaymentService.handle_webhook",
            new_callable=AsyncMock,
        ):
            r = await async_client.post(
                "/api/billing/webhook",
                json={"event": "payment.succeeded", "object": {}},
                headers={"X-Forwarded-For": "185.71.76.1"},
            )
            assert r.status_code == 200


class TestRequirePro:
    def test_require_pro_free_user(self, test_user: User) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            require_pro(test_user, "Test Feature")
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "PLAN_UPGRADE_REQUIRED"

    def test_require_pro_pro_user(self, pro_user: User) -> None:
        # Should not raise
        require_pro(pro_user, "Test Feature")


class TestWebhookXForwardedFor:
    """X-Forwarded-For spoofing: последний IP должен быть из YooKassa, не первый."""

    async def test_spoofed_forwarded_for_is_rejected(
        self, async_client: AsyncClient
    ) -> None:
        # Attacker puts YooKassa IP first, real IP is last → must be rejected
        r = await async_client.post(
            "/api/billing/webhook",
            json={"event": "payment.succeeded", "object": {}},
            headers={"X-Forwarded-For": "185.71.76.1, 1.2.3.4"},
        )
        assert r.status_code == 403

    async def test_real_yookassa_ip_last_is_allowed(
        self, async_client: AsyncClient
    ) -> None:
        with patch(
            "kartochka.services.payment_service.PaymentService.handle_webhook",
            new_callable=AsyncMock,
        ):
            # nginx adds YooKassa IP at the end — trusted
            r = await async_client.post(
                "/api/billing/webhook",
                json={"event": "payment.succeeded", "object": {}},
                headers={"X-Forwarded-For": "1.2.3.4, 185.71.76.1"},
            )
            assert r.status_code == 200


class TestWebhookIdempotency:
    """Повторный webhook с тем же payment_id не должен создавать вторую подписку."""

    async def test_duplicate_webhook_skipped(
        self, test_db: AsyncSession, test_user: User
    ) -> None:
        payment_id = "test-payment-idempotent-001"
        sub = Subscription(
            user_id=test_user.id,
            plan="pro",
            status="active",
            yookassa_payment_id=payment_id,
            expires_at=datetime.now(UTC) + timedelta(days=31),
        )
        test_db.add(sub)
        test_user.plan = "pro"
        await test_db.commit()

        # Call _activate_pro again with the same payment_id
        await payment_service._activate_pro(test_user.id, payment_id, test_db)

        # Still only one subscription with this payment_id
        from sqlalchemy import select as sel

        subs = (
            (
                await test_db.execute(
                    sel(Subscription).where(
                        Subscription.yookassa_payment_id == payment_id
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(subs) == 1


class TestSubscriptionLifecycle:
    async def test_get_subscription_none(
        self,
        async_client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        r = await async_client.get("/api/billing/subscription", headers=auth_headers)
        assert r.status_code == 200
        assert r.json() is None

    async def test_cancel_subscription_downgrades_plan(
        self,
        async_client: AsyncClient,
        test_db: AsyncSession,
        test_user: User,
        auth_headers: dict[str, str],
    ) -> None:
        """Cancellation must immediately downgrade user.plan to 'free'."""
        sub = Subscription(
            user_id=test_user.id,
            plan="pro",
            status="active",
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        test_db.add(sub)
        test_user.plan = "pro"
        await test_db.commit()

        r = await async_client.post("/api/billing/cancel", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data is not None
        assert data["status"] == "cancelled"

        # Plan must be downgraded immediately
        await test_db.refresh(test_user)
        assert test_user.plan == "free"


class TestCheckExpiredSubscriptions:
    async def test_expires_subscription(
        self, test_db: AsyncSession, test_user: User
    ) -> None:
        sub = Subscription(
            user_id=test_user.id,
            plan="pro",
            status="active",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        test_db.add(sub)
        test_user.plan = "pro"
        await test_db.commit()

        count = await payment_service.check_expired_subscriptions(test_db)
        assert count >= 1

        await test_db.refresh(sub)
        assert sub.status == "expired"
        await test_db.refresh(test_user)
        assert test_user.plan == "free"
