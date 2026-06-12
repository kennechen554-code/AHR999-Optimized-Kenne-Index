"""系统邮件与邮箱验证流程测试。"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.model.user import EmailVerificationToken, User
from tests.conftest import get_test_factory, register_user


@pytest.mark.asyncio
async def test_resend_verification_creates_hashed_token(authed_client: AsyncClient) -> None:
    """重发邮箱验证邮件即使 SMTP 未配置，也应生成哈希令牌且不暴露明文。"""
    response = await authed_client.post("/api/v1/auth/resend-verification")
    assert response.status_code == 200
    assert response.json()["ok"] is True

    factory = get_test_factory()
    async with factory() as session:
        user = (await session.execute(select(User).where(User.email == "owner@test.com"))).scalar_one()
        tokens = (
            await session.execute(
                select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
            )
        ).scalars().all()

    assert tokens
    assert all(len(item.token_hash) == 64 for item in tokens)
    assert all(item.used_at is None for item in tokens)


@pytest.mark.asyncio
async def test_verify_email_rejects_invalid_token(client: AsyncClient) -> None:
    """错误邮箱验证 token → 422。"""
    await register_user(client, email="verify_invalid@test.com", password="Verify1234!")
    response = await client.post("/api/v1/auth/verify-email", json={"token": "bad-token"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_verify_email_marks_user_verified(client: AsyncClient) -> None:
    """使用数据库中的验证 token 等价哈希构造流程，确认用户被标记为已验证。"""
    # 注册会创建 token，但只保存哈希。这里直接插入已知 token 的哈希以避免依赖真实邮件。
    await register_user(client, email="verify_ok@test.com", password="Verify1234!")

    import hashlib
    from datetime import datetime, timedelta, timezone

    raw_token = "known-verification-token"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    factory = get_test_factory()
    async with factory() as session:
        user = (await session.execute(select(User).where(User.email == "verify_ok@test.com"))).scalar_one()
        session.add(
            EmailVerificationToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        await session.commit()

    response = await client.post("/api/v1/auth/verify-email", json={"token": raw_token})
    assert response.status_code == 200

    async with factory() as session:
        user = (await session.execute(select(User).where(User.email == "verify_ok@test.com"))).scalar_one()
        assert user.email_verified is True
        assert user.email_verified_at is not None
