from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from datetime import UTC
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from kartochka.config import settings
from kartochka.database import async_session_maker, get_db
from kartochka.metrics import (
    active_users_30d,
    http_requests_total,
    registered_users_total,
)
from kartochka.models.template import Template
from kartochka.models.user import User
from kartochka.routers import auth, generations, pages, templates, uploads
from kartochka.services.auth_service import hash_password
from kartochka.utils.logging import logger
from kartochka.utils.rate_limit import limiter


async def create_demo_user_if_not_exists(session: Any) -> None:
    result = await session.execute(
        select(User).where(User.email == "demo@kartochka.ru")
    )
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            email="demo@kartochka.ru",
            hashed_password=hash_password("demo123"),
            full_name="Демо Пользователь",
            api_key=str(uuid.uuid4()),
            plan="pro",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    # Always ensure default templates exist (idempotent — skips if already seeded)
    await create_default_templates(session, user)


async def _make_preview(session: Any, template: Template) -> None:
    """Render a preview PNG for a template using its default variable values."""
    from kartochka.services.image_service import generate_image
    from kartochka.utils.helpers import generate_uid

    variables_data: list[dict[str, str]] = json.loads(template.variables)
    input_data = {
        v["name"]: v.get("default", "") for v in variables_data if isinstance(v, dict)
    }
    preview_uid = generate_uid()
    output_path = (
        Path(settings.storage_path) / "generated" / f"preview_{preview_uid}.png"
    )
    try:
        await generate_image(
            canvas_json=template.canvas_json,
            input_data=input_data,
            output_format="png",
            canvas_width=template.canvas_width,
            canvas_height=template.canvas_height,
            output_width=None,
            output_height=None,
            user_plan="pro",
            output_path=output_path,
            is_preview=False,
        )
        template.preview_url = (
            f"{settings.base_url}/storage/generated/preview_{preview_uid}.png"
        )
        await session.commit()
    except Exception:
        logger.exception("seed_preview_failed template=%s", template.uid)


