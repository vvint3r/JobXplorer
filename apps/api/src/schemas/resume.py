"""Resume request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ResumeCreate(BaseModel):
    name: str
    is_default: bool = False


class ResumeResponse(BaseModel):
    id: uuid.UUID
    name: str
    pdf_storage_path: str | None
    components_json: dict | None
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeListResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_default: bool
    components_json: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeDetailResponse(ResumeResponse):
    resume_text: str | None

    model_config = {"from_attributes": True}
