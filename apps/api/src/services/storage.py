"""TenantStorage — replaces src/paths.py for multi-tenant file operations.

Uses Supabase Storage for file uploads (resumes, cookies) and
PostgreSQL for structured data (replaces CSV/JSON file I/O).
"""

import uuid

from supabase import create_client

from ..config import get_settings

RESUMES_BUCKET = "resumes"
COOKIES_BUCKET = "cookies"


class TenantStorage:
    """Per-user file storage backed by Supabase Storage buckets."""

    def __init__(self, user_id: uuid.UUID):
        self.user_id = user_id
        settings = get_settings()
        self._client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    def _user_path(self, bucket: str, filename: str) -> str:
        """Namespace files by user_id to enforce tenant isolation."""
        return f"{self.user_id}/{filename}"

    async def upload_resume(self, filename: str, content: bytes) -> str:
        """Upload a resume PDF. Returns the storage path."""
        path = self._user_path(RESUMES_BUCKET, filename)
        self._client.storage.from_(RESUMES_BUCKET).upload(
            path, content, file_options={"content-type": "application/pdf", "upsert": "true"}
        )
        return path

    async def download_resume(self, storage_path: str) -> bytes:
        """Download a resume PDF by its storage path."""
        return self._client.storage.from_(RESUMES_BUCKET).download(storage_path)

    async def upload_cookies(self, filename: str, content: bytes) -> str:
        """Upload LinkedIn cookies file."""
        path = self._user_path(COOKIES_BUCKET, filename)
        self._client.storage.from_(COOKIES_BUCKET).upload(
            path, content, file_options={"content-type": "text/plain", "upsert": "true"}
        )
        return path

    async def download_cookies(self, storage_path: str) -> bytes:
        """Download cookies file."""
        return self._client.storage.from_(COOKIES_BUCKET).download(storage_path)

    async def delete_file(self, storage_path: str, bucket: str = RESUMES_BUCKET) -> None:
        """Delete a file from storage."""
        self._client.storage.from_(bucket).remove([storage_path])

    async def get_signed_url(self, storage_path: str, bucket: str = RESUMES_BUCKET, expires_in: int = 3600) -> str:
        """Get a temporary signed URL for a stored file."""
        result = self._client.storage.from_(bucket).create_signed_url(storage_path, expires_in)
        return result["signedURL"]
