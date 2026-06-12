"""Operation audit API routes."""

import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_main_session
from app.core.exceptions import PermissionDeniedError
from app.model.tenant_models import OperationAuditLog
from app.model.user import UserRole
from app.repository.operation_audit_repository import list_operation_logs
from app.schema.audit import OperationAuditListResponse

router = APIRouter(prefix="/audit", tags=["操作审计"])


@router.get("/operations", response_model=OperationAuditListResponse)
async def get_operations(
    user: CurrentUser,
    action: str | None = None,
    result: str | None = None,
    user_id: int | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request_id: str | None = None,
    page: int = 1,
    page_size: int = 25,
    session: AsyncSession = Depends(get_main_session),
) -> OperationAuditListResponse:
    if user.role == UserRole.MEMBER:
        if user_id is not None and user_id != user.id:
            raise PermissionDeniedError("成员只能查看自己的操作审计")
        user_id = user.id
    records, count, normalized_page_size = await list_operation_logs(
        session=session,
        tenant_id=user.tenant_id,
        action=action,
        result=result,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        page=page,
        page_size=page_size,
    )
    return OperationAuditListResponse(
        records=records,
        count=count,
        page=max(page, 1),
        page_size=normalized_page_size,
    )


@router.get("/operations/export")
async def export_operations(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> StreamingResponse:
    filters = [OperationAuditLog.tenant_id == user.tenant_id]
    if user.role == UserRole.MEMBER:
        filters.append(OperationAuditLog.user_id == user.id)
    result = await session.execute(
        select(OperationAuditLog)
        .where(*filters)
        .order_by(OperationAuditLog.created_at.desc(), OperationAuditLog.id.desc())
    )
    output = io.StringIO()
    fieldnames = [
        "created_at", "user_id", "tenant_id", "action", "result", "resource_type",
        "resource_id", "request_id", "summary", "ip_address", "user_agent",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for record in result.scalars().all():
        writer.writerow({
            "created_at": record.created_at.isoformat() if record.created_at else "",
            "user_id": record.user_id,
            "tenant_id": record.tenant_id,
            "action": record.action,
            "result": record.result,
            "resource_type": record.resource_type,
            "resource_id": record.resource_id,
            "request_id": record.request_id,
            "summary": record.summary,
            "ip_address": record.ip_address,
            "user_agent": record.user_agent,
        })
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kenne-operation-audit.csv"'},
    )
