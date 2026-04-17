from datetime import datetime

from pydantic import BaseModel


class TemplateCreate(BaseModel):
    name: str
    description: str | None = None
    marketplace: str = "universal"
    canvas_json: str = "{}"
    variables: str = "[]"
    canvas_width: int = 900
    canvas_height: int = 1200


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    marketplace: str | None = None
    canvas_json: str | None = None
    variables: str | None = None
    canvas_width: int | None = None
    canvas_height: int | None = None
    preview_url: str | None = None


class TemplateResponse(BaseModel):
    id: int
    uid: str
    name: str
    description: str | None
    marketplace: str
    canvas_json: str
    variables: str
    canvas_width: int
    canvas_height: int
    preview_url: str | None
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    id: int
    uid: str
    name: str
    description: str | None
    marketplace: str
    canvas_width: int
    canvas_height: int
    preview_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
