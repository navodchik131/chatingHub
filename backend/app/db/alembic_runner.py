"""Запуск Alembic после legacy _migrate_* — новые DDL только через revisions."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

log = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def run_alembic_upgrade_head() -> None:
    ini_path = _BACKEND_DIR / "alembic.ini"
    if not ini_path.is_file():
        log.debug("alembic.ini not found, skip upgrade")
        return
    try:
        cfg = Config(str(ini_path))
        command.upgrade(cfg, "head")
        log.info("Alembic: upgrade head OK")
    except Exception:
        log.exception("Alembic upgrade head failed")
