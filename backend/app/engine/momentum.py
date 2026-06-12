"""
动量过滤器。

防落刀机制：在价格急跌期间降低定投倍数。

状态判定逻辑：
- STABLE:      7日/14日跌幅在正常范围 → 足额执行 (1.0x)
- STABILIZING: 急跌后已反弹 ≥ bounce_min → 谨慎参与 (0.75x)
- FALLING:     急跌中且无有效反弹 → 轻仓防御 (0.40x)

从原 kenne_index.py:_momentum_state() 提取。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MomentumConfig:
    """每个币种的动量判定阈值。"""
    knife_7d: float    # 7日跌幅阈值（负数）
    knife_14d: float   # 14日跌幅阈值（负数）
    bounce_min: float  # 企稳确认最小反弹幅度


# NOTE: FALLING 保留 0.4x 而非 0：历史底部往往诞生于持续下跌中，
# 完全缺席会错失关键入场点
MOMENTUM_MULTIPLIERS = {
    "STABLE": 1.00,
    "STABILIZING": 0.75,
    "FALLING": 0.40,
}


def detect_momentum(
    ret_7d: float,
    ret_14d: float,
    bounce_7: float,
    config: MomentumConfig,
) -> str:
    """
    判定当前动量状态。

    Args:
        ret_7d: 7 日收益率（如 -0.15 表示跌 15%）
        ret_14d: 14 日收益率
        bounce_7: 当前价距 7 日最低点的反弹幅度
        config: 币种特定的阈值配置

    Returns:
        'STABLE' | 'STABILIZING' | 'FALLING'
    """
    is_knife = (ret_7d < config.knife_7d) or (ret_14d < config.knife_14d)
    has_bounce = bounce_7 >= config.bounce_min

    if is_knife and not has_bounce:
        return "FALLING"
    elif is_knife and has_bounce:
        return "STABILIZING"
    else:
        return "STABLE"


def get_momentum_multiplier(momentum: str) -> float:
    """获取动量状态对应的执行倍数。"""
    return MOMENTUM_MULTIPLIERS.get(momentum, 1.0)
