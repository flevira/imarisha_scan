from datetime import datetime

from imarisha_scan.core import DocumentJob
from imarisha_scan.main import build_home_title, get_runtime_config


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
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)

    cfg = get_runtime_config()

    assert cfg.port == 8550
    assert cfg.host == "0.0.0.0"
    assert cfg.web_mode is False


def test_runtime_config_railway(monkeypatch) -> None:
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")

    cfg = get_runtime_config()

    assert cfg.port == 8080
    assert cfg.web_mode is True
