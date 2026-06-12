"""Small in-memory rate limiter for high-risk local API endpoints."""

from collections import defaultdict, deque
from time import monotonic

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.redis_client import get_redis


LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/auth/login": (10, 60),
    "/api/v1/auth/register": (5, 300),
    "/api/v1/auth/refresh": (60, 60),
    "/api/v1/auth/forgot-password": (5, 300),
    "/api/v1/auth/reset-password": (8, 300),
    "/api/v1/exchange/run-dca": (20, 300),
    "/api/v1/backtest/custom": (8, 300),
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._events: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        limit = LIMITS.get(request.url.path)
        if not limit:
            return await call_next(request)

        max_count, window_seconds = limit
        client = request.client.host if request.client else "unknown"
        token = request.cookies.get("access_token", "")
        key = f"{request.url.path}:{client}:{token[-16:]}"
        if await self._is_limited_by_redis(key, max_count, window_seconds):
            return self._limited_response()

        now = monotonic()
        events = self._events[key]
        while events and now - events[0] > window_seconds:
            events.popleft()
        if len(events) >= max_count:
            return self._limited_response()
        events.append(now)
        return await call_next(request)

    async def _is_limited_by_redis(self, key: str, max_count: int, window_seconds: int) -> bool:
        backend = get_settings().rate_limit_backend.lower()
        if backend == "memory":
            return False
        client = await get_redis()
        if client is None:
            return False
        redis_key = f"rate-limit:{key}"
        count = await client.incr(redis_key)
        if count == 1:
            await client.expire(redis_key, window_seconds)
        return int(count) > max_count

    def _limited_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"ok": False, "code": 429, "message": "请求过于频繁，请稍后重试", "detail": ""},
        )
