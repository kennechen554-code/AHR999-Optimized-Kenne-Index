"""共享测试 fixture — SQLite + httpx AsyncClient。

所有 API 集成测试共享此 conftest，零外部依赖。

设计要点：
- 使用 session-scoped 的单一 engine + session_factory
- 每个 test_app fixture 执行 drop_all + create_all 实现数据隔离
- 共享同一个 engine 避免跨连接 schema 缓存不一致
"""

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import Base

# ─── 测试数据库路径 ──────────────────────────────────────────────

_TEST_DB_PATH = Path(__file__).parent / "_test_temp.db"
_TEST_DB_URL = f"sqlite+aiosqlite:///{_TEST_DB_PATH.as_posix()}"

# 全局唯一 engine + factory，所有测试共享
_engine: AsyncEngine = create_async_engine(_TEST_DB_URL)
_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=_engine, expire_on_commit=False
)


async def _override_get_main_session() -> AsyncGenerator[AsyncSession, None]:
    """替换主库 Session，指向测试 SQLite。"""
    async with _factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ─── 辅助函数 ─────────────────────────────────────────────────────


async def register_user(
    client: AsyncClient,
    email: str = "test@example.com",
    password: str = "Test1234!",
    display_name: str = "",
) -> dict[str, Any]:
    """注册用户并返回响应 JSON。"""
    payload: dict[str, Any] = {"email": email, "password": password, "accepted_terms": True}
    if display_name:
        payload["display_name"] = display_name
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200, f"注册失败: {response.text}"
    return response.json()


async def login_user(
    client: AsyncClient,
    email: str = "test@example.com",
    password: str = "Test1234!",
) -> dict[str, Any]:
    """登录用户并返回响应 JSON。"""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, f"登录失败: {response.text}"
    return response.json()


def get_test_factory() -> async_sessionmaker[AsyncSession]:
    """暴露 session factory 给测试文件使用（如 _add_member_to_tenant）。"""
    return _factory


# ─── 测试配置 ────────────────────────────────────────────────────


def _make_test_settings(csrf_enabled: bool = False) -> Any:
    from app.core.config import Settings

    return Settings(
        database_url=_TEST_DB_URL,
        tenant_db_url_template="sqlite+aiosqlite:///:memory:",
        debug=True,
        csrf_protection=csrf_enabled,
        redis_url="redis://localhost:6379/0",
        cookie_secure=False,
        rate_limit_backend="memory",
    )


# ─── App 构建 ────────────────────────────────────────────────────


def _build_test_app(csrf_enabled: bool = False) -> Any:
    """构建测试用 FastAPI app。"""
    import importlib

    from app.core.config import get_settings
    from app.core.database import get_main_session
    from app.core.redis_client import get_redis

    test_settings = _make_test_settings(csrf_enabled)

    import app.core.config as config_module

    original_settings = config_module._settings
    config_module._settings = test_settings

    try:
        import app.main as main_module

        importlib.reload(main_module)
        app_instance = main_module.create_app()
    finally:
        config_module._settings = original_settings

    app_instance.dependency_overrides[get_main_session] = _override_get_main_session
    app_instance.dependency_overrides[get_settings] = lambda: test_settings
    app_instance.dependency_overrides[get_redis] = AsyncMock(return_value=None)

    return app_instance


# ─── 表管理（使用全局 engine）───────────────────────────────────

async def _recreate_tables() -> None:
    """丢弃并重建所有表，确保每个测试的干净状态。

    NOTE: dispose(close=False) 会清空连接池，迫使后续 session 使用全新连接，
    避免陈旧连接缓存了旧的 schema 信息。
    """
    # 清理池中可能缓存了旧 schema 的连接
    await _engine.dispose(close=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


# ─── App Fixture ─────────────────────────────────────────────────


@pytest_asyncio.fixture
async def test_app() -> AsyncGenerator[Any, None]:
    """关闭 CSRF 的测试 app（大多数测试使用）。"""
    await _recreate_tables()
    app = _build_test_app(csrf_enabled=False)
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def csrf_app() -> AsyncGenerator[Any, None]:
    """开启 CSRF 的测试 app（CSRF 测试专用）。"""
    await _recreate_tables()
    app = _build_test_app(csrf_enabled=True)
    yield app
    app.dependency_overrides.clear()


# ─── Client Fixture ──────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(test_app: Any) -> AsyncGenerator[AsyncClient, None]:
    """未认证的 httpx 客户端。"""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture
async def authed_client(test_app: Any) -> AsyncGenerator[AsyncClient, None]:
    """已注册+登录的客户端（OWNER 角色）。"""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        await register_user(c, email="owner@test.com", password="Owner1234!")
        yield c


@pytest_asyncio.fixture
async def csrf_client(csrf_app: Any) -> AsyncGenerator[AsyncClient, None]:
    """开启 CSRF 的客户端。"""
    transport = ASGITransport(app=csrf_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture
async def premium_authed_client(test_app: Any) -> AsyncGenerator[AsyncClient, None]:
    """已登录且租户为 PREMIUM 套餐的客户端。"""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        await register_user(c, email="premium@test.com", password="Premium1234!")

        from sqlalchemy import select, update

        from app.model.user import PlanType, Tenant, User

        async with _factory() as session:
            result = await session.execute(
                select(User).where(User.email == "premium@test.com")
            )
            user = result.scalar_one()
            user.email_verified = True
            await session.execute(
                update(Tenant)
                .where(Tenant.id == user.tenant_id)
                .values(plan=PlanType.PREMIUM)
            )
            await session.commit()
        yield c


@pytest_asyncio.fixture
async def basic_authed_client(test_app: Any) -> AsyncGenerator[AsyncClient, None]:
    """已登录且租户为 BASIC 套餐的客户端。"""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        await register_user(c, email="basic@test.com", password="Basic1234!")

        from sqlalchemy import select, update

        from app.model.user import PlanType, Tenant, User

        async with _factory() as session:
            result = await session.execute(
                select(User).where(User.email == "basic@test.com")
            )
            user = result.scalar_one()
            user.email_verified = True
            await session.execute(
                update(Tenant)
                .where(Tenant.id == user.tenant_id)
                .values(plan=PlanType.BASIC)
            )
            await session.commit()
        yield c
