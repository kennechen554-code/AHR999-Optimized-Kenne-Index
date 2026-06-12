"""Centralized subscription entitlement checks."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError
from app.model.user import PlanType, Tenant, User

PLAN_ENTITLEMENTS: dict[PlanType, dict[str, bool | int | float | list[str]]] = {
    PlanType.PREMIUM: {
        "signals": True,
        "mvrv": True,
        "simulated_trading": True,
        "live_trading": True,
        "backtesting": True,
        "automation": True,
        "email_reports": True,
        "ai_daily_report": True,
        "max_exchanges": 8,
        "max_live_order_usdt": 2000,
        "supported_exchanges": ["okx", "binance", "bybit", "bitget", "gateio", "kucoin", "htx", "mexc"],
    },
    PlanType.BASIC: {
        "signals": True,
        "mvrv": True,
        "simulated_trading": True,
        "live_trading": False,
        "backtesting": False,
        "automation": False,
        "email_reports": False,
        "ai_daily_report": False,
        "max_exchanges": 1,
        "max_live_order_usdt": 0,
        "supported_exchanges": ["okx"],
    },
    PlanType.FREE: {
        "signals": True,
        "mvrv": False,
        "simulated_trading": True,
        "live_trading": False,
        "backtesting": False,
        "automation": False,
        "email_reports": False,
        "ai_daily_report": False,
        "max_exchanges": 1,
        "max_live_order_usdt": 0,
        "supported_exchanges": ["okx"],
    },
}


def plan_entitlements(plan: PlanType) -> dict[str, bool | int | float | list[str]]:
    """Return a copy of the feature flags and limits for a plan."""
    entitlements = PLAN_ENTITLEMENTS.get(plan, PLAN_ENTITLEMENTS[PlanType.FREE])
    return {
        key: list(value) if isinstance(value, list) else value
        for key, value in entitlements.items()
    }


async def get_tenant_plan(session: AsyncSession, tenant_id: int) -> PlanType:
    result = await session.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    return tenant.plan if tenant else PlanType.FREE


async def get_user_entitlements(
    session: AsyncSession,
    user: User,
) -> dict[str, bool | int | float | list[str]]:
    plan = await get_tenant_plan(session, user.tenant_id)
    return plan_entitlements(plan)


async def require_feature(session: AsyncSession, user: User, key: str, feature: str) -> None:
    entitlements = await get_user_entitlements(session, user)
    if not entitlements.get(key):
        raise PermissionDeniedError(f"{feature} 当前套餐不可用")


async def require_premium(session: AsyncSession, user: User, feature: str) -> None:
    plan = await get_tenant_plan(session, user.tenant_id)
    if plan != PlanType.PREMIUM:
        raise PermissionDeniedError(f"{feature} 仅对 Premium 会员开放")


async def require_live_trading(session: AsyncSession, user: User) -> None:
    await require_feature(session, user, "live_trading", "实盘执行")


async def require_backtesting(session: AsyncSession, user: User) -> None:
    await require_feature(session, user, "backtesting", "自定义回测")


async def require_automation(session: AsyncSession, user: User) -> None:
    await require_feature(session, user, "automation", "自动化任务")


async def require_mvrv(session: AsyncSession, user: User) -> None:
    await require_feature(session, user, "mvrv", "MVRV 指标")


async def require_email_reports(session: AsyncSession, user: User) -> None:
    await require_feature(session, user, "email_reports", "邮件报告")


async def require_exchange_supported(session: AsyncSession, user: User, exchange: str) -> None:
    entitlements = await get_user_entitlements(session, user)
    supported = entitlements.get("supported_exchanges", [])
    if not isinstance(supported, list) or exchange not in supported:
        raise PermissionDeniedError(f"当前套餐不支持交易所: {exchange}")


async def supported_exchanges_for_user(session: AsyncSession, user: User) -> list[str]:
    entitlements = await get_user_entitlements(session, user)
    supported = entitlements.get("supported_exchanges", [])
    return [str(item) for item in supported] if isinstance(supported, list) else []


async def enforce_live_order_cap(session: AsyncSession, user: User, total_usdt: float) -> None:
    entitlements = await get_user_entitlements(session, user)
    cap = float(entitlements.get("max_live_order_usdt", 0) or 0)
    if cap <= 0 or total_usdt > cap:
        raise PermissionDeniedError(f"实盘单次金额不能超过 {cap:.2f} USDT")
