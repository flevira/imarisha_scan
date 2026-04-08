from imarisha_scan.omr import BubbleRegion, OmrConfig, OmrDetector, QuestionBubbleTemplate


def _blank_matrix(width: int, height: int, value: int = 255) -> list[list[int]]:
    return [[value for _ in range(width)] for _ in range(height)]


def _fill_rect(matrix: list[list[int]], x: int, y: int, w: int, h: int, value: int = 0) -> None:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            matrix[yy][xx] = value


def test_detect_marked_bubbles() -> None:
    matrix = _blank_matrix(80, 40)

    # Q1 bubbles A-E
    q1 = QuestionBubbleTemplate(
        question_id="81535",
        bubbles=(
            BubbleRegion("A", 5, 5, 5, 5),
            BubbleRegion("B", 12, 5, 5, 5),
            BubbleRegion("C", 19, 5, 5, 5),
            BubbleRegion("D", 26, 5, 5, 5),
            BubbleRegion("E", 33, 5, 5, 5),
        ),
    )
    # Q2 bubbles A-E
    q2 = QuestionBubbleTemplate(
        question_id="81570",
        bubbles=(
            BubbleRegion("A", 5, 15, 5, 5),
            BubbleRegion("B", 12, 15, 5, 5),
            BubbleRegion("C", 19, 15, 5, 5),
            BubbleRegion("D", 26, 15, 5, 5),
            BubbleRegion("E", 33, 15, 5, 5),
        ),
    )

    _fill_rect(matrix, 19, 5, 5, 5, value=0)   # q1 -> C
    _fill_rect(matrix, 12, 15, 5, 5, value=0)  # q2 -> B

    detector = OmrDetector(OmrConfig(fill_threshold=0.45, ambiguity_gap=0.12))
    result = detector.detect_from_matrix(matrix, [q1, q2])

    assert result["81535"].answer == "C"
    assert result["81570"].answer == "B"
    assert result["81535"].needs_review is False


def test_ambiguous_mark_goes_to_review() -> None:
    matrix = _blank_matrix(40, 20)
    q = QuestionBubbleTemplate(
        question_id="90001",
        bubbles=(
            BubbleRegion("A", 2, 2, 5, 5),
            BubbleRegion("B", 10, 2, 5, 5),
            BubbleRegion("C", 18, 2, 5, 5),
            BubbleRegion("D", 26, 2, 5, 5),
            BubbleRegion("E", 34, 2, 5, 5),
        ),
    )

    _fill_rect(matrix, 2, 2, 5, 5, value=0)
    _fill_rect(matrix, 10, 2, 5, 5, value=20)

    detector = OmrDetector(OmrConfig(fill_threshold=0.45, ambiguity_gap=0.3))
    result = detector.detect_from_matrix(matrix, [q])

    assert result["90001"].answer == ""
    assert result["90001"].needs_review is True
