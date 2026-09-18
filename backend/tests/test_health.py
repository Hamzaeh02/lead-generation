import pytest

pytestmark = pytest.mark.asyncio


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_reports_dependency_checks(client):
    response = await client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert "checks" in body
    assert set(body["checks"].keys()) == {"database", "redis"}
