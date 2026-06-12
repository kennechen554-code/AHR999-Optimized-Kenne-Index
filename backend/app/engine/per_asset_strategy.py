from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from app.engine.kenne_index import COIN_PROFILES

SYMBOLS = ("BTC", "ETH", "SOL")
START_DATE = pd.Timestamp("2018-07-20")
FEE_RATE = 0.001
DEFAULT_MONTHLY_BUDGET = 700.0

REQUIRED_COLUMNS = {"Open time", "Open", "High", "Low", "Close", "Volume"}

PER_ASSET_STRATEGIES: dict[str, dict] = {
    "per_asset_strict_dd": {
        "label": "严格回撤版",
        "asset": {
            "BTC": {
                "interval": 14, "budget_weight": 0.897845872, "deep_thr": 0.4963125106,
                "dca_thr": 1.1108928707, "stop_thr": 1.501143578, "deep_mult": 5.4221275312,
                "dca_mult": 1.084976198, "floor_mult": 0.35, "value_power": 0.75,
                "falling_mult": 0.5368018104, "stabilizing_mult": 0.9088664705,
                "alpha": 1.0865431407, "spend_base": 0.4352207988, "spend_extra": 2.4810100067,
                "max_run_budget_mult": 5.9271551509, "score_cap": 8.2157162429,
                "hard_downtrend_cut": -0.3, "hard_downtrend_mult": 1.0,
                "over_trend_cut": 0.4, "over_trend_mult": 1.0, "ret90_overheat": 1.2,
                "ret90_mult": 0.75,
            },
            "ETH": {
                "interval": 7, "budget_weight": 0.0565204241, "deep_thr": 0.371509835,
                "dca_thr": 0.7876500926, "stop_thr": 1.5853540834, "deep_mult": 4.7098157858,
                "dca_mult": 0.6221228694, "floor_mult": 0.0, "value_power": 0.75,
                "falling_mult": 0.2721477445, "stabilizing_mult": 0.7117464895,
                "alpha": 1.2732619553, "spend_base": 0.1552390098, "spend_extra": 2.1369125381,
                "max_run_budget_mult": 1.0971111835, "score_cap": 5.4054527344,
                "hard_downtrend_cut": -0.45, "hard_downtrend_mult": 0.5,
                "over_trend_cut": 999, "over_trend_mult": 0.0, "ret90_overheat": 1.4,
                "ret90_mult": 0.0,
            },
            "SOL": {
                "interval": 14, "budget_weight": 0.045633704, "deep_thr": 0.3312661591,
                "dca_thr": 0.7273516942, "stop_thr": 1.049354863, "deep_mult": 8.0238715077,
                "dca_mult": 0.6295660133, "floor_mult": 0.05, "value_power": 1.0,
                "falling_mult": 0.025013224, "stabilizing_mult": 0.353090791,
                "alpha": 0.2114192315, "spend_base": 0.1255793658, "spend_extra": 2.8965279113,
                "max_run_budget_mult": 4.7853318774, "score_cap": 4.0954338739,
                "hard_downtrend_cut": -999, "hard_downtrend_mult": 0.1,
                "over_trend_cut": 1.2, "over_trend_mult": 0.1, "ret90_overheat": 1.5,
                "ret90_mult": 0.25,
            },
        },
        "cash_catchup_frac": 0.0,
        "cash_catchup_cap": 1.0,
        "reserve_frac": 0.08,
        "reserve_release_score": 5.6120960886,
    },
    "per_asset_balanced_return": {
        "label": "收益优先版",
        "asset": {
            "BTC": {
                "interval": 3, "budget_weight": 0.5666224388, "deep_thr": 0.5062758802,
                "dca_thr": 1.1962920664, "stop_thr": 1.5998873853, "deep_mult": 5.2077331267,
                "dca_mult": 1.3472388821, "floor_mult": 0.35, "value_power": 0.5,
                "falling_mult": 0.2747548954, "stabilizing_mult": 0.961888,
                "alpha": 1.294694097, "spend_base": 0.6626321388, "spend_extra": 2.8949518915,
                "max_run_budget_mult": 3.4771098848, "score_cap": 5.5051903157,
                "hard_downtrend_cut": -0.45, "hard_downtrend_mult": 1.0,
                "over_trend_cut": 0.9, "over_trend_mult": 0.25, "ret90_overheat": 999,
                "ret90_mult": 0.0,
            },
            "ETH": {
                "interval": 14, "budget_weight": 0.3493568307, "deep_thr": 0.3805464888,
                "dca_thr": 1.1902302579, "stop_thr": 1.6710289965, "deep_mult": 4.3455656993,
                "dca_mult": 0.5022774374, "floor_mult": 0.05, "value_power": 0.25,
                "falling_mult": 0.106544555, "stabilizing_mult": 0.9344595489,
                "alpha": 1.0800530701, "spend_base": 0.5451803704, "spend_extra": 3.2527573275,
                "max_run_budget_mult": 3.9218792044, "score_cap": 3.9643848982,
                "hard_downtrend_cut": -0.3, "hard_downtrend_mult": 1.0,
                "over_trend_cut": 0.5, "over_trend_mult": 0.0, "ret90_overheat": 0.9,
                "ret90_mult": 0.5,
            },
            "SOL": {
                "interval": 7, "budget_weight": 0.0840207304, "deep_thr": 0.4325891594,
                "dca_thr": 1.1079305582, "stop_thr": 1.350857292, "deep_mult": 7.7826385382,
                "dca_mult": 0.6915648729, "floor_mult": 0.0, "value_power": 0.5,
                "falling_mult": 0.3959704221, "stabilizing_mult": 0.3241885496,
                "alpha": 0.620434546, "spend_base": 0.3167177328, "spend_extra": 3.6630536204,
                "max_run_budget_mult": 1.6780004946, "score_cap": 5.3294869982,
                "hard_downtrend_cut": -0.65, "hard_downtrend_mult": 0.5,
                "over_trend_cut": 0.8, "over_trend_mult": 0.0, "ret90_overheat": 1.5,
                "ret90_mult": 0.6,
            },
        },
        "cash_catchup_frac": 0.0,
        "cash_catchup_cap": 1.0,
        "reserve_frac": 0.0,
        "reserve_release_score": 4.680612813,
    },
}

