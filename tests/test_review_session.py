from imarisha_scan.ui import ReviewRecord, ReviewSession


def test_review_session_edit_approve_reject() -> None:
    session = ReviewSession(
        [
            ReviewRecord(exam_type="EXAM", user_id="82", test_id="", exam_id="1756"),
            ReviewRecord(exam_type="EXAM", user_id="82", test_id="", exam_id="1756"),
        ]
    )

    session.update_field(0, "exam_id", "2001")
    assert session.rows[0].exam_id == "2001"

    session.approve(0)
    session.reject(1)

    assert session.approved_count == 1
    assert session.rejected_count == 1
    assert len(session.error_queue) == 1
