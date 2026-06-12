"""DCA 执行重试、订单状态机与未决订单回溯回溯集成测试。"""

import pytest
import ccxt.async_support as ccxt
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import select

from app.model.tenant_models import TradeRecord, UserConfig
from app.service.dca_service import run_dca
from app.service.task_service import resolve_pending_orders
from tests.conftest import get_test_factory


@pytest.mark.asyncio
async def test_dca_live_state_machine_success_with_retry(test_app: pytest.FixtureRequest) -> None:
    factory = get_test_factory()
    
    # 1. 准备实盘用户配置
    async with factory() as session:
        user_cfg = UserConfig(
            user_id=111,
            tenant_id=222,
            exchange="okx",
            api_key_encrypted="enc-key",
            api_secret_encrypted="enc-secret",
            simulated=False,  # 实盘
            budget_amount=100.0,
            strategy_mode="per_asset_strict_dd"
        )
        session.add(user_cfg)
        await session.commit()

    config_payload = {
        "user_id": 111,
        "tenant_id": 222,
        "exchange": "okx",
        "api_key_encrypted": "enc-key",
        "api_secret_encrypted": "enc-secret",
        "simulated": False,
        "budget_amount": 100.0,
        "strategy_mode": "per_asset_strict_dd"
    }

    # 2. 模拟 ccxt 报错和重试逻辑
    # 第一次抛出限频错误 (DDoSProtection)，第二次下单成功
    mock_exchange = AsyncMock()
    mock_exchange.fetch_ticker.return_value = {"last": 60000.0}
    
    # 用副作用模拟重试：第一次限频报错，第二次成功
    mock_exchange.create_market_buy_order.side_effect = [
        ccxt.DDoSProtection("Rate limit exceeded"),
        {"id": "okx-order-123", "status": "closed"}
    ]

    with patch("app.service.dca_service.create_exchange", MagicMock(return_value=mock_exchange)):
        # 开启短延时避免测试卡顿
        with patch("asyncio.sleep", AsyncMock()):
            async with factory() as session:
                # 模拟行情文件
                data_files = {"BTC": MagicMock()}
                
                # 拦截 build_per_asset_orders
                mock_order = MagicMock(symbol="BTC", usdt_amount=100.0, price=60000.0, score=1.0, momentum="up")
                with patch("app.service.dca_service.build_per_asset_orders", return_value=[mock_order]):
                    result = await run_dca(config_payload, data_files, dry_run=False, session=session)
                    
                    assert result["ok"] is True
                    assert len(result["orders"]) == 1
                    assert result["orders"][0]["status"] == "filled"
                    assert result["orders"][0]["order_status"] == "filled"
                    assert result["orders"][0]["order_id"] == "okx-order-123"

                # 3. 校验数据库中的 TradeRecord，最终应该被更新为 filled
                records = (await session.execute(select(TradeRecord).where(TradeRecord.user_id == 111))).scalars().all()
                assert len(records) == 1
                assert records[0].order_status == "filled"
                assert records[0].status == "filled"
                assert records[0].order_id == "okx-order-123"


@pytest.mark.asyncio
async def test_dca_live_state_machine_timeout_retains_pending_and_recovery(test_app: pytest.FixtureRequest) -> None:
    factory = get_test_factory()
    
    # 1. 准备配置
    async with factory() as session:
        user_cfg = UserConfig(
            user_id=333,
            tenant_id=444,
            exchange="okx",
            api_key_encrypted="enc-key",
            api_secret_encrypted="enc-secret",
            simulated=False,
            budget_amount=100.0,
            strategy_mode="per_asset_strict_dd"
        )
        session.add(user_cfg)
        await session.commit()

    config_payload = {
        "user_id": 333,
        "tenant_id": 444,
        "exchange": "okx",
        "api_key_encrypted": "enc-key",
        "api_secret_encrypted": "enc-secret",
        "simulated": False,
        "budget_amount": 100.0,
        "strategy_mode": "per_asset_strict_dd"
    }

    # 2. 模拟下单超时错误 RequestTimeout
    mock_exchange = AsyncMock()
    mock_exchange.fetch_ticker.return_value = {"last": 60000.0}
    mock_exchange.create_market_buy_order.side_effect = ccxt.RequestTimeout("Network read timeout")

    with patch("app.service.dca_service.create_exchange", MagicMock(return_value=mock_exchange)):
        with patch("asyncio.sleep", AsyncMock()):
            with patch("app.service.dca_service.send_alert", AsyncMock()) as mock_alert:
                async with factory() as session:
                    data_files = {"BTC": MagicMock()}
                    mock_order = MagicMock(symbol="BTC", usdt_amount=100.0, price=60000.0, score=1.0, momentum="up")
                    with patch("app.service.dca_service.build_per_asset_orders", return_value=[mock_order]):
                        result = await run_dca(config_payload, data_files, dry_run=False, session=session)
                        
                        assert result["orders"][0]["order_status"] == "pending"
                        assert result["orders"][0]["status"] == "failed"

                    # 3. 验证数据库，订单状态依然为 pending
                    records = (await session.execute(select(TradeRecord).where(TradeRecord.user_id == 333))).scalars().all()
                    assert len(records) == 1
                    assert records[0].order_status == "pending"
                    mock_alert.assert_called_once()

    # 4. 测试回溯恢复 resolve_pending_orders 逻辑
    # 模拟交易所存在该成交
    fake_trades = [
        {
            "id": "trade-9999",
            "order": "okx-order-9999",
            "timestamp": int(records[0].created_at.timestamp() * 1000) + 1000,
            "cost": 100.0,
            "price": 60000.0,
            "amount": 0.00166667
        }
    ]
    mock_exchange_recover = AsyncMock()
    mock_exchange_recover.fetch_my_trades.return_value = fake_trades

    with patch("app.service.exchange_service.create_exchange", MagicMock(return_value=mock_exchange_recover)):
        with patch("app.service.alert_service.send_alert", AsyncMock()) as mock_alert_rec:
            await resolve_pending_orders(factory)
            
            # 5. 验证是否成功回溯并把状态更新为 filled
            async with factory() as session:
                recovered_records = (await session.execute(select(TradeRecord).where(TradeRecord.user_id == 333))).scalars().all()
                assert len(recovered_records) == 1
                assert recovered_records[0].order_status == "filled"
                assert recovered_records[0].status == "filled"
                assert recovered_records[0].order_id == "okx-order-9999"
                mock_alert_rec.assert_called_once()
