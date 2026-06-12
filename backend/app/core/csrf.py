"""CSRF protection for HttpOnly cookie authentication."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
EXEMPT_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/verify-email",
    "/api/v1/stripe/webhook",
}


class CsrfProtectionMiddleware(BaseHTTPMiddleware):
    """Require X-CSRF-Token for cookie-authenticated write requests."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        if request.method in SAFE_METHODS or request.url.path in EXEMPT_PATHS:
            return await call_next(request)
        if not request.url.path.startswith("/api/v1/"):
            return await call_next(request)
        if request.headers.get("authorization", "").startswith("Bearer "):
            return await call_next(request)
        if not request.cookies.get("access_token"):
            return await call_next(request)

        cookie_token = request.cookies.get("csrf_token", "")
        header_token = request.headers.get("x-csrf-token", "")
        if not cookie_token or not header_token or cookie_token != header_token:
            return JSONResponse(
                status_code=403,
                content={"ok": False, "code": 403, "message": "CSRF 校验失败，请刷新页面后重试", "detail": ""},
            )
        return await call_next(request)
