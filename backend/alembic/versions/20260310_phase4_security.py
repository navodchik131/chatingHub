"""auth_token_version + http_rate_limit_buckets

Revision ID: 20260310_phase4
Revises: 20260310_baseline
Create Date: 2026-03-10
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260310_phase4"
down_revision: Union[str, None] = "20260310_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("users"):
        cols = {c["name"] for c in insp.get_columns("users")}
        if "auth_token_version" not in cols:
            op.add_column(
                "users",
                sa.Column(
                    "auth_token_version",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                ),
            )
    if not insp.has_table("http_rate_limit_buckets"):
        op.create_table(
            "http_rate_limit_buckets",
            sa.Column("bucket_key", sa.String(length=128), primary_key=True),
            sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    op.drop_table("http_rate_limit_buckets")
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("users"):
        cols = {c["name"] for c in insp.get_columns("users")}
        if "auth_token_version" in cols:
            op.drop_column("users", "auth_token_version")
