"""Search configs router — CRUD for job search parameters."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models.search_config import SearchConfig
from ..models.user import User
from ..schemas.search import SearchConfigCreate, SearchConfigResponse, SearchConfigUpdate, make_job_title_clean

router = APIRouter()


@router.get("/", response_model=list[SearchConfigResponse])
async def list_search_configs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SearchConfig)
        .where(SearchConfig.user_id == user.id)
        .order_by(SearchConfig.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=SearchConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_search_config(
    body: SearchConfigCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    config = SearchConfig(
        user_id=user.id,
        job_title=body.job_title,
        job_title_clean=make_job_title_clean(body.job_title),
        salary_min=body.salary_min,
        salary_max=body.salary_max,
        job_type=body.job_type,
        search_type=body.search_type,
        work_geo_codes=body.work_geo_codes,
        remote_filter=body.remote_filter,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.get("/{config_id}", response_model=SearchConfigResponse)
async def get_search_config(
    config_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SearchConfig).where(SearchConfig.id == config_id, SearchConfig.user_id == user.id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Search config not found")
    return config


@router.patch("/{config_id}", response_model=SearchConfigResponse)
async def update_search_config(
    config_id: uuid.UUID,
    body: SearchConfigUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SearchConfig).where(SearchConfig.id == config_id, SearchConfig.user_id == user.id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Search config not found")

    update_data = body.model_dump(exclude_unset=True)
    if "job_title" in update_data:
        update_data["job_title_clean"] = make_job_title_clean(update_data["job_title"])
    for key, value in update_data.items():
        setattr(config, key, value)

    await db.commit()
    await db.refresh(config)
    return config


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search_config(
    config_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SearchConfig).where(SearchConfig.id == config_id, SearchConfig.user_id == user.id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Search config not found")
    await db.delete(config)
    await db.commit()
