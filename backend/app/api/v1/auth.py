"""Authentication routes for registration, login, token refresh, and user context."""

import logging
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.core.database import get_main_session
from app.core.exceptions import AuthenticationError, PermissionDeniedError, ValidationError
from app.core.request_id import get_request_id
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.model.tenant_models import PasswordResetToken, TenantInvitation
from app.model.user import EmailVerificationToken, PlanType, Tenant, User, UserRole, UserSession
from app.repository.operation_audit_repository import add_operation_log
from app.schema.auth import (
    ChangePasswordRequest,
    AcceptInvitationRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.schema.signal import ApiResponse
from app.service.email_service import send_system_email
from app.service.entitlement_service import plan_entitlements

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["认证"])


def build_entitlements(plan: PlanType) -> dict:
    """Return the feature flags the frontend needs to render SaaS gates."""
    return plan_entitlements(plan)


def _issue_tokens(user_id: int, tenant_id: int, session_id: str = "") -> tuple[str, str]:
    token_data = {"sub": str(user_id), "tenant_id": tenant_id}
    if session_id:
        token_data["sid"] = session_id
    return create_access_token(token_data), create_refresh_token(token_data)


def _set_access_cookie(response: Response, access_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
    )


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    _set_access_cookie(response, access_token)
    _set_refresh_cookie(response, refresh_token)
    response.set_cookie(
        key="csrf_token",
        value=secrets.token_urlsafe(24),
        httponly=False,
        secure=get_settings().cookie_secure,
        samesite="lax",
        max_age=get_settings().refresh_token_expire_days * 24 * 60 * 60,
    )


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _create_session_record(
    session: AsyncSession,
    user: User,
    refresh_token: str,
    request: Request,
) -> UserSession:
    record = UserSession(
        session_id=secrets.token_urlsafe(24),
        user_id=user.id,
        tenant_id=user.tenant_id,
        refresh_token_hash=_token_hash(refresh_token),
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    session.add(record)
    await session.flush()
    return record


async def _create_email_verification_token(session: AsyncSession, user: User) -> str:
    token = secrets.token_urlsafe(32)
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=_token_hash(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    await session.flush()
    return token


async def _send_verification_email(session: AsyncSession, user: User) -> None:
    token = await _create_email_verification_token(session, user)
    settings = get_settings()
    verify_url = f"{settings.cors_origins[0]}/verify-email?token={token}"

    if settings.debug:
        logger.info("==================================================")
        logger.info("DEVELOPMENT ONLY - EMAIL VERIFICATION LINK FOR: %s", user.email)
        logger.info("%s", verify_url)
        logger.info("==================================================")
        try:
            settings.data_dir.mkdir(parents=True, exist_ok=True)
            (settings.data_dir / "latest_verification_url.txt").write_text(verify_url, encoding="utf-8")
        except OSError as exc:
            logger.debug("write verification debug link skipped: %s", exc)
    
    try:
        send_system_email(
            user.email,
            "Kenne Index 邮箱验证",
            f"请在 24 小时内使用以下链接验证邮箱：\n{verify_url}",
        )
    except Exception as exc:
        logger.warning("email verification send failed user_id=%d: %s", user.id, exc)


@router.post("/register", response_model=TokenResponse)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_main_session),
) -> TokenResponse:
    if not body.accepted_terms:
        raise ValidationError("您必须同意用户服务协议与隐私政策才能注册")

    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise ValidationError("该邮箱已注册")

    tenant = Tenant(
        name=body.display_name or body.email.split("@")[0],
        plan=PlanType.FREE,
        max_users=1,
    )
    session.add(tenant)
    await session.flush()

    referred_by_id = None
    if body.referral_code:
        referrer = (await session.execute(
            select(User).where(User.referral_code == body.referral_code)
        )).scalar_one_or_none()
        if referrer:
            referred_by_id = referrer.id

    ref_code = f"K_{secrets.token_hex(4).upper()}"

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name or body.email.split("@")[0],
        role=UserRole.OWNER,
        tenant_id=tenant.id,
        accepted_terms=True,
        accepted_terms_at=datetime.now(timezone.utc),
        referral_code=ref_code,
        referred_by_id=referred_by_id,
    )
    session.add(user)
    await session.flush()

    initial_session_id = secrets.token_urlsafe(24)
    access_token, refresh_token = _issue_tokens(user.id, tenant.id, initial_session_id)
    user_session = UserSession(
        session_id=initial_session_id,
        user_id=user.id,
        tenant_id=tenant.id,
        refresh_token_hash=_token_hash(refresh_token),
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    session.add(user_session)
    await _send_verification_email(session, user)
    _set_auth_cookies(response, access_token, refresh_token)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=tenant.id,
        action="auth.register",
        resource_type="user",
        resource_id=str(user.id),
        request_id=get_request_id(request),
        result="success",
        summary="用户注册",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )

    logger.info("New user registered email=%s tenant_id=%d", body.email, tenant.id)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/invitations/accept", response_model=TokenResponse)
