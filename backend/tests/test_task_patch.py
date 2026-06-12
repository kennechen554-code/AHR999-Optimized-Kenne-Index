"""任务 PATCH 接口测试。"""

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import register_user


@pytest.mark.asyncio
async def test_get_task_status(premium_authed_client: AsyncClient) -> None:
    """GET /tasks/status → 200。"""
    response = await premium_authed_client.get("/api/v1/tasks/status")
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert "running" in data
    assert len(data["tasks"]) >= 1


@pytest.mark.asyncio
async def test_patch_task_interval(premium_authed_client: AsyncClient) -> None:
    """PATCH /tasks/{id} interval_minutes=60 → 成功。"""
    status = (await premium_authed_client.get("/api/v1/tasks/status")).json()
    task_id = status["tasks"][0]["id"]

    response = await premium_authed_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"interval_minutes": 60},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["task"]["interval_minutes"] == 60


@pytest.mark.asyncio
async def test_patch_task_invalid_interval(premium_authed_client: AsyncClient) -> None:
    """interval_minutes=1 → 422。"""
    status = (await premium_authed_client.get("/api/v1/tasks/status")).json()
    task_id = status["tasks"][0]["id"]

    response = await premium_authed_client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"interval_minutes": 1},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_task_enable_dry_run(premium_authed_client: AsyncClient) -> None:
    """启用 dry_run 任务 → 成功。"""
    status = (await premium_authed_client.get("/api/v1/tasks/status")).json()
    dry_run_task = next(
        (t for t in status["tasks"] if t["task_type"] == "automation_dry_run"),
        None,
    )
    assert dry_run_task is not None

    response = await premium_authed_client.patch(
        f"/api/v1/tasks/{dry_run_task['id']}",
        json={"enabled": True},
    )
    assert response.status_code == 200
    assert response.json()["task"]["enabled"] is True


@pytest.mark.asyncio
async def test_patch_task_enable_live_blocked(premium_authed_client: AsyncClient) -> None:
    """启用 automation_live 任务 → 403。"""
    status = (await premium_authed_client.get("/api/v1/tasks/status")).json()
    live_task = next(
        (t for t in status["tasks"] if t["task_type"] == "automation_live"),
        None,
    )
    assert live_task is not None

    response = await premium_authed_client.patch(
        f"/api/v1/tasks/{live_task['id']}",
        json={"enabled": True},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_patch_task_requires_premium(test_app: object) -> None:
    """FREE 用户 PATCH 任务 → 403。"""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        await register_user(c, email="free_task@test.com", password="Free1234!")
        status = (await c.get("/api/v1/tasks/status")).json()
        task_id = status["tasks"][0]["id"]

        response = await c.patch(
            f"/api/v1/tasks/{task_id}",
            json={"interval_minutes": 60},
        )
        assert response.status_code == 403
