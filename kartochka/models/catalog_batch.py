from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kartochka.database import Base

if TYPE_CHECKING:
    from kartochka.models.catalog_item import CatalogItem
    from kartochka.models.template import Template
    from kartochka.models.user import User


class CatalogBatch(Base):
    __tablename__ = "catalog_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(36), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"))
    name: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(20))
    marketplace: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    processed_items: Mapped[int] = mapped_column(Integer, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, default=0)
    output_format: Mapped[str] = mapped_column(String(10), default="png")
    column_mapping: Mapped[str | None] = mapped_column(Text, nullable=True)
    zip_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publish_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publish_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    published_items: Mapped[int] = mapped_column(Integer, default=0)
    publish_failed_items: Mapped[int] = mapped_column(Integer, default=0)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    items: Mapped[list[CatalogItem]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
    template: Mapped[Template] = relationship()
    user: Mapped[User] = relationship(back_populates="catalog_batches")

    __table_args__ = (Index("ix_catalog_batches_status", "status"),)
