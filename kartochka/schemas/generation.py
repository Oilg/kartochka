from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GenerationCreate(BaseModel):
    template_uid: str
    input_data: dict[str, str] = {}
    output_format: Literal["png", "jpg", "jpeg", "webp"] = "png"
    output_width: int | None = Field(default=None, ge=1, le=5000)
    output_height: int | None = Field(default=None, ge=1, le=5000)


class GenerationResponse(BaseModel):
    id: int
    uid: str
    template_id: int
    status: str
    output_format: str
    output_width: int | None
    output_height: int | None
    file_path: str | None
    file_size: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
