from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

try:
    from imarisha_scan.ocr.base import OcrEngine, OcrResult
    from imarisha_scan.preprocess import PreprocessPipeline, PreprocessResult
    from imarisha_scan.queueing import QueueStore
except ModuleNotFoundError:
    from .base import OcrEngine, OcrResult  # type: ignore[no-redef]
    from preprocess import PreprocessPipeline, PreprocessResult  # type: ignore[no-redef]
    from queueing import QueueStore  # type: ignore[no-redef]


@dataclass(frozen=True)
class OcrPolicy:
    auto_pass_threshold: float = 0.9
    manual_review_threshold: float = 0.6


@dataclass(frozen=True)
class OcrResultRecord:
    job_id: str
    source_path: str
    processed_path: str
    text: str
    provider: str
    confidence: float
    decision: str
    created_at: datetime


class OcrResultStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ocr_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    processed_path TEXT NOT NULL,
                    text TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    decision TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def save(self, record: OcrResultRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ocr_results(job_id, source_path, processed_path, text, provider, confidence, decision, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.source_path,
                    record.processed_path,
                    record.text,
                    record.provider,
                    record.confidence,
                    record.decision,
                    record.created_at.isoformat(),
                ),
            )

    def list_for_job(self, job_id: str) -> list[OcrResultRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM ocr_results WHERE job_id=? ORDER BY id", (job_id,)).fetchall()
        return [
            OcrResultRecord(
                job_id=row["job_id"],
                source_path=row["source_path"],
                processed_path=row["processed_path"],
                text=row["text"],
                provider=row["provider"],
                confidence=float(row["confidence"]),
                decision=row["decision"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]


class OcrWorkflow:
    def __init__(
        self,
        preprocess: PreprocessPipeline,
        engine: OcrEngine,
        store: OcrResultStore,
        policy: OcrPolicy | None = None,
    ) -> None:
        self.preprocess = preprocess
        self.engine = engine
        self.store = store
        self.policy = policy or OcrPolicy()

    def process_file(self, job_id: str, input_path: str | Path, output_dir: str | Path, dpi: int | None = None) -> OcrResultRecord:
        pre_result: PreprocessResult = self.preprocess.preprocess_file(input_path, output_dir, dpi=dpi)
        ocr_result: OcrResult = self.engine.extract_text(pre_result.output_path)

        confidence = ocr_result.confidence if ocr_result.confidence is not None else self._estimate_confidence(ocr_result.text)
        decision = self._decision_for(confidence)

        record = OcrResultRecord(
            job_id=job_id,
            source_path=str(Path(input_path)),
            processed_path=str(pre_result.output_path),
            text=ocr_result.text,
            provider=ocr_result.provider,
            confidence=confidence,
            decision=decision,
            created_at=datetime.now(UTC),
        )
        self.store.save(record)
        return record

    def _decision_for(self, confidence: float) -> str:
        if confidence >= self.policy.auto_pass_threshold:
            return "auto_pass"
        if confidence >= self.policy.manual_review_threshold:
            return "manual_review"
        return "manual_review"

    @staticmethod
    def _estimate_confidence(text: str) -> float:
        cleaned = text.strip()
        if not cleaned:
            return 0.0
        if len(cleaned) > 80:
            return 0.92
        if len(cleaned) > 30:
            return 0.75
        return 0.55


class BatchOcrWorker:
    def __init__(self, queue: QueueStore, workflow: OcrWorkflow, output_dir: str | Path, max_attempts: int = 3) -> None:
        self.queue = queue
        self.workflow = workflow
        self.output_dir = Path(output_dir)
        self.max_attempts = max_attempts

    def run_once(self, worker_id: str = "ocr-worker") -> OcrResultRecord | None:
        job = self.queue.claim_next(worker=worker_id)
        if job is None:
            return None
        try:
            record = self.workflow.process_file(
                job_id=job.id,
                input_path=job.source_path,
                output_dir=self.output_dir,
            )
            self.queue.mark_done(job.id)
            return record
        except Exception as exc:
            requeue = job.attempt_count < self.max_attempts
            self.queue.mark_failed(job.id, error=str(exc), requeue=requeue)
            raise
