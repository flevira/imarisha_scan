from imarisha_scan.ui import ReviewRecord, ReviewSession


def test_review_session_edit_approve_reject() -> None:
    session = ReviewSession(
        [
            ReviewRecord(user_id="82", question_id="81535", test_id="", exam_id="1756", answer="C"),
            ReviewRecord(user_id="82", question_id="81570", test_id="", exam_id="1756", answer="A"),
        ]
    )

    session.update_field(0, "answer", "B")
    assert session.rows[0].answer == "B"

    session.approve(0)
    session.reject(1)

    assert session.approved_count == 1
    assert session.rejected_count == 1
    assert len(session.error_queue) == 1
