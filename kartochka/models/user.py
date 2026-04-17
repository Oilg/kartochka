from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kartochka.database import Base

if TYPE_CHECKING:
    from kartochka.models.generation import Generation
    from kartochka.models.template import Template


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    api_key: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    plan: Mapped[str] = mapped_column(String(20), default="free")
    free_generations_used_today: Mapped[int] = mapped_column(Integer, default=0)
    generations_reset_date: Mapped[date | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now()
    )

    templates: Mapped[list[Template]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    generations: Mapped[list[Generation]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
