"""Baseline — схема до Alembic создаётся через init_db/_migrate_*.

Revision ID: 20260310_baseline
Revises:
Create Date: 2026-03-10

Новые изменения схемы добавляйте следующими ревизиями alembic revision --autogenerate.
"""

from __future__ import annotations

from typing import Sequence, Union

revision: str = "20260310_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
