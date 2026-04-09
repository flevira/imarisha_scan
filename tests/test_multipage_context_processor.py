from imarisha_scan.workflow import MultiPageContextProcessor, PageScan


def _ocr_with_questions(user_id: str) -> str:
    return f"""
Student ID: {user_id}
81535   A B C D E
81570   A B C D E
"""


def test_context_switches_when_new_qr_appears() -> None:
    processor = MultiPageContextProcessor()

    pages = [
        PageScan(
            page_no=1,
            qr_payload="type=EXAM;studentId=82;examId=1756",
            ocr_text=_ocr_with_questions("82"),
            answers_by_question={"81535": "A", "81570": "B"},
        ),
        PageScan(
            page_no=2,
            qr_payload=None,
            ocr_text=_ocr_with_questions("82"),
            answers_by_question={"81535": "C", "81570": "D"},
        ),
        PageScan(
            page_no=3,
            qr_payload="type=EXAM;studentId=99;examId=2001",
            ocr_text=_ocr_with_questions("99"),
            answers_by_question={"81535": "E", "81570": "A"},
        ),
    ]

    records, issues = processor.process_pages("batch.pdf", pages)

    assert not issues
    # one QR metadata row per page
    assert len(records) == 3

    page1 = [r for r in records if r["page_no"] == "1"]
    page2 = [r for r in records if r["page_no"] == "2"]
    page3 = [r for r in records if r["page_no"] == "3"]

    assert all(r["user_id"] == "82" and r["exam_type"] == "EXAM" for r in page1)
    assert all(r["user_id"] == "82" and r["exam_type"] == "EXAM" for r in page2)
    assert all(r["user_id"] == "99" and r["exam_type"] == "EXAM" for r in page3)

    assert all(r["segment_no"] == "1" for r in page1 + page2)
    assert all(r["segment_no"] == "2" for r in page3)


def test_missing_initial_qr_goes_to_issue_queue() -> None:
    processor = MultiPageContextProcessor()

    pages = [
        PageScan(
            page_no=1,
            qr_payload=None,
            ocr_text=_ocr_with_questions("82"),
            answers_by_question={"81535": "A", "81570": "B"},
        )
    ]

    records, issues = processor.process_pages("batch.pdf", pages)

    assert records == []
    assert len(issues) == 1
    assert issues[0].code == "missing_context"
