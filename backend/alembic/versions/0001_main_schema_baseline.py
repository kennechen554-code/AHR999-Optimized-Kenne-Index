"""main schema baseline

Revision ID: 0001_main_schema_baseline
Revises:
Create Date: 2026-05-10 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_main_schema_baseline"
down_revision = None
branch_labels = None
depends_on = None


plan_type = sa.Enum("FREE", "BASIC", "PREMIUM", name="plantype")
user_role = sa.Enum("OWNER", "ADMIN", "MEMBER", name="userrole")


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("plan", plan_type, nullable=False),
        sa.Column("max_users", sa.Integer(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=128), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=128), nullable=True),
        sa.Column("subscription_status", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column("hashed_password", sa.String(length=512), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=256), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index(op.f("ix_user_sessions_is_revoked"), "user_sessions", ["is_revoked"], unique=False)
    op.create_index(op.f("ix_user_sessions_session_id"), "user_sessions", ["session_id"], unique=False)
    op.create_index(op.f("ix_user_sessions_tenant_id"), "user_sessions", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"], unique=False)
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_email_verification_tokens_token_hash"), "email_verification_tokens", ["token_hash"], unique=False)
    op.create_index(op.f("ix_email_verification_tokens_user_id"), "email_verification_tokens", ["user_id"], unique=False)
    op.create_table(
        "user_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("exchange", sa.String(length=32), nullable=False),
        sa.Column("api_key_encrypted", sa.String(length=512), nullable=False),
        sa.Column("api_secret_encrypted", sa.String(length=512), nullable=False),
        sa.Column("api_passphrase_encrypted", sa.String(length=512), nullable=False),
        sa.Column("simulated", sa.Boolean(), nullable=False),
        sa.Column("budget_mode", sa.String(length=16), nullable=False),
        sa.Column("budget_amount", sa.Float(), nullable=False),
        sa.Column("run_interval_days", sa.Integer(), nullable=False),
        sa.Column("strategy_mode", sa.String(length=48), nullable=False),
        sa.Column("smtp_host", sa.String(length=128), nullable=False),
        sa.Column("smtp_port", sa.Integer(), nullable=False),
        sa.Column("smtp_user_encrypted", sa.String(length=512), nullable=False),
        sa.Column("smtp_password_encrypted", sa.String(length=512), nullable=False),
        sa.Column("email_to", sa.String(length=256), nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False),
        sa.Column("notify_on_execution", sa.Boolean(), nullable=False),
        sa.Column("notify_on_budget", sa.Boolean(), nullable=False),
        sa.Column("notify_on_error", sa.Boolean(), nullable=False),
        sa.Column("automation_enabled", sa.Boolean(), nullable=False),
        sa.Column("automation_market_data", sa.Boolean(), nullable=False),
        sa.Column("automation_dry_run", sa.Boolean(), nullable=False),
        sa.Column("automation_live_enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_configs_tenant_id"), "user_configs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_user_configs_user_id"), "user_configs", ["user_id"], unique=True)
    op.create_table(
        "trade_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=8), nullable=False),
        sa.Column("exchange", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("strategy_mode", sa.String(length=48), nullable=False),
        sa.Column("usdt", sa.Float(), nullable=False),
        sa.Column("kenne_index", sa.Float(), nullable=False),
        sa.Column("mult", sa.Float(), nullable=False),
        sa.Column("momentum", sa.String(length=16), nullable=False),
        sa.Column("order_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("note", sa.String(length=512), nullable=False),
        sa.Column("dedupe_key", sa.String(length=128), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trade_records_dedupe_key"), "trade_records", ["dedupe_key"], unique=False)
    op.create_index(op.f("ix_trade_records_mode"), "trade_records", ["mode"], unique=False)
    op.create_index(op.f("ix_trade_records_symbol"), "trade_records", ["symbol"], unique=False)
    op.create_index(op.f("ix_trade_records_tenant_id"), "trade_records", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_trade_records_user_id"), "trade_records", ["user_id"], unique=False)
    op.create_table(
        "operation_audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.String(length=512), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_operation_audit_logs_action"), "operation_audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_operation_audit_logs_created_at"), "operation_audit_logs", ["created_at"], unique=False)
    op.create_index(op.f("ix_operation_audit_logs_request_id"), "operation_audit_logs", ["request_id"], unique=False)
    op.create_index(op.f("ix_operation_audit_logs_result"), "operation_audit_logs", ["result"], unique=False)
    op.create_index(op.f("ix_operation_audit_logs_tenant_id"), "operation_audit_logs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_operation_audit_logs_user_id"), "operation_audit_logs", ["user_id"], unique=False)
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_password_reset_tokens_token_hash"), "password_reset_tokens", ["token_hash"], unique=False)
    op.create_index(op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"], unique=False)
    op.create_table(
        "automation_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=48), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result", sa.String(length=16), nullable=False),
        sa.Column("last_message", sa.String(length=512), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_automation_tasks_enabled"), "automation_tasks", ["enabled"], unique=False)
    op.create_index(op.f("ix_automation_tasks_task_type"), "automation_tasks", ["task_type"], unique=False)
    op.create_index(op.f("ix_automation_tasks_tenant_id"), "automation_tasks", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_automation_tasks_user_id"), "automation_tasks", ["user_id"], unique=False)
    op.create_table(
        "task_run_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("message", sa.String(length=512), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_run_logs_status"), "task_run_logs", ["status"], unique=False)
    op.create_index(op.f("ix_task_run_logs_task_type"), "task_run_logs", ["task_type"], unique=False)
    op.create_index(op.f("ix_task_run_logs_tenant_id"), "task_run_logs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_task_run_logs_user_id"), "task_run_logs", ["user_id"], unique=False)
    op.create_table(
        "stripe_event_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(op.f("ix_stripe_event_logs_event_id"), "stripe_event_logs", ["event_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_stripe_event_logs_event_id"), table_name="stripe_event_logs")
    op.drop_table("stripe_event_logs")
    op.drop_index(op.f("ix_task_run_logs_user_id"), table_name="task_run_logs")
    op.drop_index(op.f("ix_task_run_logs_tenant_id"), table_name="task_run_logs")
    op.drop_index(op.f("ix_task_run_logs_task_type"), table_name="task_run_logs")
    op.drop_index(op.f("ix_task_run_logs_status"), table_name="task_run_logs")
    op.drop_table("task_run_logs")
    op.drop_index(op.f("ix_automation_tasks_user_id"), table_name="automation_tasks")
    op.drop_index(op.f("ix_automation_tasks_tenant_id"), table_name="automation_tasks")
    op.drop_index(op.f("ix_automation_tasks_task_type"), table_name="automation_tasks")
    op.drop_index(op.f("ix_automation_tasks_enabled"), table_name="automation_tasks")
    op.drop_table("automation_tasks")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_token_hash"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index(op.f("ix_operation_audit_logs_user_id"), table_name="operation_audit_logs")
    op.drop_index(op.f("ix_operation_audit_logs_tenant_id"), table_name="operation_audit_logs")
    op.drop_index(op.f("ix_operation_audit_logs_result"), table_name="operation_audit_logs")
    op.drop_index(op.f("ix_operation_audit_logs_request_id"), table_name="operation_audit_logs")
    op.drop_index(op.f("ix_operation_audit_logs_created_at"), table_name="operation_audit_logs")
    op.drop_index(op.f("ix_operation_audit_logs_action"), table_name="operation_audit_logs")
    op.drop_table("operation_audit_logs")
    op.drop_index(op.f("ix_trade_records_user_id"), table_name="trade_records")
    op.drop_index(op.f("ix_trade_records_tenant_id"), table_name="trade_records")
    op.drop_index(op.f("ix_trade_records_symbol"), table_name="trade_records")
    op.drop_index(op.f("ix_trade_records_mode"), table_name="trade_records")
    op.drop_index(op.f("ix_trade_records_dedupe_key"), table_name="trade_records")
    op.drop_table("trade_records")
    op.drop_index(op.f("ix_user_configs_user_id"), table_name="user_configs")
    op.drop_index(op.f("ix_user_configs_tenant_id"), table_name="user_configs")
    op.drop_table("user_configs")
    op.drop_index(op.f("ix_email_verification_tokens_user_id"), table_name="email_verification_tokens")
    op.drop_index(op.f("ix_email_verification_tokens_token_hash"), table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_tenant_id"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_session_id"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_is_revoked"), table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_table("tenants")
    user_role.drop(op.get_bind(), checkfirst=True)
    plan_type.drop(op.get_bind(), checkfirst=True)
