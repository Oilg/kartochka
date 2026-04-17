import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.config import settings
from kartochka.database import get_db
from kartochka.models.generation import Generation
from kartochka.models.template import Template
from kartochka.models.user import User
from kartochka.schemas.generation import GenerationCreate, GenerationResponse
from kartochka.services.image_service import generate_image
from kartochka.utils.dependencies import get_current_user, get_current_user_flexible
from kartochka.utils.helpers import generate_uid

router = APIRouter(prefix="/api/generations", tags=["generations"])


async def check_generation_limits(user: User, db: AsyncSession) -> None:
    today = date.today()
    if user.generations_reset_date != today:
        user.free_generations_used_today = 0
        user.generations_reset_date = today
        await db.commit()

    if user.plan == "free":
        limit = settings.free_plan_max_generations_per_day
        if user.free_generations_used_today >= limit:
            raise HTTPException(
                403,
                detail={
                    "error": True,
                    "code": "GENERATION_LIMIT_REACHED",
                    "message": f"Достигнут дневной лимит генераций ({limit}). Перейдите на Pro.",
                },
            )


@router.post("/", response_model=GenerationResponse)
async def create_generation(
    data: GenerationCreate,
    user: User = Depends(get_current_user_flexible),
    db: AsyncSession = Depends(get_db),
) -> GenerationResponse:
    await check_generation_limits(user, db)

    # Find template
    result = await db.execute(
        select(Template).where(
            Template.uid == data.template_uid, Template.user_id == user.id
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            404,
            detail={"error": True, "code": "NOT_FOUND", "message": "Шаблон не найден"},
        )

    gen_uid = generate_uid()
    extension = data.output_format.lower()
    output_path = Path(settings.storage_path) / "generated" / f"{gen_uid}.{extension}"

    generation = Generation(
        uid=gen_uid,
        user_id=user.id,
        template_id=template.id,
        input_data=json.dumps(data.input_data),
        status="processing",
        output_format=data.output_format,
        output_width=data.output_width,
        output_height=data.output_height,
    )
    db.add(generation)
    await db.commit()
    await db.refresh(generation)

    try:
        await generate_image(
            canvas_json=template.canvas_json,
            input_data=data.input_data,
            output_format=data.output_format,
            canvas_width=template.canvas_width,
            canvas_height=template.canvas_height,
            output_width=data.output_width,
            output_height=data.output_height,
            user_plan=user.plan,
            output_path=output_path,
        )

        generation.status = "completed"
        generation.file_path = str(output_path)
        generation.file_size = output_path.stat().st_size
        user.free_generations_used_today += 1
    except Exception as e:
        generation.status = "failed"
        generation.error_message = str(e)

    await db.commit()
    await db.refresh(generation)
    return GenerationResponse.model_validate(generation)


@router.get("/", response_model=list[GenerationResponse])
async def list_generations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GenerationResponse]:
    result = await db.execute(
        select(Generation)
        .where(Generation.user_id == user.id)
        .order_by(Generation.created_at.desc())
        .limit(50)
    )
    gens = list(result.scalars().all())
    return [GenerationResponse.model_validate(g) for g in gens]


@router.get("/{uid}", response_model=GenerationResponse)
async def get_generation(
    uid: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationResponse:
    result = await db.execute(
        select(Generation).where(Generation.uid == uid, Generation.user_id == user.id)
    )
    gen = result.scalar_one_or_none()
    if not gen:
        raise HTTPException(
            404,
            detail={
                "error": True,
                "code": "NOT_FOUND",
                "message": "Генерация не найдена",
            },
        )
    return GenerationResponse.model_validate(gen)


@router.get("/{uid}/download")
async def download_generation(
    uid: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    result = await db.execute(
        select(Generation).where(Generation.uid == uid, Generation.user_id == user.id)
    )
    gen = result.scalar_one_or_none()
    if not gen or gen.status != "completed" or not gen.file_path:
        raise HTTPException(
            404,
            detail={"error": True, "code": "NOT_FOUND", "message": "Файл не найден"},
        )

    path = Path(gen.file_path)
    if not path.exists():
        raise HTTPException(
            404,
            detail={
                "error": True,
                "code": "FILE_NOT_FOUND",
                "message": "Файл не найден на диске",
            },
        )

    fmt = gen.output_format.lower()
    media_types = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
    }
    media_type = media_types.get(fmt, "application/octet-stream")

    return FileResponse(
        path=str(path), media_type=media_type, filename=f"kartochka_{uid}.{fmt}"
    )


@router.delete("/{uid}")
async def delete_generation(
    uid: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    result = await db.execute(
        select(Generation).where(Generation.uid == uid, Generation.user_id == user.id)
    )
    gen = result.scalar_one_or_none()
    if not gen:
        raise HTTPException(
            404,
            detail={
                "error": True,
                "code": "NOT_FOUND",
                "message": "Генерация не найдена",
            },
        )

    if gen.file_path:
        path = Path(gen.file_path)
        if path.exists():
            path.unlink()

    await db.delete(gen)
    await db.commit()
    return {"success": True}
