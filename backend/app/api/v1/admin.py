"""Tenant administration routes."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, StepUpCode, require_verified_email
from app.core.database import get_main_session
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.core.request_id import get_request_id
from app.model.tenant_models import OperationAuditLog, RetentionPolicy, RiskEvent, TaskRunLog, TenantInvitation
from app.model.user import Tenant, User, UserRole, UserSession
from app.repository.operation_audit_repository import add_operation_log
from app.service.mfa_service import require_step_up
from app.service.risk_event_service import record_risk_event

router = APIRouter(prefix="/admin", tags=["管理"])


class AdminUserStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


class TenantRiskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    live_trading_paused: bool


class CreateInvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    role: UserRole = UserRole.MEMBER


class UpdateUserRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole


class RetentionPolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_audit_days: int = 365
    task_run_days: int = 180
    risk_event_days: int = 730


def _ensure_admin(user: User) -> None:
    if user.role not in {UserRole.OWNER, UserRole.ADMIN}:
        raise PermissionDeniedError("仅管理员可执行该操作")


async def _active_owner_count(session: AsyncSession, tenant_id: int) -> int:
    result = await session.execute(
        select(func.count()).select_from(User).where(
            User.tenant_id == tenant_id,
            User.role == UserRole.OWNER,
            User.is_active.is_(True),
        )
    )
    return int(result.scalar_one() or 0)


async def _active_user_count(session: AsyncSession, tenant_id: int) -> int:
    result = await session.execute(
        select(func.count()).select_from(User).where(
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
        )
    )
    return int(result.scalar_one() or 0)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _invitation_to_dict(invitation: TenantInvitation, include_token: str = "") -> dict:
    return {
        "id": invitation.id,
        "email": invitation.email,
        "role": invitation.role,
        "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else "",
        "accepted_at": invitation.accepted_at.isoformat() if invitation.accepted_at else "",
        "revoked_at": invitation.revoked_at.isoformat() if invitation.revoked_at else "",
        **({"token": include_token} if include_token else {}),
    }


@router.get("/users")
async def list_users(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    _ensure_admin(user)
    result = await session.execute(
        select(User, Tenant)
        .join(Tenant, Tenant.id == User.tenant_id)
        .where(User.tenant_id == user.tenant_id)
        .order_by(User.created_at.desc())
    )
    users = []
    for item, tenant in result.all():
        users.append({
            "id": item.id,
            "email": item.email,
            "display_name": item.display_name,
            "role": item.role.value,
            "tenant_id": item.tenant_id,
            "plan": tenant.plan.value,
            "subscription_status": tenant.subscription_status,
            "is_active": item.is_active,
            "email_verified": item.email_verified,
            "last_login_at": item.last_login_at.isoformat() if item.last_login_at else "",
            "created_at": item.created_at.isoformat() if item.created_at else "",
        })
    return {"users": users}


@router.get("/invitations")
async def list_invitations(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    _ensure_admin(user)
    result = await session.execute(
        select(TenantInvitation)
        .where(TenantInvitation.tenant_id == user.tenant_id)
        .order_by(TenantInvitation.created_at.desc(), TenantInvitation.id.desc())
    )
    return {"invitations": [_invitation_to_dict(item) for item in result.scalars().all()]}


@router.post("/invitations")
async def create_invitation(
    body: CreateInvitationRequest,
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    _ensure_admin(user)
    require_verified_email(user, "邀请团队成员")
    tenant = (await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))).scalar_one_or_none()
    if not tenant:
        raise NotFoundError("租户", str(user.tenant_id))
    if await _active_user_count(session, user.tenant_id) >= tenant.max_users:
        raise PermissionDeniedError("当前套餐成员数已达上限")
    existing_user = (await session.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing_user:
        raise ValidationError("该邮箱已注册")
    pending = (await session.execute(
        select(TenantInvitation).where(
            TenantInvitation.tenant_id == user.tenant_id,
            TenantInvitation.email == body.email,
            TenantInvitation.accepted_at.is_(None),
            TenantInvitation.revoked_at.is_(None),
        )
    )).scalar_one_or_none()
    if pending:
        raise ValidationError("该邮箱已有待接受邀请")

    raw_token = secrets.token_urlsafe(32)
    invitation = TenantInvitation(
        tenant_id=user.tenant_id,
        email=str(body.email),
        role=body.role.value,
        token_hash=_hash_token(raw_token),
        created_by_user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="admin.invitation_create",
        resource_type="invitation",
        resource_id=str(invitation.id),
        request_id=get_request_id(request),
        result="success",
        summary=f"邀请 {body.email} role={body.role.value}",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return {"ok": True, "invitation": _invitation_to_dict(invitation, raw_token)}


@router.delete("/invitations/{invitation_id}")
async def revoke_invitation(
    invitation_id: int,
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    _ensure_admin(user)
    result = await session.execute(
        select(TenantInvitation).where(
            TenantInvitation.id == invitation_id,
            TenantInvitation.tenant_id == user.tenant_id,
        )
    )
    invitation = result.scalar_one_or_none()
    if not invitation:
        raise NotFoundError("邀请", str(invitation_id))
    invitation.revoked_at = datetime.now(timezone.utc)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="admin.invitation_revoke",
        resource_type="invitation",
        resource_id=str(invitation.id),
        request_id=get_request_id(request),
        result="success",
        summary=f"撤销邀请 {invitation.email}",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return {"ok": True, "message": "邀请已撤销"}


@router.patch("/users/{target_user_id}/role")
async def update_user_role(
    target_user_id: int,
    body: UpdateUserRoleRequest,
    request: Request,
    user: CurrentUser,
    step_up_code: StepUpCode = None,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    _ensure_admin(user)
    require_verified_email(user, "修改成员角色")
    await require_step_up(session, user, step_up_code or "", "修改成员角色")
    target = (await session.execute(
        select(User).where(User.id == target_user_id, User.tenant_id == user.tenant_id)
    )).scalar_one_or_none()
    if not target:
        raise NotFoundError("用户", str(target_user_id))
    if target.role == UserRole.OWNER and body.role != UserRole.OWNER and await _active_owner_count(session, user.tenant_id) <= 1:
        raise PermissionDeniedError("不能移除最后一个 OWNER")
    target.role = body.role
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="admin.user_role",
        resource_type="user",
        resource_id=str(target.id),
        request_id=get_request_id(request),
        result="success",
        summary=f"更新用户角色 role={body.role.value}",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return {"ok": True, "message": "用户角色已更新"}


@router.patch("/tenant/risk")
async def update_tenant_risk(
    body: TenantRiskRequest,
    request: Request,
    user: CurrentUser,
    step_up_code: StepUpCode = None,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    _ensure_admin(user)
    require_verified_email(user, "租户交易风控变更")
    await require_step_up(session, user, step_up_code or "", "租户交易风控变更")
    result = await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise NotFoundError("租户", str(user.tenant_id))

    tenant.live_trading_paused = body.live_trading_paused
    await record_risk_event(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        event_type="tenant_live_trading_paused" if body.live_trading_paused else "tenant_live_trading_resumed",
        severity="warning" if body.live_trading_paused else "info",
        summary=f"live_trading_paused={body.live_trading_paused}",
        request_id=get_request_id(request),
    )
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="admin.tenant_risk",
        resource_type="tenant",
        resource_id=str(tenant.id),
        request_id=get_request_id(request),
        result="success",
        summary=f"live_trading_paused={body.live_trading_paused}",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return {"ok": True, "message": "租户交易风控已更新", "live_trading_paused": tenant.live_trading_paused}


@router.get("/risk-events")
async def list_risk_events(
    user: CurrentUser,
    unresolved_only: bool = False,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    _ensure_admin(user)
    filters = [RiskEvent.tenant_id == user.tenant_id]
    if unresolved_only:
        filters.append(RiskEvent.resolved_at.is_(None))
    result = await session.execute(
        select(RiskEvent)
        .where(*filters)
        .order_by(RiskEvent.created_at.desc(), RiskEvent.id.desc())
        .limit(100)
    )
    return {
        "events": [
            {
                "id": item.id,
                "event_type": item.event_type,
                "severity": item.severity,
                "summary": item.summary,
                "request_id": item.request_id,
                "created_at": item.created_at.isoformat() if item.created_at else "",
                "resolved_at": item.resolved_at.isoformat() if item.resolved_at else "",
            }
            for item in result.scalars().all()
        ]
    }


@router.post("/risk-events/{event_id}/resolve")
async def resolve_risk_event(
    event_id: int,
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    _ensure_admin(user)
    event = (
        await session.execute(select(RiskEvent).where(RiskEvent.id == event_id, RiskEvent.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not event:
        raise NotFoundError("风险事件", str(event_id))
    event.resolved_at = datetime.now(timezone.utc)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="admin.risk_event_resolve",
        resource_type="risk_event",
        resource_id=str(event.id),
        request_id=get_request_id(request),
        result="success",
        summary=f"处理风险事件 {event.event_type}",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return {"ok": True, "message": "风险事件已处理"}


@router.get("/retention-policy")
async def get_retention_policy(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    _ensure_admin(user)
    policy = (
        await session.execute(select(RetentionPolicy).where(RetentionPolicy.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not policy:
        policy = RetentionPolicy(tenant_id=user.tenant_id)
        session.add(policy)
        await session.flush()
    return {
        "operation_audit_days": policy.operation_audit_days,
        "task_run_days": policy.task_run_days,
        "risk_event_days": policy.risk_event_days,
    }


@router.post("/retention-policy")
async def update_retention_policy(
    body: RetentionPolicyRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    _ensure_admin(user)
    policy = (
        await session.execute(select(RetentionPolicy).where(RetentionPolicy.tenant_id == user.tenant_id))
    ).scalar_one_or_none()
    if not policy:
        policy = RetentionPolicy(tenant_id=user.tenant_id)
        session.add(policy)
    policy.operation_audit_days = max(body.operation_audit_days, 30)
    policy.task_run_days = max(body.task_run_days, 30)
    policy.risk_event_days = max(body.risk_event_days, 30)
    await session.flush()
    return {"ok": True, "message": "保留策略已更新"}


@router.post("/retention/cleanup")
async def run_retention_cleanup(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    _ensure_admin(user)
    policy = (
        await session.execute(select(RetentionPolicy).where(RetentionPolicy.tenant_id == user.tenant_id))
    ).scalar_one_or_none() or RetentionPolicy(tenant_id=user.tenant_id)
    now = datetime.now(timezone.utc)
    audit_cutoff = now - timedelta(days=policy.operation_audit_days)
    task_cutoff = now - timedelta(days=policy.task_run_days)
    risk_cutoff = now - timedelta(days=policy.risk_event_days)
    audit_result = await session.execute(delete(OperationAuditLog).where(OperationAuditLog.tenant_id == user.tenant_id, OperationAuditLog.created_at < audit_cutoff))
    task_result = await session.execute(delete(TaskRunLog).where(TaskRunLog.tenant_id == user.tenant_id, TaskRunLog.finished_at < task_cutoff))
    risk_result = await session.execute(delete(RiskEvent).where(RiskEvent.tenant_id == user.tenant_id, RiskEvent.created_at < risk_cutoff, RiskEvent.resolved_at.is_not(None)))
    return {
        "ok": True,
        "deleted": {
            "operation_audit": int(audit_result.rowcount or 0),
            "task_runs": int(task_result.rowcount or 0),
            "risk_events": int(risk_result.rowcount or 0),
        },
    }


@router.patch("/users/{target_user_id}/status")
async def update_user_status(
    target_user_id: int,
    body: AdminUserStatusRequest,
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    _ensure_admin(user)
    result = await session.execute(
        select(User).where(User.id == target_user_id, User.tenant_id == user.tenant_id)
    )
    target = result.scalar_one_or_none()
    if not target:
        raise NotFoundError("用户", str(target_user_id))
    if target.id == user.id and not body.is_active:
        raise PermissionDeniedError("不能禁用当前登录账号")
    if target.role == UserRole.OWNER and not body.is_active and await _active_owner_count(session, user.tenant_id) <= 1:
        raise PermissionDeniedError("不能禁用最后一个 OWNER")

    target.is_active = body.is_active
    if not body.is_active:
        revoke_result = await session.execute(select(UserSession).where(UserSession.user_id == target.id))
        for item in revoke_result.scalars().all():
            item.is_revoked = True
            item.revoked_at = datetime.now(timezone.utc)

    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="admin.user_status",
        resource_type="user",
        resource_id=str(target.id),
        request_id=get_request_id(request),
        result="success",
        summary=f"更新用户状态 is_active={body.is_active}",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return {"ok": True, "message": "用户状态已更新"}
