"""CompanionMediaAsset.price_stars для одиночного paid media

Revision ID: 20260315_asset_price_stars
Revises: 20260314_stars_unibox
Create Date: 2026-03-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260315_asset_price_stars"
down_revision: Union[str, None] = "20260314_stars_unibox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("companion_media_assets"):
        return
    cols = {c["name"] for c in insp.get_columns("companion_media_assets")}
    if "price_stars" not in cols:
        op.add_column(
            "companion_media_assets",
            sa.Column("price_stars", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    op.drop_column("companion_media_assets", "price_stars")
