"""Trading preflight tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.model.user import User
from tests.conftest import get_test_factory, register_user


@pytest.mark.asyncio
async def test_preflight_reports_unverified_email(client: AsyncClient) -> None:
    await register_user(client, email="preflight_unverified@test.com", password="Preflight1234!")

    response = await client.get("/api/v1/exchange/preflight")

    assert response.status_code == 200
    data = response.json()
    email_check = next(item for item in data["checks"] if item["key"] == "email_verified")
    assert email_check["ok"] is False


@pytest.mark.asyncio
async def test_preflight_reports_verified_email(premium_authed_client: AsyncClient) -> None:
    factory = get_test_factory()
    async with factory() as session:
        user = (await session.execute(select(User).where(User.email == "premium@test.com"))).scalar_one()
        user.email_verified = True
        await session.commit()

    response = await premium_authed_client.get("/api/v1/exchange/preflight")

    assert response.status_code == 200
    data = response.json()
    assert data["live"]["enabled_by_plan"] is True
    assert data["live"]["cap_usdt"] > 0
    assert any(item["key"] == "global_live" for item in data["checks"])
