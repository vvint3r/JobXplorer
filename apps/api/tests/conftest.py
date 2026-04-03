"""Shared test fixtures for the JobXplore API test suite.

Uses SQLite in-memory (aiosqlite) so tests run without a live PostgreSQL server.
The `client` fixture wires FastAPI's dependency overrides so every test gets a
fresh, isolated in-memory database and a pre-seeded test user.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.auth import get_current_user
from src.database import Base, get_db
from src.main import app
from src.models.job import Job
from src.models.user import User

# ── Constants ────────────────────────────────────────────────────────────────

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_USER_EMAIL = "test@example.com"

# ── Engine / session ─────────────────────────────────────────────────────────


@pytest.fixture()
async def engine():
    """Per-test SQLite in-memory engine with schema created."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture()
async def db(engine):
    """Open async session for the in-memory database."""
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session


# ── Seed objects ──────────────────────────────────────────────────────────────


@pytest.fixture()
async def test_user(db: AsyncSession) -> User:
    """Insert and return a test User row."""
    user = User(id=TEST_USER_ID, email=TEST_USER_EMAIL)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture()
async def test_job(db: AsyncSession, test_user: User) -> Job:
    """Insert and return a minimal Job row owned by the test user."""
    job = Job(
        user_id=test_user.id,
        job_title="Software Engineer",
        job_url="https://example.com/jobs/123",
        company_title="Acme Corp",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


# ── FastAPI client with dependency overrides ──────────────────────────────────


@pytest.fixture()
async def client(db: AsyncSession, test_user: User) -> AsyncClient:
    """AsyncClient with get_db and get_current_user overridden to use the test DB."""

    async def _get_db():
        yield db

    async def _get_current_user():
        return test_user

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
