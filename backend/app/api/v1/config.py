"""
配置管理 API 路由。
"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, StepUpCode, require_verified_email
from app.core.database import get_main_session
from app.core.request_id import get_request_id
from app.repository.config_repository import get_config_response, upsert_config
from app.repository.operation_audit_repository import add_operation_log
from app.schema.signal import ApiResponse, ConfigResponse, ConfigUpdateRequest
from app.service.entitlement_service import require_automation, require_exchange_supported
from app.service.mfa_service import require_step_up

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/config", tags=["配置"])


@router.get("", response_model=ConfigResponse)
async def get_config(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> ConfigResponse:
    """获取当前用户配置（敏感信息已掩码）。"""
    return await get_config_response(session, user.id, user.tenant_id)


@router.post("", response_model=ApiResponse)
async def update_config(
    body: ConfigUpdateRequest,
    request: Request,
    user: CurrentUser,
    step_up_code: StepUpCode = None,
    session: AsyncSession = Depends(get_main_session),
) -> ApiResponse:
    """更新用户配置。"""
    if body.api_key or body.api_secret or body.api_passphrase or body.automation_enabled or body.automation_market_data or body.automation_dry_run or body.automation_live_enabled:
        require_verified_email(user, "更新交易所密钥或自动化配置")
        await require_step_up(session, user, step_up_code or "", "更新交易所密钥或自动化配置")
    await require_exchange_supported(session, user, body.exchange)
    if body.automation_enabled or body.automation_market_data or body.automation_dry_run or body.automation_live_enabled:
        await require_automation(session, user)
    await upsert_config(session, user.id, user.tenant_id, body)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="config.update",
        resource_type="config",
        resource_id=str(user.id),
        request_id=get_request_id(request),
        result="success",
        summary=f"更新配置 exchange={body.exchange} strategy={body.strategy_mode}",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    logger.info("配置已更新: user_id=%d exchange=%s", user.id, body.exchange)
    return ApiResponse(ok=True, message="配置保存成功")
