"""
用户配置与交易审计 ORM 模型。

当前阶段这些表落在主库中，并通过 tenant_id / user_id 做数据边界。
后续如切换到独立租户库，模型字段保持兼容。
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserConfig(Base):
    """
    用户定投配置（每个用户一条记录）。

    API Key/Secret/Passphrase 使用 AES 加密存储，
    读取时需调用 security.decrypt_value() 解密。
    """
    __tablename__ = "user_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)

    # ─── 交易所配置 ────────────────────────────────────────
    exchange: Mapped[str] = mapped_column(String(32), default="okx")
    api_key_encrypted: Mapped[str] = mapped_column(String(512), default="")
    api_secret_encrypted: Mapped[str] = mapped_column(String(512), default="")
    api_passphrase_encrypted: Mapped[str] = mapped_column(String(512), default="")
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)

    # ─── 策略配置 ──────────────────────────────────────────
    budget_mode: Mapped[str] = mapped_column(String(16), default="MONTHLY")
    budget_amount: Mapped[float] = mapped_column(Float, default=700.0)
    run_interval_days: Mapped[int] = mapped_column(Integer, default=7)
    strategy_mode: Mapped[str] = mapped_column(String(48), default="per_asset_strict_dd")

    # ─── 通知配置 ──────────────────────────────────────────
    smtp_host: Mapped[str] = mapped_column(String(128), default="smtp.gmail.com")
    smtp_port: Mapped[int] = mapped_column(Integer, default=587)
    smtp_user_encrypted: Mapped[str] = mapped_column(String(512), default="")
    smtp_password_encrypted: Mapped[str] = mapped_column(String(512), default="")
    email_to: Mapped[str] = mapped_column(String(256), default="")
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_on_execution: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_budget: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_error: Mapped[bool] = mapped_column(Boolean, default=True)
    automation_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    automation_market_data: Mapped[bool] = mapped_column(Boolean, default=False)
    automation_dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    automation_live_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TradeRecord(Base):
    """
    交易记录（替代 dca_log.json）。

    每笔定投操作生成一条记录，包含信号快照和执行结果。
    """
    __tablename__ = "trade_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    ts: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), default="dry_run", index=True)
    strategy_mode: Mapped[str] = mapped_column(String(48), default="per_asset_strict_dd")
    usdt: Mapped[float] = mapped_column(Float, default=0.0)
    kenne_index: Mapped[float] = mapped_column(Float, default=0.0)
    mult: Mapped[float] = mapped_column(Float, default=0.0)
    momentum: Mapped[str] = mapped_column(String(16), default="")
    order_id: Mapped[str] = mapped_column(String(128), default="")
    # NOTE: status 可选值: filled, dry_run, skipped, failed
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    order_status: Mapped[str] = mapped_column(String(32), default="filled")
    note: Mapped[str] = mapped_column(String(512), default="")
    dedupe_key: Mapped[str] = mapped_column(String(128), default="", index=True)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    qty: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class OperationAuditLog(Base):
    """系统操作审计日志，不记录敏感明文。"""
    __tablename__ = "operation_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), default="")
    resource_id: Mapped[str] = mapped_column(String(128), default="")
    request_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    result: Mapped[str] = mapped_column(String(16), default="success", index=True)
    summary: Mapped[str] = mapped_column(String(512), default="")
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class PasswordResetToken(Base):
    """一次性密码重置令牌，只保存哈希。"""
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class AutomationTask(Base):
    """用户级自动化任务配置。"""
    __tablename__ = "automation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_result: Mapped[str] = mapped_column(String(16), default="")
    last_message: Mapped[str] = mapped_column(String(512), default="")
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TaskRunLog(Base):
    """自动化任务运行日志。"""
    __tablename__ = "task_run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(512), default="")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StripeEventLog(Base):
    """Stripe webhook 幂等事件记录。"""
    __tablename__ = "stripe_event_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class TenantInvitation(Base):
    """Pending invitation for joining an existing tenant."""
    __tablename__ = "tenant_invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    created_by_user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class MfaBackupCode(Base):
    """Single-use MFA backup code hash."""
    __tablename__ = "mfa_backup_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class AccountDeletionRequest(Base):
    """Confirmed or pending account deletion request."""
    __tablename__ = "account_deletion_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RiskEvent(Base):
    """Risk and alert event for trading and operations."""
    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info", index=True)
    summary: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    request_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


class RetentionPolicy(Base):
    """Per-tenant retention settings for audit-like records."""
    __tablename__ = "retention_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    operation_audit_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    task_run_days: Mapped[int] = mapped_column(Integer, nullable=False, default=180)
    risk_event_days: Mapped[int] = mapped_column(Integer, nullable=False, default=730)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class BalanceSnapshot(Base):
    """
    每日账户余额与对账快照。
    """
    __tablename__ = "balance_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    exchange: Mapped[str] = mapped_column(String(32), nullable=False)
    asset: Mapped[str] = mapped_column(String(16), nullable=False)
    remote_balance: Mapped[float] = mapped_column(Float, default=0.0)
    local_calculated: Mapped[float] = mapped_column(Float, default=0.0)
    difference: Mapped[float] = mapped_column(Float, default=0.0)
    difference_pct: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="matched")  # matched, mismatched
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

