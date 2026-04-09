from __future__ import annotations

import re
from dataclasses import dataclass


REQUIRED_FIELDS = ("user_id", "question_id", "test_id", "exam_id", "answer")


@dataclass(frozen=True)
class SheetContext:
    user_id: str
    test_id: str
    exam_id: str
    doc_type: str


class AnswerSheetExtractor:
    """Rule-based extractor for SMARTPREPO answer sheets."""

    def parse_qr_payload(self, payload: str) -> SheetContext:
        parts = self._parse_pairs(payload)
        doc_type = parts.get("type", "").upper()
        user_id = parts.get("user_id", parts.get("userid", parts.get("studentid", "")))
        test_id = parts.get("test_id", parts.get("testid", ""))
        exam_id = parts.get("exam_id", parts.get("examid", ""))
        assessment_id = parts.get("assessmentid", "")

        if doc_type == "TEST" and not test_id:
            test_id = assessment_id
        if doc_type == "EXAM" and not exam_id:
            exam_id = assessment_id

        if doc_type not in {"TEST", "EXAM"}:
            raise ValueError("QR payload must include type=TEST or type=EXAM")
        if not user_id:
            raise ValueError("QR payload must include user_id")
        if doc_type == "TEST" and not test_id:
            raise ValueError("QR payload with type=TEST must include test_id")
        if doc_type == "EXAM" and not exam_id:
            raise ValueError("QR payload with type=EXAM must include exam_id")

        return SheetContext(user_id=user_id, test_id=test_id, exam_id=exam_id, doc_type=doc_type)

    def extract_rows(
        self,
        ocr_text: str,
        qr_payload: str,
        answers_by_question: dict[str, str] | None = None,
    ) -> list[dict[str, str]]:
        context = self.parse_qr_payload(qr_payload)

        user_id = context.user_id or self._extract_user_id(ocr_text)
        question_ids = self._extract_question_ids(ocr_text)
        provided_answers = {str(k): str(v).strip().upper() for k, v in (answers_by_question or {}).items()}
        detected_answers = self._extract_answers_by_question(ocr_text)
        rows: list[dict[str, str]] = []

        for question_id in question_ids:
            answer = provided_answers.get(question_id, detected_answers.get(question_id, ""))
            row = {
                "user_id": user_id,
                "question_id": question_id,
                "test_id": context.test_id,
                "exam_id": context.exam_id,
                "answer": answer,
            }
            self._validate_row(row, context.doc_type)
            rows.append(row)

        return rows


    def extract_rows_from_detection_results(
        self,
        ocr_text: str,
        qr_payload: str,
        detections: dict[str, object],
    ) -> list[dict[str, str]]:
        answers: dict[str, str] = {}
        for qid, det in detections.items():
            answer = getattr(det, "answer", "")
            answers[qid] = answer
        return self.extract_rows(ocr_text, qr_payload, answers)

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
        return cls._extract_answers_by_question(ocr_text)
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

    @staticmethod
    def _validate_row(row: dict[str, str], doc_type: str) -> None:
        if not row["user_id"]:
            raise ValueError("user_id is required")
        if not row["question_id"]:
            raise ValueError("question_id is required")
        if row["answer"] not in {"A", "B", "C", "D", "E"}:
            raise ValueError(f"answer must be one of A-E for question {row['question_id']}")

        if doc_type == "TEST":
            if not row["test_id"]:
                raise ValueError("test_id is required when type=TEST")
            row["exam_id"] = ""
        elif doc_type == "EXAM":
            if not row["exam_id"]:
                raise ValueError("exam_id is required when type=EXAM")
            row["test_id"] = ""
