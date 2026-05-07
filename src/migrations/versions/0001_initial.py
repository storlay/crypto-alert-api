"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-07
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    coin_enum = sa.Enum("BTC", "ETH", "SOL", "BNB", "XRP", name="coin")
    direction_enum = sa.Enum("above", "below", name="direction")
    alert_status_enum = sa.Enum("active", "triggered", "cancelled", name="alert_status")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("coin", coin_enum, nullable=False),
        sa.Column("direction", direction_enum, nullable=False),
        sa.Column("threshold", sa.Numeric(18, 8), nullable=False),
        sa.Column("status", alert_status_enum, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_price", sa.Numeric(18, 8), nullable=True),
    )
    op.create_index(
        "ix_alerts_active_by_coin",
        "alerts",
        ["coin"],
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_alerts_active_by_user",
        "alerts",
        ["user_id"],
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "candles_1m",
        sa.Column("coin", coin_enum, primary_key=True),
        sa.Column("open_time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("open", sa.Numeric(18, 8), nullable=False),
        sa.Column("high", sa.Numeric(18, 8), nullable=False),
        sa.Column("low", sa.Numeric(18, 8), nullable=False),
        sa.Column("close", sa.Numeric(18, 8), nullable=False),
        sa.Column("volume", sa.Numeric(28, 8), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("candles_1m")
    op.drop_index("ix_alerts_active_by_user", table_name="alerts")
    op.drop_index("ix_alerts_active_by_coin", table_name="alerts")
    op.drop_table("alerts")
    op.drop_table("users")
    sa.Enum(name="alert_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="direction").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="coin").drop(op.get_bind(), checkfirst=True)
