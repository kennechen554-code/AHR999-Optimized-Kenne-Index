"""
预算管理服务。

支持两种预算模式：
- MONTHLY: 月度预算 → 按执行间隔均摊到每次
- FIXED:   每次固定金额，无月度上限

从原 kenne_dca.py:Budget 类提取。
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def calculate_per_run_budget(
    budget_mode: str,
    budget_amount: float,
    run_interval_days: int,
) -> float:
    """
    计算本次可用预算。

    Args:
        budget_mode: 'MONTHLY' 或 'FIXED'
        budget_amount: 总预算（MONTHLY=月度总额, FIXED=单次金额）
        run_interval_days: 执行间隔天数

    Returns:
        本次可投入的 USDT 金额
    """
    if budget_mode == "FIXED":
        return budget_amount

    # MONTHLY: 月度预算 / 每月执行次数
    runs_per_month = 30 / max(run_interval_days, 1)
    per_run = budget_amount / runs_per_month

    logger.info(
        "预算: %s %.2f USDT, 间隔 %d 天, 每次 ~%.2f USDT",
        budget_mode, budget_amount, run_interval_days, per_run,
    )

    return round(per_run, 2)


def calculate_monthly_spent(
    records: list[dict],
    year: int | None = None,
    month: int | None = None,
) -> float:
    """
    计算指定月份的已投入总金额。

    Args:
        records: 交易记录列表（含 'ts' 和 'usdt' 字段）
        year: 年份，默认当前年
        month: 月份，默认当前月

    Returns:
        该月已投入的 USDT 总额
    """
    now = datetime.now(timezone.utc)
    target_year = year or now.year
    target_month = month or now.month

    total = 0.0
    for record in records:
        ts_str = record.get("ts", "")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts.year == target_year and ts.month == target_month:
                status = record.get("status", "")
                if status in ("filled", "dry_run"):
                    total += record.get("usdt", 0.0)
        except (ValueError, TypeError):
            continue

    return total
