"""Persistent audit history repository."""

from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.model.tenant_models import TradeRecord
from app.schema.signal import AssetHistoryStat, TradeRecordResponse


AUDIT_SPEND_STATUSES = ("filled", "dry_run")


def _record_to_response(record: TradeRecord) -> TradeRecordResponse:
    return TradeRecordResponse(
        id=record.id,
        ts=record.ts,
        symbol=record.symbol,
        exchange=record.exchange,
        mode=record.mode,
        strategy_mode=record.strategy_mode,
        usdt=record.usdt,
        kenne_index=record.kenne_index,
        mult=record.mult,
        momentum=record.momentum,
        order_id=record.order_id,
        status=record.status,
        note=record.note,
        price=record.price,
        qty=record.qty,
        created_at=record.created_at.isoformat() if record.created_at else "",
    )


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError("日期格式无效，请使用 YYYY-MM-DD 或 ISO 时间") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _month_bounds(month: str | None) -> tuple[datetime | None, datetime | None]:
    if not month:
        return None, None
    try:
        year_text, month_text = month.split("-")
        year = int(year_text)
        month_index = int(month_text)
    except ValueError as exc:
        raise ValidationError("月份格式无效，请使用 YYYY-MM") from exc
    if month_index < 1 or month_index > 12:
        raise ValidationError("月份范围无效，请使用 01-12")
    start = datetime(year, month_index, 1, tzinfo=timezone.utc)
    if month_index == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month_index + 1, 1, tzinfo=timezone.utc)
    return start, end


async def add_trade_records(
    session: AsyncSession,
    user_id: int,
    tenant_id: int,
    orders: list[dict],
    mode: str,
    strategy_mode: str,
) -> list[TradeRecord]:
    records: list[TradeRecord] = []
    for order in orders:
        if order.get("db_saved"):
            continue
        record = TradeRecord(
            user_id=user_id,
            tenant_id=tenant_id,
            ts=str(order.get("ts") or datetime.now(timezone.utc).isoformat()),
            symbol=str(order.get("symbol") or ""),
            exchange=str(order.get("exchange") or "okx"),
            mode=mode,
            strategy_mode=str(order.get("strategy_mode") or strategy_mode),
            usdt=float(order.get("usdt") or 0),
            kenne_index=float(order.get("kenne_index") or 0),
            mult=float(order.get("mult") or 0),
            momentum=str(order.get("momentum") or ""),
            order_id=str(order.get("order_id") or ""),
            status=str(order.get("status") or "failed"),
            order_status=str(order.get("order_status") or ("dry_run" if mode == "dry_run" else "filled")),
            note=str(order.get("note") or ""),
            dedupe_key=str(order.get("dedupe_key") or ""),
            price=float(order.get("price") or 0),
            qty=float(order.get("qty") or 0),
        )
        session.add(record)
        records.append(record)
    await session.flush()
    return records


async def list_trade_records(
    session: AsyncSession,
    user_id: int,
    tenant_id: int,
    month: str | None = None,
    status: str | None = None,
    symbol: str | None = None,
    mode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[TradeRecordResponse], int, float, int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    filters = [TradeRecord.user_id == user_id, TradeRecord.tenant_id.in_((tenant_id, 0))]
    if status and status != "all":
        filters.append(TradeRecord.status == status)
    if symbol and symbol != "all":
        filters.append(TradeRecord.symbol == symbol.upper())
    if mode and mode != "all":
        filters.append(TradeRecord.mode == mode)

    start_dt, end_dt = _month_bounds(month)
    explicit_start = _parse_date(start_date)
    explicit_end = _parse_date(end_date)
    start_dt = explicit_start or start_dt
    end_dt = explicit_end or end_dt
    if start_dt:
        filters.append(TradeRecord.created_at >= start_dt)
    if end_dt:
        filters.append(TradeRecord.created_at <= end_dt)

    count_result = await session.execute(select(func.count()).select_from(TradeRecord).where(*filters))
    count = int(count_result.scalar_one() or 0)

    total_result = await session.execute(
        select(func.coalesce(func.sum(TradeRecord.usdt), 0.0)).where(
            *filters,
            TradeRecord.status.in_(AUDIT_SPEND_STATUSES),
        )
    )
    total = float(total_result.scalar_one() or 0)

    records_result = await session.execute(
        select(TradeRecord)
        .where(*filters)
        .order_by(TradeRecord.created_at.desc(), TradeRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = [_record_to_response(record) for record in records_result.scalars().all()]
    return records, count, round(total, 2), page_size


async def monthly_spent(
    session: AsyncSession,
    user_id: int,
    tenant_id: int,
    statuses: tuple[str, ...],
    now: datetime | None = None,
) -> float:
    target = now or datetime.now(timezone.utc)
    start = datetime(target.year, target.month, 1, tzinfo=timezone.utc)
    if target.month == 12:
        end = datetime(target.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(target.year, target.month + 1, 1, tzinfo=timezone.utc)

    result = await session.execute(
        select(func.coalesce(func.sum(TradeRecord.usdt), 0.0)).where(
            TradeRecord.user_id == user_id,
            TradeRecord.tenant_id.in_((tenant_id, 0)),
            TradeRecord.status.in_(statuses),
            TradeRecord.created_at >= start,
            TradeRecord.created_at < end,
        )
    )
    return float(result.scalar_one() or 0)


async def clear_trade_records(session: AsyncSession, user_id: int, tenant_id: int) -> int:
    result = await session.execute(
        delete(TradeRecord).where(
            TradeRecord.user_id == user_id,
            TradeRecord.tenant_id.in_((tenant_id, 0)),
        )
    )
    return int(result.rowcount or 0)


async def asset_stats(session: AsyncSession, user_id: int, tenant_id: int) -> list[AssetHistoryStat]:
    result = await session.execute(
        select(TradeRecord).where(
            TradeRecord.user_id == user_id,
            TradeRecord.tenant_id.in_((tenant_id, 0)),
            TradeRecord.status.in_(AUDIT_SPEND_STATUSES),
        )
    )
    grouped: dict[str, dict[str, float]] = {}
    for record in result.scalars().all():
        item = grouped.setdefault(
            record.symbol,
            {"total_usdt": 0.0, "total_qty": 0.0, "sim_usdt": 0.0, "live_usdt": 0.0},
        )
        item["total_usdt"] += record.usdt
        item["total_qty"] += record.qty
        if record.status == "dry_run":
            item["sim_usdt"] += record.usdt
        if record.status == "filled":
            item["live_usdt"] += record.usdt

    stats = []
    for symbol, item in sorted(grouped.items()):
        qty = item["total_qty"]
        stats.append(
            AssetHistoryStat(
                symbol=symbol,
                total_usdt=round(item["total_usdt"], 2),
                total_qty=round(qty, 8),
                avg_price=round(item["total_usdt"] / qty, 2) if qty > 0 else 0,
                sim_usdt=round(item["sim_usdt"], 2),
                live_usdt=round(item["live_usdt"], 2),
            )
        )
    return stats
