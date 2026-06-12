"""Operation audit log repository."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.tenant_models import OperationAuditLog
from app.schema.audit import OperationAuditLogResponse


def _to_response(record: OperationAuditLog) -> OperationAuditLogResponse:
    return OperationAuditLogResponse(
        id=record.id,
        user_id=record.user_id,
        tenant_id=record.tenant_id,
        action=record.action,
        resource_type=record.resource_type,
        resource_id=record.resource_id,
        request_id=record.request_id,
        result=record.result,
        summary=record.summary,
        ip_address=record.ip_address,
        user_agent=record.user_agent,
        created_at=record.created_at.isoformat() if record.created_at else "",
    )


async def add_operation_log(
    session: AsyncSession,
    *,
    user_id: int = 0,
    tenant_id: int = 0,
    action: str,
    resource_type: str = "",
    resource_id: str = "",
    request_id: str = "",
    result: str = "success",
    summary: str = "",
    ip_address: str = "",
    user_agent: str = "",
) -> OperationAuditLog:
    record = OperationAuditLog(
        user_id=user_id,
        tenant_id=tenant_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id[:64],
        result=result,
        summary=summary[:512],
        ip_address=ip_address[:64],
        user_agent=user_agent[:256],
        created_at=datetime.now(timezone.utc),
    )
    session.add(record)
    await session.flush()
    return record


async def list_operation_logs(
    session: AsyncSession,
    tenant_id: int,
    action: str | None = None,
    result: str | None = None,
    user_id: int | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request_id: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[OperationAuditLogResponse], int, int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    filters = [OperationAuditLog.tenant_id == tenant_id]
    if action and action != "all":
        filters.append(OperationAuditLog.action == action)
    if result and result != "all":
        filters.append(OperationAuditLog.result == result)
    if user_id:
        filters.append(OperationAuditLog.user_id == user_id)
    if resource_type and resource_type != "all":
        filters.append(OperationAuditLog.resource_type == resource_type)
    if resource_id:
        filters.append(OperationAuditLog.resource_id == resource_id)
    if request_id:
        filters.append(OperationAuditLog.request_id == request_id)

    count_result = await session.execute(select(func.count()).select_from(OperationAuditLog).where(*filters))
    count = int(count_result.scalar_one() or 0)
    rows = await session.execute(
        select(OperationAuditLog)
        .where(*filters)
        .order_by(OperationAuditLog.created_at.desc(), OperationAuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [_to_response(item) for item in rows.scalars().all()], count, page_size
