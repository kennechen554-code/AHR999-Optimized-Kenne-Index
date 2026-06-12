"""
资金分配算法。

按各币种的最终执行倍数（final_mult）加权分配预算，
并应用单币种权重上限（3 轮迭代归一化，防止极端行情下权重失控）。

从原 kenne_dca.py:allocate() 提取。
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# NOTE: 各币种单次权重上限（防止单币过度集中）
MAX_WEIGHT: dict[str, float] = {
    "BTC": 0.60,
    "ETH": 0.50,
    "SOL": 0.50,
}

# NOTE: 低于此金额的单笔订单跳过
MIN_ORDER_USDT = 5.0


@dataclass
class AllocationResult:
    """单币种分配结果。"""
    symbol: str
    usdt_amount: float
    weight: float


def allocate(
    active_signals: list[dict],
    budget_usdt: float,
    max_weight: dict[str, float] | None = None,
) -> list[AllocationResult]:
    """
    按信号权重分配定投预算。

    算法：
    1. 提取所有 final_mult > 0 的活跃信号
    2. 按 final_mult 值计算初始权重
    3. 3 轮迭代应用单币种上限并重新归一化
    4. 按最终权重分配 USDT 金额

    Args:
        active_signals: 含有 'symbol' 和 'final_mult' 键的信号列表
        budget_usdt: 本次可用总预算（USDT）
        max_weight: 各币种权重上限，默认使用 MAX_WEIGHT

    Returns:
        分配结果列表（仅包含金额 >= MIN_ORDER_USDT 的币种）
    """
    if max_weight is None:
        max_weight = MAX_WEIGHT

    active = [s for s in active_signals if s.get("final_mult", 0) > 0]
    if not active or budget_usdt <= 0:
        return []

    # 初始权重 = final_mult
    norm: dict[str, float] = {s["symbol"]: s["final_mult"] for s in active}

    # 3 轮迭代归一化 + 上限裁剪
    for _ in range(3):
        total = sum(norm.values())
        if total <= 0:
            return []
        norm = {k: v / total for k, v in norm.items()}
        norm = {k: min(v, max_weight.get(k, 1.0)) for k, v in norm.items()}

    # 最终归一化
    total = sum(norm.values())
    if total <= 0:
        return []
    norm = {k: v / total for k, v in norm.items()}

    results = []
    for signal in active:
        symbol = signal["symbol"]
        weight = norm.get(symbol, 0.0)
        amount = round(weight * budget_usdt, 2)

        if amount >= MIN_ORDER_USDT:
            results.append(AllocationResult(
                symbol=symbol,
                usdt_amount=amount,
                weight=round(weight, 4),
            ))

    return results
