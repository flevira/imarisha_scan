from __future__ import annotations

from dataclasses import dataclass

from imarisha_scan.extract import AnswerSheetExtractor


@dataclass(frozen=True)
class PageScan:
    page_no: int
    ocr_text: str
    answers_by_question: dict[str, str]
    qr_payload: str | None = None


@dataclass(frozen=True)
class PageIssue:
    page_no: int
    code: str
    message: str


class MultiPageContextProcessor:
    """Processes multi-page scans where QR context can change between pages."""

    def __init__(self, extractor: AnswerSheetExtractor | None = None) -> None:
        self.extractor = extractor or AnswerSheetExtractor()

    def process_pages(self, source_file: str, pages: list[PageScan]) -> tuple[list[dict[str, str]], list[PageIssue]]:
        records: list[dict[str, str]] = []
        issues: list[PageIssue] = []

        active_qr: str | None = None
        segment_no = 0

        for page in sorted(pages, key=lambda p: p.page_no):
            if page.qr_payload:
                if page.qr_payload != active_qr:
                    active_qr = page.qr_payload
                    segment_no += 1

            if not active_qr:
                issues.append(PageIssue(page_no=page.page_no, code="missing_context", message="No QR context found yet"))
                continue

            try:
                rows = self.extractor.extract_rows(page.ocr_text, active_qr, page.answers_by_question)
            except Exception as exc:
                issues.append(PageIssue(page_no=page.page_no, code="extract_failed", message=str(exc)))
                continue

            for row in rows:
                row["source_file"] = source_file
                row["page_no"] = str(page.page_no)
                row["segment_no"] = str(segment_no)
                records.append(row)

        return records, issues
