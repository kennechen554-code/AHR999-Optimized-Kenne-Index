"""Exchange operations: exchange metadata, balances, DCA execution, and market data refresh."""

import json
import logging
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, StepUpCode, require_verified_email
from app.core.config import get_settings
from app.core.database import get_main_session
from app.core.exceptions import BudgetExhaustedError, ExchangeError, PermissionDeniedError
from app.core.request_id import get_request_id
from app.model.user import Tenant
from app.repository.config_repository import get_config_dict
from app.repository.history_repository import add_trade_records, monthly_spent
from app.repository.operation_audit_repository import add_operation_log
from app.schema.signal import DcaRunResponse
from app.service.dca_service import run_dca
from app.service.entitlement_service import (
    enforce_live_order_cap,
    get_user_entitlements,
    require_automation,
    require_exchange_supported,
    require_live_trading,
    supported_exchanges_for_user,
)
from app.service.exchange_service import (
    EXCHANGE_MAP,
    create_exchange,
    fetch_balance,
    fetch_candles_from_exchange,
)
from app.service.mfa_service import require_step_up
from app.service.risk_event_service import record_risk_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/exchange", tags=["交易所"])
MARKET_DATA_SOURCES = ("okx", "binance")


def _order_usdt_sum(orders: list[dict], statuses: set[str]) -> float:
    return sum(float(order.get("usdt", 0) or 0) for order in orders if str(order.get("status", "")).lower() in statuses)


def _audit_summary(cfg: dict[str, object], dry_run: bool, result: dict[str, object]) -> str:
    orders = [item for item in result.get("orders", []) if isinstance(item, dict)]
    symbols = sorted({str(order.get("symbol")) for order in orders if order.get("symbol")})
    failed_count = sum(1 for order in orders if str(order.get("status", "")).lower() in {"failed", "rejected", "error"})
    summary = {
        "exchange": str(cfg.get("exchange", "okx")),
        "dry_run": dry_run,
        "mode": str(result.get("mode") or ("dry_run" if dry_run else "live")),
        "order_count": len(orders),
        "symbols": symbols,
        "total_usdt": float(result.get("total_usdt", 0) or 0),
        "filled_usdt": _order_usdt_sum(orders, {"filled"}),
        "dry_run_usdt": _order_usdt_sum(orders, {"dry_run"}),
        "failed_count": failed_count,
    }
    return json.dumps(summary, ensure_ascii=False, sort_keys=True)


async def _ensure_live_trading_open(session: AsyncSession, user: CurrentUser) -> None:
    settings = get_settings()
    if not settings.global_live_trading_enabled:
        raise PermissionDeniedError("全局实盘交易开关已关闭")
    result = await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant and tenant.live_trading_paused:
        raise PermissionDeniedError("当前租户实盘交易已暂停")


