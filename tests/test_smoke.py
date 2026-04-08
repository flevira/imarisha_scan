from datetime import datetime

from imarisha_scan.core import DocumentJob
from imarisha_scan.main import (
    build_home_title,
    get_ingest_root_dir,
    get_runtime_config,
    should_fallback_to_web,
)


def test_home_title() -> None:
    assert build_home_title() == "Imarisha Scan"


def test_document_job_defaults() -> None:
    job = DocumentJob(
        id="job-1",
        source="sample.pdf",
        status="queued",
        created_at=datetime(2026, 1, 1),
    )
    assert job.total_pages == 0


def test_runtime_config_defaults(monkeypatch) -> None:
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("FLET_WEB", raising=False)

    cfg = get_runtime_config()

    assert cfg.port == 8550
    assert cfg.host == "0.0.0.0"
    assert cfg.web_mode is False


def test_runtime_config_web_flag(monkeypatch) -> None:
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("FLET_WEB", "1")

    cfg = get_runtime_config()

    assert cfg.port == 8080
    assert cfg.web_mode is True


def test_ingest_root_dir_defaults_to_runtime_data(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("IMARISHA_INGEST_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)

    root = get_ingest_root_dir()

    assert root == (tmp_path / "runtime_data").resolve()


def test_ingest_root_dir_respects_env(monkeypatch, tmp_path) -> None:
    custom = tmp_path / "uploads"
    monkeypatch.setenv("IMARISHA_INGEST_ROOT", str(custom))

    root = get_ingest_root_dir()

    assert root == custom.resolve()


def test_ssl_error_triggers_web_fallback() -> None:
    err = RuntimeError("CERTIFICATE_VERIFY_FAILED")
    assert should_fallback_to_web(err) is True


def test_unrelated_error_does_not_trigger_web_fallback() -> None:
    err = RuntimeError("some other crash")
    assert should_fallback_to_web(err) is False
