"""Insights router — JD insight results."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models.insight import JDInsight
from ..models.user import User
from ..schemas.alignment import JDInsightResponse

router = APIRouter()


@router.get("/", response_model=list[JDInsightResponse])
async def list_insights(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JDInsight).where(JDInsight.user_id == user.id).order_by(JDInsight.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/{insight_id}", response_model=JDInsightResponse)
async def get_insight(
    insight_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JDInsight).where(JDInsight.id == insight_id, JDInsight.user_id == user.id)
    )
    insight = result.scalar_one_or_none()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    return insight
