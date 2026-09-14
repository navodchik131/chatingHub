"""Stars Business + Unibox: user_id, price_stars на пак, поля заказа

Revision ID: 20260314_stars_unibox
Revises: 20260314_stars_business
Create Date: 2026-03-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260314_stars_unibox"
down_revision: Union[str, None] = "20260314_stars_business"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_names(table: str) -> set[str]:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table(table):
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    conn_cols = _col_names("stars_business_connections")
    if insp.has_table("stars_business_connections"):
        if "user_id" not in conn_cols:
            op.add_column(
                "stars_business_connections",
                sa.Column("user_id", sa.Integer(), nullable=True),
            )
        op.create_foreign_key(
            "fk_stars_business_connections_user_id",
            "stars_business_connections",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_stars_business_connections_user_id",
            "stars_business_connections",
            ["user_id"],
        )

    if insp.has_table("companion_media_packs") and "price_stars" not in _col_names("companion_media_packs"):
        op.add_column(
            "companion_media_packs",
            sa.Column("price_stars", sa.Integer(), nullable=False, server_default="0"),
        )

    if insp.has_table("stars_business_orders"):
        order_cols = _col_names("stars_business_orders")
        for col_name, col_type in (
            ("conversation_id", sa.Integer()),
            ("pack_id", sa.Integer()),
            ("asset_id", sa.Integer()),
            ("created_by_user_id", sa.Integer()),
            ("unibox_message_id", sa.Integer()),
        ):
            if col_name not in order_cols:
                op.add_column(
                    "stars_business_orders",
                    sa.Column(col_name, col_type, nullable=True),
                )
        op.create_foreign_key(
            "fk_stars_business_orders_conversation_id",
            "stars_business_orders",
            "conversations",
            ["conversation_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_stars_business_orders_pack_id",
            "stars_business_orders",
            "companion_media_packs",
            ["pack_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_stars_business_orders_asset_id",
            "stars_business_orders",
            "companion_media_assets",
            ["asset_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_stars_business_orders_created_by_user_id",
            "stars_business_orders",
            "users",
            ["created_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            "fk_stars_business_orders_unibox_message_id",
            "stars_business_orders",
            "messages",
            ["unibox_message_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            "ix_stars_business_orders_conversation_id",
            "stars_business_orders",
            ["conversation_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_stars_business_orders_conversation_id", table_name="stars_business_orders")
    op.drop_constraint(
        "fk_stars_business_orders_unibox_message_id",
        "stars_business_orders",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_stars_business_orders_created_by_user_id",
        "stars_business_orders",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_stars_business_orders_asset_id",
        "stars_business_orders",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_stars_business_orders_pack_id",
        "stars_business_orders",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_stars_business_orders_conversation_id",
        "stars_business_orders",
        type_="foreignkey",
    )
    op.drop_column("stars_business_orders", "unibox_message_id")
    op.drop_column("stars_business_orders", "created_by_user_id")
    op.drop_column("stars_business_orders", "asset_id")
    op.drop_column("stars_business_orders", "pack_id")
    op.drop_column("stars_business_orders", "conversation_id")

    op.drop_column("companion_media_packs", "price_stars")

    op.drop_index("ix_stars_business_connections_user_id", table_name="stars_business_connections")
    op.drop_constraint(
        "fk_stars_business_connections_user_id",
        "stars_business_connections",
        type_="foreignkey",
    )
    op.drop_column("stars_business_connections", "user_id")
