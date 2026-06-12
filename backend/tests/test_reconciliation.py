"""余额对账审计集成测试。"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import select

from app.model.tenant_models import BalanceSnapshot, TradeRecord, UserConfig, RiskEvent
from app.service.reconciliation_service import reconcile_balances
from tests.conftest import get_test_factory


@pytest.mark.asyncio
async def test_reconciliation_matched_and_mismatched(test_app: pytest.FixtureRequest) -> None:
    factory = get_test_factory()
    
    # 1. 准备配置数据
    async with factory() as session:
        user_cfg = UserConfig(
            user_id=888,
            tenant_id=999,
            exchange="okx",
            api_key_encrypted="encrypted-api-key",
            api_secret_encrypted="encrypted-api-secret",
            simulated=True
        )
        session.add(user_cfg)
        
        # 写入一条上一期的初始快照数据
        initial_btc_snap = BalanceSnapshot(
            user_id=888,
            tenant_id=999,
            exchange="okx",
            asset="BTC",
            remote_balance=1.0,  # 上一次的交易所余额
            local_calculated=1.0,
            difference=0.0,
            difference_pct=0.0,
            status="matched"
        )
        session.add(initial_btc_snap)
        
        # 写入这期间本地成功定投买入 0.5 BTC 的记录
        trade = TradeRecord(
            user_id=888,
            tenant_id=999,
            ts="2026-05-25T00:00:00Z",
            symbol="BTC",
            exchange="okx",
            mode="live",
            usdt=30000.0,
            status="filled",
            order_status="filled",
            qty=0.5,
            price=60000.0
        )
        session.add(trade)
        await session.commit()

    # 2. 模拟交易所返回的数据
    # 预期交易所余额 = 上一次余额 (1.0) + 本次定投 delta (0.5) = 1.5 BTC
    fake_balances = {
        "BTC": {"total": 1.5, "free": 1.5, "used": 0.0},
        "ETH": {"total": 0.0, "free": 0.0, "used": 0.0},
        "SOL": {"total": 0.0, "free": 0.0, "used": 0.0},
        "USDT": {"total": 0.0, "free": 0.0, "used": 0.0}
    }

    # 3. 模拟对账测试：完全匹配
    with patch("app.service.reconciliation_service.create_exchange", MagicMock()):
        with patch("app.service.reconciliation_service.fetch_balance", AsyncMock(return_value=fake_balances)):
            async with factory() as session:
                snapshots = await reconcile_balances(session, user_id=888, tenant_id=999)
                
                # 确认生成了 4 个资产的对账快照
                assert len(snapshots) == 4
                btc_snap = next(s for s in snapshots if s.asset == "BTC")
                assert btc_snap.status == "matched"
                assert btc_snap.remote_balance == 1.5
                assert btc_snap.local_calculated == 1.5
                assert btc_snap.difference == 0.0

    # 4. 测试对账：发生偏差不匹配 (交易所只有 1.1 BTC, 偏差达 0.4 BTC > 1%)
    fake_mismatched_balances = {
        "BTC": {"total": 1.1, "free": 1.1, "used": 0.0},
        "ETH": {"total": 0.0, "free": 0.0, "used": 0.0},
        "SOL": {"total": 0.0, "free": 0.0, "used": 0.0},
        "USDT": {"total": 0.0, "free": 0.0, "used": 0.0}
    }

    mock_send_alert = AsyncMock()
    with patch("app.service.reconciliation_service.create_exchange", MagicMock()):
        with patch("app.service.reconciliation_service.fetch_balance", AsyncMock(return_value=fake_mismatched_balances)):
            with patch("app.service.reconciliation_service.send_alert", mock_send_alert):
                async with factory() as session:
                    snapshots = await reconcile_balances(session, user_id=888, tenant_id=999)
                    btc_snap = next(s for s in snapshots if s.asset == "BTC")
                    
                    # 确认状态为 mismatched
                    assert btc_snap.status == "mismatched"
                    assert btc_snap.remote_balance == 1.1
                    assert btc_snap.local_calculated == 1.5
                    assert abs(btc_snap.difference - (-0.4)) < 1e-6
                    
                    # 确认产生了 RiskEvent 审计日志
                    events = (await session.execute(select(RiskEvent).where(RiskEvent.event_type == "reconciliation_mismatch"))).scalars().all()
                    assert len(events) == 1
                    assert "对账比对异常" in events[0].summary
                    
                    # 确认触发了报警
                    mock_send_alert.assert_called_once()
