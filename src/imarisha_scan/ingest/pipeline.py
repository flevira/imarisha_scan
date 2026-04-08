from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from imarisha_scan.scanner import FolderImportAdapter, WindowsTwainAdapter, WindowsWiaAdapter


@dataclass(frozen=True)
class IngestConfig:
    root_dir: Path
    scans_dirname: str = "scans"
    incoming_dirname: str = "incoming"
    processing_dirname: str = "processing"
    processed_dirname: str = "processed"
    error_dirname: str = "error"
    archive_dirname: str = "archive"
    allowed_suffixes: tuple[str, ...] = (".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp")
    min_batch_size: int = 10
    max_batch_size: int = 100

    @property
    def scans_dir(self) -> Path:
        return self.root_dir / self.scans_dirname

    @property
    def incoming_dir(self) -> Path:
        return self.root_dir / self.incoming_dirname

    @property
    def processing_dir(self) -> Path:
        return self.root_dir / self.processing_dirname

    @property
    def processed_dir(self) -> Path:
        return self.root_dir / self.processed_dirname

    @property
    def error_dir(self) -> Path:
        return self.root_dir / self.error_dirname

    @property
    def archive_dir(self) -> Path:
        return self.root_dir / self.archive_dirname


class FolderLifecycleManager:
    def __init__(self, config: IngestConfig) -> None:
        self.config = config
        self.scans_reader = FolderImportAdapter(config.allowed_suffixes)
        self.incoming_reader = FolderImportAdapter(config.allowed_suffixes)

    def ensure_directories(self) -> None:
        for folder in (
            self.config.scans_dir,
            self.config.incoming_dir,
            self.config.processing_dir,
            self.config.processed_dir,
            self.config.error_dir,
            self.config.archive_dir,
        ):
            folder.mkdir(parents=True, exist_ok=True)

    def pull_scans_to_incoming(self) -> list[Path]:
        self.ensure_directories()
        moved: list[Path] = []
        for item in self.scans_reader.scan_to_files(self.config.scans_dir):
            target = self.config.incoming_dir / item.name
            item.replace(target)
            moved.append(target)
        return moved

    def stage_batch(self, limit: int | None = None) -> list[Path]:
        self.ensure_directories()
        batch_limit = min(limit or self.config.max_batch_size, self.config.max_batch_size)
        candidates = self.incoming_reader.scan_to_files(self.config.incoming_dir)[:batch_limit]
        staged: list[Path] = []
        for item in candidates:
            stamped = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            target = self.config.processing_dir / f"{stamped}_{item.name}"
            item.replace(target)
            staged.append(target)
        return staged

    def mark_processed(self, file_path: str | Path, success: bool = True) -> Path:
        source = Path(file_path)
        target_dir = self.config.processed_dir if success else self.config.error_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        source.replace(target)
        return target

    def archive_processed(self) -> list[Path]:
        self.ensure_directories()
        today = datetime.now(UTC)
        archive_target = self.config.archive_dir / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"
        archive_target.mkdir(parents=True, exist_ok=True)
        archived: list[Path] = []
        for item in self.incoming_reader.scan_to_files(self.config.processed_dir):
            target = archive_target / item.name
            item.replace(target)
            archived.append(target)
        return archived


class WindowsUsbIngestService:
    """Scan flow for Windows: prefer TWAIN, fallback to WIA."""

    def __init__(
        self,
        twain: WindowsTwainAdapter | None = None,
        wia: WindowsWiaAdapter | None = None,
    ) -> None:
        self.twain = twain or WindowsTwainAdapter()
        self.wia = wia or WindowsWiaAdapter()

    def scan(self, output_dir: str | Path, pages: int = 1) -> list[Path]:
        if self.twain.is_available():
            return self.twain.scan_to_files(output_dir, pages=pages)
        if self.wia.is_available():
            return self.wia.scan_to_files(output_dir, pages=pages)
        raise RuntimeError("No Windows scanner adapter available. Install TWAIN driver or WIA-compatible stack.")
