"""管理员禁用用户接口测试。"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from tests.conftest import get_test_factory, register_user


async def _add_member_to_tenant(
    owner_email: str,
    member_email: str,
    member_password: str,
) -> None:
    """在同一租户内创建 MEMBER 用户。"""
    from app.core.security import hash_password
    from app.model.user import User, UserRole

    factory = get_test_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.email == owner_email))
        owner = result.scalar_one()
        member = User(
            email=member_email,
            hashed_password=hash_password(member_password),
            display_name="Member",
            role=UserRole.MEMBER,
            tenant_id=owner.tenant_id,
        )
        session.add(member)
        await session.commit()


@pytest.mark.asyncio
async def test_admin_list_users(authed_client: AsyncClient) -> None:
    """OWNER 调用 GET /admin/users → 200。"""
    response = await authed_client.get("/api/v1/admin/users")
    assert response.status_code == 200
    data = response.json()
    assert "users" in data
    assert len(data["users"]) >= 1
    assert data["users"][0]["role"] == "owner"


@pytest.mark.asyncio
async def test_admin_disable_user(authed_client: AsyncClient) -> None:
    """OWNER 禁用同租户 MEMBER → 200。"""
    await _add_member_to_tenant(
        owner_email="owner@test.com",
        member_email="member_disable@test.com",
        member_password="Member1234!",
    )

    users = (await authed_client.get("/api/v1/admin/users")).json()["users"]
    member = next(u for u in users if u["email"] == "member_disable@test.com")

    response = await authed_client.patch(
        f"/api/v1/admin/users/{member['id']}/status",
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


@pytest.mark.asyncio
async def test_disabled_user_cannot_login(
    authed_client: AsyncClient,
    test_app: object,
) -> None:
    """被禁用用户登录 → 401。"""
    await _add_member_to_tenant(
        owner_email="owner@test.com",
        member_email="will_disable@test.com",
        member_password="Disable1234!",
    )

    users = (await authed_client.get("/api/v1/admin/users")).json()["users"]
    member = next(u for u in users if u["email"] == "will_disable@test.com")
    await authed_client.patch(
        f"/api/v1/admin/users/{member['id']}/status",
        json={"is_active": False},
    )

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as victim:
        response = await victim.post(
            "/api/v1/auth/login",
            json={"email": "will_disable@test.com", "password": "Disable1234!"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_cannot_disable_self(authed_client: AsyncClient) -> None:
    """OWNER 禁用自己 → 403。"""
    users = (await authed_client.get("/api/v1/admin/users")).json()["users"]
    owner = next(u for u in users if u["role"] == "owner")

    response = await authed_client.patch(
        f"/api/v1/admin/users/{owner['id']}/status",
        json={"is_active": False},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_rejected(test_app: object) -> None:
    """MEMBER 角色调用管理接口 → 403。"""
    transport = ASGITransport(app=test_app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as admin_client:
        await register_user(admin_client, email="admin_y@test.com", password="Admin1234!")

    await _add_member_to_tenant(
        owner_email="admin_y@test.com",
        member_email="member_y@test.com",
        member_password="Member1234!",
    )

    async with AsyncClient(transport=transport, base_url="http://testserver") as member_client:
        await member_client.post(
            "/api/v1/auth/login",
            json={"email": "member_y@test.com", "password": "Member1234!"},
        )
        response = await member_client.get("/api/v1/admin/users")
        assert response.status_code == 403
