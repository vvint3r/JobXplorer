"""Jobs router — list, detail, filter, application tracking."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models.alignment import AlignmentScore
from ..models.job import Job
from ..models.optimized_resume import OptimizedResume
from ..models.user import User
from ..schemas.job import JobDetailResponse, JobResponse

router = APIRouter()


@router.get("/", response_model=list[JobResponse])
async def list_jobs(
    search_config_id: uuid.UUID | None = None,
    company: str | None = None,
    sort_by: str = Query("date_extracted", pattern="^(date_extracted|job_title|company_title|created_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Job).where(Job.user_id == user.id)

    if search_config_id:
        query = query.where(Job.search_config_id == search_config_id)
    if company:
        query = query.where(Job.company_title.ilike(f"%{company}%"))

    sort_col = getattr(Job, sort_by, Job.date_extracted)
    query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/count")
async def count_jobs(
    search_config_id: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(func.count(Job.id)).where(Job.user_id == user.id)
    if search_config_id:
        query = query.where(Job.search_config_id == search_config_id)
    result = await db.execute(query)
    return {"count": result.scalar()}


def _normalize_url(url: str) -> str:
    """Strip tracking params and normalize for matching."""
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    # Remove common tracking parameters
    clean_params = {
        k: v for k, v in params.items()
        if not k.startswith("utm_") and k not in ("source", "ref", "fbclid", "gclid")
    }
    clean_query = urlencode(clean_params, doseq=True)
    cleaned = urlunparse(parsed._replace(query=clean_query, fragment=""))
    return cleaned.rstrip("/")


@router.get("/lookup")
async def lookup_job_by_url(
    url: str = Query(..., min_length=5),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lookup a job by URL. Used by the Chrome extension to match pages to known jobs."""
    normalized = _normalize_url(url)

    # Extract domain+path for flexible matching
    from urllib.parse import urlparse

    parsed = urlparse(normalized)
    # Use host + path as match key (ignore query params for broader matches)
    match_key = f"{parsed.netloc}{parsed.path}".rstrip("/")

    result = await db.execute(
        select(Job).where(
            Job.user_id == user.id,
            or_(
                Job.job_url.ilike(f"%{match_key}%"),
                Job.application_url.ilike(f"%{match_key}%"),
            ),
        ).limit(1)
    )
    job = result.scalar_one_or_none()
    if not job:
        return None

    # Check for optimized resume
    opt_result = await db.execute(
        select(OptimizedResume.id)
        .where(OptimizedResume.job_id == job.id)
        .order_by(OptimizedResume.created_at.desc())
        .limit(1)
    )
    opt_id = opt_result.scalar_one_or_none()

    # Get alignment score
    score_result = await db.execute(
        select(AlignmentScore.alignment_score, AlignmentScore.alignment_grade)
        .where(AlignmentScore.job_id == job.id)
        .order_by(AlignmentScore.scored_at.desc())
        .limit(1)
    )
    score = score_result.one_or_none()

    return {
        "id": str(job.id),
        "job_title": job.job_title,
        "company_title": job.company_title,
        "application_url": job.application_url,
        "job_url": job.job_url,
        "alignment_score": score.alignment_score if score else None,
        "alignment_grade": score.alignment_grade if score else None,
        "optimized_resume_id": str(opt_id) if opt_id else None,
        "has_optimized_resume": opt_id is not None,
        "application_status": job.application_status,
    }


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Fetch latest alignment score if available
    score_result = await db.execute(
        select(AlignmentScore)
        .where(AlignmentScore.job_id == job.id)
        .order_by(AlignmentScore.scored_at.desc())
        .limit(1)
    )
    score = score_result.scalar_one_or_none()

    response = JobDetailResponse.model_validate(job)
    if score:
        response.alignment_score = score.alignment_score
        response.alignment_grade = score.alignment_grade
    return response


# ── Application status tracking ──────────────────────────────────────────────


class ApplicationStatusUpdate(BaseModel):
    status: str  # applied, skipped, failed, interested, rejected


@router.patch("/{job_id}/status")
async def update_application_status(
    job_id: uuid.UUID,
    body: ApplicationStatusUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the application status for a job."""
    valid_statuses = {"applied", "skipped", "failed", "interested", "rejected", None}
    if body.status and body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(s for s in valid_statuses if s)}")

    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.application_status = body.status
    await db.commit()
    return {"status": "ok", "job_id": str(job_id), "application_status": body.status}


@router.patch("/bulk-status")
async def bulk_update_application_status(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk update application status for multiple jobs."""
    job_ids = body.get("job_ids", [])
    new_status = body.get("status")
    if not job_ids or not new_status:
        raise HTTPException(status_code=400, detail="job_ids and status are required")

    updated = 0
    for jid in job_ids:
        result = await db.execute(
            select(Job).where(Job.id == uuid.UUID(jid), Job.user_id == user.id)
        )
        job = result.scalar_one_or_none()
        if job:
            job.application_status = new_status
            updated += 1

    await db.commit()
    return {"status": "ok", "updated": updated}
