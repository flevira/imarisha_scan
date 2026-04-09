import json
from pathlib import Path

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
            ReviewRecord(exam_type="EXAM", user_id="1", test_id="T1", exam_id="E1", status="pending"),
            ReviewRecord(exam_type="EXAM", user_id="2", test_id="T1", exam_id="E1", status="approved"),
            ReviewRecord(exam_type="EXAM", user_id="3", test_id="T1", exam_id="E1", status="rejected"),
        ]
    )

    rows = completed_rows_for_export(session)

    assert len(rows) == 2
    assert [row["status"] for row in rows] == ["approved", "rejected"]


def test_serialize_completed_rows_to_csv_includes_header_and_rows() -> None:
    csv_text = serialize_completed_rows_to_csv(
        [
            {
                "exam_type": "EXAM",
                "user_id": "82",
                "test_id": "",
                "exam_id": "1756",
                "status": "approved",
            }
        ]
    )
    assert "exam_type,user_id,test_id,exam_id,status" in csv_text
    assert "EXAM,82,,1756,approved" in csv_text


def test_load_review_session_uses_blank_placeholder_fields_without_sidecars(tmp_path, monkeypatch) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    (processing / "20260408_SMARTREPO_ACADEMY.jpg").write_text("scan", encoding="utf-8")

    session = load_review_session(ingest_root)

    assert len(session.rows) == 1
    row = session.rows[0]
    assert row.source_file == "20260408_SMARTREPO_ACADEMY.jpg"
    assert row.exam_type == ""
    assert row.user_id == ""
    assert row.test_id == ""
    assert row.exam_id == ""


