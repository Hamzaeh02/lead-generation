import pytest

pytestmark = pytest.mark.asyncio


async def test_security_headers_present_on_every_response(client):
    response = await client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "permissions-policy" in response.headers


async def test_hsts_not_sent_outside_production(client):
    response = await client.get("/health")
    assert "strict-transport-security" not in response.headers


async def test_metrics_endpoint_exposes_prometheus_format(client):
    await client.get("/health")

    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "http_requests_total" in response.text
    assert "http_request_duration_seconds" in response.text


async def test_request_id_header_present(client):
    response = await client.get("/health")
    assert "x-request-id" in response.headers
