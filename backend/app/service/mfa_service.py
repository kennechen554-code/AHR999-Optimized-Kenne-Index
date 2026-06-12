"""TOTP MFA helpers using the Python standard library."""

import base64
import hashlib
import hmac
import secrets
import struct
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedError
from app.core.security import decrypt_value, encrypt_value
from app.model.tenant_models import MfaBackupCode
from app.model.user import User


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _normalize_secret(secret: str) -> bytes:
    padded = secret.upper() + "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(padded)


def totp_code(secret: str, for_time: int | None = None, step: int = 30) -> str:
    counter = int((for_time or int(time.time())) / step)
    digest = hmac.new(_normalize_secret(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{code % 1_000_000:06d}"


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    candidate = "".join(ch for ch in code if ch.isdigit())
    if len(candidate) != 6:
        return False
    now = int(time.time())
    return any(hmac.compare_digest(totp_code(secret, now + offset * 30), candidate) for offset in range(-window, window + 1))


def hash_backup_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def generate_backup_codes(count: int = 8) -> list[str]:
    return [secrets.token_urlsafe(9) for _ in range(count)]


async def store_backup_codes(session: AsyncSession, user_id: int, codes: list[str]) -> None:
    for code in codes:
        session.add(MfaBackupCode(user_id=user_id, code_hash=hash_backup_code(code)))
    await session.flush()


async def consume_backup_code(session: AsyncSession, user_id: int, code: str) -> bool:
    record = (
        await session.execute(
            select(MfaBackupCode).where(
                MfaBackupCode.user_id == user_id,
                MfaBackupCode.code_hash == hash_backup_code(code),
                MfaBackupCode.used_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if not record:
        return False
    from datetime import datetime, timezone

    record.used_at = datetime.now(timezone.utc)
    await session.flush()
    return True


async def verify_step_up(session: AsyncSession, user: User, code: str) -> bool:
    if not user.mfa_enabled:
        return True
    if not code:
        return False
    secret = decrypt_value(user.mfa_secret_encrypted)
    if secret and verify_totp(secret, code):
        return True
    return await consume_backup_code(session, user.id, code)


async def require_step_up(session: AsyncSession, user: User, code: str, feature: str) -> None:
    if not await verify_step_up(session, user, code):
        raise PermissionDeniedError(f"{feature} 需要 MFA step-up 验证")


def encrypt_totp_secret(secret: str) -> str:
    return encrypt_value(secret)
