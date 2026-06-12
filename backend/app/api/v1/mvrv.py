"""
MVRV-Z proxy API.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.database import get_main_session
from app.core.redis_client import cache_get, cache_set
from app.engine.mvrv import compute_mvrv_z
from app.service.entitlement_service import require_mvrv

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mvrv", tags=["MVRV"])

COINGECKO_IDS = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
BINANCE_SYMBOLS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}


def _fetch_coingecko_markets(settings) -> dict[str, dict[str, Any]]:
    ids = ",".join(COINGECKO_IDS.values())
    params = {
        "vs_currency": "usd",
        "ids": ids,
        "order": "market_cap_desc",
        "per_page": 10,
        "sparkline": "false",
    }
    headers = {}
    if settings.coingecko_api_key:
        headers["x-cg-demo-api-key"] = settings.coingecko_api_key

    response = requests.get(
        "https://api.coingecko.com/api/v3/coins/markets",
        params=params,
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    return {item["symbol"].upper(): item for item in response.json()}


def _fetch_binance_price(symbol: str) -> float | None:
    binance_symbol = BINANCE_SYMBOLS.get(symbol)
    if not binance_symbol:
        return None

    try:
        response = requests.get(
            "https://api.binance.com/api/v3/avgPrice",
            params={"symbol": binance_symbol},
            timeout=6,
        )
        response.raise_for_status()
        return float(response.json()["price"])
    except Exception as exc:
        logger.warning("Binance price fallback used for %s: %s", symbol, exc)
        return None


def _fetch_glassnode_mvrv_z(symbol: str, settings) -> float | None:
    if not settings.glassnode_api_key:
        return None

    try:
        response = requests.get(
            "https://api.glassnode.com/v1/metrics/market/mvrv_z_score",
            params={"a": symbol, "api_key": settings.glassnode_api_key},
            timeout=10,
        )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            return None
        return float(rows[-1]["v"])
    except Exception as exc:
        logger.warning("Glassnode MVRV-Z unavailable for %s: %s", symbol, exc)
        return None


def _extract_metric_value(rows: list[dict[str, Any]], field: str) -> float | None:
    for row in reversed(rows):
        for key in (field, "value", "v"):
            value = row.get(key)
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value)
                except ValueError:
                    continue

        for key, value in row.items():
            if key.lower() in {"time", "timestamp", "date", "height"}:
                continue
            if isinstance(value, (int, float)):
                return float(value)
    return None


def _fetch_researchbitcoin_mvrv_z(symbol: str, settings) -> float | None:
    if symbol != "BTC" or not settings.researchbitcoin_api_token:
        return None

    from_time = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
    try:
        response = requests.get(
            "https://api.researchbitcoin.net/v2/market_value_to_realized_value/mvrv_z",
            params={
                "resolution": "d1",
                "from_time": from_time,
                "output_format": "json",
            },
            headers={"X-API-Token": settings.researchbitcoin_api_token},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", [])
        if not isinstance(data, list):
            return None
        return _extract_metric_value(data, "mvrv_z")
    except Exception as exc:
        logger.warning("ResearchBitcoin MVRV-Z unavailable for %s: %s", symbol, exc)
        return None


def _fetch_official_mvrv_z(symbol: str, settings) -> tuple[float | None, str | None]:
    researchbitcoin_value = _fetch_researchbitcoin_mvrv_z(symbol, settings)
    if researchbitcoin_value is not None:
        return researchbitcoin_value, "ResearchBitcoin API"

    glassnode_value = _fetch_glassnode_mvrv_z(symbol, settings)
    if glassnode_value is not None:
        return glassnode_value, "Glassnode API"

    return None, None


@router.get("")
async def get_mvrv_data(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    """
    Return MVRV-Z proxy values.

    When GLASSNODE_API_KEY is configured, return Glassnode's official MVRV-Z.
    Otherwise fall back to Binance spot average price and local OHLCV history
    for a standard-formula proxy.
    """
    await require_mvrv(session, user)
    settings = get_settings()
    cache_key = "mvrv_data_v2"

    cached = await cache_get(cache_key)
    if cached:
        return {"ok": True, "data": cached}

    try:
        cg_map = _fetch_coingecko_markets(settings)
    except Exception as exc:
        logger.warning("CoinGecko metadata unavailable for MVRV-Z proxy: %s", exc)
        cg_map = {}

    results = []
    for symbol in COINGECKO_IDS:
        csv_path = settings.data_files.get(symbol)
        if not csv_path or not csv_path.exists():
            continue

        item = cg_map.get(symbol, {})
        binance_price = _fetch_binance_price(symbol)
        current_price = binance_price or item.get("current_price", 0)
        supply = item.get("circulating_supply", 0) or 0
        official_mvrv_z, official_source = _fetch_official_mvrv_z(symbol, settings)
        mvrv = compute_mvrv_z(
            csv_path=csv_path,
            symbol=symbol,
            current_price=current_price,
            circulating_supply=supply,
        )

        market_cap = item.get("market_cap") or (mvrv.current_price * supply if supply else 0)
        results.append({
            "symbol": symbol,
            "mvrv_z": round(official_mvrv_z if official_mvrv_z is not None else mvrv.mvrv_z, 4),
            "market_cap": market_cap,
            "realized_cap": round(mvrv.realized_cap, 2),
            "realized_price": round(mvrv.realized_price, 4),
            "current_price": round(mvrv.current_price, 4),
            "rank": item.get("market_cap_rank", 0),
            "vol_24h": item.get("total_volume", 0),
            "supply": supply,
            "funding": None,
            "depth": None,
            "source": official_source if official_mvrv_z is not None else ("Binance avgPrice + local OHLCV proxy" if binance_price else "CoinGecko/current CSV fallback + local OHLCV proxy"),
            "model": "official_onchain_mvrv_z_score" if official_mvrv_z is not None else mvrv.model,
        })

    if results:
        await cache_set(cache_key, results, 600)

    return {"ok": True, "data": results}
