"""Automation task API routes."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_verified_email
from app.core.database import get_main_session
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.request_id import get_request_id
from app.model.tenant_models import AutomationTask
from app.repository.config_repository import get_config_model
from app.service.entitlement_service import require_automation
from app.repository.operation_audit_repository import add_operation_log
from app.schema.audit import (
    AutomationTaskUpdateRequest,
    TaskRunLogListResponse,
    TaskRunRequest,
    TaskStatusResponse,
)
from app.service.task_service import list_task_runs, task_runtime, task_to_dict

router = APIRouter(prefix="/tasks", tags=["自动化任务"])


async def _ensure_premium(user: CurrentUser, session: AsyncSession) -> None:
    require_verified_email(user, "自动化任务")
    await require_automation(session, user)


@router.get("/status", response_model=TaskStatusResponse)
async def get_task_status(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> TaskStatusResponse:
    return TaskStatusResponse(**await task_runtime.status_for_user(session, user.id, user.tenant_id))


@router.get("/runs", response_model=TaskRunLogListResponse)
async def get_task_runs(
    user: CurrentUser,
    page: int = 1,
    page_size: int = 25,
    session: AsyncSession = Depends(get_main_session),
) -> TaskRunLogListResponse:
    records, count, normalized_page_size = await list_task_runs(session, user.id, user.tenant_id, page, page_size)
    return TaskRunLogListResponse(records=records, count=count, page=max(page, 1), page_size=normalized_page_size)


@router.patch("/{task_id}")
async def update_task(
    task_id: int,
    body: AutomationTaskUpdateRequest,
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    await _ensure_premium(user, session)
    result = await session.execute(
        select(AutomationTask).where(
            AutomationTask.id == task_id,
            AutomationTask.user_id == user.id,
            AutomationTask.tenant_id == user.tenant_id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError("自动化任务", str(task_id))
    if body.interval_minutes is not None:
        if body.interval_minutes < 5 or body.interval_minutes > 43200:
            raise ValidationError("任务间隔必须在 5 分钟到 30 天之间")
        task.interval_minutes = body.interval_minutes
    if body.enabled is not None:
        if task.task_type == "automation_live" and body.enabled:
            raise PermissionDeniedError("自动实盘仍处于预留闸门，当前不允许开启")
        task.enabled = body.enabled
        cfg = await get_config_model(session, user.id, user.tenant_id)
        if cfg and task.task_type == "automation_dry_run":
            cfg.automation_enabled = body.enabled or cfg.automation_market_data or cfg.automation_live_enabled
            cfg.automation_dry_run = body.enabled
        if cfg and task.task_type == "market_data":
            cfg.automation_enabled = body.enabled or cfg.automation_dry_run or cfg.automation_live_enabled
            cfg.automation_market_data = body.enabled
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="task.update",
        resource_type="task",
        resource_id=str(task.id),
        request_id=get_request_id(request),
        result="success",
        summary=f"更新任务 {task.task_type}",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return {"ok": True, "task": task_to_dict(task)}


@router.post("/run-now")
async def run_task_now(
    body: TaskRunRequest,
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    await _ensure_premium(user, session)
    if body.task != "automation_dry_run":
        raise ValidationError("当前仅支持 automation_dry_run")
    result = await task_runtime.run_automation_for_user(session, user.id, user.tenant_id)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="task.run_now",
        resource_type="task",
        resource_id=body.task,
        request_id=get_request_id(request),
        result="success" if result.get("ok") else "failed",
        summary=str(result.get("message", "")),
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return result