DEFAULT_STRATEGY_MODE = "per_asset_strict_dd"

STRATEGY_PUBLIC_COPY: dict[str, dict[str, str]] = {
    "per_asset_strict_dd": {
        "risk_level": "稳健",
        "description": "默认实盘策略。优先控制最大回撤，保留现金缓冲，只在高置信估值区间释放更多预算。",
    },
    "per_asset_balanced_return": {
        "risk_level": "进取",
        "description": "收益与资金利用率优先。提高 ETH/SOL 权重和部署频率，适合愿意承受更深回撤的回测分析。",
    },
}


def strategy_metadata() -> list[dict[str, object]]:
    """Return frontend-facing strategy metadata from the executable strategy source."""
    strategies: list[dict[str, object]] = []
    for mode, params in PER_ASSET_STRATEGIES.items():
        copy = STRATEGY_PUBLIC_COPY.get(mode, {})
        assets = []
        for symbol, asset_params in params["asset"].items():
            assets.append({
                "symbol": symbol,
                "interval_days": int(asset_params["interval"]),
                "budget_weight": round(float(asset_params["budget_weight"]), 6),
                "deep_threshold": round(float(asset_params["deep_thr"]), 6),
                "dca_threshold": round(float(asset_params["dca_thr"]), 6),
                "stop_threshold": round(float(asset_params["stop_thr"]), 6),
                "falling_multiplier": round(float(asset_params["falling_mult"]), 6),
                "stabilizing_multiplier": round(float(asset_params["stabilizing_mult"]), 6),
            })
        strategies.append({
            "mode": mode,
            "label": str(params["label"]),
            "default": mode == DEFAULT_STRATEGY_MODE,
            "risk_level": copy.get("risk_level", ""),
            "description": copy.get("description", ""),
            "reserve_frac": round(float(params["reserve_frac"]), 6),
            "reserve_release_score": round(float(params["reserve_release_score"]), 6),
            "assets": assets,
        })
    return strategies


@dataclass
class StrategyOrder:
    symbol: str
    usdt_amount: float
    score: float
    kenne_index: float
    momentum: str
    price: float


def normalize_strategy_mode(mode: str | None) -> str:
    return mode if mode in PER_ASSET_STRATEGIES else DEFAULT_STRATEGY_MODE


