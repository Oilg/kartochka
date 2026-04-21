from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kartochka.database import Base

if TYPE_CHECKING:
    from kartochka.models.catalog_batch import CatalogBatch
    from kartochka.models.generation import Generation


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(36), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    catalog_batch_id: Mapped[int] = mapped_column(
        ForeignKey("catalog_batches.id"), index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    price: Mapped[str | None] = mapped_column(String(50), nullable=True)
    old_price: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discount: Mapped[str | None] = mapped_column(String(20), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_fields: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_id: Mapped[int | None] = mapped_column(
        ForeignKey("generations.id", ondelete="SET NULL"), nullable=True
    )
    generation_status: Mapped[str] = mapped_column(String(20), default="pending")
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    batch: Mapped[CatalogBatch] = relationship(back_populates="items")
    generation: Mapped[Generation | None] = relationship()

    __table_args__ = (Index("ix_catalog_items_status", "generation_status"),)
