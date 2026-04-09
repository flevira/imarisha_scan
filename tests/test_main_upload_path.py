from imarisha_scan.main import completed_rows_for_export, load_review_session, normalize_upload_path, pick_default_scan_file
from imarisha_scan.ui import ReviewRecord, ReviewSession


def test_normalize_upload_path_removes_wrapping_single_quotes() -> None:
    assert normalize_upload_path("'~/Documents/Scans and PDF'") == "~/Documents/Scans and PDF"


def test_normalize_upload_path_removes_wrapping_double_quotes() -> None:
    assert normalize_upload_path('"~/Documents/Scans and PDF"') == "~/Documents/Scans and PDF"


def test_normalize_upload_path_preserves_path_without_wrapping_quotes() -> None:
    assert normalize_upload_path("~/Documents/teacher's scans") == "~/Documents/teacher's scans"


def test_pick_default_scan_file_returns_none_when_no_files() -> None:
    assert pick_default_scan_file([], None) is None


def test_pick_default_scan_file_keeps_existing_selection() -> None:
    files = ["scan_1.pdf", "scan_2.pdf"]
    assert pick_default_scan_file(files, "scan_2.pdf") == "scan_2.pdf"


def test_pick_default_scan_file_uses_first_when_selection_missing() -> None:
    files = ["scan_1.pdf", "scan_2.pdf"]
    assert pick_default_scan_file(files, "unknown.pdf") == "scan_1.pdf"


def test_completed_rows_for_export_includes_approved_and_rejected_only() -> None:
    session = ReviewSession(
        [
            ReviewRecord(user_id="1", question_id="Q1", test_id="T1", exam_id="E1", answer="A", status="pending"),
            ReviewRecord(user_id="2", question_id="Q2", test_id="T1", exam_id="E1", answer="B", status="approved"),
            ReviewRecord(user_id="3", question_id="Q3", test_id="T1", exam_id="E1", answer="C", status="rejected"),
        ]
    )

    rows = completed_rows_for_export(session)

    assert len(rows) == 2
    assert [row["status"] for row in rows] == ["approved", "rejected"]


def test_load_review_session_uses_blank_placeholder_fields(tmp_path, monkeypatch) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    (processing / "20260408_SMARTREPO_ACADEMY.jpg").write_text("scan", encoding="utf-8")

    session = load_review_session(ingest_root)

    assert len(session.rows) == 1
    row = session.rows[0]
    assert row.source_file == "20260408_SMARTREPO_ACADEMY.jpg"
    assert row.user_id == ""
    assert row.question_id == ""
    assert row.test_id == ""
    assert row.exam_id == ""
    assert row.answer == ""
