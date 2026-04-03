"""Pipeline run request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class PipelineRunCreate(BaseModel):
    search_config_id: uuid.UUID
    pipeline_type: str = "full"  # full, search, insights, alignment, optimize


class PipelineRunResponse(BaseModel):
    id: uuid.UUID
    search_config_id: uuid.UUID | None
    pipeline_type: str
    status: str
    current_stage: str | None
    progress: float
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
