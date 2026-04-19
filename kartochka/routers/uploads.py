from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from kartochka.models.user import User
from kartochka.services.storage_service import get_image_dimensions, save_upload
from kartochka.utils.dependencies import get_current_user
from kartochka.utils.helpers import check_magic_bytes
from kartochka.utils.logging import logger
from kartochka.utils.rate_limit import limiter

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/image")
@limiter.limit("30/minute")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            400,
            detail={
                "error": True,
                "code": "FILE_TOO_LARGE",
                "message": "Файл слишком большой (максимум 10MB)",
            },
        )

    if not check_magic_bytes(content, file.content_type or ""):
        raise HTTPException(
            400,
            detail={
                "error": True,
                "code": "INVALID_FILE",
                "message": "Недопустимый тип файла. Разрешены: PNG, JPEG, WebP",
            },
        )

    original_name = file.filename or "upload"
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else "png"
    if ext not in ALLOWED_EXTENSIONS:
        ext = "png"

    filename, url = await save_upload(content, ext)
    width, height = await get_image_dimensions(content)

    logger.info(
        "upload_success user_id=%s filename=%s size=%d", user.id, filename, len(content)
    )
    return {"url": url, "filename": filename, "width": width, "height": height}
