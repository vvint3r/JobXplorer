"""Optimized resume request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class OptimizedResumeResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    resume_id: uuid.UUID
    method: str
    optimized_json: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OptimizedResumeSummary(BaseModel):
    """Lightweight version without full JSON payload — for list views."""
    id: uuid.UUID
    job_id: uuid.UUID
    resume_id: uuid.UUID
    method: str
    job_title: str | None = None
    company: str | None = None
    alignment_score: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OptimizeJobRequest(BaseModel):
    """Request to optimize resume for a specific job."""
    job_id: uuid.UUID
    resume_id: uuid.UUID | None = None  # defaults to user's default resume


class BulkOptimizeRequest(BaseModel):
    """Request to optimize resumes for multiple jobs (top-N by alignment)."""
    search_config_id: uuid.UUID | None = None
    min_score: float = 50.0
    limit: int = 10
    resume_id: uuid.UUID | None = None