@router.get("/list")
async def list_exchanges(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict[str, str]:
    supported = await supported_exchanges_for_user(session, user)
    return {key: value for key, value in EXCHANGE_MAP.items() if key in supported}


@router.get("/balance")
async def check_balance(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    cfg = await get_config_dict(session, user.id, user.tenant_id)
    await require_exchange_supported(session, user, str(cfg.get("exchange", "okx")))
    if not cfg.get("api_key_encrypted"):
        raise ExchangeError("未配置 API Key")

    exchange = create_exchange(
        cfg.get("exchange", "okx"),
        cfg.get("api_key_encrypted", ""),
        cfg.get("api_secret_encrypted", ""),
        cfg.get("api_passphrase_encrypted", ""),
        cfg.get("simulated", True),
    )
    return await fetch_balance(exchange)


@router.get("/preflight")
async def trading_preflight(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    cfg = await get_config_dict(session, user.id, user.tenant_id)
    exchange_id = str(cfg.get("exchange", "okx"))
    settings = get_settings()
    supported = await supported_exchanges_for_user(session, user)
    tenant_result = await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    entitlements = await get_user_entitlements(session, user)
    live_cap = float(entitlements.get("max_live_order_usdt", 0) or 0)
    entitlements_supported = exchange_id in supported
    spent_live = await monthly_spent(session, user.id, user.tenant_id, statuses=("filled",))
    spent_dry = await monthly_spent(session, user.id, user.tenant_id, statuses=("dry_run",))
    monthly_budget = float(cfg.get("budget_amount", 0) or 0)
    market_data = {}
    now = datetime.now(timezone.utc)
    for symbol, path in settings.data_files.items():
        exists = path.exists()
        updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc) if exists else None
        age_hours = round((now - updated_at).total_seconds() / 3600, 2) if updated_at else None
        market_data[symbol] = {
            "exists": exists,
            "updated_at": updated_at.isoformat() if updated_at else "",
            "age_hours": age_hours,
            "size_bytes": path.stat().st_size if exists else 0,
        }

    balance_status = "not_checked"
    balance_error = ""
    if cfg.get("api_key_encrypted"):
        try:
            exchange = create_exchange(
                exchange_id,
                cfg.get("api_key_encrypted", ""),
                cfg.get("api_secret_encrypted", ""),
                cfg.get("api_passphrase_encrypted", ""),
                cfg.get("simulated", True),
            )
            await fetch_balance(exchange)
            balance_status = "ok"
        except Exception as exc:
            balance_status = "failed"
            balance_error = str(exc)

    checks = [
        {"key": "email_verified", "ok": bool(user.email_verified), "message": "邮箱已验证"},
        {"key": "exchange_supported", "ok": entitlements_supported, "message": f"套餐支持交易所 {exchange_id}"},
        {"key": "api_key", "ok": bool(cfg.get("api_key_encrypted")), "message": "交易所 API Key 已配置"},
        {"key": "balance", "ok": balance_status in {"ok", "not_checked"}, "message": f"余额读取状态: {balance_status}"},
        {"key": "global_live", "ok": settings.global_live_trading_enabled, "message": "全局实盘开关已开启"},
        {"key": "tenant_live", "ok": not bool(tenant and tenant.live_trading_paused), "message": "租户实盘未暂停"},
        {"key": "budget", "ok": monthly_budget > 0, "message": f"月度预算 {monthly_budget:.2f} USDT"},
    ]

    return {
        "ok": all(item["ok"] for item in checks),
        "exchange": exchange_id,
        "simulated": bool(cfg.get("simulated", True)),
        "budget": {
            "mode": str(cfg.get("budget_mode", "MONTHLY")),
            "monthly_budget": monthly_budget,
            "spent_live": round(spent_live, 2),
            "spent_dry": round(spent_dry, 2),
            "remaining_live": round(max(monthly_budget - spent_live, 0), 2),
        },
        "live": {
            "enabled_by_plan": bool(entitlements.get("live_trading")),
            "global_enabled": settings.global_live_trading_enabled,
            "tenant_paused": bool(tenant and tenant.live_trading_paused),
            "cap_usdt": live_cap,
        },
        "balance": {"status": balance_status, "error": balance_error},
        "market_data": market_data,
        "checks": checks,
    }


@router.post("/run-dca", response_model=DcaRunResponse)
async def execute_dca(
    request: Request,
    user: CurrentUser,
    dry_run: bool = True,
    confirm_live: bool = False,
    step_up_code: StepUpCode = None,
    session: AsyncSession = Depends(get_main_session),
) -> DcaRunResponse:
    if not dry_run:
        require_verified_email(user, "实盘执行")
        await require_step_up(session, user, step_up_code or "", "实盘执行")
        await _ensure_live_trading_open(session, user)
        await require_live_trading(session, user)
        if not confirm_live:
            raise PermissionDeniedError("实盘执行需要二次确认")

    cfg = await get_config_dict(session, user.id, user.tenant_id)
    await require_exchange_supported(session, user, str(cfg.get("exchange", "okx")))
    settings = get_settings()
    strategy_mode = str(cfg.get("strategy_mode", "per_asset_strict_dd"))

    if cfg.get("budget_mode") == "MONTHLY":
        statuses = ("dry_run",) if dry_run else ("filled",)
        spent = await monthly_spent(session, user.id, user.tenant_id, statuses=statuses)
        monthly_budget = float(cfg.get("budget_amount", 700) or 700)
        remaining = max(monthly_budget - spent, 0)
        if remaining <= 0:
            await record_risk_event(
                session,
                tenant_id=user.tenant_id,
                user_id=user.id,
                event_type="budget_exhausted",
                severity="warning",
                summary="月度预算已用完",
                request_id=get_request_id(request),
            )
            raise BudgetExhaustedError("本月预算已用完，请调整预算或等待下个周期")
        cfg = {**cfg, "budget_amount": min(monthly_budget, remaining)}

    if not dry_run:
        await enforce_live_order_cap(session, user, float(cfg.get("budget_amount", 0) or 0))
    cfg["user_id"] = user.id
    cfg["tenant_id"] = user.tenant_id
    try:
        result = await run_dca(cfg, settings.data_files, dry_run=dry_run, session=session)
    except TypeError as e:
        if "session" in str(e):
            result = await run_dca(cfg, settings.data_files, dry_run=dry_run)
        else:
            raise
    if not result.get("ok"):
        await record_risk_event(
            session,
            tenant_id=user.tenant_id,
            user_id=user.id,
            event_type="dca_execution_failed",
            severity="critical" if not dry_run else "warning",
            summary=str(result.get("message", "执行失败")),
            request_id=get_request_id(request),
        )
    if not dry_run:
        await enforce_live_order_cap(session, user, float(result.get("total_usdt", 0) or 0))
        await enforce_live_order_cap(session, user, _order_usdt_sum(result.get("orders", []), {"filled"}))
    await add_trade_records(
        session=session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        orders=result.get("orders", []),
        mode=str(result.get("mode") or ("dry_run" if dry_run else "live")),
        strategy_mode=strategy_mode,
    )
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="exchange.run_dca",
        resource_type="dca",
        resource_id=str(result.get("mode") or ""),
        request_id=get_request_id(request),
        result="success" if result.get("ok") else "failed",
        summary=_audit_summary(cfg, dry_run, result),
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return DcaRunResponse(**result)


@router.post("/update-data")
async def update_market_data(
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> list[dict]:
    require_verified_email(user, "自动化行情更新")
    await require_automation(session, user)
    settings = get_settings()
    results = []

    for symbol, csv_path in settings.data_files.items():
        try:
            if csv_path.exists():
                existing = pd.read_csv(csv_path)
                existing["Open time"] = pd.to_datetime(
                    existing["Open time"].astype(str).str.strip(),
                    format="mixed",
                )
                last_ts = existing["Open time"].max()
                since_ms = int(last_ts.timestamp() * 1000)
            else:
                existing = None
                since_ms = None

            ohlcv: list[list] = []
            source = ""
            last_error = ""
            for exchange_id in MARKET_DATA_SOURCES:
                try:
                    ohlcv = await fetch_candles_from_exchange(
                        exchange_id, f"{symbol}/USDT", "4h", since_ms=since_ms,
                    )
                    source = exchange_id
                    break
                except ExchangeError as exc:
                    last_error = str(exc)
                    logger.warning(
                        "[%s] market data source %s failed: %s",
                        symbol,
                        exchange_id,
                        exc,
                    )

            if not source:
                raise ExchangeError(last_error or "所有行情源均不可用")

            if not ohlcv:
                results.append({"symbol": symbol, "added": 0, "source": source})
                continue

            new_df = pd.DataFrame(
                ohlcv,
                columns=["Open time", "Open", "High", "Low", "Close", "Volume"],
            )
            new_df["Open time"] = pd.to_datetime(new_df["Open time"], unit="ms")

            if existing is not None:
                combined = (
                    pd.concat([existing, new_df])
                    .drop_duplicates("Open time")
                    .sort_values("Open time")
                )
                added = len(combined) - len(existing)
            else:
                combined = new_df
                added = len(new_df)

            combined.to_csv(csv_path, index=False)
            results.append({"symbol": symbol, "added": added, "source": source})
            logger.info("[%s] market data updated from %s +%d candles", symbol, source, added)
        except Exception as exc:
            logger.error("[%s] market data update failed: %s", symbol, exc)
            results.append({"symbol": symbol, "error": str(exc)})

    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="exchange.update_data",
        resource_type="market_data",
        request_id=get_request_id(request),
        result="success",
        summary=f"更新行情 {len(results)} 个资产",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return results
