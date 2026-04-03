"""Pydantic schemas for application logs."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ApplicationLogCreate(BaseModel):
    """Request body for logging an application attempt."""

    job_id: uuid.UUID
    board_type: str
    method: str = "extension_auto_fill"
    status: str  # filled, submitted, failed, partial
    fields_filled: int | None = None
    fields_total: int | None = None
    error_message: str | None = None
    optimized_resume_id: uuid.UUID | None = None


class ApplicationLogResponse(BaseModel):
    """Response for a single application log entry."""

    id: uuid.UUID
    job_id: uuid.UUID
    board_type: str
    method: str
    status: str
    fields_filled: int | None
    fields_total: int | None
    error_message: str | None
    optimized_resume_id: uuid.UUID | None
    applied_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationStatsResponse(BaseModel):
    """Aggregate application statistics."""

    total: int
    filled: int
    submitted: int
    failed: int
    partial: int
    by_board: dict[str, int]
    by_method: dict[str, int]


class TimelineEntry(BaseModel):
    """A single day's application count."""

    date: str  # YYYY-MM-DD
    count: int


class ApplicationTimelineResponse(BaseModel):
    """Time-series of application counts for charting."""

    period: str
    entries: list[TimelineEntry]