def test_load_review_session_prefers_json_sidecar_rows(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_001.jpg"
    scan_file.write_text("binary", encoding="utf-8")
    (processing / "sheet_001.json").write_text(
        '[{"exam_type":"EXAM","user_id":"82","test_id":"","exam_id":"1756"}]',
        encoding="utf-8",
    )

    session = load_review_session(ingest_root)

    assert len(session.rows) == 1
    row = session.rows[0]
    assert row.source_file == "sheet_001.jpg"
    assert row.exam_type == "EXAM"
    assert row.user_id == "82"
    assert row.exam_id == "1756"

def test_load_review_session_extracts_from_qr_sidecar(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_002.jpg"
    scan_file.write_text("binary", encoding="utf-8")
    (processing / "sheet_002.qr.txt").write_text("type=EXAM;studentId=82;examId=1756", encoding="utf-8")

    session = load_review_session(ingest_root)

    assert len(session.rows) == 1
    assert session.rows[0].exam_type == "EXAM"
    assert session.rows[0].user_id == "82"
    assert session.rows[0].exam_id == "1756"


def test_run_ocr_and_extract_for_processing_file_creates_extracted_sidecar(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_003.jpg"
    scan_file.write_text("binary", encoding="utf-8")

    scan_file.with_suffix(".qr.txt").write_text("type=EXAM;studentId=82;examId=1756", encoding="utf-8")

    message = run_ocr_and_extract_for_processing_file(ingest_root, scan_file)

    extracted_path = scan_file.with_suffix(".extracted.json")
    assert "OCR and extraction sidecars generated" in message
    payload = json.loads(extracted_path.read_text(encoding="utf-8"))
    assert payload == [{"exam_type": "EXAM", "user_id": "82", "test_id": "", "exam_id": "1756"}]

def test_run_ocr_creates_exam_dataset_only(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_stages.jpg"
    scan_file.write_text("binary", encoding="utf-8")
    scan_file.with_suffix(".qr.txt").write_text("type=EXAM;studentId=82;examId=1756", encoding="utf-8")

    message = run_ocr_and_extract_for_processing_file(ingest_root, scan_file)

    exam_data = json.loads(scan_file.with_suffix(".exam_data.json").read_text(encoding="utf-8"))
    assert "Extracted QR metadata only" in message
    assert exam_data == [{"exam_type": "EXAM", "exam_id": "1756", "test_id": "", "student_id": "82"}]


def test_load_review_session_supports_legacy_sidecar_extensions(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_004.jpg"
    scan_file.write_text("binary", encoding="utf-8")
    scan_file.with_suffix(".qr").write_text("type=EXAM;studentId=82;examId=1756", encoding="utf-8")

    session = load_review_session(ingest_root)

    assert len(session.rows) == 1
    assert session.rows[0].exam_id == "1756"


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
    original_scan.with_suffix(".qr").write_text("type=EXAM;studentId=82;examId=1756", encoding="utf-8")

    message = run_ocr_and_extract_for_processing_file(ingest_root, staged_file)

    extracted_path = staged_file.with_suffix(".extracted.json")
    assert "OCR and extraction sidecars generated" in message
    payload = json.loads(extracted_path.read_text(encoding="utf-8"))
    assert payload[0]["user_id"] == "82"


def test_run_ocr_creates_placeholder_when_qr_missing_without_ocr(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_005.jpg"
    scan_file.write_text("binary", encoding="utf-8")

    message = run_ocr_and_extract_for_processing_file(ingest_root, scan_file)

    qr_sidecar = scan_file.with_suffix(".qr.txt")
    assert "Created placeholder sidecars" in message
    assert qr_sidecar.exists()
    assert qr_sidecar.read_text(encoding="utf-8").strip() == "type=EXAM;studentId=;examId="


def test_run_ocr_creates_placeholder_qr_sidecar_when_qr_missing(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_006.jpg"
    scan_file.write_text("binary", encoding="utf-8")
    scan_file.with_suffix(".ocr.txt").write_text("Student ID: 82\n", encoding="utf-8")

    message = run_ocr_and_extract_for_processing_file(ingest_root, scan_file)

    qr_sidecar = scan_file.with_suffix(".qr.txt")
    assert "Created placeholder sidecars" in message
    assert qr_sidecar.exists()
    assert qr_sidecar.read_text(encoding="utf-8").strip() == "type=EXAM;studentId=;examId="


def test_run_ocr_uses_qr_decoder_payload_when_qr_sidecar_missing(tmp_path, monkeypatch) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_qr_decode.jpg"
    scan_file.write_text("binary", encoding="utf-8")
    scan_file.with_suffix(".ocr.txt").write_text("Student ID: 82\n", encoding="utf-8")

    from imarisha_scan import main as main_module
    from imarisha_scan.qr import QrDecodeResult

    monkeypatch.setattr(
        main_module.QrPayloadDecoder,
        "decode_payload",
        lambda self, image_path: QrDecodeResult(payload="type=EXAM;studentId=82;examId=1756", backend="mock"),
    )

    message = run_ocr_and_extract_for_processing_file(ingest_root, scan_file)

    qr_sidecar = scan_file.with_suffix(".qr.txt")
    extracted_path = scan_file.with_suffix(".extracted.json")
    assert "OCR and extraction sidecars generated" in message
    assert qr_sidecar.read_text(encoding="utf-8").strip() == "type=EXAM;studentId=82;examId=1756"
    payload = json.loads(extracted_path.read_text(encoding="utf-8"))
    assert payload[0]["exam_id"] == "1756"


def test_run_ocr_prefers_preprocessed_image_for_qr_decode(tmp_path, monkeypatch) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_from_pdf.pdf"
    scan_file.write_text("binary", encoding="utf-8")

    artifacts_preprocess = ingest_root / "artifacts" / "preprocess"
    rendered_path = artifacts_preprocess / "pre_sheet_from_pdf.png"

    from imarisha_scan import main as main_module
    from imarisha_scan.qr import QrDecodeResult

    def fake_render(pdf, output_dir):
        rendered_path.parent.mkdir(parents=True, exist_ok=True)
        rendered_path.write_text("png", encoding="utf-8")
        return [rendered_path]

    monkeypatch.setattr(main_module, "_render_pdf_pages_for_ocr", fake_render)

    decode_calls: list[str] = []

    def fake_decode(self, image_path):
        decode_calls.append(str(image_path))
        return QrDecodeResult(payload="type=EXAM;studentId=82;examId=1756", backend="mock")

    monkeypatch.setattr(main_module.QrPayloadDecoder, "decode_payload", fake_decode)

    message = run_ocr_and_extract_for_processing_file(ingest_root, scan_file)

    qr_sidecar = scan_file.with_suffix(".qr.txt")
    extracted_path = scan_file.with_suffix(".extracted.json")
    assert "OCR and extraction sidecars generated" in message
    assert decode_calls == [str(rendered_path)]
    assert qr_sidecar.read_text(encoding="utf-8").strip() == "type=EXAM;studentId=82;examId=1756"
    payload = json.loads(extracted_path.read_text(encoding="utf-8"))
    assert payload[0]["exam_id"] == "1756"


def test_run_ocr_pdf_combines_all_rendered_pages_into_extracted_rows(tmp_path, monkeypatch) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "three_pages.pdf"
    scan_file.write_text("binary", encoding="utf-8")

    artifacts_preprocess = ingest_root / "artifacts" / "preprocess"
    page_1 = artifacts_preprocess / "pre_three_pages_page-1.png"
    page_2 = artifacts_preprocess / "pre_three_pages_page-2.png"
    page_3 = artifacts_preprocess / "pre_three_pages_page-3.png"
    for page in (page_1, page_2, page_3):
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("png", encoding="utf-8")

    from imarisha_scan import main as main_module
    from imarisha_scan.qr import QrDecodeResult

    monkeypatch.setattr(main_module, "_render_pdf_pages_for_ocr", lambda pdf, output_dir: [page_1, page_2, page_3])
    monkeypatch.setattr(
        main_module.QrPayloadDecoder,
        "decode_payload",
        lambda self, image_path: QrDecodeResult(payload="type=EXAM;studentId=82;examId=1756", backend="mock"),
    )

    message = run_ocr_and_extract_for_processing_file(ingest_root, scan_file)

    extracted_path = scan_file.with_suffix(".extracted.json")
    payload = json.loads(extracted_path.read_text(encoding="utf-8"))
    assert "OCR and extraction sidecars generated" in message
    assert payload == [{"exam_type": "EXAM", "user_id": "82", "test_id": "", "exam_id": "1756"}]


def test_run_ocr_uses_existing_qr_sidecar_and_common_student_id(tmp_path, monkeypatch) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_sidecar_mode.jpg"
    scan_file.write_text("binary", encoding="utf-8")
    scan_file.with_suffix(".ocr.txt").write_text("Student ID: 999\n", encoding="utf-8")
    scan_file.with_suffix(".qr.txt").write_text("type=EXAM;studentId=82;examId=SIDECAR", encoding="utf-8")

    from imarisha_scan import main as main_module

    monkeypatch.setattr(
        main_module.QrPayloadDecoder,
        "decode_payload",
        lambda self, image_path: (_ for _ in ()).throw(AssertionError("decoder should not run when QR sidecar exists")),
    )

    message = run_ocr_and_extract_for_processing_file(ingest_root, scan_file)

    extracted_path = scan_file.with_suffix(".extracted.json")
    assert "OCR and extraction sidecars generated" in message
    payload = json.loads(extracted_path.read_text(encoding="utf-8"))
    assert payload[0]["exam_id"] == "SIDECAR"
    assert payload[0]["user_id"] == "82"


def test_run_ocr_keeps_existing_qr_sidecar_without_overwrite(tmp_path, monkeypatch) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_qr_mode.jpg"
    scan_file.write_text("binary", encoding="utf-8")
    scan_file.with_suffix(".ocr.txt").write_text("Student ID: 82\n", encoding="utf-8")
    scan_file.with_suffix(".qr.txt").write_text("type=EXAM;studentId=82;examId=SIDECAR", encoding="utf-8")

    from imarisha_scan import main as main_module
    monkeypatch.setattr(
        main_module.QrPayloadDecoder,
        "decode_payload",
        lambda self, image_path: (_ for _ in ()).throw(AssertionError("decoder should not run when QR sidecar exists")),
    )

    message = run_ocr_and_extract_for_processing_file(ingest_root, scan_file)

    qr_sidecar = scan_file.with_suffix(".qr.txt")
    extracted_path = scan_file.with_suffix(".extracted.json")
    assert "OCR and extraction sidecars generated" in message
    assert qr_sidecar.read_text(encoding="utf-8").strip() == "type=EXAM;studentId=82;examId=SIDECAR"
    payload = json.loads(extracted_path.read_text(encoding="utf-8"))
    assert payload[0]["exam_id"] == "SIDECAR"


def test_run_ocr_ignores_ocr_sidecar_for_qr_inference(tmp_path) -> None:
    ingest_root = tmp_path / "runtime_data"
    processing = ingest_root / "processing"
    processing.mkdir(parents=True)
    scan_file = processing / "sheet_007.jpg"
    scan_file.write_text("binary", encoding="utf-8")
    scan_file.with_suffix(".ocr.txt").write_text(
        "type=EXAM;studentId=82;examId=1756\nSome text\n",
        encoding="utf-8",
    )

    message = run_ocr_and_extract_for_processing_file(ingest_root, scan_file)

    qr_sidecar = scan_file.with_suffix(".qr.txt")
    assert "Created placeholder sidecars" in message
    assert qr_sidecar.read_text(encoding="utf-8").strip() == "type=EXAM;studentId=;examId="
