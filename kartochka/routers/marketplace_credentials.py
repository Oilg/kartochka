from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.database import get_db
from kartochka.models.marketplace_credential import MarketplaceCredential
from kartochka.models.user import User
from kartochka.schemas.marketplace_credential import (
    MarketplaceCredentialCreate,
    MarketplaceCredentialResponse,
)
from kartochka.services.encryption_service import encryption_service
from kartochka.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/marketplace-credentials", tags=["marketplace"])


@router.get("/", response_model=list[MarketplaceCredentialResponse])
async def list_credentials(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MarketplaceCredential]:
    result = await db.execute(
        select(MarketplaceCredential).where(MarketplaceCredential.user_id == user.id)
    )
    return list(result.scalars().all())


@router.post("/", response_model=MarketplaceCredentialResponse)
async def upsert_credential(
    data: MarketplaceCredentialCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MarketplaceCredential:
    # Check if exists
    existing = (
        await db.execute(
            select(MarketplaceCredential).where(
                MarketplaceCredential.user_id == user.id,
                MarketplaceCredential.marketplace == data.marketplace,
            )
        )
    ).scalar_one_or_none()

    encrypted_key = encryption_service.encrypt(data.api_key)
    encrypted_client_id = (
        encryption_service.encrypt(data.client_id) if data.client_id else None
    )

    # Verify credentials
    is_valid = False
    if data.marketplace == "wildberries":
        from kartochka.services.wildberries_service import wildberries_service

        is_valid = await wildberries_service.verify_credentials(data.api_key)
    elif data.marketplace == "ozon":
        if not data.client_id:
            raise HTTPException(400, detail="client_id is required for Ozon")
        from kartochka.services.ozon_service import ozon_service

        is_valid = await ozon_service.verify_credentials(data.client_id, data.api_key)

    now = datetime.now(UTC)

    if existing:
        existing.encrypted_api_key = encrypted_key
        existing.encrypted_client_id = encrypted_client_id
        existing.publish_mode = data.publish_mode
        existing.is_valid = is_valid
        existing.last_verified_at = now
        await db.commit()
        await db.refresh(existing)
        return existing

    cred = MarketplaceCredential(
        user_id=user.id,
        marketplace=data.marketplace,
        encrypted_api_key=encrypted_key,
        encrypted_client_id=encrypted_client_id,
        publish_mode=data.publish_mode,
        is_valid=is_valid,
        last_verified_at=now,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return cred


@router.delete("/{marketplace}", status_code=204)
async def delete_credential(
    marketplace: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    cred = (
        await db.execute(
            select(MarketplaceCredential).where(
                MarketplaceCredential.user_id == user.id,
                MarketplaceCredential.marketplace == marketplace,
            )
        )
    ).scalar_one_or_none()
    if not cred:
        raise HTTPException(404, detail="Credential not found")
    await db.delete(cred)
    await db.commit()
    return Response(status_code=204)


@router.post("/{marketplace}/verify", response_model=MarketplaceCredentialResponse)
async def verify_credential(
    marketplace: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MarketplaceCredential:
    cred = (
        await db.execute(
            select(MarketplaceCredential).where(
                MarketplaceCredential.user_id == user.id,
                MarketplaceCredential.marketplace == marketplace,
            )
        )
    ).scalar_one_or_none()
    if not cred:
        raise HTTPException(404, detail="Credential not found")

    api_key = encryption_service.decrypt(cred.encrypted_api_key)
    is_valid = False
    if marketplace == "wildberries":
        from kartochka.services.wildberries_service import wildberries_service

        is_valid = await wildberries_service.verify_credentials(api_key)
    elif marketplace == "ozon":
        client_id = encryption_service.decrypt(cred.encrypted_client_id or "")
        from kartochka.services.ozon_service import ozon_service

        is_valid = await ozon_service.verify_credentials(client_id, api_key)

    cred.is_valid = is_valid
    cred.last_verified_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(cred)
    return cred
