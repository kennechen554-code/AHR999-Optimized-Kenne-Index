"""Persistent user configuration repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value, encrypt_value
from app.model.tenant_models import UserConfig
from app.schema.signal import ConfigResponse, ConfigUpdateRequest


def _mask(value: str) -> str:
    """Mask sensitive values for API responses."""
    if len(value) <= 8:
        return "****" if value else ""
    return value[:4] + "****" + value[-4:]


def _decrypt(cipher_text: str) -> str:
    if not cipher_text:
        return ""
    return decrypt_value(cipher_text)


def _preserve_masked_value(new_value: str, old_value: str) -> str:
    """Keep the existing secret when the frontend sends a masked value back."""
    if "****" in new_value and old_value:
        return old_value
    return new_value


def default_config_dict() -> dict[str, object]:
    return {
        "exchange": "okx",
        "api_key": "",
        "api_secret": "",
        "api_passphrase": "",
        "api_key_encrypted": "",
        "api_secret_encrypted": "",
        "api_passphrase_encrypted": "",
        "simulated": True,
        "budget_mode": "MONTHLY",
        "budget_amount": 700.0,
        "run_interval_days": 7,
        "strategy_mode": "per_asset_strict_dd",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_user": "",
        "smtp_password": "",
        "smtp_user_encrypted": "",
        "smtp_password_encrypted": "",
        "email_to": "",
        "notifications_enabled": False,
        "notify_on_execution": True,
        "notify_on_budget": True,
        "notify_on_error": True,
        "automation_enabled": False,
        "automation_market_data": False,
        "automation_dry_run": False,
        "automation_live_enabled": False,
    }


async def get_config_model(session: AsyncSession, user_id: int, tenant_id: int) -> UserConfig | None:
    result = await session.execute(
        select(UserConfig).where(
            UserConfig.user_id == user_id,
            UserConfig.tenant_id == tenant_id,
        )
    )
    cfg = result.scalar_one_or_none()
    if cfg:
        return cfg

    legacy_result = await session.execute(select(UserConfig).where(UserConfig.user_id == user_id))
    legacy_cfg = legacy_result.scalar_one_or_none()
    if legacy_cfg and legacy_cfg.tenant_id == 0:
        legacy_cfg.tenant_id = tenant_id
        await session.flush()
        return legacy_cfg
    return None


async def get_config_dict(session: AsyncSession, user_id: int, tenant_id: int) -> dict[str, object]:
    cfg = await get_config_model(session, user_id, tenant_id)
    if not cfg:
        return default_config_dict()

    api_key = _decrypt(cfg.api_key_encrypted)
    api_secret = _decrypt(cfg.api_secret_encrypted)
    api_passphrase = _decrypt(cfg.api_passphrase_encrypted)
    smtp_user = _decrypt(cfg.smtp_user_encrypted)
    smtp_password = _decrypt(cfg.smtp_password_encrypted)

    return {
        "exchange": cfg.exchange,
        "api_key": api_key,
        "api_secret": api_secret,
        "api_passphrase": api_passphrase,
        "api_key_encrypted": cfg.api_key_encrypted,
        "api_secret_encrypted": cfg.api_secret_encrypted,
        "api_passphrase_encrypted": cfg.api_passphrase_encrypted,
        "simulated": cfg.simulated,
        "budget_mode": cfg.budget_mode,
        "budget_amount": cfg.budget_amount,
        "run_interval_days": cfg.run_interval_days,
        "strategy_mode": cfg.strategy_mode,
        "smtp_host": cfg.smtp_host,
        "smtp_port": cfg.smtp_port,
        "smtp_user": smtp_user,
        "smtp_password": smtp_password,
        "smtp_user_encrypted": cfg.smtp_user_encrypted,
        "smtp_password_encrypted": cfg.smtp_password_encrypted,
        "email_to": cfg.email_to,
        "notifications_enabled": cfg.notifications_enabled,
        "notify_on_execution": cfg.notify_on_execution,
        "notify_on_budget": cfg.notify_on_budget,
        "notify_on_error": cfg.notify_on_error,
        "automation_enabled": cfg.automation_enabled,
        "automation_market_data": cfg.automation_market_data,
        "automation_dry_run": cfg.automation_dry_run,
        "automation_live_enabled": cfg.automation_live_enabled,
    }


async def get_config_response(session: AsyncSession, user_id: int, tenant_id: int) -> ConfigResponse:
    cfg = await get_config_dict(session, user_id, tenant_id)
    return ConfigResponse(
        exchange=str(cfg["exchange"]),
        api_key=_mask(str(cfg["api_key"])),
        api_secret=_mask(str(cfg["api_secret"])),
        api_passphrase=_mask(str(cfg["api_passphrase"])),
        simulated=bool(cfg["simulated"]),
        budget_mode=str(cfg["budget_mode"]),
        budget_amount=float(cfg["budget_amount"]),
        run_interval_days=int(cfg["run_interval_days"]),
        strategy_mode=str(cfg["strategy_mode"]),
        smtp_host=str(cfg["smtp_host"]),
        smtp_port=int(cfg["smtp_port"]),
        smtp_user=_mask(str(cfg["smtp_user"])),
        smtp_password="****" if cfg["smtp_password"] else "",
        email_to=str(cfg["email_to"]),
        notifications_enabled=bool(cfg["notifications_enabled"]),
        notify_on_execution=bool(cfg["notify_on_execution"]),
        notify_on_budget=bool(cfg["notify_on_budget"]),
        notify_on_error=bool(cfg["notify_on_error"]),
        automation_enabled=bool(cfg["automation_enabled"]),
        automation_market_data=bool(cfg["automation_market_data"]),
        automation_dry_run=bool(cfg["automation_dry_run"]),
        automation_live_enabled=bool(cfg["automation_live_enabled"]),
    )


async def upsert_config(
    session: AsyncSession,
    user_id: int,
    tenant_id: int,
    body: ConfigUpdateRequest,
) -> UserConfig:
    current = await get_config_dict(session, user_id, tenant_id)
    api_key = _preserve_masked_value(body.api_key, str(current["api_key"]))
    api_secret = _preserve_masked_value(body.api_secret, str(current["api_secret"]))
    api_passphrase = _preserve_masked_value(body.api_passphrase, str(current["api_passphrase"]))
    smtp_user = _preserve_masked_value(body.smtp_user, str(current["smtp_user"]))
    smtp_password = _preserve_masked_value(body.smtp_password, str(current["smtp_password"]))

    cfg = await get_config_model(session, user_id, tenant_id)
    if not cfg:
        cfg = UserConfig(user_id=user_id, tenant_id=tenant_id)
        session.add(cfg)

    cfg.exchange = body.exchange
    cfg.api_key_encrypted = encrypt_value(api_key)
    cfg.api_secret_encrypted = encrypt_value(api_secret)
    cfg.api_passphrase_encrypted = encrypt_value(api_passphrase)
    cfg.simulated = body.simulated
    cfg.budget_mode = body.budget_mode
    cfg.budget_amount = body.budget_amount
    cfg.run_interval_days = body.run_interval_days
    cfg.strategy_mode = body.strategy_mode
    cfg.smtp_host = body.smtp_host
    cfg.smtp_port = body.smtp_port
    cfg.smtp_user_encrypted = encrypt_value(smtp_user)
    cfg.smtp_password_encrypted = encrypt_value(smtp_password)
    cfg.email_to = body.email_to
    cfg.notifications_enabled = body.notifications_enabled
    cfg.notify_on_execution = body.notify_on_execution
    cfg.notify_on_budget = body.notify_on_budget
    cfg.notify_on_error = body.notify_on_error
    cfg.automation_enabled = body.automation_enabled
    cfg.automation_market_data = body.automation_market_data
    cfg.automation_dry_run = body.automation_dry_run
    # 自动实盘默认强约束为手动启用；后续执行链路仍会再次校验 Premium。
    cfg.automation_live_enabled = body.automation_live_enabled
    await session.flush()
    return cfg
