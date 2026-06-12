"""Operational health checks."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.database import get_main_session
from app.core.exceptions import PermissionDeniedError
from app.core.redis_client import get_redis
from app.model.user import UserRole
from app.service.task_service import task_runtime

router = APIRouter(prefix="/health", tags=["health"])


async def _collect_health(session: AsyncSession) -> dict[str, object]:
    settings = get_settings()
    checks: dict[str, object] = {
        "app": "ok",
        "database": "unknown",
        "redis": "disabled",
        "system_smtp": bool(settings.system_smtp_host and settings.system_smtp_user),
        "stripe_webhook": bool(settings.stripe_webhook_secret) or settings.debug,
        "tasks": task_runtime.status(),
        "market_data": {},
    }
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "failed"

    redis = await get_redis()
    checks["redis"] = "ok" if redis else "unavailable"

    market_data: dict[str, dict[str, object]] = {}
    for symbol, path in settings.data_files.items():
        exists = path.exists()
        market_data[symbol] = {
            "exists": exists,
            "updated_at": path.stat().st_mtime if exists else None,
            "size_bytes": path.stat().st_size if exists else 0,
        }
    checks["market_data"] = market_data
    return checks


@router.get("")
async def health(session: AsyncSession = Depends(get_main_session)) -> dict[str, object]:
    return await _collect_health(session)


@router.get("/detail")
async def health_detail(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict[str, object]:
    if user.role not in {UserRole.OWNER, UserRole.ADMIN}:
        raise PermissionDeniedError("仅管理员可查看详细健康检查")
    return await _collect_health(session)
