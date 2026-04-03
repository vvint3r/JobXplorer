"""Resumes router — upload, parse, CRUD."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models.resume import Resume
from ..models.user import User
from ..schemas.resume import ResumeCreate, ResumeListResponse, ResumeResponse
from ..services.storage import TenantStorage

router = APIRouter()


@router.get("/", response_model=list[ResumeListResponse])
async def list_resumes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.user_id == user.id).order_by(Resume.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    name: str,
    is_default: bool = False,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a resume PDF, store in Supabase Storage, and parse components."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    content = await file.read()
    storage = TenantStorage(user.id)
    storage_path = await storage.upload_resume(file.filename, content)

    # If setting as default, unset other defaults
    if is_default:
        result = await db.execute(
            select(Resume).where(Resume.user_id == user.id, Resume.is_default == True)
        )
        for existing in result.scalars().all():
            existing.is_default = False

    resume = Resume(
        user_id=user.id,
        name=name,
        pdf_storage_path=storage_path,
        is_default=is_default,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    # Trigger async PDF parsing
    from ..tasks.resume_parse import parse_resume_task
    parse_resume_task.delay(str(resume.id), str(user.id))

    return resume


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    if resume.pdf_storage_path:
        storage = TenantStorage(user.id)
        await storage.delete_file(resume.pdf_storage_path)

    await db.delete(resume)
    await db.commit()
