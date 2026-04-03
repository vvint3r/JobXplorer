"""Job request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class JobResponse(BaseModel):
    id: uuid.UUID
    job_title: str
    company_title: str | None
    job_url: str
    application_url: str | None
    salary_range: str | None
    location: str | None
    remote_status: str | None
    days_since_posted: int | None
    date_extracted: datetime | None
    application_status: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobDetailResponse(JobResponse):
    description: str | None
    search_config_id: uuid.UUID | None
    alignment_score: float | None = None
    alignment_grade: str | None = None


class JobListParams(BaseModel):
    search_config_id: uuid.UUID | None = None
    company: str | None = None
    min_score: float | None = None
    sort_by: str = "date_extracted"
    sort_order: str = "desc"
    page: int = 1
    per_page: int = 50
