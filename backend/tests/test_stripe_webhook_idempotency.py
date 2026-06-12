"""Stripe webhook 幂等处理测试。"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.v1 import stripe_billing
from app.model.tenant_models import StripeEventLog
from app.model.user import PlanType, Tenant
from tests.conftest import get_test_factory, register_user


@pytest.mark.asyncio
async def test_stripe_webhook_duplicate_event_is_idempotent(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同一个 Stripe event_id 重复投递时，不重复更新套餐或写多条事件。"""
    await register_user(client, email="stripe@test.com", password="Stripe1234!")

    factory = get_test_factory()
    async def override_get_main_session():
        async with factory() as session:
            yield session

    monkeypatch.setattr(stripe_billing, "get_main_session", override_get_main_session)

    async with factory() as session:
        tenant = (await session.execute(select(Tenant))).scalar_one()
        tenant_id = tenant.id
        await session.commit()

    payload = {
        "id": "evt_test_duplicate",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"tenant_id": str(tenant_id), "plan": "premium"},
                "customer": "cus_test",
                "subscription": "sub_test",
            }
        },
    }

    first = await client.post("/api/v1/stripe/webhook", json=payload)
    second = await client.post("/api/v1/stripe/webhook", json=payload)

    assert first.status_code == 200
    assert first.json()["received"] is True
    assert second.status_code == 200
    assert second.json()["duplicate"] is True

    async with factory() as session:
        tenant = (await session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
        events = (await session.execute(select(StripeEventLog))).scalars().all()

    assert tenant.plan == PlanType.PREMIUM
    assert tenant.subscription_status == "active"
    assert len(events) == 1
