import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.model.user import User
from app.core.kms import get_key_provider, EnvKeyProvider, VaultKeyProvider

@pytest.mark.anyio
async def test_kms_key_providers():
    """测试 KMS 密钥管理器及其分发。"""
    provider = get_key_provider()
    assert provider is not None
    # 默认应为 EnvKeyProvider（因为没有设置 KMS_PROVIDER='vault'）
    assert isinstance(provider, EnvKeyProvider)
    key = provider.get_encryption_key()
    assert len(key) == 32

    # 测试 Vault 降级
    vault_prov = VaultKeyProvider()
    # 因为没有设置 VAULT_TOKEN，它应该优雅退避返回本地环境变量密钥
    key_v = vault_prov.get_encryption_key()
    assert len(key_v) == 32
    assert key_v == key


@pytest.mark.anyio
async def test_public_signals_endpoint(client: AsyncClient):
    """测试匿名公开信号端点和缓存。"""
    response = await client.get("/api/v1/signals/public")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # 检查返回格式
    for coin in data:
        assert "symbol" in coin
        assert "price" in coin
        assert "history" in coin
        assert isinstance(coin["history"], list)
        
    # 测试缓存：再次请求应该极快
    response2 = await client.get("/api/v1/signals/public")
    assert response2.status_code == 200
    assert response2.json() == data


@pytest.mark.anyio
async def test_referral_registration_flow(client: AsyncClient, test_app):
    """测试推荐注册机制（邀请码生成与推荐人绑定）。"""
    # 1. 注册推荐人
    reg1 = await client.post("/api/v1/auth/register", json={
        "email": "referrer@example.com",
        "password": "Password123!",
        "display_name": "Referrer User",
        "accepted_terms": True
    })
    assert reg1.status_code == 200
    
    # 2. 从数据库拉取推荐人，获取其自动生成的邀请码
    from tests.conftest import get_test_factory
    session_factory = get_test_factory()
    async with session_factory() as session:
        referrer = (await session.execute(
            select(User).where(User.email == "referrer@example.com")
        )).scalar_one()
        ref_code = referrer.referral_code
        assert ref_code.startswith("K_")
        assert len(ref_code) == 10  # K_ + 8位 hex

    # 3. 使用推荐人的邀请码注册被推荐人
    reg2 = await client.post("/api/v1/auth/register", json={
        "email": "referee@example.com",
        "password": "Password123!",
        "display_name": "Referee User",
        "accepted_terms": True,
        "referral_code": ref_code
    })
    assert reg2.status_code == 200
    
    # 4. 检查被推荐人是否正确绑定了 referred_by_id
    async with session_factory() as session:
        referee = (await session.execute(
            select(User).where(User.email == "referee@example.com")
        )).scalar_one()
        assert referee.referred_by_id == referrer.id
        assert referee.referral_code.startswith("K_")

    # 5. 测试登录态下获取定投表现 API
    # 先以被推荐人登录
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "referee@example.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    
    # 获取 performance
    perf_res = await client.get("/api/v1/share/performance")
    assert perf_res.status_code == 200
    perf_data = perf_res.json()
    assert perf_data["referral_code"] == referee.referral_code
    assert perf_data["invited_count"] == 0
    assert perf_data["total_invested"] == 0.0
    assert perf_data["profit_rate"] == 0.0

    # 6. 测试匿名拉取邀请码公开信息接口 invite-info
    info_res = await client.get(f"/api/v1/share/invite-info?code={referrer.referral_code}")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["referrer_name"] == "R***r"  # Referrer User -> R***r
    assert info_data["profit_rate"] == 0.0
    
    # 7. 测试无效的邀请码
    info_bad = await client.get("/api/v1/share/invite-info?code=K_BAD123")
    assert info_bad.status_code == 404
