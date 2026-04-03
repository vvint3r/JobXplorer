"""Integration tests for the /api/v1/notifications router."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.notification import Notification
from src.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _seed_notification(
    db: AsyncSession,
    user: User,
    *,
    read: bool = False,
    title: str = "Test Notification",
    message: str = "Something happened",
) -> Notification:
    notif = Notification(
        user_id=user.id,
        type="pipeline_complete",
        title=title,
        message=message,
        read_at=datetime.now(UTC) if read else None,
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)
    return notif


# ── GET /count ────────────────────────────────────────────────────────────────

class TestNotificationCount:
    async def test_zero_when_no_notifications(self, client: AsyncClient):
        resp = await client.get("/api/v1/notifications/count")
        assert resp.status_code == 200
        assert resp.json()["unread"] == 0

    async def test_counts_unread_only(self, client: AsyncClient, db: AsyncSession, test_user: User):
        await _seed_notification(db, test_user, read=False)
        await _seed_notification(db, test_user, read=False)
        await _seed_notification(db, test_user, read=True)

        resp = await client.get("/api/v1/notifications/count")
        assert resp.status_code == 200
        assert resp.json()["unread"] == 2

    async def test_requires_auth(self, anon_client: AsyncClient):
        resp = await anon_client.get("/api/v1/notifications/count")
        assert resp.status_code == 403


# ── GET / ─────────────────────────────────────────────────────────────────────

class TestListNotifications:
    async def test_empty_list(self, client: AsyncClient):
        resp = await client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_seeded_notifications(
        self, client: AsyncClient, db: AsyncSession, test_user: User
    ):
        await _seed_notification(db, test_user, title="Alert 1")
        await _seed_notification(db, test_user, title="Alert 2")

        resp = await client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        titles = {n["title"] for n in data}
        assert titles == {"Alert 1", "Alert 2"}

    async def test_unread_come_first(
        self, client: AsyncClient, db: AsyncSession, test_user: User
    ):
        await _seed_notification(db, test_user, title="Read One", read=True)
        await _seed_notification(db, test_user, title="Unread One", read=False)

        resp = await client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["title"] == "Unread One"

    async def test_max_50_returned(
        self, client: AsyncClient, db: AsyncSession, test_user: User
    ):
        for i in range(55):
            await _seed_notification(db, test_user, title=f"Notif {i}")

        resp = await client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        assert len(resp.json()) == 50


# ── POST /{id}/read ───────────────────────────────────────────────────────────

class TestMarkRead:
    async def test_marks_notification_as_read(
        self, client: AsyncClient, db: AsyncSession, test_user: User
    ):
        notif = await _seed_notification(db, test_user)
        assert notif.read_at is None

        resp = await client.post(f"/api/v1/notifications/{notif.id}/read")
        assert resp.status_code == 200
        data = resp.json()
        assert data["read_at"] is not None

    async def test_404_for_unknown_id(self, client: AsyncClient):
        fake_id = uuid.uuid4()
        resp = await client.post(f"/api/v1/notifications/{fake_id}/read")
        assert resp.status_code == 404

    async def test_cannot_mark_other_users_notification(
        self, client: AsyncClient, db: AsyncSession
    ):
        """A notification belonging to a different user should return 404."""
        other_user = User(id=uuid.uuid4(), email="other@example.com")
        db.add(other_user)
        await db.commit()
        await db.refresh(other_user)

        other_notif = await _seed_notification(db, other_user, title="Other's notif")

        resp = await client.post(f"/api/v1/notifications/{other_notif.id}/read")
        assert resp.status_code == 404


# ── POST /read-all ────────────────────────────────────────────────────────────

class TestMarkAllRead:
    async def test_marks_all_unread_as_read(
        self, client: AsyncClient, db: AsyncSession, test_user: User
    ):
        await _seed_notification(db, test_user, read=False)
        await _seed_notification(db, test_user, read=False)

        resp = await client.post("/api/v1/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["unread"] == 0

    async def test_count_is_zero_after_read_all(
        self, client: AsyncClient, db: AsyncSession, test_user: User
    ):
        await _seed_notification(db, test_user, read=False)

        await client.post("/api/v1/notifications/read-all")

        count_resp = await client.get("/api/v1/notifications/count")
        assert count_resp.json()["unread"] == 0

    async def test_noop_when_nothing_to_read(self, client: AsyncClient):
        resp = await client.post("/api/v1/notifications/read-all")
        assert resp.status_code == 200
        assert resp.json()["unread"] == 0


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
async def anon_client():
    """Client with no auth override — for testing 403 responses."""
    from httpx import ASGITransport
    from src.main import app as _app

    async with AsyncClient(transport=ASGITransport(app=_app), base_url="http://test") as c:
        yield c
