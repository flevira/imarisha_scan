from pathlib import Path

from imarisha_scan.export import CsvExporter
from imarisha_scan.extract import ExtractionRule, RuleExtractor
from imarisha_scan.queueing import QueueStore
from imarisha_scan.scanner import FolderImportAdapter


def test_queue_store_lifecycle(tmp_path: Path) -> None:
    db_path = tmp_path / "jobs.db"
    queue = QueueStore(db_path)

    job_id = queue.enqueue("/tmp/sample.pdf")
    claimed = queue.claim_next(worker="worker-1", lease_seconds=1)

    assert claimed is not None
    assert claimed.id == job_id
    assert claimed.status == "processing"

    queue.mark_done(job_id)
    done = queue.get(job_id)

    assert done is not None
    assert done.status == "done"


def test_rule_extractor_and_csv_export(tmp_path: Path) -> None:
    extractor = RuleExtractor(
        [
            ExtractionRule("invoice_no", r"Invoice\s*#:\s*(\S+)"),
            ExtractionRule("amount", r"Amount:\s*\$([0-9]+\.[0-9]{2})"),
        ]
    )
    text = "Invoice #: INV-123\nAmount: $42.10"

    data = extractor.extract(text)

    out_file = tmp_path / "export.csv"
    exporter = CsvExporter()
    exporter.export_rows([data], ["invoice_no", "amount"], out_file)

    content = out_file.read_text(encoding="utf-8")
    assert "invoice_no,amount" in content
    assert "INV-123,42.10" in content


def test_folder_import_adapter_filters_supported_files(tmp_path: Path) -> None:
    (tmp_path / "a.pdf").write_text("x", encoding="utf-8")
    (tmp_path / "b.jpg").write_text("x", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("x", encoding="utf-8")

    adapter = FolderImportAdapter()
    files = adapter.scan_to_files(tmp_path)

    assert [p.name for p in files] == ["a.pdf", "b.jpg"]
