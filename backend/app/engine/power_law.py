"""
幂律增长模型重拟合引擎。

模型: log10(price) = slope × log10(days_since_genesis) + intercept

从原 kenne_index.py:_refit() 提取，去除 print 日志，改为纯函数设计。
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)

# NOTE: 数据量低于此天数时不执行重拟合，使用默认参数
MIN_DAYS_FOR_REFIT = 365


@dataclass(frozen=True)
class RefitResult:
    """幂律重拟合结果。"""
    slope: float
    intercept: float
    r_squared: float
    data_points: int
    refitted: bool  # 是否实际执行了重拟合（数据不足时返回 False）


def refit_power_law(
    daily_df: pd.DataFrame,
    default_slope: float,
    default_intercept: float,
    default_r2: float,
) -> RefitResult:
    """
    用全量历史日线数据重拟合幂律参数。

    使用 scipy.stats.linregress 对 log10(days) vs log10(price) 做线性回归。
    数据不足 MIN_DAYS_FOR_REFIT 天时，返回默认参数不执行回归。

    Args:
        daily_df: 至少包含 'days'（>0）和 'Close' 列的 DataFrame
        default_slope: 默认斜率（回退值）
        default_intercept: 默认截距（回退值）
        default_r2: 默认 R²（回退值）

    Returns:
        RefitResult 包含拟合参数和元信息
    """
    valid = daily_df[daily_df["days"] > 0].dropna(subset=["Close"])

    if len(valid) < MIN_DAYS_FOR_REFIT:
        logger.debug(
            "数据不足 %d 天（需 %d），使用默认参数",
            len(valid), MIN_DAYS_FOR_REFIT,
        )
        return RefitResult(
            slope=default_slope,
            intercept=default_intercept,
            r_squared=default_r2,
            data_points=len(valid),
            refitted=False,
        )

    log_days = np.log10(valid["days"].values)
    log_prices = np.log10(valid["Close"].values)
    slope, intercept, r_value, _, _ = scipy_stats.linregress(log_days, log_prices)
    r_squared = r_value ** 2

    logger.info(
        "幂律重拟合完成: slope=%.4f intercept=%.4f R²=%.4f (N=%d)",
        slope, intercept, r_squared, len(valid),
    )

    return RefitResult(
        slope=slope,
        intercept=intercept,
        r_squared=r_squared,
        data_points=len(valid),
        refitted=True,
    )
