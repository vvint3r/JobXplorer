"""User request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserProfileUpdate(BaseModel):
    full_name: str | None = None
    personal_info: dict | None = None
    application_info: dict | None = None
    work_authorization: dict | None = None
    voluntary_disclosures: dict | None = None
    custom_answers: dict | None = None
    search_preferences: dict | None = None
    supplementary_terms: list | None = None


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    plan: str
    personal_info: dict | None
    application_info: dict | None
    work_authorization: dict | None
    voluntary_disclosures: dict | None
    custom_answers: dict | None
    search_preferences: dict | None
    supplementary_terms: list | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OpenAIKeyUpdate(BaseModel):
    api_key: str
