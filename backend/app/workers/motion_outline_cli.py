"""CLI: тяжёлый outline rembg/OpenCV в отдельном процессе (OOM не убивает API)."""

from __future__ import annotations

import argparse
import logging
import sys

from app.config import settings
from app.services.motion_outline_subprocess import (
    apply_subprocess_memory_limit_mb,
    render_motion_outline_job_sync,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("motion_outline_cli")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render motion video outline (subprocess worker)")
    parser.add_argument("--owner-id", type=int, required=True)
    parser.add_argument("--file-id", type=str, required=True)
    args = parser.parse_args(argv)

    apply_subprocess_memory_limit_mb(settings.motion_outline_subprocess_memory_mb)

    try:
        render_motion_outline_job_sync(args.owner_id, args.file_id)
    except Exception as e:
        log.exception("motion outline CLI failed owner=%s file_id=%s", args.owner_id, args.file_id)
        print(str(e) or type(e).__name__, file=sys.stderr)
        return 1

    print(f"ok owner={args.owner_id} file_id={args.file_id.strip()[:128]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