def read_daily(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"CSV 缺少列: {', '.join(sorted(missing))}")
    df["Open time"] = pd.to_datetime(df["Open time"], format="mixed")
    df = df.set_index("Open time").sort_index()
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.resample("D").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna(subset=["Close", "Low", "High"])


def compute_features(symbol: str, csv_path: Path) -> pd.DataFrame:
    profile = COIN_PROFILES[symbol]
    df = read_daily(csv_path).copy()
    genesis = pd.to_datetime(profile.genesis)
    df["days"] = (df.index - genesis).days
    df = df[df["days"] > 0].copy()

    x = np.log10(df["days"].to_numpy(float))
    y = np.log10(df["Close"].to_numpy(float))
    n = np.arange(1, len(df) + 1, dtype=float)
    sx, sy = np.cumsum(x), np.cumsum(y)
    sxx, sxy = np.cumsum(x * x), np.cumsum(x * y)
    denom = n * sxx - sx * sx

    slope = np.full(len(df), profile.slope, dtype=float)
    intercept = np.full(len(df), profile.intercept, dtype=float)
    ok = (n >= 365) & (np.abs(denom) > 1e-12)
    slope[ok] = (n[ok] * sxy[ok] - sx[ok] * sy[ok]) / denom[ok]
    intercept[ok] = (sy[ok] - slope[ok] * sx[ok]) / n[ok]

    close = df["Close"].astype(float)
    df["valuation"] = 10 ** (slope * np.log10(df["days"].to_numpy(float)) + intercept)
    df["cost_200"] = np.exp(np.log(close).rolling(200).mean())
    df["kenne"] = (close / df["cost_200"]) * (close / df["valuation"])
    df["ret_7d"] = close.pct_change(7)
    df["ret_14d"] = close.pct_change(14)
    df["ret_90d"] = close.pct_change(90)
    df["low7"] = df["Low"].rolling(7).min()
    df["bounce_7"] = (close - df["low7"]) / df["low7"]
    df["ma200"] = close.rolling(200).mean()
    df["trend200"] = close / df["ma200"] - 1
    return df.dropna(subset=["kenne"])


def _momentum_state(symbol: str, row: pd.Series) -> str | None:
    profile = COIN_PROFILES[symbol]
    if any(pd.isna(row.get(k)) for k in ["ret_7d", "ret_14d", "bounce_7"]):
        return None
    is_knife = row["ret_7d"] < profile.momentum.knife_7d or row["ret_14d"] < profile.momentum.knife_14d
    has_bounce = row["bounce_7"] >= profile.momentum.bounce_min
    if is_knife and not has_bounce:
        return "FALLING"
    if is_knife and has_bounce:
        return "STABILIZING"
    return "STABLE"


def asset_score(symbol: str, row: pd.Series, params: dict) -> float:
    p = params["asset"][symbol]
    ki = row.get("kenne")
    if pd.isna(ki) or ki <= 0:
        return 0.0

    if ki <= p["deep_thr"]:
        base = p["deep_mult"] * ((p["deep_thr"] / ki) ** p["value_power"] if p["value_power"] > 0 else 1.0)
    elif ki <= p["dca_thr"]:
        t = (ki - p["deep_thr"]) / max(1e-9, p["dca_thr"] - p["deep_thr"])
        base = p["deep_mult"] * (1 - t) + p["dca_mult"] * t
    elif ki <= p["stop_thr"]:
        t = (ki - p["dca_thr"]) / max(1e-9, p["stop_thr"] - p["dca_thr"])
        base = p["dca_mult"] * (1 - t) + p["floor_mult"] * t
    else:
        base = 0.0

    base = min(base, p["score_cap"])
    momentum = _momentum_state(symbol, row)
    if momentum is None:
        return 0.0
    if momentum == "FALLING":
        base *= p["falling_mult"]
    elif momentum == "STABILIZING":
        base *= p["stabilizing_mult"]

    trend200 = row.get("trend200")
    if pd.notna(trend200):
        if trend200 < p["hard_downtrend_cut"] and momentum == "FALLING":
            base *= p["hard_downtrend_mult"]
        if trend200 > p["over_trend_cut"] and ki > p["dca_thr"]:
            base *= p["over_trend_mult"]

    ret90 = row.get("ret_90d")
    if pd.notna(ret90) and ret90 > p["ret90_overheat"]:
        base *= p["ret90_mult"]

    return max(0.0, base * p["alpha"])


