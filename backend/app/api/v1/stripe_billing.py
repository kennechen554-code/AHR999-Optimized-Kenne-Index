"""Stripe billing routes for public plan metadata, checkout, webhook, and portal."""

import json
import logging
import secrets

import stripe
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import Settings, get_settings
from app.core.database import get_main_session
from app.core.exceptions import AppException, ValidationError
from app.model.tenant_models import StripeEventLog
from app.model.user import PlanType, Tenant
from app.repository.operation_audit_repository import add_operation_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stripe", tags=["付费"])


def _stripe_event_to_dict(event: object) -> dict[str, object]:
    if isinstance(event, dict):
        return event
    to_dict_recursive = getattr(event, "to_dict_recursive", None)
    if callable(to_dict_recursive):
        converted = to_dict_recursive()
        if isinstance(converted, dict):
            return converted
    to_dict = getattr(event, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        if isinstance(converted, dict):
            return converted
    return dict(event)  # type: ignore[arg-type]


def _plans() -> list[dict]:
    return [
        {
            "id": "basic",
            "name": "基础版",
            "name_en": "Basic",
            "price": "¥29",
            "period": "/月",
            "description": "适合个人投资者验证信号与模拟执行。",
            "features": [
                "Kenne Index 实时信号",
                "MVRV-Z Score 参考",
                "模拟盘 DCA 执行",
                "单交易所配置",
                "历史记录与预算预览",
                "回测功能锁定，仅可查看权益说明",
            ],
            "entitlements": {
                "live_trading": False,
                "backtesting": False,
                "automation": False,
                "email_reports": False,
                "max_exchanges": 1,
            },
        },
        {
            "id": "premium",
            "name": "专业版",
            "name_en": "Premium",
            "price": "¥99",
            "period": "/月",
            "description": "面向需要实盘执行、审计和多交易所扩展的专业用户。",
            "features": [
                "包含基础版全部能力",
                "Premium 实盘交易闸门",
                "Premium 自定义 CSV 与服务器路径回测",
                "AI 智能日报 · 自动推送",
                "单次实盘额度与二次确认",
                "8 家交易所支持",
                "自动调度与邮件报告预留",
                "优先支持",
            ],
            "entitlements": {
                "live_trading": True,
                "backtesting": True,
                "automation": True,
                "email_reports": True,
                "max_exchanges": 8,
            },
            "recommended": True,
        },
    ]


def _init_stripe(require_key: bool = True) -> None:
    settings = get_settings()
    if settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key
        return
    if require_key:
        raise ValidationError("Stripe 未配置，请在环境变量中设置 STRIPE_SECRET_KEY")


def _price_id_for_plan(plan: str) -> str:
    settings = get_settings()
    price_id_map = {
        "basic": settings.stripe_basic_price_id,
        "premium": settings.stripe_premium_price_id,
    }
    price_id = price_id_map.get(plan)
    if not price_id:
        raise ValidationError(f"无效或未配置的套餐: {plan}")
    return price_id


def _plan_from_price_id(price_id: str | None) -> PlanType:
    settings = get_settings()
    if price_id and price_id == settings.stripe_premium_price_id:
        return PlanType.PREMIUM
    if price_id and price_id == settings.stripe_basic_price_id:
        return PlanType.BASIC
    return PlanType.BASIC


@router.get("/plans")
async def get_plans() -> dict:
    """Public plan metadata used by marketing and billing screens."""
    return {"plans": _plans()}


@router.post("/checkout")
async def create_checkout_session(user: CurrentUser, plan: str = "basic") -> dict:
    _init_stripe()
    settings = get_settings()
    price_id = _price_id_for_plan(plan)

    try:
        checkout = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{settings.cors_origins[0]}/app/billing?payment=success",
            cancel_url=f"{settings.cors_origins[0]}/app/billing?payment=cancel",
            client_reference_id=str(user.id),
            metadata={
                "user_id": str(user.id),
                "tenant_id": str(user.tenant_id),
                "plan": plan,
            },
        )
        logger.info("Stripe checkout created user_id=%d plan=%s session=%s", user.id, plan, checkout.id)
        return {"checkout_url": checkout.url}
    except stripe.StripeError as exc:
        logger.error("Stripe checkout failed: %s", exc)
        raise AppException(502, f"支付服务异常: {exc}") from exc


@router.post("/portal")
async def create_portal_session(user: CurrentUser) -> dict:
    _init_stripe()
    settings = get_settings()

    async for session in get_main_session():
        result = await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))
        tenant = result.scalar_one_or_none()

    if not tenant or not tenant.stripe_customer_id:
        raise ValidationError("尚未找到关联的 Stripe 客户，请先订阅套餐")

    try:
        portal = stripe.billing_portal.Session.create(
            customer=tenant.stripe_customer_id,
            return_url=f"{settings.cors_origins[0]}/app/billing",
        )
        return {"portal_url": portal.url}
    except stripe.StripeError as exc:
        raise AppException(502, f"订阅管理入口创建失败: {exc}") from exc


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict:
    _init_stripe(require_key=False)
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        if settings.stripe_webhook_secret:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret,
            )
        elif not settings.debug:
            raise AppException(500, "Stripe Webhook 未配置签名密钥")
        else:
            event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        logger.warning("Stripe webhook verification failed: %s", exc)
        raise AppException(400, "Webhook 签名验证失败") from exc

    event_dict = _stripe_event_to_dict(event)
    event_type = str(event_dict.get("type", ""))
    event_id = str(event_dict.get("id", ""))
    data_wrapper = event_dict.get("data", {})
    if not isinstance(data_wrapper, dict) or not isinstance(data_wrapper.get("object"), dict):
        raise AppException(400, "Stripe Webhook 数据格式无效")
    data = data_wrapper["object"]

    if event_id:
        async for session in get_main_session():
            existing = await session.execute(
                select(StripeEventLog).where(StripeEventLog.event_id == event_id)
            )
            if existing.scalar_one_or_none():
                return {"received": True, "duplicate": True}
            session.add(StripeEventLog(event_id=event_id, event_type=event_type))
            await session.commit()

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data)
    elif event_type == "invoice.payment_failed":
        await _handle_invoice_failed(data)

    return {"received": True}


