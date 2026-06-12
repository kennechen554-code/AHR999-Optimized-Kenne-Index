"""
安全工具：JWT 令牌 + 密码哈希 + 对称加密。

- JWT: 用于用户认证，存储在 HttpOnly Cookie 中
- bcrypt: 用于密码哈希
- Fernet (AES-128-CBC): 用于加密存储 API Key 等敏感配置
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


# ─── JWT ──────────────────────────────────────────────────────────


def create_access_token(data: dict[str, Any]) -> str:
    """
    生成访问令牌（短期有效）。

    Args:
        data: 需要编码的数据，通常包含 sub（用户 ID）和 tenant_id

    Returns:
        JWT 字符串
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode = {**data, "exp": expire, "type": "access"}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict[str, Any]) -> str:
    """生成刷新令牌（长期有效）。"""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    to_encode = {**data, "exp": expire, "type": "refresh"}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """
    解码并验证 JWT 令牌。

    Raises:
        AuthenticationError: 令牌无效或已过期
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as exc:
        logger.warning("JWT 解码失败: %s", exc)
        raise AuthenticationError("令牌无效或已过期") from exc


# ─── 密码哈希 ─────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    """使用 bcrypt 对密码进行哈希处理。"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希是否匹配。"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ─── 对称加密（Fernet / AES）─────────────────────────────────────


def _get_fernet() -> Fernet:
    """
    根据 KMS 服务派生 Fernet 密钥。
    """
    import base64
    from app.core.kms import get_key_provider

    key_bytes = get_key_provider().get_encryption_key()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_value(plain_text: str) -> str:
    """加密字符串，返回密文（用于存储 API Key 等）。"""
    if not plain_text:
        return ""
    fernet = _get_fernet()
    return fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_value(cipher_text: str) -> str:
    """解密字符串，还原明文。"""
    if not cipher_text:
        return ""
    fernet = _get_fernet()
    return fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
