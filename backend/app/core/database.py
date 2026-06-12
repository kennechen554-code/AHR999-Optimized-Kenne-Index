"""
数据库连接管理。

当前生产路径使用主库 + tenant_id / user_id 做行级租户边界。
租户库 Session 工具仅作为后续物理隔离演进预留，业务代码尚未使用。
"""

import logging
from typing import Any
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
    pass


# ─── 主库连接 ─────────────────────────────────────────────────────

_main_engine: AsyncEngine | None = None
_main_session_factory: async_sessionmaker[AsyncSession] | None = None

# ─── 租户库连接缓存 ───────────────────────────────────────────────

_tenant_engines: dict[int, AsyncEngine] = {}
_tenant_session_factories: dict[int, async_sessionmaker[AsyncSession]] = {}


def _build_engine_kwargs(url: str, debug: bool = False) -> dict[str, Any]:
    """
    根据数据库 URL 构建引擎参数。

    NOTE: SQLite 不支持 pool_size / max_overflow / pool_pre_ping，
    检测 URL 前缀自动适配。
    """
    kwargs: dict[str, Any] = {"echo": debug}
    if "sqlite" not in url:
        kwargs.update(pool_pre_ping=True, pool_size=5, max_overflow=10)
    return kwargs


def _get_main_engine() -> AsyncEngine:
    """获取主库引擎（懒初始化）。"""
    global _main_engine
    if _main_engine is None:
        settings = get_settings()
        kwargs = _build_engine_kwargs(settings.database_url, settings.debug)
        _main_engine = create_async_engine(settings.database_url, **kwargs)
    return _main_engine


