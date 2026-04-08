from datetime import datetime

from imarisha_scan.core import DocumentJob
from imarisha_scan.main import build_home_title


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
