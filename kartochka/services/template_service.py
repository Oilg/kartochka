from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kartochka.config import settings
from kartochka.models.template import Template
from kartochka.models.user import User
from kartochka.schemas.template import TemplateCreate, TemplateUpdate
from kartochka.utils.helpers import generate_uid


async def create_template(
    db: AsyncSession, user: User, data: TemplateCreate
) -> Template:
    # Check template limit for free plan
    if user.plan == "free":
        count_result = await db.execute(
            select(func.count())
            .select_from(Template)
            .where(Template.user_id == user.id)
        )
        count = count_result.scalar() or 0
        if count >= settings.free_plan_max_templates:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": True,
                    "code": "TEMPLATE_LIMIT_REACHED",
                    "message": f"Достигнут лимит шаблонов ({settings.free_plan_max_templates}) для тарифа Free.",
                },
            )

    template = Template(
        uid=generate_uid(),
        user_id=user.id,
        name=data.name,
        description=data.description,
        marketplace=data.marketplace,
        canvas_json=data.canvas_json,
        variables=data.variables,
        canvas_width=data.canvas_width,
        canvas_height=data.canvas_height,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


async def get_user_templates(
    db: AsyncSession,
    user: User,
    marketplace: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> list[Template]:
    query = select(Template).where(Template.user_id == user.id)
    if marketplace:
        query = query.where(Template.marketplace == marketplace)
    query = query.offset(offset).limit(limit).order_by(Template.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_template_by_uid(db: AsyncSession, uid: str, user_id: int) -> Template:
    result = await db.execute(
        select(Template).where(Template.uid == uid, Template.user_id == user_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            404,
            detail={"error": True, "code": "NOT_FOUND", "message": "Шаблон не найден"},
        )
    return template


async def update_template(
    db: AsyncSession, template: Template, data: TemplateUpdate
) -> Template:
    update_data = data.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(template, key, value)
    await db.commit()
    await db.refresh(template)
    return template


async def delete_template(db: AsyncSession, template: Template) -> None:
    await db.delete(template)
    await db.commit()
