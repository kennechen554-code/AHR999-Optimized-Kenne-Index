"""
统一异常定义与 FastAPI 全局异常处理器。

所有业务层异常继承 AppException，通过 HTTP 异常处理器
返回统一的 JSON 响应格式。
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """通用业务异常基类。"""

    def __init__(self, code: int, message: str, detail: str = ""):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppException):
    """资源不存在。"""

    def __init__(self, resource: str, identifier: str = ""):
        msg = f"{resource} 不存在"
        if identifier:
            msg += f": {identifier}"
        super().__init__(404, msg)


class AuthenticationError(AppException):
    """认证失败（登录凭证错误、Token 过期等）。"""

    def __init__(self, message: str = "认证失败"):
        super().__init__(401, message)


class PermissionDeniedError(AppException):
    """权限不足。"""

    def __init__(self, message: str = "权限不足"):
        super().__init__(403, message)


class ValidationError(AppException):
    """业务校验失败。"""

    def __init__(self, message: str):
        super().__init__(422, message)


class ExchangeError(AppException):
    """交易所 API 调用失败。"""

    def __init__(self, message: str):
        super().__init__(502, f"交易所错误: {message}")


class BudgetExhaustedError(AppException):
    """预算耗尽。"""

    def __init__(self, message: str = "本月预算已耗尽"):
        super().__init__(400, message)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器，确保所有异常返回统一 JSON 格式。"""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        request_id = str(getattr(request.state, "request_id", ""))
        return JSONResponse(
            status_code=exc.code,
            content={
                "ok": False,
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = str(getattr(request.state, "request_id", ""))
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "code": 500,
                "message": "服务器内部错误",
                "detail": str(exc) if app.debug else "",
                "request_id": request_id,
            },
        )
