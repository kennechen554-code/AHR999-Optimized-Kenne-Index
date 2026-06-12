"""
交易所余额对账审计服务。

拉取交易所真实余额快照，与本地定投扣款账目进行增量差异对账，并在异常时记录 RiskEvent 并告警。
"""

import logging
import asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.model.tenant_models import BalanceSnapshot, TradeRecord, UserConfig
from app.service.exchange_service import create_exchange, fetch_balance
from app.service.risk_event_service import record_risk_event
from app.service.alert_service import send_alert

logger = logging.getLogger(__name__)


async def reconcile_balances(session: AsyncSession, user_id: int, tenant_id: int) -> list[BalanceSnapshot]:
    """
    对指定用户的交易所余额进行每日增量对账审计。
    """
    # 1. 获取用户交易所配置
    cfg = await session.execute(
        select(UserConfig).where(
            UserConfig.user_id == user_id,
            UserConfig.tenant_id == tenant_id,
        )
    )
    user_cfg = cfg.scalar_one_or_none()
    if not user_cfg or not user_cfg.api_key_encrypted:
        logger.info("No active API config for user %d, skipping reconciliation", user_id)
        return []

    # 2. 拉取真实交易所余额
    try:
        exchange = create_exchange(
            user_cfg.exchange,
            user_cfg.api_key_encrypted,
            user_cfg.api_secret_encrypted,
            user_cfg.api_passphrase_encrypted,
            user_cfg.simulated,
        )
        balances = await fetch_balance(exchange)
    except Exception as exc:
        logger.error("Failed to fetch balance during reconciliation for user %d: %s", user_id, exc)
        return []

    assets = ["BTC", "ETH", "SOL", "USDT"]
    snapshots = []

    for asset in assets:
        remote_bal = 0.0
        if asset in balances:
            remote_bal = float(balances[asset].get("total", 0.0) or 0.0)

        # 3. 找出上一次的对账快照
        last_snap_query = await session.execute(
            select(BalanceSnapshot)
            .where(
                BalanceSnapshot.user_id == user_id,
                BalanceSnapshot.tenant_id == tenant_id,
                BalanceSnapshot.asset == asset,
            )
            .order_by(BalanceSnapshot.created_at.desc())
            .limit(1)
        )
        last_snapshot = last_snap_query.scalar_one_or_none()

        # 4. 计算本地预期余额 (增量比对)
        if last_snapshot:
            # 统计自上次对账快照生成以来的系统定投交易记录
            if asset == "USDT":
                # USDT 是扣减的
                trade_query = await session.execute(
                    select(func.coalesce(func.sum(TradeRecord.usdt), 0.0)).where(
                        TradeRecord.user_id == user_id,
                        TradeRecord.tenant_id == tenant_id,
                        TradeRecord.status == "filled",
                        TradeRecord.mode == "live",
                        TradeRecord.created_at >= last_snapshot.created_at,
                    )
                )
                delta_qty = -float(trade_query.scalar_one() or 0.0)
            else:
                # 其它币种是买入增加的
                trade_query = await session.execute(
                    select(func.coalesce(func.sum(TradeRecord.qty), 0.0)).where(
                        TradeRecord.user_id == user_id,
                        TradeRecord.tenant_id == tenant_id,
                        TradeRecord.symbol == asset,
                        TradeRecord.status == "filled",
                        TradeRecord.mode == "live",
                        TradeRecord.created_at >= last_snapshot.created_at,
                    )
                )
                delta_qty = float(trade_query.scalar_one() or 0.0)

            local_calculated = last_snapshot.remote_balance + delta_qty
            difference = remote_bal - local_calculated
            difference_pct = abs(difference) / (local_calculated or 1.0) if local_calculated != 0 else 0.0
        else:
            # 第一次对账直接作为基准 baseline
            local_calculated = remote_bal
            difference = 0.0
            difference_pct = 0.0

        status = "matched"
        # 当有历史参考对账记录，且偏差率大于 1%，且偏差绝对值非极微小时，标记为 mismatched 异常
        if last_snapshot and difference_pct > 0.01 and abs(difference) > 0.0001:
            status = "mismatched"
            summary = f"对账比对异常: {asset} 预期 {local_calculated:.6f}, 实际 {remote_bal:.6f}, 偏差 {difference:.6f} ({difference_pct:.2%})"
            
            # 写入风险审计事件
            await record_risk_event(
                session,
                tenant_id=tenant_id,
                user_id=user_id,
                event_type="reconciliation_mismatch",
                severity="warning",
                summary=summary,
            )
            
            # 异步发送多渠道警报
            asyncio.create_task(
                send_alert(
                    title=f"交易所余额对账比对异常: {asset}",
                    message=(
                        f"用户 ID: {user_id}\n"
                        f"租户 ID: {tenant_id}\n"
                        f"资产: {asset}\n"
                        f"预期余额: {local_calculated:.6f}\n"
                        f"实际余额: {remote_bal:.6f}\n"
                        f"偏差量: {difference:.6f}\n"
                        f"偏差比例: {difference_pct:.2%}"
                    ),
                    severity="warning"
                )
            )

        # 5. 写入当前快照
        snapshot = BalanceSnapshot(
            tenant_id=tenant_id,
            user_id=user_id,
            exchange=user_cfg.exchange,
            asset=asset,
            remote_balance=remote_bal,
            local_calculated=local_calculated,
            difference=difference,
            difference_pct=difference_pct,
            status=status,
        )
        session.add(snapshot)
        snapshots.append(snapshot)

    await session.commit()
    return snapshots
