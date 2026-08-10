from unittest.mock import patch

from app.config import settings
from app.services.fx_rate import cached_cbr_rub_per_usd_sync, studio_motion_rub_per_usd_effective


def test_studio_motion_rub_per_usd_is_cbr_plus_margin():
    with patch("app.services.fx_rate.cached_cbr_rub_per_usd_sync", return_value=84.0):
        with patch.object(settings, "studio_motion_rub_per_usd_margin", 4.0):
            assert studio_motion_rub_per_usd_effective() == 88.0


def test_studio_motion_rub_per_usd_fallback_cbr():
    # Без прогрева кэша — fallback 90 + margin 4
    with patch.object(settings, "studio_motion_rub_per_usd_margin", 4.0):
        with patch("app.services.fx_rate._cache", {"rub_per_usd": None, "updated_at": None, "source": "fallback"}):
            assert cached_cbr_rub_per_usd_sync() == 90.0
            assert studio_motion_rub_per_usd_effective() == 94.0
