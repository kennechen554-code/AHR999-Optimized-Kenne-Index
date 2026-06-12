"""Trading risk control tests."""

import json
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1 import exchange as exchange_api
from app.model.tenant_models import OperationAuditLog
from app.model.user import Tenant, User
from tests.conftest import get_test_factory, register_user


@pytest.mark.asyncio
async def test_unverified_user_cannot_place_live_order(client: AsyncClient) -> None:
    await register_user(client, email="unverified_live@test.com", password="Unverified1234!")
    response = await client.post("/api/v1/exchange/run-dca?dry_run=false&confirm_live=true")

    assert response.status_code == 403
    assert "邮箱验证" in response.text


@pytest.mark.asyncio
async def test_global_live_trading_switch_blocks_live_orders(
    premium_authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        exchange_api,
        "get_settings",
        lambda: SimpleNamespace(global_live_trading_enabled=False),
    )

    response = await premium_authed_client.post(
        "/api/v1/exchange/run-dca?dry_run=false&confirm_live=true"
    )

    assert response.status_code == 403
    assert "全局实盘交易开关已关闭" in response.text


@pytest.mark.asyncio
async def test_tenant_live_trading_pause_blocks_live_orders(
    premium_authed_client: AsyncClient,
) -> None:
    factory = get_test_factory()
    async with factory() as session:
        user = (await session.execute(select(User).where(User.email == "premium@test.com"))).scalar_one()
        tenant = (await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
        tenant.live_trading_paused = True
        await session.commit()

    response = await premium_authed_client.post(
        "/api/v1/exchange/run-dca?dry_run=false&confirm_live=true"
    )

    assert response.status_code == 403
    assert "实盘交易已暂停" in response.text


@pytest.mark.asyncio
async def test_admin_can_pause_tenant_live_trading(premium_authed_client: AsyncClient) -> None:
    response = await premium_authed_client.patch(
        "/api/v1/admin/tenant/risk",
        json={"live_trading_paused": True},
    )

    assert response.status_code == 200
    assert response.json()["live_trading_paused"] is True

    factory = get_test_factory()
    async with factory() as session:
        user = (await session.execute(select(User).where(User.email == "premium@test.com"))).scalar_one()
        tenant = (await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one()
        assert tenant.live_trading_paused is True


@pytest.mark.asyncio
async def test_live_filled_orders_sum_enforces_cap(
    premium_authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_dca(
        cfg: dict[str, object],
        data_files: dict[str, object],
        dry_run: bool,
    ) -> dict[str, object]:
        return {
            "ok": True,
            "mode": "live",
            "total_usdt": 100,
            "orders": [
                {"symbol": "BTC", "usdt": 1500, "status": "filled"},
                {"symbol": "ETH", "usdt": 700, "status": "filled"},
            ],
            "message": "filled over cap",
        }

    monkeypatch.setattr(exchange_api, "run_dca", fake_run_dca)

    response = await premium_authed_client.post(
        "/api/v1/exchange/run-dca?dry_run=false&confirm_live=true"
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_exchange_run_audit_summary_is_structured_json(
    premium_authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_dca(
        cfg: dict[str, object],
        data_files: dict[str, object],
        dry_run: bool,
    ) -> dict[str, object]:
        return {
            "ok": True,
            "mode": "dry_run",
            "total_usdt": 88,
            "orders": [
                {"symbol": "BTC", "usdt": 55, "status": "dry_run"},
                {"symbol": "ETH", "usdt": 33, "status": "dry_run"},
            ],
            "message": "dry audit",
        }

    monkeypatch.setattr(exchange_api, "run_dca", fake_run_dca)

    response = await premium_authed_client.post("/api/v1/exchange/run-dca?dry_run=true")
    assert response.status_code == 200

    factory = get_test_factory()
    async with factory() as session:
        audit = (
            await session.execute(
                select(OperationAuditLog).where(OperationAuditLog.action == "exchange.run_dca")
            )
        ).scalar_one()
        payload = json.loads(audit.summary)

    assert payload["exchange"] == "okx"
    assert payload["dry_run"] is True
    assert payload["order_count"] == 2
    assert payload["symbols"] == ["BTC", "ETH"]
    assert payload["dry_run_usdt"] == 88
