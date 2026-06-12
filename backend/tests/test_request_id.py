"""Request ID propagation tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_request_id_response_header(client: AsyncClient) -> None:
    response = await client.get("/api/health", headers={"x-request-id": "rid-health"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "rid-health"


@pytest.mark.asyncio
async def test_request_id_written_to_operation_audit(authed_client: AsyncClient) -> None:
    request_id = "rid-audit-001"
    response = await authed_client.post(
        "/api/v1/auth/resend-verification",
        headers={"x-request-id": request_id},
    )
    assert response.status_code == 200

    audit_response = await authed_client.get(
        "/api/v1/audit/operations",
        params={"request_id": request_id},
    )
    assert audit_response.status_code == 200
    data = audit_response.json()
    assert data["count"] == 1
    assert data["records"][0]["request_id"] == request_id


@pytest.mark.asyncio
async def test_request_id_in_error_body(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/me",
        headers={"x-request-id": "rid-error-001"},
    )

    assert response.status_code == 401
    assert response.headers["X-Request-ID"] == "rid-error-001"
    assert response.json()["request_id"] == "rid-error-001"
