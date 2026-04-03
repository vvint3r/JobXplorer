"""Alignment and insights schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class AlignmentScoreResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    resume_id: uuid.UUID
    alignment_score: float
    alignment_grade: str
    matched_inputs: dict | None
    gaps: dict | None
    scored_at: datetime

    model_config = {"from_attributes": True}


class JDInsightResponse(BaseModel):
    id: uuid.UUID
    search_config_id: uuid.UUID
    total_jobs_analysed: int
    categorised_phrases: dict | None
    summary: dict | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class InputIndexResponse(BaseModel):
    id: uuid.UUID
    master_job_title: str
    inputs: dict
    index_metadata: dict | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