async def _handle_checkout_completed(data: dict) -> None:
    metadata = data.get("metadata", {})
    tenant_id = metadata.get("tenant_id")
    plan = metadata.get("plan", "basic")
    customer_id = data.get("customer")
    subscription_id = data.get("subscription")

    if not tenant_id:
        logger.warning("Checkout completed without tenant_id metadata")
        return

    plan_map = {"basic": PlanType.BASIC, "premium": PlanType.PREMIUM}
    async for session in get_main_session():
        result = await session.execute(select(Tenant).where(Tenant.id == int(tenant_id)))
        tenant = result.scalar_one_or_none()
        if tenant:
            tenant.stripe_customer_id = customer_id
            tenant.stripe_subscription_id = subscription_id
            tenant.plan = plan_map.get(plan, PlanType.BASIC)
            tenant.subscription_status = "active"
            await add_operation_log(
                session,
                user_id=0,
                tenant_id=tenant.id,
                action="stripe.checkout_completed",
                resource_type="subscription",
                resource_id=str(subscription_id or ""),
                result="success",
                summary=f"订阅创建 plan={plan}",
            )
            await session.commit()

    logger.info("Subscription created tenant_id=%s plan=%s customer=%s", tenant_id, plan, customer_id)


async def _handle_subscription_updated(data: dict) -> None:
    subscription_id = data.get("id")
    status = data.get("status", "unknown")
    price_id = None
    items = data.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")

    async for session in get_main_session():
        result = await session.execute(
            select(Tenant).where(Tenant.stripe_subscription_id == subscription_id)
        )
        tenant = result.scalar_one_or_none()
        if tenant:
            tenant.plan = _plan_from_price_id(price_id) if status in {"active", "trialing"} else PlanType.FREE
            tenant.subscription_status = status
            await add_operation_log(
                session,
                user_id=0,
                tenant_id=tenant.id,
                action="stripe.subscription_updated",
                resource_type="subscription",
                resource_id=str(subscription_id or ""),
                result="success",
                summary=f"订阅状态 {status}",
            )
            await session.commit()

    logger.info("Subscription updated subscription=%s status=%s", subscription_id, status)


async def _handle_subscription_deleted(data: dict) -> None:
    subscription_id = data.get("id")

    async for session in get_main_session():
        result = await session.execute(
            select(Tenant).where(Tenant.stripe_subscription_id == subscription_id)
        )
        tenant = result.scalar_one_or_none()
        if tenant:
            tenant.plan = PlanType.FREE
            tenant.stripe_subscription_id = None
            tenant.subscription_status = "canceled"
            await add_operation_log(
                session,
                user_id=0,
                tenant_id=tenant.id,
                action="stripe.subscription_deleted",
                resource_type="subscription",
                resource_id=str(subscription_id or ""),
                result="success",
                summary="订阅取消",
            )
            await session.commit()

    logger.info("Subscription canceled subscription=%s", subscription_id)


async def _handle_invoice_failed(data: dict) -> None:
    subscription_id = data.get("subscription")
    async for session in get_main_session():
        result = await session.execute(
            select(Tenant).where(Tenant.stripe_subscription_id == subscription_id)
        )
        tenant = result.scalar_one_or_none()
        if tenant:
            tenant.subscription_status = "past_due"
            await add_operation_log(
                session,
                user_id=0,
                tenant_id=tenant.id,
                action="stripe.invoice_failed",
                resource_type="subscription",
                resource_id=str(subscription_id or ""),
                result="failed",
                summary="账单支付失败",
            )
            await session.commit()

    logger.warning("Invoice payment failed subscription=%s", subscription_id)


class DevUpgradeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: str  # "free", "basic", "premium"


@router.post("/dev-upgrade")
async def dev_upgrade_tenant(
    body: DevUpgradeRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    """[DEV ONLY] 一键模拟升级当前租户的套餐，供本地测试和商业演示使用。"""
    settings = get_settings()
    if not settings.debug:
        raise AppException(403, "该操作仅限本地 DEBUG 开发调试模式使用，生产环境已强制关闭")

    tenant = (await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one_or_none()
    if not tenant:
        raise AppException(404, f"未找到关联的租户: {user.tenant_id}")

    plan_map = {
        "free": PlanType.FREE,
        "basic": PlanType.BASIC,
        "premium": PlanType.PREMIUM,
    }
    target_plan = plan_map.get(body.plan.lower())
    if target_plan is None:
        raise ValidationError(f"无效的套餐类型: {body.plan}")

    tenant.plan = target_plan
    tenant.subscription_status = "active" if body.plan.lower() != "free" else "canceled"
    if body.plan.lower() == "free":
        tenant.stripe_subscription_id = None
    else:
        tenant.stripe_subscription_id = f"sub_dev_{secrets.token_hex(8)}"

    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="stripe.dev_upgrade",
        resource_type="subscription",
        resource_id=str(tenant.stripe_subscription_id or ""),
        result="success",
        summary=f"[DEV] 模拟升级当前租户套餐为 {body.plan}",
    )
    await session.commit()
    return {"ok": True, "message": f"成功模拟切换租户套餐为 {body.plan}"}
