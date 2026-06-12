"""
DCA 定投执行服务。

整合信号计算 → 资金分配 → 交易执行的完整链路。
"""

import asyncio
import importlib
import logging
from datetime import datetime, timezone
from types import ModuleType

from sqlalchemy.ext.asyncio import AsyncSession
from app.model.tenant_models import TradeRecord
from app.service.alert_service import send_alert

from app.engine.allocator import allocate
from app.engine.kenne_index import compute_signal
from app.engine.per_asset_strategy import build_per_asset_orders, normalize_strategy_mode
from app.service.budget_service import calculate_per_run_budget
from app.service.exchange_service import create_exchange, execute_market_buy

logger = logging.getLogger(__name__)


def _get_ccxt_module() -> ModuleType:
    return importlib.import_module("ccxt.async_support")


async def _execute_live_order(
    session: AsyncSession | None,
    config: dict,
    user_id: int,
    tenant_id: int,
    symbol: str,
    usdt_amount: float,
    strategy_mode: str,
    now_ts: str,
    kenne_index: float = 0.0,
    mult: float = 0.0,
    momentum: str = "",
) -> dict:
    """
    实盘订单执行：插入 pending -> CCXT 下单 (带指数退避重试) -> 更新 filled/failed 状态机。
    """
    symbol_pair = f"{symbol}/USDT"
    record = None

    # 1. 只有 session 不为 None 时才插入 pending 记录
    if session is not None:
        record = TradeRecord(
            user_id=user_id,
            tenant_id=tenant_id,
            ts=now_ts,
            symbol=symbol,
            exchange=config.get("exchange", "okx"),
            mode="live",
            strategy_mode=strategy_mode,
            usdt=usdt_amount,
            status="failed",  # 默认值
            order_status="pending",
            price=0.0,
            qty=0.0,
            order_id="",
            kenne_index=kenne_index,
            mult=mult,
            momentum=momentum,
            note="Pending execution",
        )
        session.add(record)
        await session.commit()  # 提交 pending 到数据库

    # 2. 执行 CCXT 交易 (带指数退避重试)
    max_retries = 3
    delay = 1.0
    order_result = None
    last_exc = None
    is_timeout = False
    ccxt_module = _get_ccxt_module()

    for attempt in range(max_retries):
        try:
            exchange = create_exchange(
                config.get("exchange", "okx"),
                config.get("api_key_encrypted", ""),
                config.get("api_secret_encrypted", ""),
                config.get("api_passphrase_encrypted", ""),
                config.get("simulated", True),
            )
            order_result = await execute_market_buy(exchange, symbol_pair, usdt_amount)
            last_exc = None
            break
        except ccxt_module.RequestTimeout as exc:
            # 外部请求超时：不重试，防止重复下单，直接作为 pending 异常退栈
            last_exc = exc
            is_timeout = True
            logger.warning(
                "[%s] Market buy request timeout. Not retrying to avoid double orders: %s",
                symbol, exc
            )
            break
        except (ccxt_module.RateLimitExceeded, ccxt_module.DDoSProtection, ccxt_module.ExchangeNotAvailable) as exc:
            last_exc = exc
            if attempt == max_retries - 1:
                break
            logger.warning(
                "[%s] Attempt %d failed (retryable error): %s. Retrying in %.1fs...",
                symbol, attempt + 1, exc, delay
            )
            await asyncio.sleep(delay)
            delay *= 2.0
        except Exception as exc:
            # 其它不可恢复异常（如余额不足、权限错误）：不重试
            last_exc = exc
            logger.error("[%s] Non-retryable order error: %s", symbol, exc)
            break

    # 3. 更新状态机
    if order_result:
        # 下单成功
        from app.core.metrics import DCA_EXECUTIONS, DCA_AMOUNT
        DCA_EXECUTIONS.labels(symbol=symbol, status="filled", mode="live").inc()
        DCA_AMOUNT.labels(symbol=symbol, mode="live").inc(usdt_amount)

        note = f"Executed successfully via {config.get('exchange', 'okx')}"
        if session is not None and record is not None:
            record.status = "filled"
            record.order_status = "filled"
            record.price = float(order_result.get("price") or 0)
            record.qty = float(order_result.get("qty") or 0)
            record.order_id = str(order_result.get("order_id") or "")
            record.note = note
            await session.commit()

        return {
            "symbol": symbol,
            "usdt": usdt_amount,
            "status": "filled",
            "order_status": "filled",
            "order_id": order_result.get("order_id", ""),
            "price": order_result.get("price", 0.0),
            "qty": order_result.get("qty", 0.0),
            "ts": now_ts,
            "kenne_index": kenne_index,
            "mult": mult,
            "momentum": momentum,
            "exchange": config.get("exchange", "okx"),
            "note": note,
            "strategy_mode": strategy_mode,
            "db_saved": session is not None,
        }
    else:
        # 下单失败
        if is_timeout:
            from app.core.metrics import DCA_EXECUTIONS
            DCA_EXECUTIONS.labels(symbol=symbol, status="pending", mode="live").inc()

            note = f"Network Timeout: {last_exc}"
            if session is not None and record is not None:
                record.status = "failed"
                record.order_status = "pending"  # 保持为 pending
                record.note = note
                await session.commit()

            asyncio.create_task(
                send_alert(
                    title=f"实盘下单超时不确定状态: {symbol}",
                    message=(
                        f"用户 ID: {user_id}\n"
                        f"租户 ID: {tenant_id}\n"
                        f"资产: {symbol}\n"
                        f"下单金额: {usdt_amount} USDT\n"
                        f"状态: pending (网络超时)\n"
                        f"错误详情: {last_exc}"
                    ),
                    severity="critical"
                )
            )

            return {
                "symbol": symbol,
                "usdt": usdt_amount,
                "status": "failed",
                "order_status": "pending",
                "order_id": "",
                "price": 0.0,
                "qty": 0.0,
                "ts": now_ts,
                "kenne_index": kenne_index,
                "mult": mult,
                "momentum": momentum,
                "exchange": config.get("exchange", "okx"),
                "note": note,
                "strategy_mode": strategy_mode,
                "db_saved": session is not None,
            }
        else:
            from app.core.metrics import DCA_EXECUTIONS
            DCA_EXECUTIONS.labels(symbol=symbol, status="failed", mode="live").inc()

            note = f"Order failed: {last_exc}"
            if session is not None and record is not None:
                record.status = "failed"
                record.order_status = "failed"
                record.note = note
                await session.commit()

            asyncio.create_task(
                send_alert(
                    title=f"实盘下单失败: {symbol}",
                    message=(
                        f"用户 ID: {user_id}\n"
                        f"租户 ID: {tenant_id}\n"
                        f"资产: {symbol}\n"
                        f"下单金额: {usdt_amount} USDT\n"
                        f"状态: failed\n"
                        f"错误详情: {last_exc}"
                    ),
                    severity="critical"
                )
            )

            return {
                "symbol": symbol,
                "usdt": usdt_amount,
                "status": "failed",
                "order_status": "failed",
                "order_id": "",
                "price": 0.0,
                "qty": 0.0,
                "ts": now_ts,
                "kenne_index": kenne_index,
                "mult": mult,
                "momentum": momentum,
                "exchange": config.get("exchange", "okx"),
                "note": note,
                "strategy_mode": strategy_mode,
                "db_saved": session is not None,
            }