def build_per_asset_orders(data_files: dict, strategy_mode: str, monthly_budget: float) -> list[StrategyOrder]:
    mode = normalize_strategy_mode(strategy_mode)
    params = PER_ASSET_STRATEGIES[mode]
    today = pd.Timestamp.utcnow().tz_localize(None).normalize()
    day_offset = max(0, int((today - START_DATE).days))
    daily = float(monthly_budget or DEFAULT_MONTHLY_BUDGET) / 30.0
    intents: dict[str, float] = {}
    scores: dict[str, float] = {}
    rows: dict[str, pd.Series] = {}

    for symbol in SYMBOLS:
        csv_path = data_files.get(symbol)
        if not csv_path or not Path(csv_path).exists():
            continue
        p = params["asset"][symbol]
        if int(p["interval"]) > 1 and day_offset % int(p["interval"]) != 0:
            continue
        features = compute_features(symbol, Path(csv_path))
        if features.empty:
            continue
        row = features.iloc[-1]
        score = asset_score(symbol, row, params)
        scores[symbol] = score
        rows[symbol] = row
        if score <= 0:
            continue
        scheduled = daily * int(p["interval"]) * p["budget_weight"]
        opp = min(1.0, score / max(1e-9, p["deep_mult"] * p["alpha"]))
        intent = scheduled * (p["spend_base"] + p["spend_extra"] * opp)
        intent = min(intent, p["max_run_budget_mult"] * scheduled)
        if intent > 0:
            intents[symbol] = intent

    if not intents:
        return []

    max_score = max(scores.get(symbol, 0.0) for symbol in intents)
    spendable = daily * (1.0 - params["reserve_frac"])
    if max_score >= params["reserve_release_score"]:
        spendable = daily
    total_intent = sum(intents.values())
    spend = min(total_intent, spendable)
    if spend <= 0:
        return []

    orders: list[StrategyOrder] = []
    for symbol, intent in intents.items():
        gross = round(spend * intent / total_intent, 2)
        if gross < 5:
            continue
        row = rows[symbol]
        orders.append(StrategyOrder(
            symbol=symbol,
            usdt_amount=gross,
            score=round(scores[symbol], 4),
            kenne_index=round(float(row["kenne"]), 4),
            momentum=_momentum_state(symbol, row) or "",
            price=float(row["Close"]),
        ))
    return orders


def _xirr_equal_daily(final_equity: float, n_days: int, daily: float) -> float:
    days = np.arange(n_days, dtype=float)
    final_t = (n_days - 1) / 365.25

    def npv(rate: float) -> float:
        return -daily * np.sum(np.power(1.0 + rate, -days / 365.25)) + final_equity / ((1.0 + rate) ** final_t)

    try:
        return float(brentq(npv, -0.9999, 10.0, maxiter=100))
    except Exception:
        return float("nan")


