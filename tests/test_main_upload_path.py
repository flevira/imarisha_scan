import json

from imarisha_scan.main import (
    completed_rows_for_export,
    load_review_session,
    normalize_upload_path,
    pick_default_scan_file,
    run_ocr_and_extract_for_processing_file,
    serialize_completed_rows_to_csv,
)
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


def test_serialize_completed_rows_to_csv_includes_header_and_rows() -> None:
    csv_text = serialize_completed_rows_to_csv(
        [
            {
                "user_id": "82",
                "question_id": "81535",
                "test_id": "",
                "exam_id": "1756",
                "answer": "C",
                "status": "approved",
            }
        ]
    )
    assert "user_id,question_id,test_id,exam_id,answer,status" in csv_text
    assert "82,81535,,1756,C,approved" in csv_text


def test_load_review_session_uses_blank_placeholder_fields_without_sidecars(tmp_path, monkeypatch) -> None:
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


def test_load_review_session_prefers_json_sidecar_rows(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_001.jpg"
    scan_file.write_text("binary", encoding="utf-8")
    (processing / "sheet_001.json").write_text(
        '[{"user_id":"82","question_id":"81535","test_id":"","exam_id":"1756","answer":"c"}]',
        encoding="utf-8",
    )

    session = load_review_session(ingest_root)

    assert len(session.rows) == 1
    row = session.rows[0]
    assert row.source_file == "sheet_001.jpg"
    assert row.user_id == "82"
    assert row.question_id == "81535"
    assert row.exam_id == "1756"
    assert row.answer == "C"


def test_load_review_session_extracts_from_ocr_qr_and_answers_sidecars(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_002.jpg"
    scan_file.write_text("binary", encoding="utf-8")
    (processing / "sheet_002.ocr.txt").write_text(
        "Student ID: 82\n81535 A B C D E\n81570 A B C D E\n",
        encoding="utf-8",
    )
    (processing / "sheet_002.qr.txt").write_text("type=EXAM;studentId=82;examId=1756", encoding="utf-8")
    (processing / "sheet_002.answers.json").write_text('{"81535":"A","81570":"D"}', encoding="utf-8")

    session = load_review_session(ingest_root)

    assert len(session.rows) == 2
    assert [row.question_id for row in session.rows] == ["81535", "81570"]
    assert [row.answer for row in session.rows] == ["A", "D"]


def test_run_ocr_and_extract_for_processing_file_creates_extracted_sidecar(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_003.jpg"
    scan_file.write_text("binary", encoding="utf-8")

    scan_file.with_suffix(".ocr.txt").write_text(
        "Student ID: 82\n81535 A B C D E\n81570 A B C D E\n",
        encoding="utf-8",
    )
    scan_file.with_suffix(".qr.txt").write_text("type=EXAM;studentId=82;examId=1756", encoding="utf-8")
    scan_file.with_suffix(".answers.json").write_text('{"81535":"A","81570":"D"}', encoding="utf-8")

    message = run_ocr_and_extract_for_processing_file(ingest_root, scan_file)

    extracted_path = scan_file.with_suffix(".extracted.json")
    assert "OCR and extraction sidecars generated" in message
    payload = json.loads(extracted_path.read_text(encoding="utf-8"))
    assert [row["question_id"] for row in payload] == ["81535", "81570"]
    assert [row["answer"] for row in payload] == ["A", "D"]


def test_load_review_session_supports_legacy_sidecar_extensions(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_004.jpg"
    scan_file.write_text("binary", encoding="utf-8")
    scan_file.with_suffix(".ocr").write_text(
        "Student ID: 82\n81535 A B C D E\n81570 A B C D E\n",
        encoding="utf-8",
    )
    scan_file.with_suffix(".qr").write_text("type=EXAM;studentId=82;examId=1756", encoding="utf-8")
    scan_file.with_suffix(".answers").write_text('{"81535":"A","81570":"D"}', encoding="utf-8")

    session = load_review_session(ingest_root)

    assert len(session.rows) == 2
    assert [row.question_id for row in session.rows] == ["81535", "81570"]
    assert [row.answer for row in session.rows] == ["A", "D"]


def test_run_ocr_uses_sidecars_for_original_name_after_staging_prefix(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    scans = ingest_root / "scans"
    processing.mkdir(parents=True)
    scans.mkdir(parents=True)

    staged_file = processing / "20260409135533_SMARTREPO.pdf"
    staged_file.write_text("binary", encoding="utf-8")

    original_scan = scans / "SMARTREPO.pdf"
    original_scan.write_text("binary", encoding="utf-8")
    original_scan.with_suffix(".ocr").write_text(
        "Student ID: 82\n81535 A B C D E\n81570 A B C D E\n",
        encoding="utf-8",
    )
    original_scan.with_suffix(".qr").write_text("type=EXAM;studentId=82;examId=1756", encoding="utf-8")
    original_scan.with_suffix(".answers").write_text('{"81535":"A","81570":"D"}', encoding="utf-8")

    message = run_ocr_and_extract_for_processing_file(ingest_root, staged_file)

    extracted_path = staged_file.with_suffix(".extracted.json")
    assert "OCR and extraction sidecars generated" in message
    payload = json.loads(extracted_path.read_text(encoding="utf-8"))
    assert [row["question_id"] for row in payload] == ["81535", "81570"]


def test_run_ocr_unavailable_message_includes_env_var_hint(tmp_path, monkeypatch) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_005.jpg"
    scan_file.write_text("binary", encoding="utf-8")

    from imarisha_scan import main as main_module

    monkeypatch.setattr(main_module.LocalTesseractEngine, "is_available", lambda self: False)

    message = run_ocr_and_extract_for_processing_file(ingest_root, scan_file)

    assert "IMARISHA_TESSERACT_BIN" in message
    assert "Alternative" in message


def test_run_ocr_creates_placeholder_sidecars_when_qr_and_answers_missing(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_006.jpg"
    scan_file.write_text("binary", encoding="utf-8")
    scan_file.with_suffix(".ocr.txt").write_text("Student ID: 82\n81535 A B C D E\n", encoding="utf-8")

    message = run_ocr_and_extract_for_processing_file(ingest_root, scan_file)

    qr_sidecar = scan_file.with_suffix(".qr.txt")
    answers_sidecar = scan_file.with_suffix(".answers.json")
    assert "Created placeholder sidecars" in message
    assert qr_sidecar.exists()
    assert answers_sidecar.exists()
    assert qr_sidecar.read_text(encoding="utf-8").strip() == "type=EXAM;studentId=;examId="
    assert json.loads(answers_sidecar.read_text(encoding="utf-8")) == {}


def test_run_ocr_uses_inferred_qr_and_answers_from_ocr_text(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_007.jpg"
    scan_file.write_text("binary", encoding="utf-8")
    scan_file.with_suffix(".ocr.txt").write_text(
        "type=EXAM;studentId=82;examId=1756\n81535 - C\n81570: A\n",
        encoding="utf-8",
    )

    message = run_ocr_and_extract_for_processing_file(ingest_root, scan_file)

    extracted_path = scan_file.with_suffix(".extracted.json")
    assert "OCR and extraction sidecars generated" in message
    payload = json.loads(extracted_path.read_text(encoding="utf-8"))
    assert [row["question_id"] for row in payload] == ["81535", "81570"]
    assert [row["answer"] for row in payload] == ["C", "A"]
