"""Pipelines router — trigger and track async pipeline runs."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models.pipeline_run import PipelineRun
from ..models.search_config import SearchConfig
from ..models.user import User
from ..schemas.pipeline import PipelineRunCreate, PipelineRunResponse
from ..tasks.pipeline_chain import dispatch_pipeline

router = APIRouter()


@router.post("/run", response_model=PipelineRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_pipeline(
    body: PipelineRunCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start an async pipeline run."""
    # Verify search config belongs to user
    result = await db.execute(
        select(SearchConfig).where(
            SearchConfig.id == body.search_config_id, SearchConfig.user_id == user.id
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Search config not found")

    # Check for already-running pipeline on same config
    result = await db.execute(
        select(PipelineRun).where(
            PipelineRun.search_config_id == body.search_config_id,
            PipelineRun.status.in_(["pending", "running"]),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A pipeline is already running for this search config")

    run = PipelineRun(
        user_id=user.id,
        search_config_id=body.search_config_id,
        pipeline_type=body.pipeline_type,
        status="pending",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Dispatch Celery task
    task = dispatch_pipeline.delay(str(run.id), str(user.id), body.pipeline_type)
    run.celery_task_id = task.id
    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)

    return run


@router.get("/runs", response_model=list[PipelineRunResponse])
async def list_pipeline_runs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PipelineRun)
        .where(PipelineRun.user_id == user.id)
        .order_by(PipelineRun.created_at.desc())
        .limit(20)
    )
    return result.scalars().all()


@router.get("/runs/{run_id}", response_model=PipelineRunResponse)
async def get_pipeline_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PipelineRun).where(PipelineRun.id == run_id, PipelineRun.user_id == user.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return run


@router.post("/runs/{run_id}/cancel")
async def cancel_pipeline_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PipelineRun).where(PipelineRun.id == run_id, PipelineRun.user_id == user.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    if run.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail="Pipeline is not running")

    if run.celery_task_id:
        from ..celery_app import celery_app
        celery_app.control.revoke(run.celery_task_id, terminate=True)

    run.status = "cancelled"
    run.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "cancelled"}
