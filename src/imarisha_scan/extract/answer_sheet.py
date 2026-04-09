from __future__ import annotations

import re
from dataclasses import dataclass


REQUIRED_FIELDS = ("exam_type", "user_id", "test_id", "exam_id")


@dataclass(frozen=True)
class SheetContext:
    exam_type: str
    user_id: str
    test_id: str
    exam_id: str


class AnswerSheetExtractor:
    """Rule-based extractor for SMARTPREPO answer sheets."""

    def parse_qr_payload(self, payload: str) -> SheetContext:
        parts = self._parse_pairs(payload)
        exam_type = parts.get("type", "").upper()
        user_id = parts.get("user_id", parts.get("userid", parts.get("studentid", "")))
        test_id = parts.get("test_id", parts.get("testid", ""))
        exam_id = parts.get("exam_id", parts.get("examid", ""))
        assessment_id = parts.get("assessmentid", "")

        if exam_type == "TEST" and not test_id:
            test_id = assessment_id
        if exam_type == "EXAM" and not exam_id:
            exam_id = assessment_id

        if exam_type not in {"TEST", "EXAM"}:
            raise ValueError("QR payload must include type=TEST or type=EXAM")
        if not user_id:
            raise ValueError("QR payload must include user_id")
        if exam_type == "TEST" and not test_id:
            raise ValueError("QR payload with type=TEST must include test_id")
        if exam_type == "EXAM" and not exam_id:
            raise ValueError("QR payload with type=EXAM must include exam_id")

        return SheetContext(exam_type=exam_type, user_id=user_id, test_id=test_id, exam_id=exam_id)

    def extract_rows(
        self,
        ocr_text: str,
        qr_payload: str,
        answers_by_question: dict[str, str] | None = None,
    ) -> list[dict[str, str]]:
        del ocr_text, answers_by_question
        context = self.parse_qr_payload(qr_payload)
        return [
            {
                "exam_type": context.exam_type,
                "user_id": context.user_id,
                "test_id": context.test_id,
                "exam_id": context.exam_id,
            }
        ]


    def extract_rows_from_detection_results(
        self,
        ocr_text: str,
        qr_payload: str,
        detections: dict[str, object],
    ) -> list[dict[str, str]]:
        del detections
        return self.extract_rows(ocr_text, qr_payload, None)

    @staticmethod
    def infer_qr_payload_from_text(ocr_text: str) -> str:
        for line in ocr_text.splitlines():
            candidate = line.strip()
            if "type=" not in candidate.lower() or "=" not in candidate:
                continue
            if "studentid=" in candidate.lower() or "user_id=" in candidate.lower() or "userid=" in candidate.lower():
                return candidate
        return ""

    @classmethod
    def infer_answers_from_text(cls, ocr_text: str) -> dict[str, str]:
        del ocr_text
        return {}
    @staticmethod
    def _parse_pairs(payload: str) -> dict[str, str]:
        pairs = re.split(r"[;|,]", payload)
        out: dict[str, str] = {}
        for pair in pairs:
            if "=" not in pair:
                continue
            k, v = pair.split("=", 1)
            out[k.strip().lower()] = v.strip()
        return out

    @staticmethod
    def _extract_user_id(ocr_text: str) -> str:
        m = re.search(r"Student\s*ID\s*[:#-]\s*(\d+)", ocr_text, flags=re.IGNORECASE)
        return m.group(1) if m else ""

    @staticmethod
    def _extract_question_ids(ocr_text: str) -> list[str]:
        lines = [line.strip() for line in ocr_text.splitlines()]
        ids: list[str] = []
        for line in lines:
            m = re.match(r"^(\d{4,6})\b", line)
            if m:
                ids.append(m.group(1))
        return ids

    @staticmethod
    def _extract_answers_by_question(ocr_text: str) -> dict[str, str]:
        answers: dict[str, str] = {}
        for line in ocr_text.splitlines():
            m = re.match(r"^\s*(\d{4,6})\b(.*)$", line.strip())
            if not m:
                continue
            question_id, remainder = m.group(1), m.group(2)
            direct = re.search(r"[:=\-]\s*([A-E])\b", remainder, flags=re.IGNORECASE)
            if direct:
                answers[question_id] = direct.group(1).upper()
                continue
            choices = re.findall(r"\b([A-E])\b", remainder, flags=re.IGNORECASE)
            if len(choices) == 1:
                answers[question_id] = choices[0].upper()
        return answers
