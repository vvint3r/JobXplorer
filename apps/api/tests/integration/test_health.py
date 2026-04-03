"""Integration tests for the /health endpoint (no auth required)."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture()
async def anon_client():
    """Client without any dependency overrides — tests the raw app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestHealth:
    async def test_health_returns_200(self, anon_client: AsyncClient):
        resp = await anon_client.get("/health")
        assert resp.status_code == 200

    async def test_health_body(self, anon_client: AsyncClient):
        resp = await anon_client.get("/health")
        data = resp.json()
        assert data["status"] == "ok"
        assert "service" in data

    async def test_health_no_auth_needed(self, anon_client: AsyncClient):
        """Health check must be reachable without an Authorization header."""
        resp = await anon_client.get("/health")
        assert resp.status_code != 401
        assert resp.status_code != 403
