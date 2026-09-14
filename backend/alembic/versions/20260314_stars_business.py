"""Stars Business paid media bot (OWNER / OPERATOR)

Revision ID: 20260314_stars_business
Revises: 20260310_phase4
Create Date: 2026-03-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260314_stars_business"
down_revision: Union[str, None] = "20260310_phase4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stars_business_connections",
        sa.Column("owner_tg_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("connection_id", sa.String(length=128), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("owner_user_chat_id", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "stars_business_operators",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("operator_tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_tg_user_id"],
            ["stars_business_connections.owner_tg_user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_tg_user_id",
            "operator_tg_user_id",
            name="uq_stars_business_operator_owner_op",
        ),
    )
    op.create_index(
        "ix_stars_business_operators_owner_tg_user_id",
        "stars_business_operators",
        ["owner_tg_user_id"],
    )
    op.create_index(
        "ix_stars_business_operators_operator_tg_user_id",
        "stars_business_operators",
        ["operator_tg_user_id"],
    )
    op.create_table(
        "stars_business_fan_chats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("fan_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("fan_display_name", sa.String(length=256), nullable=True),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_tg_user_id"],
            ["stars_business_connections.owner_tg_user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_tg_user_id",
            "fan_chat_id",
            name="uq_stars_business_fan_chat",
        ),
    )
    op.create_index(
        "ix_stars_business_fan_chats_owner_tg_user_id",
        "stars_business_fan_chats",
        ["owner_tg_user_id"],
    )
    op.create_index(
        "ix_stars_business_fan_chats_fan_chat_id",
        "stars_business_fan_chats",
        ["fan_chat_id"],
    )
    op.create_index(
        "ix_stars_business_fan_chats_last_inbound_at",
        "stars_business_fan_chats",
        ["last_inbound_at"],
    )
    op.create_table(
        "stars_business_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("operator_tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("fan_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("star_count", sa.Integer(), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("media_relative_path", sa.String(length=512), nullable=False),
        sa.Column("media_type", sa.String(length=16), nullable=False, server_default="photo"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("platform_message_id", sa.BigInteger(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_tg_user_id"],
            ["stars_business_connections.owner_tg_user_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_stars_business_orders_owner_tg_user_id",
        "stars_business_orders",
        ["owner_tg_user_id"],
    )
    op.create_index(
        "ix_stars_business_orders_operator_tg_user_id",
        "stars_business_orders",
        ["operator_tg_user_id"],
    )
    op.create_index(
        "ix_stars_business_orders_fan_chat_id",
        "stars_business_orders",
        ["fan_chat_id"],
    )
    op.create_index("ix_stars_business_orders_status", "stars_business_orders", ["status"])


def downgrade() -> None:
    op.drop_table("stars_business_orders")
    op.drop_table("stars_business_fan_chats")
    op.drop_table("stars_business_operators")
    op.drop_table("stars_business_connections")