def get_main_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取主库 Session 工厂。"""
    global _main_session_factory
    if _main_session_factory is None:
        _main_session_factory = async_sessionmaker(
            bind=_get_main_engine(),
            expire_on_commit=False,
        )
    return _main_session_factory


async def get_main_session() -> AsyncGenerator[AsyncSession, None]:
    """主库 Session 依赖注入生成器（FastAPI Depends）。"""
    factory = get_main_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _get_tenant_engine(tenant_id: int) -> AsyncEngine:
    """
    获取指定租户的数据库引擎（带缓存）。

    每个租户使用独立数据库，URL 通过模板替换 tenant_id 生成。
    """
    if tenant_id not in _tenant_engines:
        settings = get_settings()
        url = settings.tenant_db_url_template.format(tenant_id=tenant_id)
        kwargs = _build_engine_kwargs(url, settings.debug)
        _tenant_engines[tenant_id] = create_async_engine(url, **kwargs)
    return _tenant_engines[tenant_id]


def get_tenant_session_factory(tenant_id: int) -> async_sessionmaker[AsyncSession]:
    """获取指定租户的 Session 工厂。"""
    if tenant_id not in _tenant_session_factories:
        _tenant_session_factories[tenant_id] = async_sessionmaker(
            bind=_get_tenant_engine(tenant_id),
            expire_on_commit=False,
        )
    return _tenant_session_factories[tenant_id]


@asynccontextmanager
async def get_tenant_session(tenant_id: int) -> AsyncGenerator[AsyncSession, None]:
    """
    租户库 Session 上下文管理器。

    用法:
        async with get_tenant_session(tenant_id) as session:
            ...
    """
    factory = get_tenant_session_factory(tenant_id)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_tables() -> None:
    """在主库中创建所有表（开发用途）。"""
    engine = _get_main_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_compat_migrations(conn, str(engine.url))
    logger.info("主库表结构创建完成")


async def _apply_compat_migrations(conn: Any, url: str) -> None:
    """Apply additive compatibility migrations for existing local databases."""
    if "sqlite" in url:
        rows = await conn.execute(text("PRAGMA table_info(tenants)"))
        columns = {row[1] for row in rows}
        if columns and "subscription_status" not in columns:
            await conn.execute(
                text("ALTER TABLE tenants ADD COLUMN subscription_status VARCHAR(32) NOT NULL DEFAULT 'none'")
            )
        await _apply_sqlite_column(conn, "tenants", "live_trading_paused", "BOOLEAN NOT NULL DEFAULT 0")
        await _apply_sqlite_column(conn, "users", "email_verified", "BOOLEAN NOT NULL DEFAULT 0")
        await _apply_sqlite_column(conn, "users", "email_verified_at", "DATETIME")
        await _apply_sqlite_column(conn, "users", "mfa_enabled", "BOOLEAN NOT NULL DEFAULT 0")
        await _apply_sqlite_column(conn, "users", "mfa_secret_encrypted", "VARCHAR(512) NOT NULL DEFAULT ''")
        await _apply_sqlite_column(conn, "users", "last_login_at", "DATETIME")
        await _apply_sqlite_column(conn, "users", "accepted_terms", "BOOLEAN NOT NULL DEFAULT 0")
        await _apply_sqlite_column(conn, "users", "accepted_terms_at", "DATETIME")
        await _apply_sqlite_column(conn, "users", "referral_code", "VARCHAR(32)")
        await _apply_sqlite_column(conn, "users", "referred_by_id", "INTEGER")
        await _apply_sqlite_column(conn, "user_configs", "tenant_id", "INTEGER NOT NULL DEFAULT 0")
        await _apply_sqlite_column(conn, "trade_records", "tenant_id", "INTEGER NOT NULL DEFAULT 0")
        await _apply_sqlite_column(conn, "trade_records", "mode", "VARCHAR(16) NOT NULL DEFAULT 'dry_run'")
        await _apply_sqlite_column(conn, "trade_records", "dedupe_key", "VARCHAR(128) NOT NULL DEFAULT ''")
        await _apply_sqlite_column(conn, "trade_records", "order_status", "VARCHAR(32) NOT NULL DEFAULT 'filled'")
        await _apply_sqlite_column(conn, "operation_audit_logs", "request_id", "VARCHAR(64) NOT NULL DEFAULT ''")
        await _apply_sqlite_column(
            conn,
            "trade_records",
            "strategy_mode",
            "VARCHAR(48) NOT NULL DEFAULT 'per_asset_strict_dd'",
        )
        for column in (
            "notifications_enabled",
            "notify_on_execution",
            "notify_on_budget",
            "notify_on_error",
            "automation_enabled",
            "automation_market_data",
            "automation_dry_run",
            "automation_live_enabled",
        ):
            await _apply_sqlite_column(conn, "user_configs", column, "BOOLEAN NOT NULL DEFAULT 0")
        return

    await conn.execute(
        text(
            "ALTER TABLE tenants "
            "ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(32) NOT NULL DEFAULT 'none'"
        )
    )
    await conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS live_trading_paused BOOLEAN NOT NULL DEFAULT false"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT false"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP WITH TIME ZONE"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN NOT NULL DEFAULT false"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_secret_encrypted VARCHAR(512) NOT NULL DEFAULT ''"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITH TIME ZONE"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS accepted_terms BOOLEAN NOT NULL DEFAULT false"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS accepted_terms_at TIMESTAMP WITH TIME ZONE"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(32)"))
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by_id INTEGER"))
    await conn.execute(text("ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS tenant_id INTEGER NOT NULL DEFAULT 0"))
    await conn.execute(text("ALTER TABLE trade_records ADD COLUMN IF NOT EXISTS tenant_id INTEGER NOT NULL DEFAULT 0"))
    await conn.execute(text("ALTER TABLE trade_records ADD COLUMN IF NOT EXISTS mode VARCHAR(16) NOT NULL DEFAULT 'dry_run'"))
    await conn.execute(text("ALTER TABLE trade_records ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR(128) NOT NULL DEFAULT ''"))
    await conn.execute(text("ALTER TABLE trade_records ADD COLUMN IF NOT EXISTS order_status VARCHAR(32) NOT NULL DEFAULT 'filled'"))
    await conn.execute(text("ALTER TABLE operation_audit_logs ADD COLUMN IF NOT EXISTS request_id VARCHAR(64) NOT NULL DEFAULT ''"))
    await conn.execute(
        text(
            "ALTER TABLE trade_records "
            "ADD COLUMN IF NOT EXISTS strategy_mode VARCHAR(48) NOT NULL DEFAULT 'per_asset_strict_dd'"
        )
    )
    for column in (
        "notifications_enabled",
        "notify_on_execution",
        "notify_on_budget",
        "notify_on_error",
        "automation_enabled",
        "automation_market_data",
        "automation_dry_run",
        "automation_live_enabled",
    ):
        await conn.execute(text(f"ALTER TABLE user_configs ADD COLUMN IF NOT EXISTS {column} BOOLEAN NOT NULL DEFAULT false"))


async def _apply_sqlite_column(conn: Any, table: str, column: str, ddl: str) -> None:
    rows = await conn.execute(text(f"PRAGMA table_info({table})"))
    columns = {row[1] for row in rows}
    if columns and column not in columns:
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


async def dispose_all_engines() -> None:
    """关闭所有数据库连接（应用关闭时调用）。"""
    global _main_engine
    if _main_engine:
        await _main_engine.dispose()
        _main_engine = None

    for engine in _tenant_engines.values():
        await engine.dispose()
    _tenant_engines.clear()
    _tenant_session_factories.clear()

    logger.info("所有数据库连接已关闭")
