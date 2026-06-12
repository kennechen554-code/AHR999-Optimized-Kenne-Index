"""
交易历史 API 路由。
"""

import csv
import hashlib
import io
import logging

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.database import get_main_session
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.core.request_id import get_request_id
from app.model.tenant_models import TradeRecord
from app.repository.history_repository import add_trade_records, asset_stats, clear_trade_records, list_trade_records
from app.repository.operation_audit_repository import add_operation_log
from app.schema.audit import HistoryImportConfirmResponse, HistoryImportPreviewResponse, HistoryImportRowPreview
from app.schema.signal import ApiResponse, HistoryResponse, HistoryStatsResponse, TradeRecordCreateRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/history", tags=["历史记录"])
IMPORT_COLUMNS = {
    "ts",
    "symbol",
    "exchange",
    "mode",
    "strategy_mode",
    "usdt",
    "price",
    "qty",
    "kenne_index",
    "mult",
    "momentum",
    "status",
    "order_id",
    "note",
}
ALLOWED_IMPORT_SYMBOLS = {"BTC", "ETH", "SOL"}
ALLOWED_IMPORT_MODES = {"dry_run", "live"}
ALLOWED_IMPORT_STATUSES = {"dry_run", "filled", "failed", "skipped"}


def _dedupe_key(row: dict[str, str]) -> str:
    parts = [
        row.get("ts", "").strip(),
        row.get("symbol", "").strip().upper(),
        row.get("mode", "").strip(),
        row.get("status", "").strip(),
        row.get("strategy_mode", "").strip(),
        row.get("usdt", "").strip(),
        row.get("price", "").strip(),
        row.get("qty", "").strip(),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


async def _read_import_rows(
    file: UploadFile,
    session: AsyncSession,
    user_id: int,
    tenant_id: int,
) -> tuple[list[HistoryImportRowPreview], list[dict[str, object]]]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise ValidationError("只允许导入 CSV 文件")
    content = await file.read()
    if not content:
        raise ValidationError("CSV 文件为空")
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValidationError("CSV 缺少表头")
    missing = sorted(IMPORT_COLUMNS.difference(set(reader.fieldnames)))
    if missing:
        raise ValidationError(f"CSV 缺少必需列: {', '.join(missing)}")

    previews: list[HistoryImportRowPreview] = []
    valid_rows: list[dict[str, object]] = []
    for index, raw in enumerate(reader, start=2):
        row = {key: str(raw.get(key) or "").strip() for key in IMPORT_COLUMNS}
        symbol = row["symbol"].upper()
        mode = row["mode"] or "dry_run"
        status = row["status"] or "dry_run"
        error = ""
        try:
            if symbol not in ALLOWED_IMPORT_SYMBOLS:
                raise ValueError("资产必须是 BTC、ETH 或 SOL")
            if mode not in ALLOWED_IMPORT_MODES:
                raise ValueError("mode 必须是 dry_run 或 live")
            if status not in ALLOWED_IMPORT_STATUSES:
                raise ValueError("status 无效")
            usdt = float(row["usdt"] or 0)
            if usdt < 0:
                raise ValueError("usdt 不能为负数")
            dedupe_key = _dedupe_key(row)
            duplicate_result = await session.execute(
                select(TradeRecord.id).where(
                    TradeRecord.user_id == user_id,
                    TradeRecord.tenant_id.in_((tenant_id, 0)),
                    TradeRecord.dedupe_key == dedupe_key,
                )
            )
            duplicate = duplicate_result.scalar_one_or_none() is not None
            payload = {
                **row,
                "symbol": symbol,
                "mode": mode,
                "status": status,
                "usdt": usdt,
                "price": float(row["price"] or 0),
                "qty": float(row["qty"] or 0),
                "kenne_index": float(row["kenne_index"] or 0),
                "mult": float(row["mult"] or 0),
                "dedupe_key": dedupe_key,
            }
            if not duplicate:
                valid_rows.append(payload)
            previews.append(
                HistoryImportRowPreview(
                    row_number=index,
                    symbol=symbol,
                    status=status,
                    mode=mode,
                    usdt=usdt,
                    dedupe_key=dedupe_key,
                    duplicate=duplicate,
                )
            )
        except ValueError as exc:
            error = str(exc)
            previews.append(
                HistoryImportRowPreview(
                    row_number=index,
                    symbol=symbol,
                    status=status,
                    mode=mode,
                    error=error,
                )
            )
    return previews, valid_rows


@router.get("", response_model=HistoryResponse)
async def get_history(
    user: CurrentUser,
    month: str | None = None,
    status: str | None = None,
    symbol: str | None = None,
    mode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    page_size: int = 25,
    session: AsyncSession = Depends(get_main_session),
) -> HistoryResponse:
    """
    查询交易历史记录。

    Args:
        month: 可选月份过滤（格式 YYYY-MM）
        status: 可选状态过滤（filled / dry_run / all）
    """
    records, count, total, normalized_page_size = await list_trade_records(
        session=session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        month=month,
        status=status,
        symbol=symbol,
        mode=mode,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return HistoryResponse(
        records=records,
        total=total,
        count=count,
        page=max(page, 1),
        page_size=normalized_page_size,
    )


@router.get("/stats", response_model=HistoryStatsResponse)
async def get_history_stats(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> HistoryStatsResponse:
    assets = await asset_stats(session, user.id, user.tenant_id)
    return HistoryStatsResponse(
        assets=assets,
        total_usdt=round(sum(item.total_usdt for item in assets), 2),
        total_qty=round(sum(item.total_qty for item in assets), 8),
    )


@router.get("/export")
async def export_history_csv(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> StreamingResponse:
    result = await session.execute(
        select(TradeRecord)
        .where(TradeRecord.user_id == user.id, TradeRecord.tenant_id.in_((user.tenant_id, 0)))
        .order_by(TradeRecord.created_at.desc(), TradeRecord.id.desc())
    )
    output = io.StringIO()
    fieldnames = [
        "ts", "created_at", "symbol", "exchange", "mode", "strategy_mode", "usdt",
        "price", "qty", "kenne_index", "mult", "momentum", "status", "order_id", "note",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for record in result.scalars().all():
        writer.writerow({
            "ts": record.ts,
            "created_at": record.created_at.isoformat() if record.created_at else "",
            "symbol": record.symbol,
            "exchange": record.exchange,
            "mode": record.mode,
            "strategy_mode": record.strategy_mode,
            "usdt": record.usdt,
            "price": record.price,
            "qty": record.qty,
            "kenne_index": record.kenne_index,
            "mult": record.mult,
            "momentum": record.momentum,
            "status": record.status,
            "order_id": record.order_id,
            "note": record.note,
        })
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kenne-trade-history.csv"'},
    )


@router.post("/import/preview", response_model=HistoryImportPreviewResponse)
async def preview_history_import(
    user: CurrentUser,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_main_session),
) -> HistoryImportPreviewResponse:
    previews, valid_rows = await _read_import_rows(file, session, user.id, user.tenant_id)
    invalid_count = sum(1 for row in previews if row.error)
    duplicate_count = sum(1 for row in previews if row.duplicate)
    return HistoryImportPreviewResponse(
        valid_count=len(valid_rows),
        invalid_count=invalid_count,
        duplicate_count=duplicate_count,
        rows=previews[:100],
        message="预览完成，最多返回前 100 行明细",
    )


@router.post("/import/confirm", response_model=HistoryImportConfirmResponse)
async def confirm_history_import(
    request: Request,
    user: CurrentUser,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_main_session),
) -> HistoryImportConfirmResponse:
    previews, valid_rows = await _read_import_rows(file, session, user.id, user.tenant_id)
    invalid_count = sum(1 for row in previews if row.error)
    if invalid_count:
        raise ValidationError("CSV 仍包含无效行，请先修正后再导入")
    grouped_by_mode: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in valid_rows:
        key = (str(row.get("mode") or "dry_run"), str(row.get("strategy_mode") or "per_asset_strict_dd"))
        grouped_by_mode.setdefault(key, []).append(row)
    imported = 0
    for (mode, strategy_mode), rows in grouped_by_mode.items():
        imported += len(await add_trade_records(session, user.id, user.tenant_id, rows, mode, strategy_mode))
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="history.import",
        resource_type="trade_record",
        request_id=get_request_id(request),
        result="success",
        summary=f"导入交易审计 {imported} 条",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return HistoryImportConfirmResponse(
        imported_count=imported,
        skipped_duplicates=sum(1 for row in previews if row.duplicate),
        message=f"已导入 {imported} 条审计记录",
    )


@router.post("/add")
async def add_trade_record(
    record: TradeRecordCreateRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> ApiResponse:
    """开发环境内部调试接口；生产审计记录只能由 DCA 执行链路写入。"""
    if not get_settings().debug:
        raise PermissionDeniedError("生产环境禁止客户端直接写入审计记录")
    await add_trade_records(
        session=session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        orders=[record.model_dump()],
        mode=record.mode,
        strategy_mode=record.strategy_mode,
    )
    return ApiResponse(ok=True, message="记录已添加")


@router.post("/init", response_model=ApiResponse)
async def init_history(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> ApiResponse:
    """开发环境清空当前账户交易历史。"""
    if not get_settings().debug:
        raise PermissionDeniedError("生产环境禁止清空真实审计历史")
    deleted = await clear_trade_records(session, user.id, user.tenant_id)
    logger.info("交易历史已初始化: user_id=%d", user.id)
    return ApiResponse(ok=True, message=f"历史记录已清空，共 {deleted} 条")
