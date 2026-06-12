"""Tenant boundary and control-plane tests."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from app.core.security import hash_password
from app.model.tenant_models import OperationAuditLog, TaskRunLog, UserConfig
from app.model.user import PlanType, Tenant, User, UserRole
from app.repository.operation_audit_repository import add_operation_log
from app.service import task_service
from tests.conftest import get_test_factory, register_user


async def _set_plan(email: str, plan: PlanType) -> User:
    factory = get_test_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.email_verified = True
        await session.execute(update(Tenant).where(Tenant.id == user.tenant_id).values(plan=plan))
        await session.commit()
        return user


@pytest.mark.asyncio
async def test_admin_cannot_disable_cross_tenant_user(test_app: object) -> None:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as tenant_a:
        await register_user(tenant_a, email="tenant_a@test.com", password="TenantA1234!")
        async with AsyncClient(transport=transport, base_url="http://testserver") as tenant_b:
            await register_user(tenant_b, email="tenant_b@test.com", password="TenantB1234!")
        victim = await _set_plan("tenant_b@test.com", PlanType.FREE)

        response = await tenant_a.patch(
            f"/api/v1/admin/users/{victim.id}/status",
            json={"is_active": False},
        )
        assert response.status_code == 404

    factory = get_test_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.email == "tenant_b@test.com"))
        assert result.scalar_one().is_active is True


@pytest.mark.asyncio
async def test_member_cannot_filter_audit_logs_for_other_user(test_app: object) -> None:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as owner_client:
        await register_user(owner_client, email="audit_owner@test.com", password="Owner1234!")

    factory = get_test_factory()
    async with factory() as session:
        owner = (await session.execute(select(User).where(User.email == "audit_owner@test.com"))).scalar_one()
        member = User(
            email="audit_member@test.com",
            hashed_password=hash_password("Member1234!"),
            display_name="Audit Member",
            role=UserRole.MEMBER,
            tenant_id=owner.tenant_id,
        )
        session.add(member)
        await session.flush()
        await add_operation_log(
            session,
            user_id=owner.id,
            tenant_id=owner.tenant_id,
            action="config.update",
            resource_type="config",
            summary="owner log",
        )
        await session.commit()
        owner_id = owner.id

    async with AsyncClient(transport=transport, base_url="http://testserver") as member_client:
        login = await member_client.post(
            "/api/v1/auth/login",
            json={"email": "audit_member@test.com", "password": "Member1234!"},
        )
        assert login.status_code == 200
        response = await member_client.get(f"/api/v1/audit/operations?user_id={owner_id}")
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_run_now_only_processes_current_user(
    test_app: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as user_a_client:
        await register_user(user_a_client, email="run_a@test.com", password="RunA1234!")
        async with AsyncClient(transport=transport, base_url="http://testserver") as user_b_client:
            await register_user(user_b_client, email="run_b@test.com", password="RunB1234!")

        user_a = await _set_plan("run_a@test.com", PlanType.PREMIUM)
        user_b = await _set_plan("run_b@test.com", PlanType.PREMIUM)

        factory = get_test_factory()
        async with factory() as session:
            session.add_all(
                [
                    UserConfig(
                        user_id=user_a.id,
                        tenant_id=user_a.tenant_id,
                        automation_enabled=True,
                        automation_dry_run=True,
                        budget_amount=1000.0,
                    ),
                    UserConfig(
                        user_id=user_b.id,
                        tenant_id=user_b.tenant_id,
                        automation_enabled=True,
                        automation_dry_run=True,
                        budget_amount=1000.0,
                    ),
                ]
            )
            await session.commit()

        async def fake_run_dca(payload: dict[str, object], data_files: dict[str, object], dry_run: bool) -> dict[str, object]:
            return {"ok": True, "mode": "dry_run", "message": "current only", "orders": []}

        monkeypatch.setattr(task_service, "run_dca", fake_run_dca)

        response = await user_a_client.post("/api/v1/tasks/run-now", json={"task": "automation_dry_run"})
        assert response.status_code == 200
        assert response.json()["processed"] == 1

    async with get_test_factory()() as session:
        logs = (await session.execute(select(TaskRunLog))).scalars().all()
        assert [log.user_id for log in logs] == [user_a.id]
        audit_logs = (await session.execute(select(OperationAuditLog))).scalars().all()
        assert any(log.action == "task.run_now" and log.user_id == user_a.id for log in audit_logs)
