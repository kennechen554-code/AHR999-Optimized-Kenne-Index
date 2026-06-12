"""
Kenne Index SaaS — FastAPI 应用入口。

使用 lifespan 管理应用生命周期（替代已废弃的 on_event）。
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.core.config import get_settings
from app.core.database import create_all_tables, dispose_all_engines
from app.core.exceptions import register_exception_handlers
from app.core.csrf import CsrfProtectionMiddleware
from app.core.rate_limit import RateLimitMiddleware
from app.core.request_id import RequestIdMiddleware
from app.core.redis_client import close_redis
from app.service.task_service import task_runtime

# API 路由
from app.api.v1.auth import router as auth_router
from app.api.v1.signals import router as signals_router
from app.api.v1.config import router as config_router
from app.api.v1.exchange import router as exchange_router
from app.api.v1.history import router as history_router
from app.api.v1.mvrv import router as mvrv_router
from app.api.v1.stripe_billing import router as stripe_router
from app.api.v1.backtest import router as backtest_router
from app.api.v1.audit import router as audit_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.security import router as security_router
from app.api.v1.admin import router as admin_router
from app.api.v1.reports import router as reports_router
from app.api.v1.health import router as health_router
from app.api.v1.share import router as share_router

from app.core.logging import setup_logging
setup_logging()
logger = logging.getLogger("kenne")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理。

    启动时：初始化数据库表
    关闭时：释放所有连接
    """
    logger.info("=== Kenne Index SaaS 启动 ===")
    await create_all_tables()
    task_runtime.start_background_loop()
    yield
    logger.info("=== Kenne Index SaaS 关闭 ===")
    await task_runtime.stop_background_loop()
    await dispose_all_engines()
    await close_redis()


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。"""
    settings = get_settings()
    settings.validate_production_settings()

    app = FastAPI(
        title="Kenne Index",
        description="智能加密货币定投系统 — SaaS 版",
        version="2.0.0",
        lifespan=lifespan,
        debug=settings.debug,
    )

    # ─── CORS ─────────────────────────────────────────────
    # NOTE: 生产环境必须配置白名单，禁止 ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)
    if settings.csrf_protection:
        app.add_middleware(CsrfProtectionMiddleware)
    app.add_middleware(RateLimitMiddleware)

    # ─── 异常处理 ──────────────────────────────────────────
    register_exception_handlers(app)

    # ─── 路由注册 ──────────────────────────────────────────
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(signals_router, prefix="/api/v1")
    app.include_router(config_router, prefix="/api/v1")
    app.include_router(exchange_router, prefix="/api/v1")
    app.include_router(history_router, prefix="/api/v1")
    app.include_router(mvrv_router, prefix="/api/v1")
    app.include_router(stripe_router, prefix="/api/v1")
    app.include_router(backtest_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(tasks_router, prefix="/api/v1")
    app.include_router(security_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(reports_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(share_router, prefix="/api/v1")

    # ─── 静态文件（回测报告）───────────────────────────────
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/api/health")
    async def health_check() -> dict:
        """健康检查端点。"""
        return {"status": "ok", "version": "2.0.0"}

    @app.get("/backtest", response_class=HTMLResponse)
    async def serve_backtest() -> HTMLResponse:
        """回测报告页面。"""
        backtest_path = static_dir / "ahr999_backtest.html"
        if backtest_path.exists():
            return HTMLResponse(backtest_path.read_text(encoding="utf-8"))
        return HTMLResponse("<h2>回测报告文件未找到</h2>")

    # ─── Prometheus 监控 ───────────────────────────────
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    return app


app = create_app()
