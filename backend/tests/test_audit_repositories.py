"""Audit persistence repository tests."""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.repository.config_repository import get_config_dict, get_config_response, upsert_config
from app.repository.history_repository import add_trade_records, list_trade_records, monthly_spent
from app.repository.operation_audit_repository import add_operation_log, list_operation_logs
from app.schema.signal import ConfigUpdateRequest


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as db_session:
        yield db_session
        await db_session.rollback()

    await engine.dispose()


@pytest.mark.asyncio
async def test_config_persists_and_preserves_masked_secrets(session: AsyncSession) -> None:
    body = ConfigUpdateRequest(
        exchange="okx",
        api_key="abcd1234key",
        api_secret="abcd1234secret",
        api_passphrase="abcd1234pass",
        smtp_user="mail@example.com",
        smtp_password="mail-secret",
    )
    await upsert_config(session, user_id=1, tenant_id=10, body=body)

    response = await get_config_response(session, user_id=1, tenant_id=10)
    assert response.api_key == "abcd****4key"
    assert response.smtp_password == "****"

    await upsert_config(
        session,
        user_id=1,
        tenant_id=10,
        body=ConfigUpdateRequest(
            exchange="binance",
            api_key=response.api_key,
            api_secret=response.api_secret,
            api_passphrase=response.api_passphrase,
            smtp_user=response.smtp_user,
            smtp_password=response.smtp_password,
        ),
    )
    stored = await get_config_dict(session, user_id=1, tenant_id=10)
    assert stored["exchange"] == "binance"
    assert stored["api_key"] == "abcd1234key"
    assert stored["smtp_password"] == "mail-secret"


@pytest.mark.asyncio
async def test_history_filters_paginates_and_calculates_monthly_spent(session: AsyncSession) -> None:
    await add_trade_records(
        session,
        user_id=1,
        tenant_id=10,
        mode="dry_run",
        strategy_mode="per_asset_strict_dd",
        orders=[
            {
                "ts": "2026-04-26T01:00:00+00:00",
                "symbol": "BTC",
                "exchange": "okx",
                "usdt": 100,
                "status": "dry_run",
                "price": 50000,
                "qty": 0.002,
                "kenne_index": 0.5,
                "mult": 1,
            },
            {
                "ts": "2026-04-26T02:00:00+00:00",
                "symbol": "ETH",
                "exchange": "okx",
                "usdt": 50,
                "status": "failed",
                "note": "insufficient balance",
            },
        ],
    )

    records, count, total, page_size = await list_trade_records(
        session,
        user_id=1,
        tenant_id=10,
        status="dry_run",
        symbol="BTC",
        page=1,
        page_size=10,
    )
    assert count == 1
    assert total == 100
    assert page_size == 10
    assert records[0].symbol == "BTC"
    assert records[0].mode == "dry_run"

    spent = await monthly_spent(session, user_id=1, tenant_id=10, statuses=("dry_run",))
    assert spent == 100


@pytest.mark.asyncio
async def test_operation_audit_log_filters_by_tenant(session: AsyncSession) -> None:
    await add_operation_log(
        session,
        user_id=1,
        tenant_id=10,
        action="config.update",
        resource_type="config",
        result="success",
        summary="更新配置",
        ip_address="127.0.0.1",
    )
    await add_operation_log(
        session,
        user_id=2,
        tenant_id=11,
        action="auth.login",
        result="success",
        summary="其他租户",
    )

    records, count, page_size = await list_operation_logs(session, tenant_id=10, page=1, page_size=20)
    assert count == 1
    assert page_size == 20
    assert records[0].action == "config.update"
    assert records[0].summary == "更新配置"
