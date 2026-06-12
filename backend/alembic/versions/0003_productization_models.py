"""productization models

Revision ID: 0003_productization_models
Revises: 0002_tenant_live_trading_pause
Create Date: 2026-05-10 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_productization_models"
down_revision = "0002_tenant_live_trading_pause"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("mfa_secret_encrypted", sa.String(length=512), nullable=False, server_default=""))

    op.create_table(
        "tenant_invitations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_tenant_invitations_email"), "tenant_invitations", ["email"], unique=False)
    op.create_index(op.f("ix_tenant_invitations_tenant_id"), "tenant_invitations", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_tenant_invitations_token_hash"), "tenant_invitations", ["token_hash"], unique=False)

    op.create_table(
        "mfa_backup_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_index(op.f("ix_mfa_backup_codes_code_hash"), "mfa_backup_codes", ["code_hash"], unique=False)
    op.create_index(op.f("ix_mfa_backup_codes_user_id"), "mfa_backup_codes", ["user_id"], unique=False)

    op.create_table(
        "account_deletion_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_account_deletion_requests_status"), "account_deletion_requests", ["status"], unique=False)
    op.create_index(op.f("ix_account_deletion_requests_tenant_id"), "account_deletion_requests", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_account_deletion_requests_token_hash"), "account_deletion_requests", ["token_hash"], unique=False)
    op.create_index(op.f("ix_account_deletion_requests_user_id"), "account_deletion_requests", ["user_id"], unique=False)

    op.create_table(
        "risk_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.String(length=512), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_risk_events_created_at"), "risk_events", ["created_at"], unique=False)
    op.create_index(op.f("ix_risk_events_event_type"), "risk_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_risk_events_request_id"), "risk_events", ["request_id"], unique=False)
    op.create_index(op.f("ix_risk_events_severity"), "risk_events", ["severity"], unique=False)
    op.create_index(op.f("ix_risk_events_tenant_id"), "risk_events", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_risk_events_user_id"), "risk_events", ["user_id"], unique=False)

    op.create_table(
        "retention_policies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("operation_audit_days", sa.Integer(), nullable=False),
        sa.Column("task_run_days", sa.Integer(), nullable=False),
        sa.Column("risk_event_days", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index(op.f("ix_retention_policies_tenant_id"), "retention_policies", ["tenant_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_retention_policies_tenant_id"), table_name="retention_policies")
    op.drop_table("retention_policies")
    op.drop_index(op.f("ix_risk_events_user_id"), table_name="risk_events")
    op.drop_index(op.f("ix_risk_events_tenant_id"), table_name="risk_events")
    op.drop_index(op.f("ix_risk_events_severity"), table_name="risk_events")
    op.drop_index(op.f("ix_risk_events_request_id"), table_name="risk_events")
    op.drop_index(op.f("ix_risk_events_event_type"), table_name="risk_events")
    op.drop_index(op.f("ix_risk_events_created_at"), table_name="risk_events")
    op.drop_table("risk_events")
    op.drop_index(op.f("ix_account_deletion_requests_user_id"), table_name="account_deletion_requests")
    op.drop_index(op.f("ix_account_deletion_requests_token_hash"), table_name="account_deletion_requests")
    op.drop_index(op.f("ix_account_deletion_requests_tenant_id"), table_name="account_deletion_requests")
    op.drop_index(op.f("ix_account_deletion_requests_status"), table_name="account_deletion_requests")
    op.drop_table("account_deletion_requests")
    op.drop_index(op.f("ix_mfa_backup_codes_user_id"), table_name="mfa_backup_codes")
    op.drop_index(op.f("ix_mfa_backup_codes_code_hash"), table_name="mfa_backup_codes")
    op.drop_table("mfa_backup_codes")
    op.drop_index(op.f("ix_tenant_invitations_token_hash"), table_name="tenant_invitations")
    op.drop_index(op.f("ix_tenant_invitations_tenant_id"), table_name="tenant_invitations")
    op.drop_index(op.f("ix_tenant_invitations_email"), table_name="tenant_invitations")
    op.drop_table("tenant_invitations")
    op.drop_column("users", "mfa_secret_encrypted")
    op.drop_column("users", "mfa_enabled")
