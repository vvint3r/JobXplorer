"""Alignment router — scores, input index, and supplementary terms management."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models.alignment import AlignmentScore, InputIndex
from ..models.user import User
from ..schemas.alignment import AlignmentScoreResponse, InputIndexResponse

router = APIRouter()


# ── Schemas for this router ───────────────────────────────────────────────────


class GenerateIndexRequest(BaseModel):
    job_title: str


class SupplementaryTermItem(BaseModel):
    term: str
    proficiency: str = "intermediate"  # entry | intermediate | expert


class SupplementaryTermsUpdate(BaseModel):
    terms: list[SupplementaryTermItem]


# ── Scores ────────────────────────────────────────────────────────────────────


@router.get("/scores", response_model=list[AlignmentScoreResponse])
async def list_alignment_scores(
    search_config_id: uuid.UUID | None = None,
    min_score: float | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(AlignmentScore).where(AlignmentScore.user_id == user.id)
    if min_score is not None:
        query = query.where(AlignmentScore.alignment_score >= min_score)
    query = query.order_by(AlignmentScore.alignment_score.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/scores/{job_id}", response_model=list[AlignmentScoreResponse])
async def get_job_scores(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlignmentScore)
        .where(AlignmentScore.job_id == job_id, AlignmentScore.user_id == user.id)
        .order_by(AlignmentScore.scored_at.desc())
    )
    return result.scalars().all()


# ── Input Index ───────────────────────────────────────────────────────────────


@router.get("/index", response_model=InputIndexResponse | None)
async def get_input_index(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InputIndex)
        .where(InputIndex.user_id == user.id)
        .order_by(InputIndex.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.put("/index", response_model=InputIndexResponse)
async def update_input_index(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually update the input index."""
    result = await db.execute(
        select(InputIndex)
        .where(InputIndex.user_id == user.id)
        .order_by(InputIndex.updated_at.desc())
        .limit(1)
    )
    index = result.scalar_one_or_none()
    if not index:
        raise HTTPException(status_code=404, detail="No input index found. Generate one first.")

    index.inputs = body.get("inputs", index.inputs)
    if "metadata" in body:
        index.index_metadata = body["metadata"]
    await db.commit()
    await db.refresh(index)
    return index


@router.post("/index/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_input_index(
    body: GenerateIndexRequest,
    user: User = Depends(get_current_user),
):
    """Trigger async input index generation via OpenAI.

    Requires an OpenAI API key to be configured in user settings.
    """
    if not user.openai_api_key_encrypted:
        raise HTTPException(
            status_code=400,
            detail="OpenAI API key not configured. Add one in Settings → Integrations.",
        )

    from ..tasks.pipeline_chain import generate_input_index_task

    task = generate_input_index_task.delay(str(user.id), body.job_title)
    return {"status": "accepted", "task_id": task.id, "job_title": body.job_title}


# ── Supplementary Terms ──────────────────────────────────────────────────────


@router.get("/supplementary-terms")
async def get_supplementary_terms(
    user: User = Depends(get_current_user),
):
    """Get the user's supplementary terms for alignment scoring."""
    return {"terms": user.supplementary_terms or []}


@router.put("/supplementary-terms")
async def update_supplementary_terms(
    body: SupplementaryTermsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace the user's supplementary terms list."""
    user.supplementary_terms = [t.model_dump() for t in body.terms]
    await db.commit()
    return {"status": "ok", "count": len(body.terms)}
