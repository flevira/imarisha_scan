from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class ReviewRecord:
    user_id: str
    question_id: str
    test_id: str
    exam_id: str
    answer: str
    status: str = "pending"  # pending | approved | rejected


class ReviewSession:
    def __init__(self, rows: list[ReviewRecord]) -> None:
        self.rows = rows
        self.error_queue: list[ReviewRecord] = []

    def update_field(self, index: int, field_name: str, value: str) -> None:
        row = self.rows[index]
        self.rows[index] = replace(row, **{field_name: value})

    def approve(self, index: int) -> None:
        row = self.rows[index]
        self.rows[index] = replace(row, status="approved")

    def reject(self, index: int) -> None:
        row = replace(self.rows[index], status="rejected")
        self.rows[index] = row
        self.error_queue.append(row)

    @property
    def approved_count(self) -> int:
        return sum(1 for r in self.rows if r.status == "approved")

    @property
    def rejected_count(self) -> int:
        return sum(1 for r in self.rows if r.status == "rejected")
