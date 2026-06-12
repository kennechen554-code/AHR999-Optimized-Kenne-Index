"""
Redis 连接管理。

用于缓存市场数据（盘口深度、资金费率、CoinGecko 行情、MVRV-Z）。
Redis 可选 — 不可用时系统退化为实时请求模式。
"""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None
_redis_available: bool | None = None


async def get_redis() -> aioredis.Redis | None:
    """
    获取 Redis 客户端实例。

    首次调用时尝试连接，连接失败则返回 None 并标记不可用，
    后续调用直接返回 None，避免重复连接尝试。
    """
    global _redis_client, _redis_available

    if _redis_available is False:
        return None

    if _redis_client is None:
        settings = get_settings()
        try:
            _redis_client = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            await _redis_client.ping()
            _redis_available = True
            logger.info("Redis 连接成功: %s", settings.redis_url)
        except Exception as exc:
            logger.warning("Redis 不可用，相关缓存功能将降级: %s", exc)
            _redis_available = False
            _redis_client = None
            return None

    return _redis_client


async def cache_get(key: str) -> Any | None:
    """从 Redis 读取缓存值（JSON 反序列化）。"""
    client = await get_redis()
    if client is None:
        return None
    try:
        raw = await client.get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("Redis GET 失败 key=%s: %s", key, exc)
        return None


async def cache_set(key: str, value: Any, expire_seconds: int = 1800) -> bool:
    """写入 Redis 缓存（JSON 序列化，默认 30 分钟过期）。"""
    client = await get_redis()
    if client is None:
        return False
    try:
        await client.setex(key, expire_seconds, json.dumps(value))
        return True
    except Exception as exc:
        logger.warning("Redis SET 失败 key=%s: %s", key, exc)
        return False


async def close_redis() -> None:
    """关闭 Redis 连接（应用关闭时调用）。"""
    global _redis_client, _redis_available
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
    _redis_available = None
    logger.info("Redis 连接已关闭")
