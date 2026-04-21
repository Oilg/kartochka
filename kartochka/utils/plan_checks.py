from __future__ import annotations

from fastapi import HTTPException

from kartochka.models.user import User


def require_pro(user: User, feature_name: str) -> None:
    if user.plan != "pro":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PLAN_UPGRADE_REQUIRED",
                "message": f"Функция «{feature_name}» доступна только на тарифе Pro.",
                "upgrade_url": "/billing/upgrade",
            },
        )
