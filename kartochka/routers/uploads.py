from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from kartochka.models.user import User
from kartochka.services.storage_service import get_image_dimensions, save_upload
from kartochka.utils.dependencies import get_current_user
from kartochka.utils.helpers import check_magic_bytes

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/image")
async def upload_image(
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

    return {"url": url, "filename": filename, "width": width, "height": height}
