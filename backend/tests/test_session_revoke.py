"""会话撤销接口测试。"""

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import register_user


@pytest.mark.asyncio
async def test_list_sessions_returns_current(authed_client: AsyncClient) -> None:
    """登录后 GET /security/sessions → 包含至少一个会话。"""
    response = await authed_client.get("/api/v1/security/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert len(data["sessions"]) >= 1


@pytest.mark.asyncio
async def test_revoke_session_success(authed_client: AsyncClient) -> None:
    """DELETE /security/sessions/{session_id} → 200。"""
    response = await authed_client.get("/api/v1/security/sessions")
    sessions = response.json()["sessions"]
    assert len(sessions) >= 1

    session_id = sessions[0]["session_id"]
    delete_response = await authed_client.delete(f"/api/v1/security/sessions/{session_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["ok"] is True


@pytest.mark.asyncio
async def test_revoked_session_cannot_access(authed_client: AsyncClient) -> None:
    """被撤销会话的 token 再次请求 → 401。"""
    response = await authed_client.get("/api/v1/security/sessions")
    sessions = response.json()["sessions"]
    session_id = sessions[0]["session_id"]

    await authed_client.delete(f"/api/v1/security/sessions/{session_id}")

    me_response = await authed_client.get("/api/v1/auth/me")
    assert me_response.status_code == 401


@pytest.mark.asyncio
async def test_cannot_revoke_other_user_session(test_app: object) -> None:
    """用户 A 不能撤销用户 B 的会话 → 404。"""
    transport = ASGITransport(app=test_app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client_a:
        await register_user(client_a, email="user_a@test.com", password="UserA1234!")
        sessions_a = (await client_a.get("/api/v1/security/sessions")).json()["sessions"]
        session_a_id = sessions_a[0]["session_id"]

    async with AsyncClient(transport=transport, base_url="http://testserver") as client_b:
        await register_user(client_b, email="user_b@test.com", password="UserB1234!")

        delete_response = await client_b.delete(
            f"/api/v1/security/sessions/{session_a_id}"
        )
        assert delete_response.status_code == 404
