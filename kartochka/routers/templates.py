import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.config import settings
from kartochka.database import get_db
from kartochka.models.user import User
from kartochka.schemas.template import (
    TemplateCreate,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdate,
)
from kartochka.services.template_service import (
    create_template,
    delete_template,
    get_template_by_uid,
    get_user_templates,
    update_template,
)
from kartochka.utils.dependencies import get_current_user
from kartochka.utils.helpers import generate_uid

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("/", response_model=list[TemplateListResponse])
async def list_templates(
    marketplace: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TemplateListResponse]:
    templates = await get_user_templates(db, user, marketplace, offset, limit)
    return [TemplateListResponse.model_validate(t) for t in templates]


@router.post("/", response_model=TemplateResponse)
async def create(
    data: TemplateCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateResponse:
    template = await create_template(db, user, data)
    return TemplateResponse.model_validate(template)


@router.get("/{uid}", response_model=TemplateResponse)
async def get_template(
    uid: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateResponse:
    template = await get_template_by_uid(db, uid, user.id)
    return TemplateResponse.model_validate(template)


@router.put("/{uid}", response_model=TemplateResponse)
async def update(
    uid: str,
    data: TemplateUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TemplateResponse:
    template = await get_template_by_uid(db, uid, user.id)
    updated = await update_template(db, template, data)
    return TemplateResponse.model_validate(updated)


@router.delete("/{uid}")
async def delete(
    uid: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    template = await get_template_by_uid(db, uid, user.id)
    await delete_template(db, template)
    return {"success": True}


@router.post("/{uid}/preview")
async def preview_template(
    uid: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    from kartochka.services.image_service import generate_image

    template = await get_template_by_uid(db, uid, user.id)

    # Use default values from variables
    variables_data: list[dict[str, str]] = json.loads(template.variables)
    input_data = {
        v["name"]: v.get("default", "") for v in variables_data if isinstance(v, dict)
    }

    preview_uid = generate_uid()
    output_path = (
        Path(settings.storage_path) / "generated" / f"preview_{preview_uid}.png"
    )

    await generate_image(
        canvas_json=template.canvas_json,
        input_data=input_data,
        output_format="png",
        canvas_width=template.canvas_width,
        canvas_height=template.canvas_height,
        output_width=None,
        output_height=None,
        user_plan=user.plan,
        output_path=output_path,
    )

    preview_url = f"{settings.base_url}/storage/generated/preview_{preview_uid}.png"
    return {"preview_url": preview_url}
