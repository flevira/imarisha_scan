import pytest

from imarisha_scan.extract import AnswerSheetExtractor
from imarisha_scan.ocr import OcrPolicy


OCR_SAMPLE = """
SMARTPREPO ACADEMY
Student ID: 82
"""


QR_EXAM_V2 = (
    "v=2;type=EXAM;assessmentId=1756;testId=;examId=1756;teacherId=1;schoolId=8;"
    "level=PRIMARY_ENGLISH;className=vi;studentId=82"
)


def test_extract_rows_exam_type_from_qr_v2() -> None:
    extractor = AnswerSheetExtractor()

    rows = extractor.extract_rows(OCR_SAMPLE, QR_EXAM_V2, None)

    assert len(rows) == 1
    assert rows[0]["exam_type"] == "EXAM"
    assert rows[0]["user_id"] == "82"
    assert rows[0]["exam_id"] == "1756"
    assert rows[0]["test_id"] == ""


def test_extract_rows_test_type() -> None:
    extractor = AnswerSheetExtractor()
    qr = "type=TEST;user_id=82;test_id=TEST_123"

    rows = extractor.extract_rows(OCR_SAMPLE, qr, None)

    assert rows[0]["exam_type"] == "TEST"
    assert rows[0]["test_id"] == "TEST_123"
    assert rows[0]["exam_id"] == ""


def test_assessment_id_fallback_for_exam_id() -> None:
    extractor = AnswerSheetExtractor()
    qr = "type=EXAM;assessmentId=2001;studentId=82"

    rows = extractor.extract_rows(OCR_SAMPLE, qr, None)

    assert rows[0]["exam_id"] == "2001"


def test_missing_required_exam_id_raises() -> None:
    extractor = AnswerSheetExtractor()

    with pytest.raises(ValueError):
        extractor.extract_rows(OCR_SAMPLE, "type=EXAM;studentId=82", None)


def test_confidence_policy_default_is_auto_accept_gt_09() -> None:
    policy = OcrPolicy()
    assert policy.auto_pass_threshold == 0.9


def test_extract_rows_from_detection_results() -> None:
    extractor = AnswerSheetExtractor()

    class _Det:
        def __init__(self, answer: str) -> None:
            self.answer = answer

    detections = {"81535": _Det("A"), "81570": _Det("B"), "81679": _Det("C")}
    rows = extractor.extract_rows_from_detection_results(OCR_SAMPLE, QR_EXAM_V2, detections)

    assert len(rows) == 1
    assert rows[0]["user_id"] == "82"


def test_extract_rows_uses_student_id_from_qr_not_ocr() -> None:
    extractor = AnswerSheetExtractor()
    ocr = OCR_SAMPLE.replace("Student ID: 82", "Student ID: 999")
    rows = extractor.extract_rows(ocr, QR_EXAM_V2, None)
    assert rows[0]["user_id"] == "82"


def test_infer_answers_from_text_returns_empty_for_qr_only_workflow() -> None:
    extractor = AnswerSheetExtractor()
    ocr = "81535 - C\n81570: A\n81679 B\n"
    answers = extractor.infer_answers_from_text(ocr)
    assert answers == {}
