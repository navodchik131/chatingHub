import os
import time
from pathlib import Path

from app.services.studio_runtime_cleanup import purge_tree_files_older_than


def test_purge_tree_files_older_than(tmp_path: Path, monkeypatch) -> None:
    from app.services import studio_runtime_cleanup as mod

    data_root = tmp_path / "data"
    cache = data_root / "motion_outline_cache"
    cache.mkdir(parents=True)
    old_file = cache / "old.mp4"
    new_file = cache / "new.mp4"
    old_file.write_bytes(b"old")
    new_file.write_bytes(b"new")

    old_ts = time.time() - 10 * 86400
    os.utime(old_file, (old_ts, old_ts))

    monkeypatch.setattr(mod, "_DATA_ROOT", data_root.resolve())
    removed = purge_tree_files_older_than(cache, days=7)
    assert removed == 1
    assert not old_file.exists()
    assert new_file.exists()


def test_purge_disabled_when_days_zero(tmp_path: Path, monkeypatch) -> None:
    from app.services import studio_runtime_cleanup as mod

    data_root = tmp_path / "data"
    cache = data_root / "motion_outline_cache"
    cache.mkdir(parents=True)
    f = cache / "x.mp4"
    f.write_bytes(b"x")
    old_ts = time.time() - 100 * 86400
    os.utime(f, (old_ts, old_ts))
    monkeypatch.setattr(mod, "_DATA_ROOT", data_root.resolve())
    assert purge_tree_files_older_than(cache, days=0) == 0
    assert f.exists()