async def run_dca(
    config: dict,
    data_files: dict,
    dry_run: bool = True,
    session: AsyncSession | None = None,
) -> dict:
    """
    执行一次 DCA 定投流程。

    流程：
    1. 计算所有币种信号
    2. 计算本次可用预算
    3. 按信号权重分配资金
    4. 逐币种执行市价买入（dry_run 时跳过实际下单）
    5. 收集执行结果

    Args:
        config: 用户配置字典（含交易所凭证、预算参数等）
        data_files: {symbol: csv_path} 映射
        dry_run: 是否为模拟执行

    Returns:
        {'ok': bool, 'mode': str, 'total_usdt': float, 'orders': list}
    """
    mode = "dry_run" if dry_run else "live"
    strategy_mode = normalize_strategy_mode(config.get("strategy_mode", "per_asset_strict_dd"))
    user_id = int(config.get("user_id", 0) or 0)
    tenant_id = int(config.get("tenant_id", 0) or 0)

    if strategy_mode.startswith("per_asset_"):
        monthly_budget = float(config.get("budget_amount", 700) or 700)
        strategy_orders = build_per_asset_orders(data_files, strategy_mode, monthly_budget)
        if not strategy_orders:
            return {
                "ok": True,
                "mode": mode,
                "total_usdt": 0,
                "orders": [],
                "message": f"{strategy_mode} 当前无可执行信号",
            }

        orders = []
        total_usdt = 0.0
        now_ts = datetime.now(timezone.utc).isoformat()
        for order in strategy_orders:
            if dry_run:
                order_result = {
                    "symbol": order.symbol,
                    "usdt": order.usdt_amount,
                    "status": "dry_run",
                    "order_id": "",
                    "price": order.price,
                    "qty": round(order.usdt_amount / order.price, 8) if order.price > 0 else 0,
                    "ts": now_ts,
                    "kenne_index": order.kenne_index,
                    "mult": order.score,
                    "momentum": order.momentum,
                    "exchange": config.get("exchange", "okx"),
                    "note": strategy_mode,
                    "strategy_mode": strategy_mode,
                }
            else:
                order_result = await _execute_live_order(
                    session=session,
                    config=config,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    symbol=order.symbol,
                    usdt_amount=order.usdt_amount,
                    strategy_mode=strategy_mode,
                    now_ts=now_ts,
                    kenne_index=order.kenne_index,
                    mult=order.score,
                    momentum=order.momentum,
                )
            orders.append(order_result)
            if order_result["status"] in ("filled", "dry_run"):
                total_usdt += order.usdt_amount
                if dry_run:
                    from app.core.metrics import DCA_EXECUTIONS, DCA_AMOUNT
                    DCA_EXECUTIONS.labels(symbol=order.symbol, status="dry_run", mode="dry_run").inc()
                    DCA_AMOUNT.labels(symbol=order.symbol, mode="dry_run").inc(order.usdt_amount)

        return {
            "ok": True,
            "mode": mode,
            "total_usdt": round(total_usdt, 2),
            "orders": orders,
            "message": f"{strategy_mode} {'模拟' if dry_run else '实盘'}执行完成",
        }

    # 1. 计算信号
    signals = []
    for symbol, csv_path in data_files.items():
        signal = compute_signal(csv_path, symbol)
        if not signal.error:
            signals.append(signal.__dict__)

    active = [s for s in signals if s.get("final_mult", 0) > 0]
    if not active:
        return {
            "ok": True,
            "mode": mode,
            "total_usdt": 0,
            "orders": [],
            "message": "当前无活跃信号，所有币种 final_mult = 0",
        }

    # 2. 计算预算
    per_run = calculate_per_run_budget(
        config.get("budget_mode", "MONTHLY"),
        config.get("budget_amount", 700),
        config.get("run_interval_days", 7),
    )

    # 3. 分配资金
    allocations = allocate(active, per_run)
    if not allocations:
        return {
            "ok": True,
            "mode": mode,
            "total_usdt": 0,
            "orders": [],
            "message": "分配后无有效订单（单笔低于最小金额）",
        }

    # 4. 执行交易
    orders = []
    total_usdt = 0.0
    now_ts = datetime.now(timezone.utc).isoformat()

    for alloc in allocations:
        if dry_run:
            # 模拟执行：仅记录，不下单
            order_result = {
                "symbol": alloc.symbol,
                "usdt": alloc.usdt_amount,
                "status": "dry_run",
                "order_id": "",
                "price": 0,
                "qty": 0,
                "ts": now_ts,
                "kenne_index": next(
                    (s["kenne_index"] for s in active if s["symbol"] == alloc.symbol), 0,
                ),
                "mult": alloc.weight,
                "momentum": next(
                    (s.get("momentum", "") for s in active if s["symbol"] == alloc.symbol), "",
                ),
                "exchange": config.get("exchange", "okx"),
                "note": strategy_mode,
                "strategy_mode": strategy_mode,
            }
        else:
            # 实盘执行
            k_idx = next((s["kenne_index"] for s in active if s["symbol"] == alloc.symbol), 0.0)
            mom = next((s.get("momentum", "") for s in active if s["symbol"] == alloc.symbol), "")
            order_result = await _execute_live_order(
                session=session,
                config=config,
                user_id=user_id,
                tenant_id=tenant_id,
                symbol=alloc.symbol,
                usdt_amount=alloc.usdt_amount,
                strategy_mode=strategy_mode,
                now_ts=now_ts,
                kenne_index=k_idx,
                mult=alloc.weight,
                momentum=mom,
            )

        orders.append(order_result)
        if order_result["status"] in ("filled", "dry_run"):
            total_usdt += alloc.usdt_amount
            if dry_run:
                from app.core.metrics import DCA_EXECUTIONS, DCA_AMOUNT
                DCA_EXECUTIONS.labels(symbol=alloc.symbol, status="dry_run", mode="dry_run").inc()
                DCA_AMOUNT.labels(symbol=alloc.symbol, mode="dry_run").inc(alloc.usdt_amount)

    return {
        "ok": True,
        "mode": mode,
        "total_usdt": round(total_usdt, 2),
        "orders": orders,
        "message": f"{'模拟' if dry_run else '实盘'}执行完成",
    }