async def accept_invitation(
    body: AcceptInvitationRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_main_session),
) -> TokenResponse:
    token_hash = _token_hash(body.token)
    invitation = (
        await session.execute(select(TenantInvitation).where(TenantInvitation.token_hash == token_hash))
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    expires_at = invitation.expires_at if invitation and invitation.expires_at.tzinfo else (
        invitation.expires_at.replace(tzinfo=timezone.utc) if invitation else now
    )
    if not invitation or invitation.accepted_at is not None or invitation.revoked_at is not None or expires_at < now:
        raise ValidationError("邀请链接无效或已过期")

    existing = await session.execute(select(User).where(User.email == invitation.email))
    if existing.scalar_one_or_none():
        raise ValidationError("该邮箱已注册")

    tenant = (await session.execute(select(Tenant).where(Tenant.id == invitation.tenant_id))).scalar_one_or_none()
    if not tenant or not tenant.is_active:
        raise ValidationError("邀请所属租户不可用")
    user_count = int((await session.execute(select(func.count()).select_from(User).where(User.tenant_id == tenant.id, User.is_active.is_(True)))).scalar_one() or 0)
    if user_count >= tenant.max_users:
        raise PermissionDeniedError("当前套餐成员数已达上限")

    user = User(
        email=invitation.email,
        hashed_password=hash_password(body.password),
        display_name=body.display_name or invitation.email.split("@")[0],
        role=UserRole(invitation.role),
        tenant_id=tenant.id,
    )
    session.add(user)
    await session.flush()
    invitation.accepted_at = now

    session_id = secrets.token_urlsafe(24)
    access_token, refresh_token = _issue_tokens(user.id, user.tenant_id, session_id)
    session.add(
        UserSession(
            session_id=session_id,
            user_id=user.id,
            tenant_id=user.tenant_id,
            refresh_token_hash=_token_hash(refresh_token),
            ip_address=request.client.host if request.client else "",
            user_agent=request.headers.get("user-agent", ""),
        )
    )
    await _send_verification_email(session, user)
    _set_auth_cookies(response, access_token, refresh_token)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="auth.invitation_accept",
        resource_type="invitation",
        resource_id=str(invitation.id),
        request_id=get_request_id(request),
        result="success",
        summary="接受团队邀请",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_main_session),
) -> TokenResponse:
    result = await session.execute(
        select(User).where(User.email == body.email, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise AuthenticationError("邮箱或密码错误")

    initial_session_id = secrets.token_urlsafe(24)
    access_token, refresh_token = _issue_tokens(user.id, user.tenant_id, initial_session_id)
    user_session = UserSession(
        session_id=initial_session_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
        refresh_token_hash=_token_hash(refresh_token),
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    session.add(user_session)
    user.last_login_at = datetime.now(timezone.utc)
    _set_auth_cookies(response, access_token, refresh_token)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="auth.login",
        resource_type="user",
        resource_id=str(user.id),
        request_id=get_request_id(request),
        result="success",
        summary="用户登录",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )

    logger.info("User logged in email=%s", body.email)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    body: RefreshRequest = RefreshRequest(),
    refresh_token_cookie: Annotated[str | None, Cookie(alias="refresh_token")] = None,
    session: AsyncSession = Depends(get_main_session),
) -> TokenResponse:
    token = body.refresh_token or refresh_token_cookie
    if not token:
        raise AuthenticationError("请先登录")

    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise AuthenticationError("令牌类型错误")

    user_id = payload.get("sub")
    session_id = payload.get("sid", "")
    result = await session.execute(
        select(User).where(User.id == int(user_id), User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise AuthenticationError("用户不存在")

    if session_id:
        session_result = await session.execute(
            select(UserSession).where(
                UserSession.session_id == session_id,
                UserSession.user_id == user.id,
                UserSession.is_revoked.is_(False),
            )
        )
        user_session = session_result.scalar_one_or_none()
        if not user_session:
            raise AuthenticationError("会话已失效，请重新登录")
        if user_session.refresh_token_hash and user_session.refresh_token_hash != _token_hash(token):
            user_session.is_revoked = True
            user_session.revoked_at = datetime.now(timezone.utc)
            raise AuthenticationError("刷新令牌已失效，请重新登录")
    else:
        user_session = await _create_session_record(session, user, token, request)

    new_access, new_refresh = _issue_tokens(user.id, user.tenant_id, user_session.session_id)
    user_session.refresh_token_hash = _token_hash(new_refresh)
    user_session.last_seen_at = datetime.now(timezone.utc)
    _set_auth_cookies(response, new_access, new_refresh)
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    user: CurrentUser,
    access_token: Annotated[str | None, Cookie()] = None,
    session: AsyncSession = Depends(get_main_session),
) -> dict:
    if access_token:
        try:
            payload = decode_token(access_token)
            session_id = payload.get("sid")
            if session_id:
                result = await session.execute(
                    select(UserSession).where(
                        UserSession.session_id == session_id,
                        UserSession.user_id == user.id,
                    )
                )
                user_session = result.scalar_one_or_none()
                if user_session:
                    user_session.is_revoked = True
                    user_session.revoked_at = datetime.now(timezone.utc)
        except Exception:
            logger.debug("logout session revoke skipped", exc_info=True)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="auth.logout",
        resource_type="user",
        resource_id=str(user.id),
        request_id=get_request_id(request),
        result="success",
        summary="用户退出登录",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("csrf_token")
    return {"ok": True, "message": "已登出"}


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.post("/change-password", response_model=ApiResponse)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> ApiResponse:
    if not verify_password(body.current_password, user.hashed_password):
        raise AuthenticationError("当前密码错误")
    user.hashed_password = hash_password(body.new_password)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="auth.change_password",
        resource_type="user",
        resource_id=str(user.id),
        request_id=get_request_id(request),
        result="success",
        summary="修改密码",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return ApiResponse(ok=True, message="密码已更新")


@router.post("/forgot-password", response_model=ApiResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_main_session),
) -> ApiResponse:
    result = await session.execute(select(User).where(User.email == body.email, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    if user:
        token = secrets.token_urlsafe(32)
        reset = PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_reset_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        session.add(reset)
        await add_operation_log(
            session,
            user_id=user.id,
            tenant_id=user.tenant_id,
            action="auth.forgot_password",
            resource_type="user",
            resource_id=str(user.id),
            request_id=get_request_id(request),
            result="success",
            summary="生成密码重置令牌",
            ip_address=request.client.host if request.client else "",
            user_agent=request.headers.get("user-agent", ""),
        )
        reset_url = f"{get_settings().cors_origins[0]}/login?reset_token={token}"
        try:
            send_system_email(user.email, "Kenne Index 密码重置", f"请在 30 分钟内使用以下链接重置密码：\n{reset_url}")
        except Exception as exc:
            logger.warning("password reset email failed user_id=%d: %s", user.id, exc)
    return ApiResponse(ok=True, message="如果该邮箱存在，系统将发送密码重置邮件")


@router.post("/reset-password", response_model=ApiResponse)
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_main_session),
) -> ApiResponse:
    token_hash = _hash_reset_token(body.token)
    result = await session.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    reset = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    expires_at = reset.expires_at if reset and reset.expires_at.tzinfo else (
        reset.expires_at.replace(tzinfo=timezone.utc) if reset else now
    )
    if not reset or reset.used_at is not None or expires_at < now:
        raise ValidationError("密码重置链接无效或已过期")

    user_result = await session.execute(select(User).where(User.id == reset.user_id, User.is_active.is_(True)))
    user = user_result.scalar_one_or_none()
    if not user:
        raise ValidationError("密码重置链接无效或已过期")

    user.hashed_password = hash_password(body.new_password)
    reset.used_at = now
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="auth.reset_password",
        resource_type="user",
        resource_id=str(user.id),
        request_id=get_request_id(request),
        result="success",
        summary="重置密码",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return ApiResponse(ok=True, message="密码已重置，请重新登录")


@router.post("/verify-email", response_model=ApiResponse)
async def verify_email(
    body: VerifyEmailRequest,
    request: Request,
    session: AsyncSession = Depends(get_main_session),
) -> ApiResponse:
    token_hash = _token_hash(body.token)
    result = await session.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    )
    verify_token = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    expires_at = verify_token.expires_at if verify_token and verify_token.expires_at.tzinfo else (
        verify_token.expires_at.replace(tzinfo=timezone.utc) if verify_token else now
    )
    if not verify_token or verify_token.used_at is not None or expires_at < now:
        raise ValidationError("邮箱验证链接无效或已过期")

    user_result = await session.execute(select(User).where(User.id == verify_token.user_id, User.is_active.is_(True)))
    user = user_result.scalar_one_or_none()
    if not user:
        raise ValidationError("邮箱验证链接无效或已过期")

    user.email_verified = True
    user.email_verified_at = now
    verify_token.used_at = now
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="auth.verify_email",
        resource_type="user",
        resource_id=str(user.id),
        request_id=get_request_id(request),
        result="success",
        summary="邮箱验证成功",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return ApiResponse(ok=True, message="邮箱已验证")


