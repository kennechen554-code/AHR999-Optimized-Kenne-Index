"""CSRF 保护中间件测试。

验证 CsrfProtectionMiddleware 在 Cookie 认证场景下正确拦截 / 放行请求。

NOTE: httpx AsyncClient 通过 ASGI transport 时，Set-Cookie 会自动存入
client.cookies，后续请求会自动带上。但需要确认 cookies 确实被设置。
"""

import pytest
from httpx import AsyncClient

from tests.conftest import register_user


@pytest.mark.asyncio
async def test_csrf_blocks_write_without_token(csrf_client: AsyncClient) -> None:
    """Cookie 认证 POST 请求缺少 CSRF token header → 403。"""
    # 注册用户（豁免路径，不受 CSRF 限制，会设置 access_token + csrf_token cookies）
    await register_user(csrf_client, email="csrf1@test.com", password="Csrf1234!")

    # 验证 cookies 已设置
    assert csrf_client.cookies.get("access_token"), "注册后应设置 access_token Cookie"
    assert csrf_client.cookies.get("csrf_token"), "注册后应设置 csrf_token Cookie"

    # POST 请求带 access_token cookie 但不带 x-csrf-token header → 403
    # NOTE: 需要清除 csrf_token cookie，否则中间件会同时拿到 cookie 和（空的）header
    # 实际上中间件比较 cookie_token != header_token，如果 header 为空就会 403
    response = await csrf_client.post(
        "/api/v1/auth/logout",
        # 不传 x-csrf-token header
    )
    assert response.status_code == 403, (
        f"期望 403，实际 {response.status_code}. "
        f"cookies: {dict(csrf_client.cookies)}"
    )
    data = response.json()
    assert "CSRF" in data.get("message", "")


@pytest.mark.asyncio
async def test_csrf_allows_with_valid_token(csrf_client: AsyncClient) -> None:
    """Cookie + 正确 X-CSRF-Token → 正常放行。"""
    await register_user(csrf_client, email="csrf2@test.com", password="Csrf1234!")

    csrf_token = csrf_client.cookies.get("csrf_token", "")
    assert csrf_token, "注册后应设置 csrf_token Cookie"

    response = await csrf_client.post(
        "/api/v1/auth/logout",
        headers={"x-csrf-token": csrf_token},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_csrf_allows_safe_methods(csrf_client: AsyncClient) -> None:
    """GET 请求 → 不校验 CSRF。"""
    await register_user(csrf_client, email="csrf3@test.com", password="Csrf1234!")

    # GET 请求不受 CSRF 限制
    response = await csrf_client.get("/api/v1/auth/me")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_csrf_allows_exempt_paths(csrf_client: AsyncClient) -> None:
    """/api/v1/auth/login 属于豁免路径 → 无需 CSRF token。"""
    await register_user(csrf_client, email="csrf4@test.com", password="Csrf1234!")

    # 登录是豁免路径，即使不传 CSRF header 也应放行
    response = await csrf_client.post(
        "/api/v1/auth/login",
        json={"email": "csrf4@test.com", "password": "Csrf1234!"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_csrf_allows_bearer_auth(csrf_client: AsyncClient) -> None:
    """Authorization: Bearer 方式 → 跳过 CSRF 校验。"""
    data = await register_user(csrf_client, email="csrf5@test.com", password="Csrf1234!")
    access_token = data["access_token"]

    # 清除所有 cookies，仅使用 Bearer
    csrf_client.cookies.clear()

    response = await csrf_client.post(
        "/api/v1/auth/logout",
        headers={"authorization": f"Bearer {access_token}"},
    )
    # Bearer 认证跳过 CSRF 校验
    assert response.status_code == 200
