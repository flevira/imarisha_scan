from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OmrConfig:
    fill_threshold: float = 0.45
    ambiguity_gap: float = 0.12


@dataclass(frozen=True)
class BubbleRegion:
    option: str
    x: int
    y: int
    w: int
    h: int


@dataclass(frozen=True)
class QuestionBubbleTemplate:
    question_id: str
    bubbles: tuple[BubbleRegion, ...]


@dataclass(frozen=True)
class DetectionResult:
    answer: str
    confidence: float
    needs_review: bool


class OmrDetector:
    def __init__(self, config: OmrConfig | None = None) -> None:
        self.config = config or OmrConfig()

    def detect_from_matrix(
        self,
        matrix: list[list[int]],
        templates: list[QuestionBubbleTemplate],
    ) -> dict[str, DetectionResult]:
        out: dict[str, DetectionResult] = {}
        for tpl in templates:
            scores = [(b.option, self._fill_score(matrix, b)) for b in tpl.bubbles]
            scores.sort(key=lambda x: x[1], reverse=True)
            top_option, top_score = scores[0]
            second_score = scores[1][1] if len(scores) > 1 else 0.0

            is_marked = top_score >= self.config.fill_threshold
            is_ambiguous = (top_score - second_score) < self.config.ambiguity_gap

            if not is_marked:
                out[tpl.question_id] = DetectionResult(answer="", confidence=top_score, needs_review=True)
                continue
            if is_ambiguous:
                out[tpl.question_id] = DetectionResult(answer="", confidence=top_score, needs_review=True)
                continue

            out[tpl.question_id] = DetectionResult(answer=top_option, confidence=top_score, needs_review=False)

        return out

    @staticmethod
    def _fill_score(matrix: list[list[int]], bubble: BubbleRegion) -> float:
        h_total = 0
        dark = 0
        for yy in range(bubble.y, bubble.y + bubble.h):
            row = matrix[yy]
            for xx in range(bubble.x, bubble.x + bubble.w):
                val = row[xx]
                h_total += 1
                if val < 128:
                    dark += 1
        return dark / h_total if h_total else 0.0
