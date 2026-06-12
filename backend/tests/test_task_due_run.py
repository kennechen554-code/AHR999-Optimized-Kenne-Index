"""Due automation task execution tests."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.model.tenant_models import AutomationTask, TaskRunLog, UserConfig
from app.model.user import User
from app.service import task_service
from tests.conftest import get_test_factory


async def _premium_user() -> User:
    factory = get_test_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.email == "premium@test.com"))
        return result.scalar_one()


@pytest.mark.asyncio
async def test_run_due_tasks_executes_due_dry_run(
    premium_authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await premium_authed_client.get("/api/v1/tasks/status")
    user = await _premium_user()
    factory = get_test_factory()

    async def fake_run_dca(payload: dict[str, object], data_files: dict[str, object], dry_run: bool) -> dict[str, object]:
        return {"ok": True, "mode": "dry_run", "message": "mock dry-run", "orders": []}

    monkeypatch.setattr(task_service, "get_main_session_factory", lambda: factory)
    monkeypatch.setattr(task_service, "run_dca", fake_run_dca)

    async with factory() as session:
        cfg = UserConfig(
            user_id=user.id,
            tenant_id=user.tenant_id,
            automation_enabled=True,
            automation_dry_run=True,
            budget_amount=1000.0,
        )
        session.add(cfg)
        task_result = await session.execute(
            select(AutomationTask).where(
                AutomationTask.user_id == user.id,
                AutomationTask.task_type == "automation_dry_run",
            )
        )
        task = task_result.scalar_one()
        task.enabled = True
        task.next_run_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
        await session.commit()

    result = await task_service.task_runtime.run_due_tasks_once()
    assert result["ok"] is True
    assert result["processed"] == 1

    async with factory() as session:
        log_result = await session.execute(select(TaskRunLog).where(TaskRunLog.user_id == user.id))
        log = log_result.scalar_one()
        assert log.task_type == "automation_dry_run"
        assert log.status == "success"
        assert "mock dry-run" in log.message


@pytest.mark.asyncio
async def test_run_due_tasks_skips_future_task(
    premium_authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await premium_authed_client.get("/api/v1/tasks/status")
    user = await _premium_user()
    factory = get_test_factory()
    monkeypatch.setattr(task_service, "get_main_session_factory", lambda: factory)

    async with factory() as session:
        task_result = await session.execute(
            select(AutomationTask).where(
                AutomationTask.user_id == user.id,
                AutomationTask.task_type == "automation_dry_run",
            )
        )
        task = task_result.scalar_one()
        task.enabled = True
        task.next_run_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
        await session.commit()

    result = await task_service.task_runtime.run_due_tasks_once()
    assert result["ok"] is True
    assert result["processed"] == 0


@pytest.mark.asyncio
async def test_run_due_tasks_skips_when_tick_lock_held(
    premium_authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await premium_authed_client.get("/api/v1/tasks/status")

    class LockedRedis:
        async def set(self, *args: object, **kwargs: object) -> bool:
            return False

    async def fake_get_redis() -> LockedRedis:
        return LockedRedis()

    monkeypatch.setattr(task_service, "get_redis", fake_get_redis)

    result = await task_service.task_runtime.run_due_tasks_once()
    assert result["ok"] is True
    assert result["processed"] == 0
    assert "另一工作进程" in result["message"]


@pytest.mark.asyncio
async def test_run_due_tasks_claim_prevents_second_execution(
    premium_authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await premium_authed_client.get("/api/v1/tasks/status")
    user = await _premium_user()
    factory = get_test_factory()
    calls = 0

    async def fake_run_dca(payload: dict[str, object], data_files: dict[str, object], dry_run: bool) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"ok": True, "mode": "dry_run", "message": "claimed", "orders": []}

    monkeypatch.setattr(task_service, "get_main_session_factory", lambda: factory)
    monkeypatch.setattr(task_service, "run_dca", fake_run_dca)

    async with factory() as session:
        session.add(
            UserConfig(
                user_id=user.id,
                tenant_id=user.tenant_id,
                automation_enabled=True,
                automation_dry_run=True,
                budget_amount=1000.0,
            )
        )
        task = (
            await session.execute(
                select(AutomationTask).where(
                    AutomationTask.user_id == user.id,
                    AutomationTask.task_type == "automation_dry_run",
                )
            )
        ).scalar_one()
        task.enabled = True
        task.next_run_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
        await session.commit()

    first = await task_service.task_runtime.run_due_tasks_once()
    second = await task_service.task_runtime.run_due_tasks_once()

    assert first["processed"] == 1
    assert second["processed"] == 0
    assert calls == 1
