from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.database import get_main_session
from app.core.request_id import get_request_id
from app.engine.per_asset_strategy import (
    DEFAULT_MONTHLY_BUDGET,
    DEFAULT_STRATEGY_MODE,
    SYMBOLS,
    normalize_strategy_mode,
    run_backtest,
    strategy_metadata,
    write_uploads_to_temp,
)
from app.repository.operation_audit_repository import add_operation_log
from app.service.entitlement_service import require_backtesting

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backtest", tags=["Backtest"])


async def _ensure_premium(user: CurrentUser, session: AsyncSession) -> None:
    await require_backtesting(session, user)


def _infer_symbol(raw: str) -> str | None:
    upper = Path(raw).name.upper()
    return next((symbol for symbol in SYMBOLS if symbol in upper), None)


def _parse_server_paths(values: list[str] | None) -> dict[str, Path]:
    if not values:
        return {}

    parsed: dict[str, Path] = {}
    for item in values:
        value = item.strip()
        if not value:
            continue

        if value.startswith("{"):
            try:
                payload = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("server_paths 不是有效 JSON") from exc
            if not isinstance(payload, dict):
                raise ValueError("server_paths JSON 必须是对象")
            for symbol, raw_path in payload.items():
                if not isinstance(raw_path, str):
                    raise ValueError(f"{symbol} 路径必须是字符串")
                normalized_symbol = str(symbol).upper()
                if normalized_symbol not in SYMBOLS:
                    raise ValueError(f"不支持的币种: {symbol}")
                parsed[normalized_symbol] = Path(raw_path)
            continue

        if "=" in value:
            symbol, raw_path = value.split("=", 1)
            normalized_symbol = symbol.strip().upper()
            if normalized_symbol not in SYMBOLS:
                raise ValueError(f"不支持的币种: {symbol}")
            parsed[normalized_symbol] = Path(raw_path.strip())
            continue

        symbol = _infer_symbol(value)
        if not symbol:
            raise ValueError("服务器路径必须能从文件名识别 BTC、ETH 或 SOL，或使用 BTC=路径 格式")
        parsed[symbol] = Path(value)

    return parsed


def _validate_local_paths(paths: dict[str, Path]) -> dict[str, Path]:
    settings = get_settings()
    allowed_dirs = settings.resolved_backtest_allowed_dirs
    resolved_paths: dict[str, Path] = {}

    for symbol, raw_path in paths.items():
        try:
            resolved = raw_path.expanduser().resolve(strict=True)
        except OSError as exc:
            raise ValueError(f"{symbol} 本地 CSV 不存在或不可读取") from exc

        if resolved.suffix.lower() != ".csv":
            raise ValueError(f"{symbol} 只允许读取 CSV 文件")

        if not any(resolved.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs):
            raise ValueError(f"{symbol} 本地路径不在允许目录内")

        resolved_paths[symbol] = resolved

    return resolved_paths


@router.get("/strategies")
async def get_strategies(user: CurrentUser) -> dict:
    """Return strategy metadata derived from executable backend strategy settings."""
    return {
        "default": DEFAULT_STRATEGY_MODE,
        "strategies": strategy_metadata(),
    }


@router.get("/local-datasets")
async def get_local_datasets(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    """Return known local backtest datasets without exposing arbitrary directory browsing."""
    await _ensure_premium(user, session)
    settings = get_settings()
    datasets = []
    for symbol, path in settings.data_files.items():
        resolved = path.resolve()
        exists = resolved.exists()
        datasets.append({
            "symbol": symbol,
            "path": str(resolved),
            "exists": exists,
            "updated_at": resolved.stat().st_mtime if exists else None,
            "size_bytes": resolved.stat().st_size if exists else 0,
        })
    return {
        "allowed_dirs": [str(path) for path in settings.resolved_backtest_allowed_dirs],
        "datasets": datasets,
    }


@router.post("/custom")
async def custom_backtest(
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
    strategy_mode: str = Form(DEFAULT_STRATEGY_MODE),
    start_date: str = Form("2018-07-20"),
    end_date: str = Form("2026-02-24"),
    monthly_budget: float = Form(DEFAULT_MONTHLY_BUDGET),
    files: list[UploadFile] | None = File(None),
    server_paths: list[str] | None = Form(None),
) -> dict:
    await _ensure_premium(user, session)

    if files and len(files) > 3:
        raise HTTPException(status_code=400, detail="最多上传 BTC/ETH/SOL 三个 CSV 文件")

    tmp = None
    try:
        payload = []
        for file in files or []:
            content = await file.read()
            if not content:
                raise ValueError(f"{file.filename or 'CSV'} 是空文件")
            payload.append((file.filename or file.name or "data.csv", content))

        data_files = {}
        if payload:
            tmp, data_files = write_uploads_to_temp(payload)

        local_paths = _validate_local_paths(_parse_server_paths(server_paths))
        duplicated = set(data_files).intersection(local_paths)
        if duplicated:
            raise ValueError(f"同一资产只能提供一个数据源: {', '.join(sorted(duplicated))}")

        data_files.update(local_paths)
        if not data_files:
            raise ValueError("请上传 CSV 或提供允许目录内的服务器本地 CSV 路径")

        result = run_backtest(
            data_files=data_files,
            strategy_mode=normalize_strategy_mode(strategy_mode),
            start=start_date,
            end=end_date,
            monthly_budget=monthly_budget,
        )
        await add_operation_log(
            session,
            user_id=user.id,
            tenant_id=user.tenant_id,
            action="backtest.custom",
            resource_type="backtest",
            resource_id=normalize_strategy_mode(strategy_mode),
            request_id=get_request_id(request),
            result="success",
            summary=f"自定义回测 {start_date} 至 {end_date}",
            ip_address=request.client.host if request.client else "",
            user_agent=request.headers.get("user-agent", ""),
        )
        return {"ok": True, "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("custom backtest failed")
        raise HTTPException(status_code=500, detail="回测失败，请检查数据格式后重试") from exc
    finally:
        if tmp is not None:
            tmp.cleanup()
