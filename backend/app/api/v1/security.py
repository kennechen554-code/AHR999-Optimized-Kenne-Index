"""Account security routes."""

import hashlib
import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, StepUpCode
from app.core.database import get_main_session
from app.core.exceptions import NotFoundError, ValidationError
from app.core.request_id import get_request_id
from app.core.security import decode_token
from app.model.tenant_models import AccountDeletionRequest
from app.model.user import User, UserSession
from app.repository.operation_audit_repository import add_operation_log
from app.schema.audit import UserSessionListResponse, UserSessionResponse
from app.service.email_service import send_system_email
from app.service.mfa_service import (
    encrypt_totp_secret,
    generate_backup_codes,
    generate_totp_secret,
    store_backup_codes,
    verify_totp,
    require_step_up,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/security", tags=["账户安全"])


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _session_to_response(item: UserSession, current_session_id: str) -> UserSessionResponse:
    return UserSessionResponse(
        id=item.id,
        session_id=item.session_id,
        ip_address=item.ip_address,
        user_agent=item.user_agent,
        is_current=item.session_id == current_session_id,
        created_at=item.created_at.isoformat() if item.created_at else "",
        last_seen_at=item.last_seen_at.isoformat() if item.last_seen_at else "",
    )


@router.get("/sessions", response_model=UserSessionListResponse)
async def list_sessions(
    user: CurrentUser,
    access_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_main_session),
) -> UserSessionListResponse:
    current_session_id = ""
    if access_token:
        current_session_id = str(decode_token(access_token).get("sid") or "")
    result = await session.execute(
        select(UserSession)
        .where(UserSession.user_id == user.id, UserSession.is_revoked.is_(False))
        .order_by(UserSession.last_seen_at.desc())
    )
    return UserSessionListResponse(
        sessions=[_session_to_response(item, current_session_id) for item in result.scalars().all()]
    )


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    result = await session.execute(
        select(UserSession).where(UserSession.session_id == session_id, UserSession.user_id == user.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError("会话", session_id)
    item.is_revoked = True
    item.revoked_at = datetime.now(timezone.utc)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="security.revoke_session",
        resource_type="session",
        resource_id=session_id,
        request_id=get_request_id(request),
        result="success",
        summary="撤销登录会话",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return {"ok": True, "message": "会话已撤销"}


@router.post("/mfa/setup")
async def setup_mfa(user: CurrentUser) -> dict:
    secret = generate_totp_secret()
    return {
        "ok": True,
        "secret": secret,
        "otpauth_url": f"otpauth://totp/Kenne%20Index:{user.email}?secret={secret}&issuer=Kenne%20Index",
    }


@router.post("/mfa/enable")
async def enable_mfa(
    body: dict,
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    secret = str(body.get("secret") or "")
    code = str(body.get("code") or "")
    if not secret or not verify_totp(secret, code):
        raise ValidationError("MFA 验证码无效")
    codes = generate_backup_codes()
    target = (await session.execute(select(User).where(User.id == user.id))).scalar_one()
    target.mfa_enabled = True
    target.mfa_secret_encrypted = encrypt_totp_secret(secret)
    await store_backup_codes(session, user.id, codes)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="security.mfa_enable",
        resource_type="user",
        resource_id=str(user.id),
        request_id=get_request_id(request),
        result="success",
        summary="启用 MFA",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return {"ok": True, "message": "MFA 已启用", "backup_codes": codes}


@router.post("/mfa/disable")
async def disable_mfa(
    request: Request,
    user: CurrentUser,
    step_up_code: StepUpCode = None,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    await require_step_up(session, user, step_up_code or "", "停用 MFA")
    target = (await session.execute(select(User).where(User.id == user.id))).scalar_one()
    target.mfa_enabled = False
    target.mfa_secret_encrypted = ""
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="security.mfa_disable",
        resource_type="user",
        resource_id=str(user.id),
        request_id=get_request_id(request),
        result="success",
        summary="停用 MFA",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return {"ok": True, "message": "MFA 已停用"}


@router.post("/deletion/request")
async def request_account_deletion(
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    raw_token = secrets.token_urlsafe(32)
    deletion = AccountDeletionRequest(
        tenant_id=user.tenant_id,
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        status="pending",
    )
    session.add(deletion)
    await session.flush()
    try:
        send_system_email(
            user.email,
            "Kenne Index 账号删除确认",
            f"如果你确认删除账号，请使用以下令牌确认：\n{raw_token}\n该操作会禁用账号并撤销所有会话。",
        )
    except Exception as exc:
        # Local/dev environments often do not have system SMTP configured.
        logger.warning("account deletion email send failed user_id=%d: %s", user.id, exc)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="security.deletion_request",
        resource_type="user",
        resource_id=str(user.id),
        request_id=get_request_id(request),
        result="success",
        summary="请求账号删除",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return {"ok": True, "message": "删除确认已发送；本地开发响应包含 token", "token": raw_token}


@router.post("/deletion/confirm")
async def confirm_account_deletion(
    body: dict,
    request: Request,
    user: CurrentUser,
    step_up_code: StepUpCode = None,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    await require_step_up(session, user, step_up_code or "", "确认账号删除")
    token = str(body.get("token") or "")
    if not token:
        raise ValidationError("删除确认令牌不能为空")
    deletion = (
        await session.execute(
            select(AccountDeletionRequest).where(
                AccountDeletionRequest.token_hash == _hash_token(token),
                AccountDeletionRequest.user_id == user.id,
                AccountDeletionRequest.status == "pending",
            )
        )
    ).scalar_one_or_none()
    if not deletion:
        raise ValidationError("删除确认令牌无效")
    target = (await session.execute(select(User).where(User.id == user.id))).scalar_one()
    target.is_active = False
    deletion.status = "confirmed"
    deletion.confirmed_at = datetime.now(timezone.utc)
    deletion.completed_at = deletion.confirmed_at
    sessions = await session.execute(select(UserSession).where(UserSession.user_id == user.id))
    for item in sessions.scalars().all():
        item.is_revoked = True
        item.revoked_at = datetime.now(timezone.utc)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="security.deletion_confirm",
        resource_type="user",
        resource_id=str(user.id),
        request_id=get_request_id(request),
        result="success",
        summary="确认账号删除并禁用账号",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return {"ok": True, "message": "账号删除请求已确认，账号已禁用"}
