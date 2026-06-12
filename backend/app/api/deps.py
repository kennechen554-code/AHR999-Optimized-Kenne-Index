"""
FastAPI 依赖注入。

提供：当前用户解析、租户 Session 注入等通用依赖。
"""

import logging
from typing import Annotated

from fastapi import Cookie, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_main_session
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_token
from app.model.user import User, UserSession

logger = logging.getLogger(__name__)


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    access_token: Annotated[str | None, Cookie()] = None,
    session: AsyncSession = Depends(get_main_session),
) -> User:
    """
    解析当前认证用户。

    支持两种传递方式：
    1. Authorization: Bearer <token>（API 调用）
    2. access_token Cookie（Web 前端）

    Raises:
        AuthenticationError: 未提供 Token / Token 无效 / 用户不存在
    """
    token: str | None = None

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif access_token:
        token = access_token

    if not token:
        raise AuthenticationError("请先登录")

    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AuthenticationError("令牌类型错误")

    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if not user_id:
        raise AuthenticationError("令牌数据不完整")

    result = await session.execute(
        select(User).where(User.id == int(user_id), User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationError("用户不存在或已禁用")

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

    return user


# NOTE: 类型别名，简化路由函数签名
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_verified_email(user: User, feature: str = "该操作") -> None:
    """Require verified email before allowing high-risk operations."""
    if not user.email_verified:
        raise PermissionDeniedError(f"{feature} 需要先完成邮箱验证")


StepUpCode = Annotated[str | None, Header(alias="X-Step-Up-Code")]
