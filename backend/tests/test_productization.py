"""Productization feature tests."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.model.tenant_models import TradeRecord
from app.model.user import Tenant, User
from app.service.mfa_service import totp_code
from tests.conftest import get_test_factory


@pytest.mark.asyncio
async def test_team_invitation_acceptance_and_role_update(
    premium_authed_client: AsyncClient,
    test_app: object,
) -> None:
    factory = get_test_factory()
    async with factory() as session:
        user = (await session.execute(select(User).where(User.email == "premium@test.com"))).scalar_one()
        tenant = (await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
        tenant.max_users = 3
        user.email_verified = True
        await session.commit()

    invite = await premium_authed_client.post(
        "/api/v1/admin/invitations",
        json={"email": "teammate@test.com", "role": "member"},
    )
    assert invite.status_code == 200
    token = invite.json()["invitation"]["token"]

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as invited:
        accepted = await invited.post(
            "/api/v1/auth/invitations/accept",
            json={"token": token, "password": "Member1234!", "display_name": "Team Mate"},
        )
        assert accepted.status_code == 200

    users = (await premium_authed_client.get("/api/v1/admin/users")).json()["users"]
    member = next(item for item in users if item["email"] == "teammate@test.com")
    changed = await premium_authed_client.patch(
        f"/api/v1/admin/users/{member['id']}/role",
        json={"role": "admin"},
    )
    assert changed.status_code == 200


@pytest.mark.asyncio
async def test_exports_and_deletion_request(premium_authed_client: AsyncClient) -> None:
    factory = get_test_factory()
    async with factory() as session:
        user = (await session.execute(select(User).where(User.email == "premium@test.com"))).scalar_one()
        session.add(
            TradeRecord(
                user_id=user.id,
                tenant_id=user.tenant_id,
                ts="2026-05-10T00:00:00+00:00",
                symbol="BTC",
                exchange="okx",
                mode="dry_run",
                strategy_mode="per_asset_strict_dd",
                usdt=12.5,
                status="dry_run",
            )
        )
        await session.commit()

    history_export = await premium_authed_client.get("/api/v1/history/export")
    assert history_export.status_code == 200
    assert "BTC" in history_export.text

    audit_export = await premium_authed_client.get("/api/v1/audit/operations/export")
    assert audit_export.status_code == 200
    assert "request_id" in audit_export.text

    deletion = await premium_authed_client.post("/api/v1/security/deletion/request")
    assert deletion.status_code == 200
    token = deletion.json()["token"]
    confirmed = await premium_authed_client.post("/api/v1/security/deletion/confirm", json={"token": token})
    assert confirmed.status_code == 200


@pytest.mark.asyncio
async def test_mfa_enable_and_step_up_required(premium_authed_client: AsyncClient) -> None:
    setup = await premium_authed_client.post("/api/v1/security/mfa/setup")
    assert setup.status_code == 200
    secret = setup.json()["secret"]

    enabled = await premium_authed_client.post(
        "/api/v1/security/mfa/enable",
        json={"secret": secret, "code": totp_code(secret)},
    )
    assert enabled.status_code == 200
    assert enabled.json()["backup_codes"]

    blocked = await premium_authed_client.patch(
        "/api/v1/admin/tenant/risk",
        json={"live_trading_paused": True},
    )
    assert blocked.status_code == 403

    allowed = await premium_authed_client.patch(
        "/api/v1/admin/tenant/risk",
        headers={"X-Step-Up-Code": totp_code(secret)},
        json={"live_trading_paused": True},
    )
    assert allowed.status_code == 200

    # 测试停用 MFA 的二次身份验证校验
    disable_blocked = await premium_authed_client.post("/api/v1/security/mfa/disable")
    assert disable_blocked.status_code == 403

    disable_allowed = await premium_authed_client.post(
        "/api/v1/security/mfa/disable",
        headers={"X-Step-Up-Code": totp_code(secret)},
    )
    assert disable_allowed.status_code == 200
    
    me_resp = await premium_authed_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["mfa_enabled"] is False


@pytest.mark.asyncio
async def test_risk_events_and_retention_policy(premium_authed_client: AsyncClient) -> None:
    response = await premium_authed_client.patch(
        "/api/v1/admin/tenant/risk",
        json={"live_trading_paused": True},
    )
    assert response.status_code == 200

    events = await premium_authed_client.get("/api/v1/admin/risk-events")
    assert events.status_code == 200
    assert events.json()["events"]

    policy = await premium_authed_client.get("/api/v1/admin/retention-policy")
    assert policy.status_code == 200
    updated = await premium_authed_client.post(
        "/api/v1/admin/retention-policy",
        json={"operation_audit_days": 90, "task_run_days": 90, "risk_event_days": 180},
    )
    assert updated.status_code == 200

    cleanup = await premium_authed_client.post("/api/v1/admin/retention/cleanup")
    assert cleanup.status_code == 200


@pytest.mark.asyncio
async def test_register_requires_accepted_terms(test_app: object) -> None:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. 不提供 accepted_terms，应该被拒绝
        resp1 = await client.post(
            "/api/v1/auth/register",
            json={"email": "noterms@test.com", "password": "Password123!"}
        )
        assert resp1.status_code == 422
        assert "服务协议" in resp1.json()["message"]

        # 2. 提供 accepted_terms = False，应该被拒绝
        resp2 = await client.post(
            "/api/v1/auth/register",
            json={"email": "noterms2@test.com", "password": "Password123!", "accepted_terms": False}
        )
        assert resp2.status_code == 422

        # 3. 提供 accepted_terms = True，应该成功
        resp3 = await client.post(
            "/api/v1/auth/register",
            json={"email": "noterms3@test.com", "password": "Password123!", "accepted_terms": True}
        )
        assert resp3.status_code == 200
