"""
Pydantic 请求/响应模型 — 认证相关。
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """注册请求。"""
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=64)
    accepted_terms: bool = Field(default=False)
    referral_code: str | None = Field(default=None)


class LoginRequest(BaseModel):
    """登录请求。"""
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token 响应。"""
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Token 刷新请求。"""
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = ""


class ChangePasswordRequest(BaseModel):
    """修改密码请求。"""
    model_config = ConfigDict(extra="forbid")

    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    """忘记密码请求。"""
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """重置密码请求。"""
    model_config = ConfigDict(extra="forbid")

    token: str
    new_password: str = Field(min_length=8, max_length=128)


class AcceptInvitationRequest(BaseModel):
    """Accept tenant invitation and create account."""
    model_config = ConfigDict(extra="forbid")

    token: str
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=64)


class VerifyEmailRequest(BaseModel):
    """邮箱验证请求。"""
    model_config = ConfigDict(extra="forbid")

    token: str


class UserResponse(BaseModel):
    """用户信息响应。"""
    id: int
    email: str
    display_name: str
    role: str
    tenant_id: int
    plan: str
    tenant: dict
    subscription_status: str = "none"
    entitlements: dict[str, bool | int | float | list[str]]
    email_verified: bool = False
    mfa_enabled: bool = False
    referral_code: str | None = None
