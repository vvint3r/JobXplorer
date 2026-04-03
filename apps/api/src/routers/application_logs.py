"""Application logs router — tracks job application attempts from the extension."""

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql import DATE
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models.application_log import ApplicationLog
from ..models.job import Job
from ..models.user import User
from ..schemas.application_log import (
    ApplicationLogCreate,
    ApplicationLogResponse,
    ApplicationStatsResponse,
    ApplicationTimelineResponse,
    TimelineEntry,
)


def _period_start(period: str) -> datetime | None:
    """Return UTC datetime for the start of the requested period, or None for all-time."""
    now = datetime.now(UTC)
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return now - timedelta(days=7)
    if period == "month":
        return now - timedelta(days=30)
    if period == "3mo":
        return now - timedelta(days=90)
    if period == "ytd":
        return datetime(now.year, 1, 1, tzinfo=UTC)
    return None  # "all" or unrecognised

router = APIRouter()

VALID_STATUSES = {"filled", "submitted", "failed", "partial"}
VALID_METHODS = {"extension_auto_fill", "manual"}


@router.post("/", response_model=ApplicationLogResponse, status_code=201)
async def log_application(
    body: ApplicationLogCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log an application attempt. Also updates the job's application_status."""
    # Validate
    if body.status not in VALID_STATUSES:
        from fastapi import HTTPException

        raise HTTPException(400, f"Invalid status. Must be one of: {VALID_STATUSES}")
    if body.method not in VALID_METHODS:
        from fastapi import HTTPException

        raise HTTPException(400, f"Invalid method. Must be one of: {VALID_METHODS}")

    # Verify job belongs to user
    result = await db.execute(
        select(Job).where(Job.id == body.job_id, Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        from fastapi import HTTPException

        raise HTTPException(404, "Job not found")

    # Create log entry
    log = ApplicationLog(
        user_id=user.id,
        job_id=body.job_id,
        board_type=body.board_type,
        method=body.method,
        status=body.status,
        fields_filled=body.fields_filled,
        fields_total=body.fields_total,
        error_message=body.error_message,
        optimized_resume_id=body.optimized_resume_id,
    )
    db.add(log)

    # Update job application_status based on the result
    status_map = {
        "submitted": "applied",
        "filled": "interested",
        "failed": "failed",
        "partial": "interested",
    }
    job.application_status = status_map.get(body.status, job.application_status)

    await db.commit()
    await db.refresh(log)
    return log


@router.get("/", response_model=list[ApplicationLogResponse])
async def list_application_logs(
    job_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List application logs, optionally filtered by job or status."""
    query = (
        select(ApplicationLog)
        .where(ApplicationLog.user_id == user.id)
        .order_by(ApplicationLog.applied_at.desc())
    )
    if job_id:
        query = query.where(ApplicationLog.job_id == job_id)
    if status:
        query = query.where(ApplicationLog.status == status)
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/stats", response_model=ApplicationStatsResponse)
async def application_stats(
    period: str = Query("all", description="today|week|month|3mo|ytd|all"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate application statistics for the current user, optionally filtered by period."""
    from_dt = _period_start(period)

    def _base_where(q):
        q = q.where(ApplicationLog.user_id == user.id)
        if from_dt:
            q = q.where(ApplicationLog.applied_at >= from_dt)
        return q

    # Total count
    total_result = await db.execute(
        _base_where(select(func.count()).select_from(ApplicationLog))
    )
    total = total_result.scalar() or 0

    # Count by status
    status_result = await db.execute(
        _base_where(
            select(ApplicationLog.status, func.count()).group_by(ApplicationLog.status)
        )
    )
    status_counts = {row[0]: row[1] for row in status_result.all()}

    # Count by board
    board_result = await db.execute(
        _base_where(
            select(ApplicationLog.board_type, func.count()).group_by(ApplicationLog.board_type)
        )
    )
    by_board = {row[0]: row[1] for row in board_result.all()}

    # Count by method
    method_result = await db.execute(
        _base_where(
            select(ApplicationLog.method, func.count()).group_by(ApplicationLog.method)
        )
    )
    by_method = {row[0]: row[1] for row in method_result.all()}

    return ApplicationStatsResponse(
        total=total,
        filled=status_counts.get("filled", 0),
        submitted=status_counts.get("submitted", 0),
        failed=status_counts.get("failed", 0),
        partial=status_counts.get("partial", 0),
        by_board=by_board,
        by_method=by_method,
    )


@router.get("/timeline", response_model=ApplicationTimelineResponse)
async def application_timeline(
    period: str = Query("month", description="today|week|month|3mo|ytd|all"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return per-day application counts for charting over the selected period."""
    from_dt = _period_start(period)

    q = (
        select(
            cast(ApplicationLog.applied_at, DATE).label("day"),
            func.count().label("cnt"),
        )
        .where(ApplicationLog.user_id == user.id)
        .group_by("day")
        .order_by("day")
    )
    if from_dt:
        q = q.where(ApplicationLog.applied_at >= from_dt)

    result = await db.execute(q)
    rows = result.all()

    entries = [TimelineEntry(date=str(row.day), count=row.cnt) for row in rows]
    return ApplicationTimelineResponse(period=period, entries=entries)
