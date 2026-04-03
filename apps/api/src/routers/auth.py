"""Auth router — user session verification."""

from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..models.user import User
from ..schemas.user import UserProfileResponse

router = APIRouter()


@router.get("/me", response_model=UserProfileResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return user
