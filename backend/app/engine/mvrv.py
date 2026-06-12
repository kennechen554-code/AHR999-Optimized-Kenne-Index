"""
MVRV-Z proxy calculation.

True MVRV-Z requires on-chain realized capitalization. This project does not
ship UTXO/account realized-cap data, so the local fallback exposes this as a
proxy: current market value minus a long-window VWAP realized-cap proxy,
normalized by cumulative market value standard deviation.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MvrvResult:
    symbol: str
    mvrv_z: float
    realized_price: float
    realized_cap: float
    current_price: float
    model: str


def compute_mvrv_z(
    csv_path: Path,
    symbol: str,
    current_price: float,
    circulating_supply: float = 0.0,
) -> MvrvResult:
    """
    Compute an MVRV-Z proxy from local OHLCV data.

    Method:
    1. Treat the 1100-day VWAP as a realized-price proxy.
    2. Approximate Market Cap and Realized Cap with the same supply scalar.
    3. Return (market_cap - realized_cap_proxy) / std(market_cap).
    """
    model = "standard_formula_proxy: (market_cap - realized_cap_proxy) / std(market_cap)"

    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            raise ValueError("empty price file")

        closes = pd.to_numeric(df["Close"], errors="coerce")
        volumes = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)
        valid = pd.DataFrame({"close": closes, "volume": volumes}).dropna()
        valid = valid[valid["close"] > 0]
        if len(valid) < 30:
            raise ValueError("not enough price rows")

        current = float(current_price or valid["close"].iloc[-1])
        if current <= 0:
            current = float(valid["close"].iloc[-1])

        # Local data is 4H, so 1100 days is roughly 6600 rows.
        window = min(len(valid), 1100 * 6)
        tail = valid.tail(window)
        if tail["volume"].sum() > 0:
            realized_price = float((tail["close"] * tail["volume"]).sum() / tail["volume"].sum())
        else:
            realized_price = float(tail["close"].mean())

        price_history = pd.concat([valid["close"], pd.Series([current])], ignore_index=True)
        price_std = float(price_history.std(ddof=0))
        z_score = (current - realized_price) / price_std if price_std > 0 else 0.0

        supply = float(circulating_supply or 0)
        return MvrvResult(
            symbol=symbol,
            mvrv_z=float(z_score),
            realized_price=realized_price,
            realized_cap=realized_price * supply if supply > 0 else 0.0,
            current_price=current,
            model=model,
        )
    except Exception as exc:
        logger.error("MVRV-Z proxy calculation failed [%s]: %s", symbol, exc)
        fallback_price = float(current_price or 0)
        return MvrvResult(
            symbol=symbol,
            mvrv_z=0.0,
            realized_price=0.0,
            realized_cap=0.0,
            current_price=fallback_price,
            model=model,
        )
