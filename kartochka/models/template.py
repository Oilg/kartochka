from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kartochka.database import Base

if TYPE_CHECKING:
    from kartochka.models.generation import Generation
    from kartochka.models.user import User


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uid: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    marketplace: Mapped[str] = mapped_column(
        String(50), default="universal"
    )  # wb, ozon, universal
    canvas_json: Mapped[str] = mapped_column(Text, default="{}")
    variables: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    canvas_width: Mapped[int] = mapped_column(Integer, default=900)
    canvas_height: Mapped[int] = mapped_column(Integer, default=1200)
    preview_url: Mapped[str | None] = mapped_column(String(500))
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="templates")
    generations: Mapped[list[Generation]] = relationship(back_populates="template")
