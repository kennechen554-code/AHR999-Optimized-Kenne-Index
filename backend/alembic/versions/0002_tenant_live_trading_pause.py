"""tenant live trading pause

Revision ID: 0002_tenant_live_trading_pause
Revises: 0001_main_schema_baseline
Create Date: 2026-05-10 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_tenant_live_trading_pause"
down_revision = "0001_main_schema_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("live_trading_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("tenants", "live_trading_paused")
