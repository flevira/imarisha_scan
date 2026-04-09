from datetime import UTC, datetime, timedelta
from pathlib import Path
import os

import pytest

from imarisha_scan.ingest import FolderLifecycleManager, IngestConfig, WindowsUsbIngestService


class _FakeAdapter:
    def __init__(self, available: bool, outputs: list[Path] | None = None) -> None:
        self._available = available
        self._outputs = outputs or []

    def is_available(self) -> bool:
        return self._available

    def scan_to_files(self, output_dir: str | Path, pages: int = 1) -> list[Path]:
        del output_dir, pages
        return self._outputs


def test_folder_lifecycle_moves_only_stable_files(tmp_path: Path) -> None:
    cfg = IngestConfig(root_dir=tmp_path, stable_cycles=2, min_batch_size=1)
    manager = FolderLifecycleManager(cfg)
    manager.ensure_directories()

    (cfg.scans_dir / "doc1.pdf").write_text("a", encoding="utf-8")

    assert manager.pull_scans_to_incoming() == []
    moved = manager.pull_scans_to_incoming()
    assert [p.name for p in moved] == ["doc1.pdf"]


def test_run_once_stages_batch_on_threshold(tmp_path: Path) -> None:
    cfg = IngestConfig(root_dir=tmp_path, stable_cycles=1, min_batch_size=2, max_batch_size=100)
    manager = FolderLifecycleManager(cfg)
    manager.ensure_directories()

    (cfg.scans_dir / "doc1.pdf").write_text("a", encoding="utf-8")
    (cfg.scans_dir / "doc2.jpg").write_text("b", encoding="utf-8")

    staged = manager.run_once()
    assert len(staged) == 2
    assert all(p.parent == cfg.processing_dir for p in staged)


def test_folder_lifecycle_supports_legacy_input_folder(tmp_path: Path) -> None:
    cfg = IngestConfig(root_dir=tmp_path, stable_cycles=1, min_batch_size=1)
    manager = FolderLifecycleManager(cfg)
    manager.ensure_directories()

    legacy_input = cfg.legacy_input_dir
    legacy_input.mkdir(parents=True, exist_ok=True)
    (legacy_input / "legacy_scan.pdf").write_text("a", encoding="utf-8")

    moved = manager.pull_scans_to_incoming()

    assert [p.name for p in moved] == ["legacy_scan.pdf"]
    assert not (legacy_input / "legacy_scan.pdf").exists()
    assert (cfg.incoming_dir / "legacy_scan.pdf").exists()


def test_retry_then_error_routing(tmp_path: Path) -> None:
    cfg = IngestConfig(root_dir=tmp_path, max_error_retries=1)
    manager = FolderLifecycleManager(cfg)
    manager.ensure_directories()

    file_path = cfg.processing_dir / "sample.pdf"
    file_path.write_text("a", encoding="utf-8")

    retry_path = manager.mark_processed(file_path, success=False, error_reason="ocr")
    assert retry_path.parent == cfg.incoming_dir
    assert ".retry1" in retry_path.name

    retry_path_2 = cfg.processing_dir / retry_path.name
    retry_path.replace(retry_path_2)
    error_path = manager.mark_processed(retry_path_2, success=False, error_reason="ocr")
    assert error_path.parent == cfg.error_dir
    assert "failed-ocr" in error_path.name


def test_cleanup_retention_removes_old_files(tmp_path: Path) -> None:
    cfg = IngestConfig(root_dir=tmp_path, processed_retention_days=30, error_retention_days=30)
    manager = FolderLifecycleManager(cfg)
    manager.ensure_directories()

    old_processed = cfg.processed_dir / "old.pdf"
    old_processed.write_text("x", encoding="utf-8")

    old_error = cfg.error_dir / "old.jpg"
    old_error.write_text("x", encoding="utf-8")

    old_archive = cfg.archive_dir / "2020" / "01" / "01"
    old_archive.mkdir(parents=True, exist_ok=True)
    (old_archive / "old.png").write_text("x", encoding="utf-8")

    old_time = (datetime.now(UTC) - timedelta(days=365)).timestamp()
    for p in [old_processed, old_error, old_archive / "old.png"]:
        p.chmod(0o644)
        os.utime(p, (old_time, old_time))

    removed = manager.cleanup_retention()
    assert removed == 3


def test_windows_ingest_prefers_twain_then_wia(tmp_path: Path) -> None:
    twain = _FakeAdapter(available=False)
    wia = _FakeAdapter(available=True, outputs=[tmp_path / "scanned.pdf"])
    service = WindowsUsbIngestService(twain=twain, wia=wia)

    files = service.scan(tmp_path, pages=2)

    assert [f.name for f in files] == ["scanned.pdf"]


def test_windows_ingest_raises_without_driver(tmp_path: Path) -> None:
    service = WindowsUsbIngestService(twain=_FakeAdapter(False), wia=_FakeAdapter(False))

    with pytest.raises(RuntimeError):
        service.scan(tmp_path)