async def create_default_templates(session: Any, user: User) -> None:
    count_result = await session.execute(
        select(Template).where(Template.user_id == user.id, Template.is_default == True)  # noqa: E712
    )
    if count_result.scalars().first():
        return

    templates_data = [
        {
            "name": "WB — Основная карточка",
            "marketplace": "wb",
            "canvas_width": 900,
            "canvas_height": 1200,
            "canvas_json": json.dumps(
                {
                    "layers": [
                        {
                            "type": "rectangle",
                            "id": "bg",
                            "x": 0,
                            "y": 0,
                            "width": 900,
                            "height": 1200,
                            "zIndex": 0,
                            "fill": "#FFFFFF",
                            "border_radius": 0,
                            "opacity": 1.0,
                        },
                        {
                            "type": "image",
                            "id": "photo",
                            "x": 0,
                            "y": 0,
                            "width": 900,
                            "height": 840,
                            "zIndex": 1,
                            "src": "{{image_url}}",
                            "fit": "cover",
                            "border_radius": 0,
                        },
                        {
                            "type": "rectangle",
                            "id": "bottom_panel",
                            "x": 0,
                            "y": 820,
                            "width": 900,
                            "height": 380,
                            "zIndex": 2,
                            "fill": "#1A1A2E",
                            "border_radius": 0,
                            "opacity": 0.92,
                        },
                        {
                            "type": "text",
                            "id": "title",
                            "x": 24,
                            "y": 840,
                            "width": 852,
                            "height": 90,
                            "zIndex": 3,
                            "text": "{{title}}",
                            "font_family": "Roboto",
                            "font_size": 30,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#FFFFFF",
                            "align": "left",
                            "max_lines": 2,
                            "line_height": 1.25,
                        },
                        {
                            "type": "text",
                            "id": "price",
                            "x": 24,
                            "y": 960,
                            "width": 300,
                            "height": 60,
                            "zIndex": 3,
                            "text": "{{price}} ₽",
                            "font_family": "Roboto",
                            "font_size": 48,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#FFFFFF",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "old_price",
                            "x": 24,
                            "y": 1030,
                            "width": 300,
                            "height": 40,
                            "zIndex": 3,
                            "text": "{{old_price}} ₽",
                            "font_family": "Roboto",
                            "font_size": 28,
                            "font_bold": False,
                            "font_italic": False,
                            "color": "#AAAAAA",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "badge",
                            "id": "discount",
                            "x": 24,
                            "y": 1090,
                            "width": 120,
                            "height": 48,
                            "zIndex": 4,
                            "badge_type": "discount",
                            "value": "{{discount}}",
                            "bg_color": "#FF4757",
                            "text_color": "#FFFFFF",
                            "border_radius": 8,
                        },
                    ]
                }
            ),
            "variables": json.dumps(
                [
                    {
                        "name": "title",
                        "label": "Название товара",
                        "default": "Кроссовки Nike Air Max 90",
                    },
                    {"name": "price", "label": "Цена", "default": "4 990"},
                    {"name": "old_price", "label": "Старая цена", "default": "7 990"},
                    {"name": "discount", "label": "Скидка", "default": "-38%"},
                    {"name": "image_url", "label": "Фото товара (URL)", "default": ""},
                ]
            ),
        },
        {
            "name": "Ozon — Инфографика",
            "marketplace": "ozon",
            "canvas_width": 1000,
            "canvas_height": 1000,
            "canvas_json": json.dumps(
                {
                    "layers": [
                        {
                            "type": "rectangle",
                            "id": "bg",
                            "x": 0,
                            "y": 0,
                            "width": 1000,
                            "height": 1000,
                            "zIndex": 0,
                            "fill": "#FFFFFF",
                            "border_radius": 0,
                            "opacity": 1.0,
                        },
                        {
                            "type": "image",
                            "id": "photo",
                            "x": 0,
                            "y": 0,
                            "width": 480,
                            "height": 1000,
                            "zIndex": 1,
                            "src": "{{image_url}}",
                            "fit": "contain",
                            "border_radius": 0,
                        },
                        {
                            "type": "rectangle",
                            "id": "right_panel",
                            "x": 480,
                            "y": 0,
                            "width": 520,
                            "height": 1000,
                            "zIndex": 2,
                            "fill": "#F8F9FA",
                            "border_radius": 0,
                            "opacity": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "brand",
                            "x": 500,
                            "y": 40,
                            "width": 480,
                            "height": 60,
                            "zIndex": 3,
                            "text": "{{brand}}",
                            "font_family": "Roboto",
                            "font_size": 36,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#2D3436",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "title",
                            "x": 500,
                            "y": 120,
                            "width": 480,
                            "height": 80,
                            "zIndex": 3,
                            "text": "{{title}}",
                            "font_family": "Roboto",
                            "font_size": 24,
                            "font_bold": False,
                            "font_italic": False,
                            "color": "#636E72",
                            "align": "left",
                            "max_lines": 2,
                            "line_height": 1.3,
                        },
                        {
                            "type": "text",
                            "id": "feature_1",
                            "x": 500,
                            "y": 240,
                            "width": 480,
                            "height": 40,
                            "zIndex": 3,
                            "text": "• {{feature_1}}",
                            "font_family": "Roboto",
                            "font_size": 20,
                            "font_bold": False,
                            "font_italic": False,
                            "color": "#2D3436",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "feature_2",
                            "x": 500,
                            "y": 290,
                            "width": 480,
                            "height": 40,
                            "zIndex": 3,
                            "text": "• {{feature_2}}",
                            "font_family": "Roboto",
                            "font_size": 20,
                            "font_bold": False,
                            "font_italic": False,
                            "color": "#2D3436",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "feature_3",
                            "x": 500,
                            "y": 340,
                            "width": 480,
                            "height": 40,
                            "zIndex": 3,
                            "text": "• {{feature_3}}",
                            "font_family": "Roboto",
                            "font_size": 20,
                            "font_bold": False,
                            "font_italic": False,
                            "color": "#2D3436",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "feature_4",
                            "x": 500,
                            "y": 390,
                            "width": 480,
                            "height": 40,
                            "zIndex": 3,
                            "text": "• {{feature_4}}",
                            "font_family": "Roboto",
                            "font_size": 20,
                            "font_bold": False,
                            "font_italic": False,
                            "color": "#2D3436",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "feature_5",
                            "x": 500,
                            "y": 440,
                            "width": 480,
                            "height": 40,
                            "zIndex": 3,
                            "text": "• {{feature_5}}",
                            "font_family": "Roboto",
                            "font_size": 20,
                            "font_bold": False,
                            "font_italic": False,
                            "color": "#2D3436",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                    ]
                }
            ),
            "variables": json.dumps(
                [
                    {
                        "name": "title",
                        "label": "Название товара",
                        "default": "Умная колонка",
                    },
                    {"name": "brand", "label": "Бренд", "default": "TechBrand"},
                    {"name": "image_url", "label": "Фото товара", "default": ""},
                    {
                        "name": "feature_1",
                        "label": "Характеристика 1",
                        "default": "Мощный звук 20W",
                    },
                    {
                        "name": "feature_2",
                        "label": "Характеристика 2",
                        "default": "Голосовой ассистент",
                    },
                    {
                        "name": "feature_3",
                        "label": "Характеристика 3",
                        "default": "Bluetooth 5.0",
                    },
                    {
                        "name": "feature_4",
                        "label": "Характеристика 4",
                        "default": "Автономия 12 часов",
                    },
                    {
                        "name": "feature_5",
                        "label": "Характеристика 5",
                        "default": "Водозащита IPX4",
                    },
                ]
            ),
        },
        {
            "name": "WB — Баннер акции",
            "marketplace": "wb",
            "canvas_width": 900,
            "canvas_height": 400,
            "canvas_json": json.dumps(
                {
                    "layers": [
                        {
                            "type": "rectangle",
                            "id": "bg",
                            "x": 0,
                            "y": 0,
                            "width": 900,
                            "height": 400,
                            "zIndex": 0,
                            "fill": "#C0392B",
                            "border_radius": 0,
                            "opacity": 1.0,
                        },
                        {
                            "type": "rectangle",
                            "id": "bg2",
                            "x": 450,
                            "y": 0,
                            "width": 450,
                            "height": 400,
                            "zIndex": 1,
                            "fill": "#922B21",
                            "border_radius": 0,
                            "opacity": 0.8,
                        },
                        {
                            "type": "image",
                            "id": "photo",
                            "x": 500,
                            "y": 20,
                            "width": 380,
                            "height": 360,
                            "zIndex": 2,
                            "src": "{{image_url}}",
                            "fit": "contain",
                            "border_radius": 0,
                        },
                        {
                            "type": "text",
                            "id": "promo_title",
                            "x": 20,
                            "y": 40,
                            "width": 460,
                            "height": 80,
                            "zIndex": 3,
                            "text": "{{promo_title}}",
                            "font_family": "Roboto",
                            "font_size": 42,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#FFFFFF",
                            "align": "left",
                            "max_lines": 2,
                            "line_height": 1.1,
                        },
                        {
                            "type": "text",
                            "id": "promo_subtitle",
                            "x": 20,
                            "y": 160,
                            "width": 460,
                            "height": 60,
                            "zIndex": 3,
                            "text": "{{promo_subtitle}}",
                            "font_family": "Roboto",
                            "font_size": 24,
                            "font_bold": False,
                            "font_italic": False,
                            "color": "#FFD32A",
                            "align": "left",
                            "max_lines": 2,
                            "line_height": 1.2,
                        },
                        {
                            "type": "text",
                            "id": "price",
                            "x": 20,
                            "y": 280,
                            "width": 300,
                            "height": 70,
                            "zIndex": 3,
                            "text": "от {{price}} ₽",
                            "font_family": "Roboto",
                            "font_size": 52,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#FFFFFF",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                    ]
                }
            ),
            "variables": json.dumps(
                [
                    {
                        "name": "promo_title",
                        "label": "Заголовок акции",
                        "default": "Летняя распродажа",
                    },
                    {
                        "name": "promo_subtitle",
                        "label": "Подзаголовок",
                        "default": "Скидки до 70% на все товары",
                    },
                    {"name": "price", "label": "Цена от", "default": "999"},
                    {"name": "image_url", "label": "Фото товара", "default": ""},
                ]
            ),
        },
        {
            "name": "Квадратная карточка",
            "marketplace": "universal",
            "canvas_width": 800,
            "canvas_height": 800,
            "canvas_json": json.dumps(
                {
                    "layers": [
                        {
                            "type": "image",
                            "id": "photo",
                            "x": 0,
                            "y": 0,
                            "width": 800,
                            "height": 800,
                            "zIndex": 0,
                            "src": "{{image_url}}",
                            "fit": "cover",
                            "border_radius": 0,
                        },
                        {
                            "type": "rectangle",
                            "id": "bottom_overlay",
                            "x": 0,
                            "y": 620,
                            "width": 800,
                            "height": 180,
                            "zIndex": 1,
                            "fill": "#1A1A2E",
                            "border_radius": 0,
                            "opacity": 0.85,
                        },
                        {
                            "type": "text",
                            "id": "title",
                            "x": 20,
                            "y": 640,
                            "width": 760,
                            "height": 80,
                            "zIndex": 2,
                            "text": "{{title}}",
                            "font_family": "Roboto",
                            "font_size": 32,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#FFFFFF",
                            "align": "left",
                            "max_lines": 2,
                            "line_height": 1.2,
                        },
                        {
                            "type": "text",
                            "id": "price",
                            "x": 20,
                            "y": 740,
                            "width": 300,
                            "height": 50,
                            "zIndex": 2,
                            "text": "{{price}} ₽",
                            "font_family": "Roboto",
                            "font_size": 38,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#FFD32A",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                    ]
                }
            ),
            "variables": json.dumps(
                [
                    {
                        "name": "title",
                        "label": "Название товара",
                        "default": "Стильные кеды",
                    },
                    {"name": "price", "label": "Цена", "default": "2 990"},
                    {"name": "image_url", "label": "Фото товара", "default": ""},
                ]
            ),
        },
        # ── Ozon — Основная карточка ─────────────────────────────────────
        {
            "name": "Ozon — Основная карточка",
            "marketplace": "ozon",
            "canvas_width": 1000,
            "canvas_height": 1000,
            "canvas_json": json.dumps(
                {
                    "layers": [
                        {
                            "type": "rectangle",
                            "id": "bg",
                            "x": 0,
                            "y": 0,
                            "width": 1000,
                            "height": 1000,
                            "zIndex": 0,
                            "fill": "#FFFFFF",
                            "border_radius": 0,
                            "opacity": 1.0,
                        },
                        {
                            "type": "rectangle",
                            "id": "photo_zone",
                            "x": 60,
                            "y": 60,
                            "width": 880,
                            "height": 620,
                            "zIndex": 1,
                            "fill": "#F0F4F8",
                            "border_radius": 12,
                            "opacity": 1.0,
                        },
                        {
                            "type": "image",
                            "id": "photo",
                            "x": 60,
                            "y": 60,
                            "width": 880,
                            "height": 620,
                            "zIndex": 2,
                            "src": "{{image_url}}",
                            "fit": "contain",
                            "border_radius": 12,
                        },
                        {
                            "type": "rectangle",
                            "id": "accent_bar",
                            "x": 0,
                            "y": 720,
                            "width": 6,
                            "height": 220,
                            "zIndex": 3,
                            "fill": "#005BFF",
                            "border_radius": 0,
                            "opacity": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "brand",
                            "x": 28,
                            "y": 730,
                            "width": 960,
                            "height": 40,
                            "zIndex": 3,
                            "text": "{{brand}}",
                            "font_family": "Roboto",
                            "font_size": 22,
                            "font_bold": False,
                            "font_italic": False,
                            "color": "#005BFF",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "title",
                            "x": 28,
                            "y": 775,
                            "width": 960,
                            "height": 80,
                            "zIndex": 3,
                            "text": "{{title}}",
                            "font_family": "Roboto",
                            "font_size": 30,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#1A1A1A",
                            "align": "left",
                            "max_lines": 2,
                            "line_height": 1.25,
                        },
                        {
                            "type": "text",
                            "id": "price",
                            "x": 28,
                            "y": 880,
                            "width": 400,
                            "height": 60,
                            "zIndex": 3,
                            "text": "{{price}} ₽",
                            "font_family": "Roboto",
                            "font_size": 46,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#005BFF",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "badge",
                            "id": "discount",
                            "x": 28,
                            "y": 60,
                            "width": 120,
                            "height": 50,
                            "zIndex": 4,
                            "badge_type": "discount",
                            "value": "{{discount}}",
                            "bg_color": "#EB4C42",
                            "text_color": "#FFFFFF",
                            "border_radius": 10,
                        },
                    ]
                }
            ),
            "variables": json.dumps(
                [
                    {"name": "brand", "label": "Бренд", "default": "Samsung"},
                    {
                        "name": "title",
                        "label": "Название товара",
                        "default": "Смартфон Galaxy A54 5G 256 ГБ",
                    },
                    {"name": "price", "label": "Цена", "default": "32 990"},
                    {"name": "discount", "label": "Скидка", "default": "-20%"},
                    {"name": "image_url", "label": "Фото товара (URL)", "default": ""},
                ]
            ),
        },
        # ── Ozon — Преимущества ──────────────────────────────────────────
        {
            "name": "Ozon — Преимущества",
            "marketplace": "ozon",
            "canvas_width": 1000,
            "canvas_height": 1000,
            "canvas_json": json.dumps(
                {
                    "layers": [
                        {
                            "type": "rectangle",
                            "id": "bg",
                            "x": 0,
                            "y": 0,
                            "width": 1000,
                            "height": 1000,
                            "zIndex": 0,
                            "fill": "#F7F8FC",
                            "border_radius": 0,
                            "opacity": 1.0,
                        },
                        {
                            "type": "rectangle",
                            "id": "header",
                            "x": 0,
                            "y": 0,
                            "width": 1000,
                            "height": 160,
                            "zIndex": 1,
                            "fill": "#005BFF",
                            "border_radius": 0,
                            "opacity": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "brand",
                            "x": 40,
                            "y": 30,
                            "width": 920,
                            "height": 50,
                            "zIndex": 2,
                            "text": "{{brand}}",
                            "font_family": "Roboto",
                            "font_size": 28,
                            "font_bold": False,
                            "font_italic": False,
                            "color": "rgba(255,255,255,0.75)",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "title",
                            "x": 40,
                            "y": 80,
                            "width": 920,
                            "height": 60,
                            "zIndex": 2,
                            "text": "{{title}}",
                            "font_family": "Roboto",
                            "font_size": 32,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#FFFFFF",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "rectangle",
                            "id": "f1_bg",
                            "x": 40,
                            "y": 185,
                            "width": 440,
                            "height": 130,
                            "zIndex": 2,
                            "fill": "#FFFFFF",
                            "border_radius": 12,
                            "opacity": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "feature_1_icon",
                            "x": 60,
                            "y": 202,
                            "width": 60,
                            "height": 60,
                            "zIndex": 3,
                            "text": "✓",
                            "font_family": "Roboto",
                            "font_size": 36,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#005BFF",
                            "align": "center",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "feature_1",
                            "x": 130,
                            "y": 205,
                            "width": 330,
                            "height": 80,
                            "zIndex": 3,
                            "text": "{{feature_1}}",
                            "font_family": "Roboto",
                            "font_size": 22,
                            "font_bold": False,
                            "font_italic": False,
                            "color": "#2D3436",
                            "align": "left",
                            "max_lines": 2,
                            "line_height": 1.3,
                        },
                        {
                            "type": "rectangle",
                            "id": "f2_bg",
                            "x": 520,
                            "y": 185,
                            "width": 440,
                            "height": 130,
                            "zIndex": 2,
                            "fill": "#FFFFFF",
                            "border_radius": 12,
                            "opacity": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "feature_2_icon",
                            "x": 540,
                            "y": 202,
                            "width": 60,
                            "height": 60,
                            "zIndex": 3,
                            "text": "✓",
                            "font_family": "Roboto",
                            "font_size": 36,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#005BFF",
                            "align": "center",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "feature_2",
                            "x": 610,
                            "y": 205,
                            "width": 330,
                            "height": 80,
                            "zIndex": 3,
                            "text": "{{feature_2}}",
                            "font_family": "Roboto",
                            "font_size": 22,
                            "font_bold": False,
                            "font_italic": False,
                            "color": "#2D3436",
                            "align": "left",
                            "max_lines": 2,
                            "line_height": 1.3,
                        },
                        {
                            "type": "rectangle",
                            "id": "f3_bg",
                            "x": 40,
                            "y": 340,
                            "width": 440,
                            "height": 130,
                            "zIndex": 2,
                            "fill": "#FFFFFF",
                            "border_radius": 12,
                            "opacity": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "feature_3_icon",
                            "x": 60,
                            "y": 357,
                            "width": 60,
                            "height": 60,
                            "zIndex": 3,
                            "text": "✓",
                            "font_family": "Roboto",
                            "font_size": 36,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#005BFF",
                            "align": "center",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "feature_3",
                            "x": 130,
                            "y": 360,
                            "width": 330,
                            "height": 80,
                            "zIndex": 3,
                            "text": "{{feature_3}}",
                            "font_family": "Roboto",
                            "font_size": 22,
                            "font_bold": False,
                            "font_italic": False,
                            "color": "#2D3436",
                            "align": "left",
                            "max_lines": 2,
                            "line_height": 1.3,
                        },
                        {
                            "type": "rectangle",
                            "id": "f4_bg",
                            "x": 520,
                            "y": 340,
                            "width": 440,
                            "height": 130,
                            "zIndex": 2,
                            "fill": "#FFFFFF",
                            "border_radius": 12,
                            "opacity": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "feature_4_icon",
                            "x": 540,
                            "y": 357,
                            "width": 60,
                            "height": 60,
                            "zIndex": 3,
                            "text": "✓",
                            "font_family": "Roboto",
                            "font_size": 36,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#005BFF",
                            "align": "center",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                        {
                            "type": "text",
                            "id": "feature_4",
                            "x": 610,
                            "y": 360,
                            "width": 330,
                            "height": 80,
                            "zIndex": 3,
                            "text": "{{feature_4}}",
                            "font_family": "Roboto",
                            "font_size": 22,
                            "font_bold": False,
                            "font_italic": False,
                            "color": "#2D3436",
                            "align": "left",
                            "max_lines": 2,
                            "line_height": 1.3,
                        },
                        {
                            "type": "rectangle",
                            "id": "photo_zone",
                            "x": 40,
                            "y": 500,
                            "width": 920,
                            "height": 380,
                            "zIndex": 2,
                            "fill": "#FFFFFF",
                            "border_radius": 12,
                            "opacity": 1.0,
                        },
                        {
                            "type": "image",
                            "id": "photo",
                            "x": 40,
                            "y": 500,
                            "width": 920,
                            "height": 380,
                            "zIndex": 3,
                            "src": "{{image_url}}",
                            "fit": "contain",
                            "border_radius": 12,
                        },
                        {
                            "type": "text",
                            "id": "price",
                            "x": 40,
                            "y": 908,
                            "width": 400,
                            "height": 60,
                            "zIndex": 3,
                            "text": "{{price}} ₽",
                            "font_family": "Roboto",
                            "font_size": 44,
                            "font_bold": True,
                            "font_italic": False,
                            "color": "#005BFF",
                            "align": "left",
                            "max_lines": 1,
                            "line_height": 1.0,
                        },
                    ]
                }
            ),
            "variables": json.dumps(
                [
                    {"name": "brand", "label": "Бренд", "default": "Xiaomi"},
                    {
                        "name": "title",
                        "label": "Название",
                        "default": "Робот-пылесос Mi Robot Vacuum",
                    },
                    {
                        "name": "feature_1",
                        "label": "Преимущество 1",
                        "default": "Навигация лазером",
                    },
                    {
                        "name": "feature_2",
                        "label": "Преимущество 2",
                        "default": "3000 Pa всасывание",
                    },
                    {
                        "name": "feature_3",
                        "label": "Преимущество 3",
                        "default": "Моет полы",
                    },
                    {
                        "name": "feature_4",
                        "label": "Преимущество 4",
                        "default": "Работает 3 часа",
                    },
                    {"name": "price", "label": "Цена", "default": "24 990"},
                    {"name": "image_url", "label": "Фото товара (URL)", "default": ""},
                ]
            ),
        },
    ]

    for tdata in templates_data:
        t = Template(
            uid=str(uuid.uuid4()),
            user_id=user.id,
            name=tdata["name"],
            marketplace=tdata["marketplace"],
            canvas_width=tdata["canvas_width"],
            canvas_height=tdata["canvas_height"],
            canvas_json=tdata["canvas_json"],
            variables=tdata["variables"],
            is_default=True,
        )
        session.add(t)
    await session.commit()

    # Generate previews for all seeded templates
    result = await session.execute(
        select(Template).where(Template.user_id == user.id, Template.is_default == True)  # noqa: E712
    )
    for tmpl in result.scalars().all():
        await _make_preview(session, tmpl)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Create storage dirs
    for folder in ["templates", "generated", "uploads"]:
        (Path(settings.storage_path) / folder).mkdir(parents=True, exist_ok=True)

    # Create fonts dir
    Path(settings.fonts_path).mkdir(parents=True, exist_ok=True)

    # Create static dir
    Path("static").mkdir(exist_ok=True)

    # Seed demo data
    async with async_session_maker() as session:
        with suppress(Exception):
            await create_demo_user_if_not_exists(session)

    logger.info("kartochka_startup complete")
    yield
    logger.info("kartochka_shutdown complete")


app = FastAPI(title="Карточка API", version="0.1.0", lifespan=lifespan)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


@app.middleware("http")
async def prometheus_http_middleware(request: Request, call_next: Any) -> Any:
    response = await call_next(request)
    # Normalise path: strip query string, collapse dynamic segments to avoid high cardinality
    path = request.url.path
    http_requests_total.labels(
        method=request.method,
        endpoint=path,
        status_code=str(response.status_code),
    ).inc()
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "code": "HTTP_ERROR",
            "message": str(detail),
            "details": None,
        },
    )


def _make_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable objects to strings."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list | tuple):
        return [_make_serializable(v) for v in obj]
    elif isinstance(obj, str | int | float | bool | type(None)):
        return obj
    else:
        return str(obj)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "code": "VALIDATION_ERROR",
            "message": "Ошибка валидации данных",
            "details": _make_serializable(exc.errors()),
        },
    )


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Liveness + readiness probe: checks DB connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        return JSONResponse({"status": "ok", "db": "ok"})
    except Exception:
        logger.exception("health_check_failed")
        return JSONResponse({"status": "error", "db": "unavailable"}, status_code=503)


@app.get("/metrics")
async def metrics(db: AsyncSession = Depends(get_db)) -> PlainTextResponse:
    """Prometheus metrics endpoint."""
    from datetime import datetime, timedelta

    from sqlalchemy import func

    try:
        total = await db.scalar(select(func.count()).select_from(User))
        registered_users_total.set(total or 0)

        cutoff = datetime.now(UTC) - timedelta(days=30)
        mau = await db.scalar(
            select(func.count()).select_from(User).where(User.last_active_at >= cutoff)
        )
        active_users_30d.set(mau or 0)
    except Exception:
        logger.exception("metrics_user_count_failed")

    data = generate_latest()
    return PlainTextResponse(data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


# Mount static files and storage
static_path = Path("static")
storage_path_dir = Path(settings.storage_path)
static_path.mkdir(exist_ok=True)
storage_path_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/storage", StaticFiles(directory=settings.storage_path), name="storage")

# Include routers
app.include_router(auth.router)
app.include_router(templates.router)
app.include_router(generations.router)
app.include_router(uploads.router)
app.include_router(pages.router)
