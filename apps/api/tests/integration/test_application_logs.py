"""Integration tests for the /api/v1/application-logs router.

Covers: POST (log application), GET (list), GET /stats.
The GET /timeline endpoint uses a PostgreSQL-specific DATE cast and is
marked to run only when DATABASE_URL points to PostgreSQL.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.application_log import ApplicationLog
from src.models.job import Job
from src.models.user import User

PREFIX = "/api/v1/application-logs"


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _seed_log(
    db: AsyncSession,
    user: User,
    job: Job,
    *,
    status: str = "submitted",
    board_type: str = "greenhouse",
    method: str = "extension_auto_fill",
    applied_at: datetime | None = None,
) -> ApplicationLog:
    log = ApplicationLog(
        user_id=user.id,
        job_id=job.id,
        board_type=board_type,
        method=method,
        status=status,
        fields_filled=10,
        fields_total=12,
        applied_at=applied_at or datetime.now(UTC),
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


# ── POST / ────────────────────────────────────────────────────────────────────

class TestLogApplication:
    async def test_creates_log(self, client: AsyncClient, test_job: Job):
        payload = {
            "job_id": str(test_job.id),
            "board_type": "greenhouse",
            "method": "extension_auto_fill",
            "status": "submitted",
            "fields_filled": 8,
            "fields_total": 10,
        }
        resp = await client.post(f"{PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "submitted"
        assert data["board_type"] == "greenhouse"
        assert data["job_id"] == str(test_job.id)

    async def test_invalid_status_returns_400(self, client: AsyncClient, test_job: Job):
        payload = {
            "job_id": str(test_job.id),
            "board_type": "greenhouse",
            "method": "extension_auto_fill",
            "status": "invalid_status",
        }
        resp = await client.post(f"{PREFIX}/", json=payload)
        assert resp.status_code == 400

    async def test_invalid_method_returns_400(self, client: AsyncClient, test_job: Job):
        payload = {
            "job_id": str(test_job.id),
            "board_type": "greenhouse",
            "method": "robot_magic",
            "status": "submitted",
        }
        resp = await client.post(f"{PREFIX}/", json=payload)
        assert resp.status_code == 400

    async def test_unknown_job_id_returns_404(self, client: AsyncClient):
        payload = {
            "job_id": str(uuid.uuid4()),
            "board_type": "greenhouse",
            "method": "extension_auto_fill",
            "status": "submitted",
        }
        resp = await client.post(f"{PREFIX}/", json=payload)
        assert resp.status_code == 404

    async def test_updates_job_application_status(
        self, client: AsyncClient, db: AsyncSession, test_job: Job
    ):
        payload = {
            "job_id": str(test_job.id),
            "board_type": "lever",
            "method": "extension_auto_fill",
            "status": "submitted",
        }
        await client.post(f"{PREFIX}/", json=payload)

        await db.refresh(test_job)
        assert test_job.application_status == "applied"

    @pytest.mark.parametrize("status,expected_job_status", [
        ("submitted", "applied"),
        ("filled", "interested"),
        ("failed", "failed"),
        ("partial", "interested"),
    ])
    async def test_status_map(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_user: User,
        status: str,
        expected_job_status: str,
    ):
        # Each parametrize run needs its own job to avoid conflicts
        job = Job(
            user_id=test_user.id,
            job_title="Engineer",
            job_url=f"https://example.com/jobs/{uuid.uuid4()}",
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        payload = {
            "job_id": str(job.id),
            "board_type": "greenhouse",
            "method": "extension_auto_fill",
            "status": status,
        }
        resp = await client.post(f"{PREFIX}/", json=payload)
        assert resp.status_code == 201

        await db.refresh(job)
        assert job.application_status == expected_job_status


# ── GET / ─────────────────────────────────────────────────────────────────────

class TestListApplicationLogs:
    async def test_empty_list(self, client: AsyncClient):
        resp = await client.get(f"{PREFIX}/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_own_logs(
        self, client: AsyncClient, db: AsyncSession, test_user: User, test_job: Job
    ):
        await _seed_log(db, test_user, test_job, status="submitted")
        await _seed_log(db, test_user, test_job, status="filled")

        resp = await client.get(f"{PREFIX}/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_filter_by_status(
        self, client: AsyncClient, db: AsyncSession, test_user: User, test_job: Job
    ):
        await _seed_log(db, test_user, test_job, status="submitted")
        await _seed_log(db, test_user, test_job, status="failed")

        resp = await client.get(f"{PREFIX}/?status=failed")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "failed"

    async def test_filter_by_job_id(
        self, client: AsyncClient, db: AsyncSession, test_user: User, test_job: Job
    ):
        other_job = Job(
            user_id=test_user.id,
            job_title="Other Job",
            job_url="https://example.com/jobs/other",
        )
        db.add(other_job)
        await db.commit()
        await db.refresh(other_job)

        await _seed_log(db, test_user, test_job)
        await _seed_log(db, test_user, other_job)

        resp = await client.get(f"{PREFIX}/?job_id={test_job.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["job_id"] == str(test_job.id)

    async def test_does_not_return_other_users_logs(
        self, client: AsyncClient, db: AsyncSession, test_job: Job
    ):
        other_user = User(id=uuid.uuid4(), email="other@example.com")
        db.add(other_user)
        await db.commit()
        await db.refresh(other_user)

        other_job = Job(
            user_id=other_user.id,
            job_title="Other Job",
            job_url="https://example.com/jobs/other",
        )
        db.add(other_job)
        await db.commit()
        await db.refresh(other_job)

        await _seed_log(db, other_user, other_job)  # another user's log

        resp = await client.get(f"{PREFIX}/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_limit_and_offset(
        self, client: AsyncClient, db: AsyncSession, test_user: User, test_job: Job
    ):
        for _ in range(5):
            await _seed_log(db, test_user, test_job)

        resp = await client.get(f"{PREFIX}/?limit=3&offset=0")
        assert len(resp.json()) == 3

        resp2 = await client.get(f"{PREFIX}/?limit=3&offset=3")
        assert len(resp2.json()) == 2


# ── GET /stats ────────────────────────────────────────────────────────────────

class TestApplicationStats:
    async def test_empty_stats(self, client: AsyncClient):
        resp = await client.get(f"{PREFIX}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["submitted"] == 0

    async def test_total_count(
        self, client: AsyncClient, db: AsyncSession, test_user: User, test_job: Job
    ):
        await _seed_log(db, test_user, test_job, status="submitted")
        await _seed_log(db, test_user, test_job, status="failed")

        resp = await client.get(f"{PREFIX}/stats")
        assert resp.json()["total"] == 2

    async def test_status_breakdown(
        self, client: AsyncClient, db: AsyncSession, test_user: User, test_job: Job
    ):
        await _seed_log(db, test_user, test_job, status="submitted")
        await _seed_log(db, test_user, test_job, status="submitted")
        await _seed_log(db, test_user, test_job, status="failed")

        resp = await client.get(f"{PREFIX}/stats")
        data = resp.json()
        assert data["submitted"] == 2
        assert data["failed"] == 1

    async def test_by_board_breakdown(
        self, client: AsyncClient, db: AsyncSession, test_user: User, test_job: Job
    ):
        await _seed_log(db, test_user, test_job, board_type="greenhouse")
        await _seed_log(db, test_user, test_job, board_type="greenhouse")
        await _seed_log(db, test_user, test_job, board_type="workday")

        resp = await client.get(f"{PREFIX}/stats")
        data = resp.json()
        assert data["by_board"]["greenhouse"] == 2
        assert data["by_board"]["workday"] == 1

    async def test_period_filter_today(
        self, client: AsyncClient, db: AsyncSession, test_user: User, test_job: Job
    ):
        # One recent log, one old log
        await _seed_log(db, test_user, test_job, applied_at=datetime.now(UTC))
        await _seed_log(
            db, test_user, test_job, applied_at=datetime.now(UTC) - timedelta(days=10)
        )

        resp = await client.get(f"{PREFIX}/stats?period=today")
        assert resp.json()["total"] == 1

    async def test_period_all_returns_everything(
        self, client: AsyncClient, db: AsyncSession, test_user: User, test_job: Job
    ):
        await _seed_log(db, test_user, test_job, applied_at=datetime.now(UTC) - timedelta(days=200))
        await _seed_log(db, test_user, test_job, applied_at=datetime.now(UTC))

        resp = await client.get(f"{PREFIX}/stats?period=all")
        assert resp.json()["total"] == 2

    async def test_valid_period_values(self, client: AsyncClient):
        for period in ("today", "week", "month", "3mo", "ytd", "all"):
            resp = await client.get(f"{PREFIX}/stats?period={period}")
            assert resp.status_code == 200, f"period={period} failed"
