from datetime import datetime

from pydantic import BaseModel


class GenerationCreate(BaseModel):
    template_uid: str
    input_data: dict[str, str] = {}
    output_format: str = "png"
    output_width: int | None = None
    output_height: int | None = None


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
