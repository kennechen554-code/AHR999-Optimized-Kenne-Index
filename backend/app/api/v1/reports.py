"""Portfolio report routes."""

from collections import defaultdict
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_main_session
from app.core.exceptions import AppException
from app.model.tenant_models import TradeRecord
from app.schema.audit import MonthlyReportItem, MonthlyReportResponse, AiDailyReportResponse
from app.service.entitlement_service import require_premium

router = APIRouter(prefix="/reports", tags=["报表"])


@router.get("/monthly", response_model=MonthlyReportResponse)
async def monthly_report(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> MonthlyReportResponse:
    result = await session.execute(
        select(TradeRecord)
        .where(
            TradeRecord.user_id == user.id,
            TradeRecord.tenant_id.in_((user.tenant_id, 0)),
            TradeRecord.status.in_(("filled", "dry_run")),
        )
        .order_by(TradeRecord.created_at.asc())
    )
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: {
        "total_usdt": 0.0,
        "total_qty": 0.0,
        "sim_usdt": 0.0,
        "live_usdt": 0.0,
        "trade_count": 0.0,
        "estimated_value": 0.0,
    })
    latest_prices: dict[str, float] = {}
    for record in result.scalars().all():
        month = (record.created_at or record.ts)  # type: ignore[assignment]
        month_key = month.strftime("%Y-%m") if hasattr(month, "strftime") else str(month)[:7]
        item = grouped[month_key]
        item["total_usdt"] += record.usdt
        item["total_qty"] += record.qty
        item["trade_count"] += 1
        if record.status == "dry_run":
            item["sim_usdt"] += record.usdt
        if record.status == "filled":
            item["live_usdt"] += record.usdt
        if record.price > 0:
            latest_prices[record.symbol] = record.price
        item["estimated_value"] += record.qty * latest_prices.get(record.symbol, record.price)

    months = []
    for month, item in sorted(grouped.items(), reverse=True):
        estimated_value = round(item["estimated_value"], 2)
        total_usdt = round(item["total_usdt"], 2)
        months.append(
            MonthlyReportItem(
                month=month,
                total_usdt=total_usdt,
                total_qty=round(item["total_qty"], 8),
                sim_usdt=round(item["sim_usdt"], 2),
                live_usdt=round(item["live_usdt"], 2),
                trade_count=int(item["trade_count"]),
                estimated_value=estimated_value,
                estimated_pnl=round(estimated_value - total_usdt, 2),
            )
        )
    return MonthlyReportResponse(
        disclaimer="估算值基于审计记录中的最近成交价，不构成会计、税务或投资建议。",
        months=months,
    )


@router.get("/ai-daily", response_model=AiDailyReportResponse)
async def ai_daily_report(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> AiDailyReportResponse:
    await require_premium(session, user, "AI 智能日报")
    
    root_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
    report_path = root_dir / "reports" / "latest_dca_report.md"
    
    if not report_path.exists():
        raise AppException(404, "AI 定报服务正在初始化，请稍后查看")
        
    try:
        content = report_path.read_text(encoding="utf-8")
        mtime = os.path.getmtime(report_path)
        generated_at = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as exc:
        raise AppException(500, f"读取报告文件失败: {exc}")
        
    return AiDailyReportResponse(content=content, generated_at=generated_at)