def run_backtest(data_files: dict[str, Path], strategy_mode: str, start: str, end: str, monthly_budget: float) -> dict:
    mode = normalize_strategy_mode(strategy_mode)
    params = PER_ASSET_STRATEGIES[mode]
    daily = float(monthly_budget or DEFAULT_MONTHLY_BUDGET) / 30.0
    features = {symbol: compute_features(symbol, path) for symbol, path in data_files.items()}
    if not features:
        raise ValueError("至少需要上传一个有效 CSV")
    min_end = min(df.index.max() for df in features.values())
    start_ts = max(pd.Timestamp(start), START_DATE)
    end_ts = min(pd.Timestamp(end), min_end)
    if end_ts <= start_ts:
        raise ValueError("回测日期范围无效")

    dates = pd.date_range(start_ts, end_ts, freq="D")
    panel = {symbol: df.reindex(dates).ffill() for symbol, df in features.items()}
    cash = 0.0
    qty = {symbol: 0.0 for symbol in features}
    shares = 0.0
    total_contrib = total_spent = 0.0
    trades = 0
    deploy = {symbol: 0.0 for symbol in features}
    navs: list[float] = []
    equities: list[float] = []
    utils: list[float] = []

    for i, date_value in enumerate(dates):
        prices = {symbol: panel[symbol].iloc[i]["Close"] for symbol in features}
        equity_before = cash + sum(qty[s] * prices[s] for s in features if pd.notna(prices[s]))
        nav_before = equity_before / shares if shares > 0 else 1.0
        cash += daily
        total_contrib += daily
        shares += daily / nav_before if nav_before > 0 else daily

        intents: dict[str, float] = {}
        scores: dict[str, float] = {}
        if i > 0:
            for symbol in features:
                p = params["asset"][symbol]
                interval = int(p["interval"])
                eligible = interval <= 1 or i % interval == 0
                if not eligible or pd.isna(prices[symbol]):
                    continue
                row = panel[symbol].iloc[i - 1]
                score = asset_score(symbol, row, params)
                scores[symbol] = score
                if score <= 0:
                    continue
                scheduled = daily * interval * p["budget_weight"]
                opp = min(1.0, score / max(1e-9, p["deep_mult"] * p["alpha"]))
                intent = scheduled * (p["spend_base"] + p["spend_extra"] * opp)
                intent = min(intent, p["max_run_budget_mult"] * scheduled)
                if intent > 0:
                    intents[symbol] = intent

        if intents and cash > 0:
            total_intent = sum(intents.values())
            max_score = max(scores.get(symbol, 0.0) for symbol in intents)
            spendable = cash * (1.0 - params["reserve_frac"])
            if max_score >= params["reserve_release_score"]:
                spendable = cash
            spend = min(total_intent, spendable, cash)
            for symbol, intent in intents.items():
                gross = spend * intent / total_intent
                price = prices[symbol]
                if gross > 0 and pd.notna(price):
                    qty[symbol] += (gross * (1.0 - FEE_RATE)) / price
                    cash -= gross
                    total_spent += gross
                    deploy[symbol] += gross
                    trades += 1

        equity = cash + sum(qty[s] * prices[s] for s in features if pd.notna(prices[s]))
        invested = equity - cash
        nav = equity / shares if shares > 0 else 1.0
        equities.append(float(equity))
        navs.append(float(nav))
        utils.append(float(invested / equity if equity > 0 else 0.0))

    nav_arr = np.array(navs)
    equity_arr = np.array(equities)
    peak = np.maximum.accumulate(nav_arr)
    dd_arr = nav_arr / peak - 1.0
    n_days = len(dates)
    final_equity = float(equity_arr[-1])
    total_dep = sum(deploy.values())

    series_step = max(1, math.ceil(len(dates) / 240))
    series = [
        {
            "date": dates[i].strftime("%Y-%m-%d"),
            "equity": round(equities[i], 2),
            "nav": round(navs[i], 6),
            "drawdown": round(float(dd_arr[i]), 6),
        }
        for i in range(0, len(dates), series_step)
    ]
    if series[-1]["date"] != dates[-1].strftime("%Y-%m-%d"):
        i = len(dates) - 1
        series.append({"date": dates[i].strftime("%Y-%m-%d"), "equity": round(equities[i], 2), "nav": round(navs[i], 6), "drawdown": round(float(dd_arr[i]), 6)})

    return {
        "strategy_mode": mode,
        "strategy_label": params["label"],
        "start": start_ts.strftime("%Y-%m-%d"),
        "end": end_ts.strftime("%Y-%m-%d"),
        "final_equity": round(final_equity, 2),
        "total_contrib": round(total_contrib, 2),
        "profit": round(final_equity - total_contrib, 2),
        "total_return": round(final_equity / total_contrib - 1.0, 6) if total_contrib else 0.0,
        "xirr": round(_xirr_equal_daily(final_equity, n_days, daily), 6),
        "max_drawdown": round(float(np.min(dd_arr)), 6),
        "avg_utilization": round(float(np.mean(utils)), 6),
        "spent_ratio": round(total_spent / total_contrib, 6) if total_contrib else 0.0,
        "cash_end": round(cash, 2),
        "trades": trades,
        "deploy_weights": {symbol: round(deploy[symbol] / total_dep, 6) if total_dep else 0.0 for symbol in features},
        "series": series,
    }


def write_uploads_to_temp(files: Iterable[tuple[str, bytes]]) -> tuple[TemporaryDirectory, dict[str, Path]]:
    tmp = TemporaryDirectory()
    paths: dict[str, Path] = {}
    for name, data in files:
        upper = name.upper()
        symbol = next((item for item in SYMBOLS if item in upper), None)
        if not symbol:
            raise ValueError(f"无法从文件名识别币种: {name}")
        path = Path(tmp.name) / f"{symbol}.csv"
        path.write_bytes(data)
        read_daily(path)
        paths[symbol] = path
    return tmp, paths
