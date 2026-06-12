"""
Kenne Index 信号计算引擎。

核心公式:
    Kenne Index = (当前价格 / 200日几何均线) × (当前价格 / 幂律增长估值)
    幂律估值    = 10 ^ (slope × log10(距创世天数) + intercept)

合并了原 kenne_index.py:analyze() 和 main.py:compute_signal() 的重复逻辑。
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import gmean

from app.engine.momentum import MomentumConfig, detect_momentum, get_momentum_multiplier
from app.engine.power_law import refit_power_law

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CoinProfile:
    """
    币种配置参数。

    硬编码值作为回退默认值，运行时通过幂律重拟合覆盖。
    """
    symbol: str
    slope: float
    intercept: float
    genesis: str         # 创世日期 YYYY-MM-DD
    buy_thresh: float    # 极低估阈值（<此值触发 2x）
    dca_thresh: float    # 定投上沿（>此值停止）
    momentum: MomentumConfig
    r2: float
    data_years: float


# ─── 默认币种配置 ──────────────────────────────────────────────────

COIN_PROFILES: dict[str, CoinProfile] = {
    "BTC": CoinProfile(
        symbol="BTC", slope=4.7777, intercept=-13.1486,
        genesis="2009-01-03", buy_thresh=0.45, dca_thresh=1.20,
        momentum=MomentumConfig(knife_7d=-0.15, knife_14d=-0.25, bounce_min=0.05),
        r2=0.78, data_years=15,
    ),
    "ETH": CoinProfile(
        symbol="ETH", slope=1.9872, intercept=-3.5997,
        genesis="2015-07-30", buy_thresh=0.45, dca_thresh=1.20,
        momentum=MomentumConfig(knife_7d=-0.15, knife_14d=-0.25, bounce_min=0.05),
        r2=0.58, data_years=10,
    ),
    "SOL": CoinProfile(
        symbol="SOL", slope=1.4446, intercept=-2.5934,
        genesis="2020-03-16", buy_thresh=0.45, dca_thresh=1.50,
        momentum=MomentumConfig(knife_7d=-0.13, knife_14d=-0.22, bounce_min=0.07),
        r2=0.53, data_years=5.5,
    ),
}


@dataclass
class SignalResult:
    """信号计算结果。"""
    symbol: str
    price: float
    cost_200: float
    valuation: float
    kenne_index: float
    zone: str
    momentum: str
    ret_7d: float
    ret_14d: float
    base_mult: float
    final_mult: float
    score: int
    pct_rank: float
    pct: dict[str, float]
    slope: float
    r2: float
    data_years: float
    date: str
    error: str | None = None


def compute_signal(csv_path: Path, symbol: str) -> SignalResult:
    """
    计算指定币种的 Kenne Index 信号。

    完整流程：
    1. 读取 CSV → 日线聚合
    2. 幂律重拟合（slope, intercept, R²）
    3. 计算幂律估值 + 200 日几何均线
    4. 计算 Kenne Index 值
    5. 动量过滤（STABLE / STABILIZING / FALLING）
    6. 确定执行倍数和区间
    7. 综合评分

    Args:
        csv_path: 4H K 线 CSV 文件路径
        symbol: 币种符号（BTC / ETH / SOL）

    Returns:
        SignalResult，如发生错误则 error 字段非空
    """
    symbol = symbol.upper()
    profile = COIN_PROFILES.get(symbol)
    if not profile:
        return SignalResult(
            symbol=symbol, price=0, cost_200=0, valuation=0,
            kenne_index=0, zone="", momentum="", ret_7d=0, ret_14d=0,
            base_mult=0, final_mult=0, score=0, pct_rank=0, pct={},
            slope=0, r2=0, data_years=0, date="",
            error=f"不支持的币种: {symbol}",
        )

    if not csv_path.exists():
        return SignalResult(
            symbol=symbol, price=0, cost_200=0, valuation=0,
            kenne_index=0, zone="", momentum="", ret_7d=0, ret_14d=0,
            base_mult=0, final_mult=0, score=0, pct_rank=0, pct={},
            slope=0, r2=0, data_years=0, date="",
            error="CSV 数据文件不存在",
        )

    try:
        df = pd.read_csv(csv_path)
        df["Open time"] = pd.to_datetime(df["Open time"], format="mixed")
        df.set_index("Open time", inplace=True)
        df_d = df.resample("D").agg({"Close": "last", "Low": "min", "High": "max"}).dropna()

        genesis = pd.to_datetime(profile.genesis)
        df_d["days"] = (df_d.index - genesis).days
        df_d = df_d[df_d["days"] > 0]

        # ── 幂律重拟合 ────────────────────────────────────────
        refit = refit_power_law(df_d, profile.slope, profile.intercept, profile.r2)
        slope = refit.slope
        intercept = refit.intercept
        r2 = refit.r_squared
        data_years = round(len(df_d) / 365, 1)

        # ── Kenne Index 核心计算 ──────────────────────────────
        df_d["valuation"] = 10 ** (slope * np.log10(df_d["days"]) + intercept)
        df_d["cost_200"] = df_d["Close"].rolling(200).apply(gmean, raw=True)
        df_d["kenne_index"] = (df_d["Close"] / df_d["cost_200"]) * (df_d["Close"] / df_d["valuation"])

        # ── 动量指标 ──────────────────────────────────────────
        df_d["ret_7d"] = df_d["Close"].pct_change(7)
        df_d["ret_14d"] = df_d["Close"].pct_change(14)
        df_d["low7"] = df_d["Low"].rolling(7).min()
        df_d["bounce_7"] = (df_d["Close"] - df_d["low7"]) / df_d["low7"]
        df_d = df_d.dropna()

        if df_d.empty:
            return SignalResult(
                symbol=symbol, price=0, cost_200=0, valuation=0,
                kenne_index=0, zone="", momentum="", ret_7d=0, ret_14d=0,
                base_mult=0, final_mult=0, score=0, pct_rank=0, pct={},
                slope=slope, r2=r2, data_years=data_years, date="",
                error="数据不足（需至少 200 日）",
            )

        row = df_d.iloc[-1]
        ki = float(row["kenne_index"])

        # ── 动量过滤 ──────────────────────────────────────────
        momentum_state = detect_momentum(
            ret_7d=float(row["ret_7d"]),
            ret_14d=float(row["ret_14d"]),
            bounce_7=float(row["bounce_7"]),
            config=profile.momentum,
        )

        # ── 执行倍数 ──────────────────────────────────────────
        if ki < profile.buy_thresh:
            base_mult = 2.0
        elif ki <= profile.dca_thresh:
            base_mult = 1.0
        else:
            base_mult = 0.0
        final_mult = base_mult * get_momentum_multiplier(momentum_state)

        # ── 综合评分 ──────────────────────────────────────────
        if ki < profile.buy_thresh:
            ahr_score = 50
        elif ki <= profile.dca_thresh:
            ratio = 1 - (ki - profile.buy_thresh) / (profile.dca_thresh - profile.buy_thresh)
            ahr_score = int(10 + 30 * ratio)
        else:
            ahr_score = max(0, 10 - int((ki - profile.dca_thresh) * 5))

        momentum_bonus = {"STABLE": 50, "STABILIZING": 25, "FALLING": 0}
        score = min(100, ahr_score + momentum_bonus.get(momentum_state, 0))

        # ── 分位统计 ──────────────────────────────────────────
        pct_rank = float((df_d["kenne_index"] < ki).mean() * 100)
        pct_quantiles = df_d["kenne_index"].quantile([0.05, 0.25, 0.50, 0.75]).to_dict()

        # ── 区间判定 ──────────────────────────────────────────
        if ki < profile.buy_thresh:
            zone = "极低估"
        elif ki <= profile.dca_thresh:
            zone = "定投区"
        else:
            zone = "观望区"

        return SignalResult(
            symbol=symbol,
            price=float(row["Close"]),
            cost_200=float(row["cost_200"]),
            valuation=float(row["valuation"]),
            kenne_index=round(ki, 4),
            zone=zone,
            momentum=momentum_state,
            ret_7d=round(float(row["ret_7d"]) * 100, 2),
            ret_14d=round(float(row["ret_14d"]) * 100, 2),
            base_mult=base_mult,
            final_mult=final_mult,
            score=score,
            pct_rank=round(pct_rank, 1),
            pct={str(k): round(v, 4) for k, v in pct_quantiles.items()},
            slope=round(slope, 4),
            r2=round(r2, 4),
            data_years=data_years,
            date=row.name.strftime("%Y-%m-%d"),
        )

    except Exception as exc:
        logger.error("[%s] 信号计算异常: %s", symbol, exc)
        return SignalResult(
            symbol=symbol, price=0, cost_200=0, valuation=0,
            kenne_index=0, zone="", momentum="", ret_7d=0, ret_14d=0,
            base_mult=0, final_mult=0, score=0, pct_rank=0, pct={},
            slope=0, r2=0, data_years=0, date="",
            error=str(exc),
        )


def compute_signal_with_history(csv_path: Path, symbol: str, history_days: int = 180) -> dict:
    """
    计算指定币种的 Kenne Index 信号并包含 180 天的历史走势数据。
    """
    symbol = symbol.upper()
    profile = COIN_PROFILES.get(symbol)
    if not profile:
        return {"error": f"不支持的币种: {symbol}", "symbol": symbol}
    if not csv_path.exists():
        return {"error": "CSV 数据文件不存在", "symbol": symbol}

    try:
        df = pd.read_csv(csv_path)
        df["Open time"] = pd.to_datetime(df["Open time"], format="mixed")
        df.set_index("Open time", inplace=True)
        df_d = df.resample("D").agg({"Close": "last", "Low": "min", "High": "max"}).dropna()

        genesis = pd.to_datetime(profile.genesis)
        df_d["days"] = (df_d.index - genesis).days
        df_d = df_d[df_d["days"] > 0]

        # ── 幂律重拟合 ────────────────────────────────────────
        refit = refit_power_law(df_d, profile.slope, profile.intercept, profile.r2)
        slope = refit.slope
        intercept = refit.intercept
        r2 = refit.r_squared
        data_years = round(len(df_d) / 365, 1)

        # ── Kenne Index 核心计算 ──────────────────────────────
        df_d["valuation"] = 10 ** (slope * np.log10(df_d["days"]) + intercept)
        df_d["cost_200"] = df_d["Close"].rolling(200).apply(gmean, raw=True)
        df_d["kenne_index"] = (df_d["Close"] / df_d["cost_200"]) * (df_d["Close"] / df_d["valuation"])

        # ── 动量指标 ──────────────────────────────────────────
        df_d["ret_7d"] = df_d["Close"].pct_change(7)
        df_d["ret_14d"] = df_d["Close"].pct_change(14)
        df_d["low7"] = df_d["Low"].rolling(7).min()
        df_d["bounce_7"] = (df_d["Close"] - df_d["low7"]) / df_d["low7"]
        df_d = df_d.dropna()

        if df_d.empty:
            return {"error": "数据不足（需至少 200 日）", "symbol": symbol}

        row = df_d.iloc[-1]
        ki = float(row["kenne_index"])

        # ── 动量过滤 ──────────────────────────────────────────
        momentum_state = detect_momentum(
            ret_7d=float(row["ret_7d"]),
            ret_14d=float(row["ret_14d"]),
            bounce_7=float(row["bounce_7"]),
            config=profile.momentum,
        )

        # ── 执行倍数 ──────────────────────────────────────────
        if ki < profile.buy_thresh:
            base_mult = 2.0
        elif ki <= profile.dca_thresh:
            base_mult = 1.0
        else:
            base_mult = 0.0
        final_mult = base_mult * get_momentum_multiplier(momentum_state)

        # ── 综合评分 ──────────────────────────────────────────
        if ki < profile.buy_thresh:
            ahr_score = 50
        elif ki <= profile.dca_thresh:
            ratio = 1 - (ki - profile.buy_thresh) / (profile.dca_thresh - profile.buy_thresh)
            ahr_score = int(10 + 30 * ratio)
        else:
            ahr_score = max(0, 10 - int((ki - profile.dca_thresh) * 5))

        momentum_bonus = {"STABLE": 50, "STABILIZING": 25, "FALLING": 0}
        score = min(100, ahr_score + momentum_bonus.get(momentum_state, 0))

        # ── 分位统计 ──────────────────────────────────────────
        pct_rank = float((df_d["kenne_index"] < ki).mean() * 100)
        pct_quantiles = df_d["kenne_index"].quantile([0.05, 0.25, 0.50, 0.75]).to_dict()

        # ── 区间判定 ──────────────────────────────────────────
        if ki < profile.buy_thresh:
            zone = "极低估"
        elif ki <= profile.dca_thresh:
            zone = "定投区"
        else:
            zone = "观望区"

        # 提取历史走势
        df_history = df_d.tail(history_days)
        history_list = []
        for idx, r in df_history.iterrows():
            history_list.append({
                "date": idx.strftime("%Y-%m-%d"),
                "price": round(float(r["Close"]), 2),
                "kenne_index": round(float(r["kenne_index"]), 4),
                "valuation": round(float(r["valuation"]), 2),
                "cost_200": round(float(r["cost_200"]), 2) if not pd.isna(r["cost_200"]) else 0.0
            })

        return {
            "symbol": symbol,
            "price": float(row["Close"]),
            "cost_200": float(row["cost_200"]),
            "valuation": float(row["valuation"]),
            "kenne_index": round(ki, 4),
            "zone": zone,
            "momentum": momentum_state,
            "ret_7d": round(float(row["ret_7d"]) * 100, 2),
            "ret_14d": round(float(row["ret_14d"]) * 100, 2),
            "base_mult": base_mult,
            "final_mult": final_mult,
            "score": score,
            "pct_rank": round(pct_rank, 1),
            "pct": {str(k): round(v, 4) for k, v in pct_quantiles.items()},
            "slope": round(slope, 4),
            "r2": round(r2, 4),
            "data_years": data_years,
            "date": row.name.strftime("%Y-%m-%d"),
            "history": history_list,
            "error": None
        }
    except Exception as exc:
        logger.error("[%s] 信号计算历史异常: %s", symbol, exc)
        return {"error": str(exc), "symbol": symbol}
