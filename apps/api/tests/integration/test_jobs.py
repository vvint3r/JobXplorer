"""Integration tests for the /api/v1/jobs router."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.job import Job
from src.models.user import User

PREFIX = "/api/v1/jobs"


async def _seed_job(
    db: AsyncSession,
    user: User,
    *,
    title: str = "Software Engineer",
    company: str = "Acme Corp",
    url: str | None = None,
) -> Job:
    job = Job(
        user_id=user.id,
        job_title=title,
        company_title=company,
        job_url=url or f"https://example.com/jobs/{uuid.uuid4()}",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


class TestListJobs:
    async def test_empty_when_no_jobs(self, client: AsyncClient):
        resp = await client.get(f"{PREFIX}/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_own_jobs(
        self, client: AsyncClient, db: AsyncSession, test_user: User
    ):
        await _seed_job(db, test_user, title="Frontend Engineer")
        await _seed_job(db, test_user, title="Backend Engineer")

        resp = await client.get(f"{PREFIX}/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_does_not_return_other_users_jobs(
        self, client: AsyncClient, db: AsyncSession
    ):
        other = User(id=uuid.uuid4(), email="other@test.com")
        db.add(other)
        await db.commit()
        await db.refresh(other)
        await _seed_job(db, other, title="Other's job")

        resp = await client.get(f"{PREFIX}/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_filter_by_company(
        self, client: AsyncClient, db: AsyncSession, test_user: User
    ):
        await _seed_job(db, test_user, company="Acme Corp")
        await _seed_job(db, test_user, company="BetaCo")

        resp = await client.get(f"{PREFIX}/?company=Acme")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["company_title"] == "Acme Corp"

    async def test_pagination(
        self, client: AsyncClient, db: AsyncSession, test_user: User
    ):
        for i in range(5):
            await _seed_job(db, test_user, title=f"Job {i}")

        resp = await client.get(f"{PREFIX}/?per_page=3&page=1")
        assert len(resp.json()) == 3

        resp2 = await client.get(f"{PREFIX}/?per_page=3&page=2")
        assert len(resp2.json()) == 2

    async def test_response_fields(
        self, client: AsyncClient, db: AsyncSession, test_user: User
    ):
        await _seed_job(db, test_user)
        resp = await client.get(f"{PREFIX}/")
        data = resp.json()[0]
        for field in ("id", "job_title", "company_title", "job_url", "created_at"):
            assert field in data, f"Missing field: {field}"


class TestCountJobs:
    async def test_count_zero(self, client: AsyncClient):
        resp = await client.get(f"{PREFIX}/count")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    async def test_count_matches_list(
        self, client: AsyncClient, db: AsyncSession, test_user: User
    ):
        await _seed_job(db, test_user)
        await _seed_job(db, test_user)
        await _seed_job(db, test_user)

        resp = await client.get(f"{PREFIX}/count")
        assert resp.json()["count"] == 3