@router.post("/resend-verification", response_model=ApiResponse)
async def resend_verification(
    request: Request,
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> ApiResponse:
    if user.email_verified:
        return ApiResponse(ok=True, message="邮箱已验证")
    await _send_verification_email(session, user)
    await add_operation_log(
        session,
        user_id=user.id,
        tenant_id=user.tenant_id,
        action="auth.resend_verification",
        resource_type="user",
        resource_id=str(user.id),
        request_id=get_request_id(request),
        result="success",
        summary="重发邮箱验证邮件",
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    return ApiResponse(ok=True, message="验证邮件已发送")


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: CurrentUser,
    session: AsyncSession = Depends(get_main_session),
) -> UserResponse:
    result = await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one_or_none()
    plan = tenant.plan if tenant else PlanType.FREE
    subscription_status = getattr(tenant, "subscription_status", None) or (
        "active" if plan != PlanType.FREE else "none"
    )

    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role.value,
        tenant_id=user.tenant_id,
        plan=plan.value,
        tenant={
            "id": tenant.id if tenant else user.tenant_id,
            "name": tenant.name if tenant else "",
            "max_users": tenant.max_users if tenant else 1,
        },
        subscription_status=subscription_status,
        entitlements=build_entitlements(plan),
        email_verified=bool(user.email_verified),
        mfa_enabled=bool(user.mfa_enabled),
        referral_code=user.referral_code,
    )
