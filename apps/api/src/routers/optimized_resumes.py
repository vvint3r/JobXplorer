"""Optimized resumes router — list, detail, optimize single/bulk, PDF export."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models.alignment import AlignmentScore
from ..models.job import Job
from ..models.optimized_resume import OptimizedResume
from ..models.resume import Resume
from ..models.user import User
from ..schemas.optimized_resume import (
    BulkOptimizeRequest,
    OptimizedResumeResponse,
    OptimizedResumeSummary,
    OptimizeJobRequest,
)

router = APIRouter()


@router.get("/", response_model=list[OptimizedResumeSummary])
async def list_optimized_resumes(
    search_config_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List optimized resumes with job metadata."""
    query = (
        select(
            OptimizedResume.id,
            OptimizedResume.job_id,
            OptimizedResume.resume_id,
            OptimizedResume.method,
            OptimizedResume.created_at,
            Job.job_title,
            Job.company_title,
        )
        .join(Job, OptimizedResume.job_id == Job.id)
        .where(OptimizedResume.user_id == user.id)
        .order_by(OptimizedResume.created_at.desc())
    )

    if search_config_id:
        query = query.where(Job.search_config_id == search_config_id)

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    rows = result.all()

    # Collect job_ids for alignment scores
    job_ids = [r.job_id for r in rows]
    scores_map: dict[uuid.UUID, float] = {}
    if job_ids:
        score_result = await db.execute(
            select(AlignmentScore.job_id, AlignmentScore.alignment_score)
            .where(AlignmentScore.job_id.in_(job_ids), AlignmentScore.user_id == user.id)
        )
        for s in score_result.all():
            scores_map[s.job_id] = s.alignment_score

    return [
        OptimizedResumeSummary(
            id=r.id,
            job_id=r.job_id,
            resume_id=r.resume_id,
            method=r.method,
            job_title=r.job_title,
            company=r.company_title,
            alignment_score=scores_map.get(r.job_id),
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/count")
async def count_optimized_resumes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func
    result = await db.execute(
        select(func.count(OptimizedResume.id)).where(OptimizedResume.user_id == user.id)
    )
    return {"count": result.scalar()}


@router.get("/{optimized_id}", response_model=OptimizedResumeResponse)
async def get_optimized_resume(
    optimized_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OptimizedResume).where(
            OptimizedResume.id == optimized_id,
            OptimizedResume.user_id == user.id,
        )
    )
    opt = result.scalar_one_or_none()
    if not opt:
        raise HTTPException(status_code=404, detail="Optimized resume not found")
    return opt


@router.get("/{optimized_id}/pdf")
async def download_optimized_resume_pdf(
    optimized_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the optimized resume as a formatted PDF."""
    from ..services.pdf_generator import generate_resume_pdf

    result = await db.execute(
        select(OptimizedResume).where(
            OptimizedResume.id == optimized_id,
            OptimizedResume.user_id == user.id,
        )
    )
    opt = result.scalar_one_or_none()
    if not opt:
        raise HTTPException(status_code=404, detail="Optimized resume not found")

    # Get job info for filename
    job_result = await db.execute(select(Job).where(Job.id == opt.job_id))
    job = job_result.scalar_one_or_none()

    pdf_bytes = generate_resume_pdf(opt.optimized_json)

    # Build filename
    personal = opt.optimized_json.get("personal_info", {})
    name = personal.get("full_name", "Resume").replace(" ", "_")
    company = (job.company_title or "Company").replace(" ", "_") if job else "Company"
    filename = f"{name}_{company}_Optimized.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/job/{job_id}", response_model=OptimizedResumeResponse | None)
async def get_optimized_resume_for_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent optimized resume for a specific job."""
    result = await db.execute(
        select(OptimizedResume)
        .where(OptimizedResume.job_id == job_id, OptimizedResume.user_id == user.id)
        .order_by(OptimizedResume.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.post("/optimize", response_model=OptimizedResumeResponse)
async def optimize_single(
    body: OptimizeJobRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Optimize resume for a single job (synchronous — keyword fallback only)."""
    from ..core.auto_application.resume_optimizer import optimise_resume_for_job
    from ..services.encryption import decrypt_value

    # Load job
    job_result = await db.execute(
        select(Job).where(Job.id == body.job_id, Job.user_id == user.id)
    )
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.description:
        raise HTTPException(status_code=400, detail="Job has no description")

    # Load resume
    if body.resume_id:
        resume_result = await db.execute(
            select(Resume).where(Resume.id == body.resume_id, Resume.user_id == user.id)
        )
    else:
        resume_result = await db.execute(
            select(Resume).where(Resume.user_id == user.id, Resume.is_default.is_(True))
        )
    resume = resume_result.scalar_one_or_none()
    if not resume:
        # Fallback to any resume
        resume_result = await db.execute(
            select(Resume).where(Resume.user_id == user.id).limit(1)
        )
        resume = resume_result.scalar_one_or_none()
    if not resume or not resume.components_json:
        raise HTTPException(status_code=400, detail="No resume with parsed components found")

    # Get OpenAI key
    openai_api_key = None
    if user.openai_api_key_encrypted:
        try:
            openai_api_key = decrypt_value(user.openai_api_key_encrypted)
        except Exception:
            pass  # Will fall back to keyword match

    result = optimise_resume_for_job(
        base_resume=resume.components_json,
        job_title=job.job_title,
        company=job.company_title or "Unknown",
        description=job.description,
        openai_api_key=openai_api_key,
    )

    method = result.get("_optimised_for", {}).get("method", "keyword_match")

    # Upsert
    existing_result = await db.execute(
        select(OptimizedResume).where(
            OptimizedResume.job_id == job.id,
            OptimizedResume.resume_id == resume.id,
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        existing.optimized_json = result
        existing.method = method
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        opt = OptimizedResume(
            id=uuid.uuid4(),
            user_id=user.id,
            job_id=job.id,
            resume_id=resume.id,
            optimized_json=result,
            method=method,
        )
        db.add(opt)
        await db.commit()
        await db.refresh(opt)
        return opt


@router.post("/bulk-optimize", status_code=202)
async def bulk_optimize(
    body: BulkOptimizeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger bulk optimization as a pipeline run (async via Celery)."""
    if not body.search_config_id:
        raise HTTPException(status_code=400, detail="search_config_id is required for bulk optimize")

    from datetime import datetime, timezone

    from ..models.pipeline_run import PipelineRun
    from ..tasks.pipeline_chain import dispatch_pipeline

    run = PipelineRun(
        user_id=user.id,
        search_config_id=body.search_config_id,
        pipeline_type="optimize",
        status="pending",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    task = dispatch_pipeline.delay(str(run.id), str(user.id), "optimize")
    run.celery_task_id = task.id
    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    await db.commit()

    return {"status": "accepted", "run_id": str(run.id), "task_id": task.id}


@router.delete("/{optimized_id}", status_code=204)
async def delete_optimized_resume(
    optimized_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OptimizedResume).where(
            OptimizedResume.id == optimized_id,
            OptimizedResume.user_id == user.id,
        )
    )
    opt = result.scalar_one_or_none()
    if not opt:
        raise HTTPException(status_code=404, detail="Optimized resume not found")
    await db.delete(opt)
    await db.commit()
