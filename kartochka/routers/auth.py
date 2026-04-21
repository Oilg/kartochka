import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.database import get_db
from kartochka.models.user import User
from kartochka.schemas.billing import NotificationsUpdate
from kartochka.schemas.user import (
    ApiKeyResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserRegisterResponse,
    UserResponse,
)
from kartochka.services.auth_service import (
    create_access_token,
    hash_password,
    verify_password,
)
from kartochka.utils.dependencies import get_current_user
from kartochka.utils.logging import logger
from kartochka.utils.rate_limit import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserRegisterResponse)
@limiter.limit("3/minute")
async def register(
    request: Request,
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserRegisterResponse:
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            400,
            detail={
                "error": True,
                "code": "EMAIL_EXISTS",
                "message": "Email уже используется",
            },
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        api_key=str(uuid.uuid4()),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("user_registered email=%s", data.email)
    return UserRegisterResponse(
        user_id=user.id,
        email=user.email,
        api_key=user.api_key,
        message="Регистрация успешна",
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        logger.warning("login_failed email=%s ip=%s", data.email, request.client)
        raise HTTPException(
            401,
            detail={
                "error": True,
                "code": "INVALID_CREDENTIALS",
                "message": "Неверный email или пароль",
            },
        )

    token = create_access_token(user.id)
    logger.info("login_success email=%s", data.email)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/regenerate-api-key", response_model=ApiKeyResponse)
async def regenerate_api_key(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyResponse:
    user.api_key = str(uuid.uuid4())
    await db.commit()
    await db.refresh(user)
    logger.info("api_key_regenerated user_id=%s", user.id)
    return ApiKeyResponse(api_key=user.api_key)


@router.patch("/notifications")
async def update_notifications(
    data: NotificationsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user.telegram_chat_id = data.telegram_chat_id
    user.telegram_notifications = data.telegram_notifications
    await db.commit()
    logger.info(
        "notifications_updated user_id=%s enabled=%s",
        user.id,
        data.telegram_notifications,
    )
    return {
        "telegram_chat_id": user.telegram_chat_id,
        "telegram_notifications": user.telegram_notifications,
    }
