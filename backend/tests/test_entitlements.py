"""Plan entitlement enforcement tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_free_user_cannot_access_mvrv(authed_client: AsyncClient) -> None:
    response = await authed_client.get("/api/v1/mvrv")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_basic_user_entitlements_allow_mvrv_flag(basic_authed_client: AsyncClient) -> None:
    response = await basic_authed_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["plan"] == "basic"
    assert data["entitlements"]["mvrv"] is True
    assert data["entitlements"]["live_trading"] is False
    assert data["entitlements"]["supported_exchanges"] == ["okx"]


@pytest.mark.asyncio
async def test_config_exchange_restricted_by_plan(basic_authed_client: AsyncClient) -> None:
    denied = await basic_authed_client.post("/api/v1/config", json={"exchange": "binance"})
    assert denied.status_code == 403

    allowed = await basic_authed_client.post("/api/v1/config", json={"exchange": "okx"})
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_exchange_list_filtered_by_plan(basic_authed_client: AsyncClient) -> None:
    response = await basic_authed_client.get("/api/v1/exchange/list")
    assert response.status_code == 200
    assert list(response.json().keys()) == ["okx"]


@pytest.mark.asyncio
async def test_free_user_cannot_update_market_data(authed_client: AsyncClient) -> None:
    response = await authed_client.post("/api/v1/exchange/update-data")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_free_user_cannot_send_test_email(authed_client: AsyncClient) -> None:
    response = await authed_client.post(
        "/api/v1/notifications/test-email",
        json={"subject": "test", "message": "hello"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_backtest_strategies_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/backtest/strategies")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_live_dca_enforces_premium_order_cap(
    premium_authed_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1 import exchange as exchange_api

    async def fake_run_dca(
        cfg: dict[str, object],
        data_files: dict[str, object],
        dry_run: bool,
    ) -> dict[str, object]:
        return {
            "ok": True,
            "mode": "live",
            "total_usdt": 2500,
            "orders": [],
            "message": "over cap",
        }

    monkeypatch.setattr(exchange_api, "run_dca", fake_run_dca)

    response = await premium_authed_client.post(
        "/api/v1/exchange/run-dca?dry_run=false&confirm_live=true"
    )
    assert response.status_code == 403
