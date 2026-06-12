"""
交易所服务 — 基于 ccxt 的统一交易所封装。

替代原 kenne_dca.py 中的手写 OKXClient，
通过 ccxt 统一支持 8 家交易所。
"""

from __future__ import annotations

import importlib
import logging
from types import ModuleType
from typing import TYPE_CHECKING, Any

from app.core.exceptions import ExchangeError
from app.core.security import decrypt_value

if TYPE_CHECKING:
    import ccxt.async_support as ccxt

logger = logging.getLogger(__name__)

# 交易所 ID → 显示名映射
EXCHANGE_MAP: dict[str, str] = {
    "okx": "OKX",
    "binance": "Binance",
    "bybit": "Bybit",
    "bitget": "Bitget",
    "gateio": "Gate.io",
    "kucoin": "KuCoin",
    "htx": "HTX",
    "mexc": "MEXC",
}

# 需要 passphrase 的交易所
PASSPHRASE_EXCHANGES = {"okx", "bitget", "kucoin"}


def _get_ccxt_module() -> ModuleType:
    return importlib.import_module("ccxt.async_support")


def create_exchange(
    exchange_id: str,
    api_key_encrypted: str,
    api_secret_encrypted: str,
    api_passphrase_encrypted: str = "",
    simulated: bool = True,
) -> ccxt.Exchange:
    """
    创建 ccxt 交易所实例。

    Args:
        exchange_id: 交易所 ID（如 'okx'）
        api_key_encrypted: AES 加密后的 API Key
        api_secret_encrypted: AES 加密后的 API Secret
        api_passphrase_encrypted: AES 加密后的 Passphrase（部分交易所需要）
        simulated: 是否使用模拟盘

    Returns:
        ccxt 交易所实例

    Raises:
        ExchangeError: 不支持的交易所
    """
    if exchange_id not in EXCHANGE_MAP:
        raise ExchangeError(f"不支持的交易所: {exchange_id}")

    ccxt_module = _get_ccxt_module()
    exchange_class = getattr(ccxt_module, exchange_id, None)
    if not callable(exchange_class):
        raise ExchangeError(f"ccxt 不支持: {exchange_id}")

    config: dict[str, Any] = {
        "apiKey": decrypt_value(api_key_encrypted),
        "secret": decrypt_value(api_secret_encrypted),
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    }

    if exchange_id in PASSPHRASE_EXCHANGES and api_passphrase_encrypted:
        config["password"] = decrypt_value(api_passphrase_encrypted)

    # NOTE: OKX 模拟盘需要设置 sandbox mode 的特殊 header
    if exchange_id == "okx" and simulated:
        config["headers"] = {"x-simulated-trading": "1"}

    exchange = exchange_class(config)
    return exchange


async def fetch_balance(exchange: ccxt.Exchange) -> dict[str, dict[str, float]]:
    """
    查询账户余额。

    Returns:
        {币种: {free: 可用, used: 冻结, total: 总计}}

    Raises:
        ExchangeError: API 调用失败
    """
    try:
        balance = await exchange.fetch_balance()
        result = {}
        for currency, data in balance.get("total", {}).items():
            if data and data > 0:
                result[currency] = {
                    "free": balance["free"].get(currency, 0) or 0,
                    "used": balance["used"].get(currency, 0) or 0,
                    "total": data,
                }
        return result
    except Exception as exc:
        from app.core.metrics import EXCHANGE_API_ERRORS
        EXCHANGE_API_ERRORS.labels(exchange=getattr(exchange, "id", "unknown"), operation="fetch_balance").inc()
        raise ExchangeError(str(exc)) from exc
    finally:
        await exchange.close()


async def execute_market_buy(
    exchange: ccxt.Exchange,
    symbol: str,
    usdt_amount: float,
) -> dict:
    """
    执行市价买入。

    Args:
        exchange: ccxt 交易所实例
        symbol: 交易对（如 'BTC/USDT'）
        usdt_amount: 买入金额（USDT）

    Returns:
        订单信息字典

    Raises:
        ExchangeError: 下单失败
    """
    ccxt_module = _get_ccxt_module()
    base_error_type = getattr(ccxt_module, "BaseError", Exception)
    try:
        ticker = await exchange.fetch_ticker(symbol)
        price = ticker["last"]
        if not price or price <= 0:
            raise ExchangeError(f"{symbol} 价格异常: {price}")

        qty = round(usdt_amount / price, 8)
        order = await exchange.create_market_buy_order(symbol, qty)

        logger.info(
            "市价买入成功: %s %.4f @ $%.2f (订单 %s)",
            symbol, qty, price, order.get("id", "unknown"),
        )

        return {
            "order_id": order.get("id", ""),
            "symbol": symbol,
            "qty": qty,
            "price": price,
            "usdt": usdt_amount,
            "status": order.get("status", "unknown"),
        }
    except (ExchangeError, base_error_type):
        from app.core.metrics import EXCHANGE_API_ERRORS
        EXCHANGE_API_ERRORS.labels(exchange=getattr(exchange, "id", "unknown"), operation="execute_market_buy").inc()
        raise
    except Exception as exc:
        from app.core.metrics import EXCHANGE_API_ERRORS
        EXCHANGE_API_ERRORS.labels(exchange=getattr(exchange, "id", "unknown"), operation="execute_market_buy").inc()
        raise ExchangeError(f"下单失败 {symbol}: {exc}") from exc
    finally:
        await exchange.close()


async def fetch_candles_from_exchange(
    exchange_id: str,
    symbol: str,
    timeframe: str = "4h",
    since_ms: int | None = None,
    limit: int = 500,
) -> list[list]:
    """
    从交易所拉取 K 线数据（无需认证）。

    NOTE: 用于数据更新任务，不消耗用户 API 配额。

    Returns:
        [[timestamp, open, high, low, close, volume], ...]
    """
    ccxt_module = _get_ccxt_module()
    exchange_class = getattr(ccxt_module, exchange_id, None)
    if not callable(exchange_class):
        raise ExchangeError(f"ccxt 不支持: {exchange_id}")

    config: dict[str, Any] = {
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    }
    params: dict[str, Any] = {}
    if exchange_id == "okx":
        # OKX 的 ccxt 默认会尝试加载多个衍生品市场；公开行情刷新只需要现货 K 线。
        config["options"] = {
            "defaultType": "spot",
            "fetchMarkets": ["spot"],
        }
        params["instType"] = "SPOT"

    exchange = exchange_class(config)
    try:
        ohlcv = await exchange.fetch_ohlcv(
            symbol, timeframe, since=since_ms, limit=limit, params=params,
        )
        return ohlcv
    except Exception as exc:
        from app.core.metrics import EXCHANGE_API_ERRORS
        EXCHANGE_API_ERRORS.labels(exchange=exchange_id, operation="fetch_ohlcv").inc()
        raise ExchangeError(f"K 线拉取失败: {exc}") from exc
    finally:
        await exchange.close()
