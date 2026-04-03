"""Integration tests for the /api/v1/users router."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User

PREFIX = "/api/v1/users"


class TestGetProfile:
    async def test_returns_current_user(self, client: AsyncClient, test_user: User):
        resp = await client.get(f"{PREFIX}/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(test_user.id)
        assert data["email"] == test_user.email

    async def test_profile_has_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{PREFIX}/profile")
        data = resp.json()
        for field in ("id", "email", "plan", "created_at"):
            assert field in data, f"Missing field: {field}"

    async def test_plan_defaults_to_free(self, client: AsyncClient):
        resp = await client.get(f"{PREFIX}/profile")
        assert resp.json()["plan"] == "free"


class TestUpdateProfile:
    async def test_update_full_name(self, client: AsyncClient, db: AsyncSession, test_user: User):
        resp = await client.put(f"{PREFIX}/profile", json={"full_name": "Jane Smith"})
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Jane Smith"

    async def test_partial_update_preserves_other_fields(
        self, client: AsyncClient, test_user: User
    ):
        email_before = test_user.email
        await client.put(f"{PREFIX}/profile", json={"full_name": "Updated Name"})

        resp = await client.get(f"{PREFIX}/profile")
        assert resp.json()["email"] == email_before

    async def test_update_personal_info(self, client: AsyncClient):
        body = {"personal_info": {"phone": "555-1234", "city": "Austin"}}
        resp = await client.put(f"{PREFIX}/profile", json=body)
        assert resp.status_code == 200
        assert resp.json()["personal_info"]["phone"] == "555-1234"

    async def test_update_work_authorization(self, client: AsyncClient):
        body = {"work_authorization": {"us_citizen": True, "requires_sponsorship": False}}
        resp = await client.put(f"{PREFIX}/profile", json=body)
        assert resp.status_code == 200
        assert resp.json()["work_authorization"]["us_citizen"] is True


class TestLinkedInCookiesStatus:
    async def test_not_uploaded_by_default(self, client: AsyncClient):
        resp = await client.get(f"{PREFIX}/linkedin-cookies/status")
        assert resp.status_code == 200
        assert resp.json()["uploaded"] is False
        assert resp.json()["path"] is None
