"""Notification API routes."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_main_session
from app.core.request_id import get_request_id
from app.repository.config_repository import get_config_dict
from app.repository.operation_audit_repository import add_operation_log
from app.schema.audit import TestEmailRequest
from app.schema.signal import ApiResponse
from app.service.email_service import send_email
from app.service.entitlement_service import require_email_reports

router = APIRouter(prefix="/notifications", tags=["通知"])


@router.post("/test-email", response_model=ApiResponse)
async def test_email(
    body: TestEmailRequest,
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> ApiResponse:
    await require_email_reports(session, user)
    cfg = await get_config_dict(session, user.id, user.tenant_id)
    send_email(cfg, body.subject, body.message)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="notification.test_email",
        resource_type="notification",
        request_id=get_request_id(request),
        result="success",
        summary="发送测试邮件",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return ApiResponse(ok=True, message="测试邮件已发送")
