from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.database import get_db
from kartochka.models.user import User
from kartochka.services.auth_service import verify_token

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": True,
                "code": "NOT_AUTHENTICATED",
                "message": "Требуется авторизация",
            },
        )

    user_id = verify_token(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": True,
                "code": "INVALID_TOKEN",
                "message": "Недействительный токен",
            },
        )

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": True,
                "code": "USER_NOT_FOUND",
                "message": "Пользователь не найден",
            },
        )

    return user


async def get_user_from_api_key(
    x_api_key: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if not x_api_key:
        return None
    result = await db.execute(
        select(User).where(User.api_key == x_api_key, User.is_active == True)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def get_current_user_flexible(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_api_key: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Try API key first
    if x_api_key:
        result = await db.execute(
            select(User).where(User.api_key == x_api_key, User.is_active == True)  # noqa: E712
        )
        user = result.scalar_one_or_none()
        if user:
            return user

    # Try JWT
    if credentials:
        user_id = verify_token(credentials.credentials)
        if user_id:
            result = await db.execute(select(User).where(User.id == int(user_id)))
            user = result.scalar_one_or_none()
            if user and user.is_active:
                return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": True,
            "code": "NOT_AUTHENTICATED",
            "message": "Требуется авторизация",
        },
    )
