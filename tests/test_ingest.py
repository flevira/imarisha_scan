from pathlib import Path

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


def test_folder_lifecycle_moves_files(tmp_path: Path) -> None:
    cfg = IngestConfig(root_dir=tmp_path)
    manager = FolderLifecycleManager(cfg)
    manager.ensure_directories()

    (cfg.scans_dir / "doc1.pdf").write_text("a", encoding="utf-8")
    (cfg.scans_dir / "doc2.jpg").write_text("b", encoding="utf-8")

    moved = manager.pull_scans_to_incoming()
    assert [p.name for p in moved] == ["doc1.pdf", "doc2.jpg"]

    staged = manager.stage_batch(limit=1)
    assert len(staged) == 1
    assert staged[0].parent == cfg.processing_dir

    done_file = manager.mark_processed(staged[0], success=True)
    assert done_file.parent == cfg.processed_dir

    archived = manager.archive_processed()
    assert len(archived) == 1
    assert cfg.archive_dir in archived[0].parents


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
