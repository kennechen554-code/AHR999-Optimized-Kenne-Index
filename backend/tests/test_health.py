"""健康检查接口测试。

验证全局 /api/health 和详细 /api/v1/health 端点。
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_global_health_check(client: AsyncClient) -> None:
    """GET /api/health → 200, status=ok。"""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "2.0.0"


@pytest.mark.asyncio
async def test_detailed_health_check(client: AsyncClient) -> None:
    """GET /api/v1/health → 200, app=ok, database=ok。"""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "ok"
    assert data["database"] == "ok"


@pytest.mark.asyncio
async def test_health_no_auth_required(client: AsyncClient) -> None:
    """无 Cookie / 无 Bearer 访问健康检查 → 200。"""
    # 确保客户端无认证信息
    client.cookies.clear()
    client.headers.pop("authorization", None)

    global_response = await client.get("/api/health")
    assert global_response.status_code == 200

    detailed_response = await client.get("/api/v1/health")
    assert detailed_response.status_code == 200


@pytest.mark.asyncio
async def test_health_detail_requires_auth(client: AsyncClient) -> None:
    """GET /api/v1/health/detail without auth should be rejected."""
    response = await client.get("/api/v1/health/detail")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_detail_for_owner(authed_client: AsyncClient) -> None:
    """OWNER can inspect operational health detail."""
    response = await authed_client.get("/api/v1/health/detail")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "ok"
    assert "tasks" in data
    assert "market_data" in data
