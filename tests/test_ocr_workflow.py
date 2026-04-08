from pathlib import Path

import pytest

from imarisha_scan.ocr import BatchOcrWorker, OcrPolicy, OcrResult, OcrResultStore, OcrWorkflow
from imarisha_scan.preprocess import PreprocessPipeline
from imarisha_scan.queueing import QueueStore


class FakeOcrEngine:
    def __init__(self, text: str, confidence: float | None = None, fail: bool = False) -> None:
        self.text = text
        self.confidence = confidence
        self.fail = fail

    def extract_text(self, image_path: str | Path, language: str = "eng") -> OcrResult:
        del image_path, language
        if self.fail:
            raise RuntimeError("OCR failed")
        return OcrResult(text=self.text, provider="fake", confidence=self.confidence)


def test_ocr_workflow_persists_and_assigns_decision(tmp_path: Path) -> None:
    source = tmp_path / "scan.jpg"
    source.write_text("raw", encoding="utf-8")

    store = OcrResultStore(tmp_path / "ocr.db")
    workflow = OcrWorkflow(
        preprocess=PreprocessPipeline(),
        engine=FakeOcrEngine(text="Some long OCR text" * 10, confidence=None),
        store=store,
        policy=OcrPolicy(auto_pass_threshold=0.9, manual_review_threshold=0.6),
    )

    record = workflow.process_file("job-1", source, tmp_path / "processed", dpi=300)
    saved = store.list_for_job("job-1")

    assert record.decision == "auto_pass"
    assert len(saved) == 1
    assert saved[0].text == record.text


def test_batch_worker_claims_and_completes_job(tmp_path: Path) -> None:
    source = tmp_path / "scan.jpg"
    source.write_text("raw", encoding="utf-8")

    queue = QueueStore(tmp_path / "queue.db")
    job_id = queue.enqueue(str(source))

    store = OcrResultStore(tmp_path / "ocr.db")
    workflow = OcrWorkflow(PreprocessPipeline(), FakeOcrEngine(text="Invoice extracted", confidence=0.91), store)
    worker = BatchOcrWorker(queue=queue, workflow=workflow, output_dir=tmp_path / "processed")

    record = worker.run_once()
    done_job = queue.get(job_id)

    assert record is not None
    assert done_job is not None
    assert done_job.status == "done"


def test_batch_worker_requeues_on_failure(tmp_path: Path) -> None:
    source = tmp_path / "scan.jpg"
    source.write_text("raw", encoding="utf-8")

    queue = QueueStore(tmp_path / "queue.db")
    job_id = queue.enqueue(str(source))

    store = OcrResultStore(tmp_path / "ocr.db")
    workflow = OcrWorkflow(PreprocessPipeline(), FakeOcrEngine(text="", fail=True), store)
    worker = BatchOcrWorker(queue=queue, workflow=workflow, output_dir=tmp_path / "processed", max_attempts=3)

    with pytest.raises(RuntimeError):
        worker.run_once()

    job = queue.get(job_id)
    assert job is not None
    assert job.status == "queued"


def test_golden_file_ocr_output(tmp_path: Path) -> None:
    fixture_dir = Path("tests/fixtures/ocr")
    source_text = (fixture_dir / "sample_input.txt").read_text(encoding="utf-8")
    expected = (fixture_dir / "sample_expected.txt").read_text(encoding="utf-8").strip()

    source = tmp_path / "sample.jpg"
    source.write_text("raw", encoding="utf-8")

    store = OcrResultStore(tmp_path / "ocr.db")
    workflow = OcrWorkflow(PreprocessPipeline(), FakeOcrEngine(text=source_text, confidence=0.95), store)

    record = workflow.process_file("job-golden", source, tmp_path / "processed", dpi=300)

    assert record.text.strip() == expected
    assert record.decision == "auto_pass"
