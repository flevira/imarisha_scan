from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

try:
    from imarisha_scan.scanner import FolderImportAdapter, WindowsTwainAdapter, WindowsWiaAdapter
except ModuleNotFoundError:
    from scanner import FolderImportAdapter, WindowsTwainAdapter, WindowsWiaAdapter  # type: ignore[no-redef]


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
    poll_interval_seconds: int = 5
    stable_cycles: int = 2
    max_wait_seconds: int = 60
    max_error_retries: int = 3
    processed_retention_days: int = 30
    error_retention_days: int = 30
    archive_retention_days: int = 180

    @property
    def scans_dir(self) -> Path:
        return self.root_dir / self.scans_dirname

    @property
    def legacy_input_dir(self) -> Path:
        """Backward-compatible source folder used by older deployments."""
        return self.root_dir / "input"

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
        self._stability: dict[str, tuple[int, int, int]] = {}
        self._retry_counts: dict[str, int] = {}

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
        """Move only stable scan files from scans/input -> incoming."""
        self.ensure_directories()
        moved: list[Path] = []

        source_dirs = [self.config.scans_dir]
        if self.config.legacy_input_dir != self.config.scans_dir and self.config.legacy_input_dir.exists():
            source_dirs.append(self.config.legacy_input_dir)

        scan_files: list[Path] = []
        for source_dir in source_dirs:
            scan_files.extend(self.scans_reader.scan_to_files(source_dir))

        active_keys = {str(p) for p in scan_files}
        self._stability = {k: v for k, v in self._stability.items() if k in active_keys}

        for item in scan_files:
            stat = item.stat()
            key = str(item)
            marker = (stat.st_size, stat.st_mtime_ns)
            prev = self._stability.get(key)
            streak = 1 if prev is None or prev[:2] != marker else prev[2] + 1
            self._stability[key] = (marker[0], marker[1], streak)
            if streak < self.config.stable_cycles:
                continue

            target = self._unique_target(self.config.incoming_dir, item.name)
            item.replace(target)
            moved.append(target)
            self._stability.pop(key, None)
        return moved

    def ready_for_batch(self) -> bool:
        files = self.incoming_reader.scan_to_files(self.config.incoming_dir)
        if not files:
            return False
        if len(files) >= self.config.min_batch_size:
            return True
        oldest = min(p.stat().st_mtime for p in files)
        oldest_at = datetime.fromtimestamp(oldest, UTC)
        waited = datetime.now(UTC) - oldest_at
        return waited.total_seconds() >= self.config.max_wait_seconds

    def stage_batch(self, limit: int | None = None) -> list[Path]:
        self.ensure_directories()
        batch_limit = min(limit or self.config.max_batch_size, self.config.max_batch_size)
        candidates = self.incoming_reader.scan_to_files(self.config.incoming_dir)[:batch_limit]
        staged: list[Path] = []
        for item in candidates:
            stamped = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            target = self._unique_target(self.config.processing_dir, f"{stamped}_{item.name}")
            item.replace(target)
            staged.append(target)
        return staged

    def run_once(self) -> list[Path]:
        self.pull_scans_to_incoming()
        if not self.ready_for_batch():
            return []
        return self.stage_batch()

    def mark_processed(self, file_path: str | Path, success: bool = True, error_reason: str | None = None) -> Path:
        source = Path(file_path)
        if success:
            target = self._unique_target(self.config.processed_dir, source.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            source.replace(target)
            return target

        key = self._retry_key(source.name)
        retries = self._retry_counts.get(key, 0) + 1
        self._retry_counts[key] = retries

        if retries <= self.config.max_error_retries:
            retry_name = self._with_retry_suffix(source.name, retries)
            target = self._unique_target(self.config.incoming_dir, retry_name)
        else:
            suffix = f".failed-{error_reason or 'error'}"
            target = self._unique_target(self.config.error_dir, source.stem + suffix + source.suffix)

        target.parent.mkdir(parents=True, exist_ok=True)
        source.replace(target)
        return target

    def archive_processed(self) -> list[Path]:
        self.ensure_directories()
        today = datetime.now(UTC)
        archive_target = self.config.archive_dir / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"
        archive_target.mkdir(parents=True, exist_ok=True)
        archived: list[Path] = []
        for item in self.incoming_reader.scan_to_files(self.config.processed_dir):
            target = self._unique_target(archive_target, item.name)
            item.replace(target)
            archived.append(target)
        return archived

    def cleanup_retention(self, now: datetime | None = None) -> int:
        self.ensure_directories()
        now = now or datetime.now(UTC)
        removed = 0
        removed += self._cleanup_dir(self.config.processed_dir, now - timedelta(days=self.config.processed_retention_days))
        removed += self._cleanup_dir(self.config.error_dir, now - timedelta(days=self.config.error_retention_days))
        removed += self._cleanup_dir_recursive(
            self.config.archive_dir,
            now - timedelta(days=self.config.archive_retention_days),
        )
        return removed

    def _cleanup_dir(self, path: Path, cutoff: datetime) -> int:
        count = 0
        for item in self.incoming_reader.scan_to_files(path):
            if datetime.fromtimestamp(item.stat().st_mtime, UTC) < cutoff:
                item.unlink(missing_ok=True)
                count += 1
        return count

    def _cleanup_dir_recursive(self, path: Path, cutoff: datetime) -> int:
        if not path.exists():
            return 0
        count = 0
        for item in path.rglob("*"):
            if item.is_file() and datetime.fromtimestamp(item.stat().st_mtime, UTC) < cutoff:
                item.unlink(missing_ok=True)
                count += 1
        return count

    @staticmethod
    def _with_retry_suffix(name: str, retries: int) -> str:
        p = Path(name)
        return f"{p.stem}.retry{retries}{p.suffix}"

    @staticmethod
    def _retry_key(name: str) -> str:
        stem = Path(name).stem
        return stem.split(".retry", 1)[0]

    @staticmethod
    def _unique_target(folder: Path, filename: str) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / filename
        if not target.exists():
            return target
        base = target.stem
        suffix = target.suffix
        i = 1
        while True:
            candidate = folder / f"{base}_{i}{suffix}"
            if not candidate.exists():
                return candidate
            i += 1


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
