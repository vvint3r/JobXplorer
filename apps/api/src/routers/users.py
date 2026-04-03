"""Users router — profile management, secrets, cookies."""

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models.user import User
from ..schemas.user import OpenAIKeyUpdate, UserProfileResponse, UserProfileUpdate
from ..services.encryption import encrypt_value
from ..services.storage import TenantStorage

router = APIRouter()


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return user


@router.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    body: UserProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user profile (personal info, application defaults, etc.)."""
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/openai-key")
async def update_openai_key(
    body: OpenAIKeyUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store encrypted OpenAI API key."""
    user.openai_api_key_encrypted = encrypt_value(body.api_key)
    await db.commit()
    return {"status": "ok"}


@router.delete("/openai-key")
async def delete_openai_key(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove stored OpenAI API key."""
    user.openai_api_key_encrypted = None
    await db.commit()
    return {"status": "ok"}


@router.post("/linkedin-cookies")
async def upload_linkedin_cookies(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload LinkedIn cookies file to encrypted storage."""
    content = await file.read()
    storage = TenantStorage(user.id)
    path = await storage.upload_cookies("linkedin_cookies.txt", content)
    user.linkedin_cookies_storage_path = path
    await db.commit()
    return {"status": "ok", "path": path}


@router.delete("/linkedin-cookies")
async def delete_linkedin_cookies(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete stored LinkedIn cookies."""
    if user.linkedin_cookies_storage_path:
        storage = TenantStorage(user.id)
        await storage.delete_file(user.linkedin_cookies_storage_path, bucket="cookies")
        user.linkedin_cookies_storage_path = None
        await db.commit()
    return {"status": "ok"}


@router.get("/linkedin-cookies/status")
async def linkedin_cookies_status(user: User = Depends(get_current_user)):
    """Check if LinkedIn cookies are uploaded."""
    return {
        "uploaded": user.linkedin_cookies_storage_path is not None,
        "path": user.linkedin_cookies_storage_path,
    }
