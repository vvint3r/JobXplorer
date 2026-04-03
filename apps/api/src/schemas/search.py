"""Search config request/response schemas."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class SearchConfigCreate(BaseModel):
    job_title: str
    salary_min: int | None = None
    salary_max: int | None = None
    job_type: str | None = None
    search_type: str | None = "exact"
    work_geo_codes: list[str] | None = None
    remote_filter: str | None = None

    @field_validator("job_title")
    @classmethod
    def clean_job_title(cls, v: str) -> str:
        return v.strip()


class SearchConfigUpdate(BaseModel):
    job_title: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    job_type: str | None = None
    search_type: str | None = None
    work_geo_codes: list[str] | None = None
    remote_filter: str | None = None
    is_active: bool | None = None


class SearchConfigResponse(BaseModel):
    id: uuid.UUID
    job_title: str
    job_title_clean: str
    salary_min: int | None
    salary_max: int | None
    job_type: str | None
    search_type: str | None
    work_geo_codes: list[str] | None
    remote_filter: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


def make_job_title_clean(title: str) -> str:
    """Convert 'Marketing Analytics' → 'marketing_analytics'."""
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
