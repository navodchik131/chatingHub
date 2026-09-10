import pytest

from app.config import Settings


def test_app_role_all_runs_inline_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ROLE", "all")
    s = Settings()
    assert s.studio_jobs_execute_in_api is True
    assert s.studio_jobs_worker_loop_enabled is False
    assert s.background_maintenance_in_process is True
    assert s.companion_jobs_worker_in_api is True
    assert s.companion_jobs_worker_loop_enabled is False
    assert s.runs_http_api is True


def test_app_role_api_no_background_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ROLE", "api")
    s = Settings()
    assert s.studio_jobs_execute_in_api is False
    assert s.studio_jobs_worker_loop_enabled is False
    assert s.background_maintenance_in_process is False
    assert s.companion_jobs_worker_in_api is False
    assert s.companion_jobs_worker_loop_enabled is False
    assert s.runs_telegram_user_worker is True


def test_app_role_worker_runs_maintenance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ROLE", "worker")
    s = Settings()
    assert s.studio_jobs_execute_in_api is False
    assert s.studio_jobs_worker_loop_enabled is True
    assert s.background_maintenance_in_process is True
    assert s.companion_jobs_worker_in_api is False
    assert s.companion_jobs_worker_loop_enabled is True
    assert s.runs_http_api is False
