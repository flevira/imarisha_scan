from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .pipeline import IngestConfig


@dataclass(frozen=True)
class ImportResult:
    source: Path
    destination: Path | None
    status: str  # imported | skipped
    reason: str = ""


class LocalStorageIngestor:
    """Imports scanned files from local/USB storage into the ingest workflow folders."""

    def __init__(self, config: IngestConfig) -> None:
        self.config = config
        self.allowed_suffixes = {s.lower() for s in config.allowed_suffixes}

    def import_files(self, file_paths: list[str | Path], target: str = "incoming") -> list[ImportResult]:
        target_dir = self._resolve_target(target)
        target_dir.mkdir(parents=True, exist_ok=True)

        results: list[ImportResult] = []
        for file_path in file_paths:
            src = Path(file_path)
            if not src.exists() or not src.is_file():
                results.append(ImportResult(source=src, destination=None, status="skipped", reason="missing_file"))
                continue
            if src.suffix.lower() not in self.allowed_suffixes:
                results.append(ImportResult(source=src, destination=None, status="skipped", reason="unsupported_format"))
                continue

            dest = self._unique_target(target_dir, src.name)
            shutil.copy2(src, dest)
            results.append(ImportResult(source=src, destination=dest, status="imported"))

        return results

    def import_directory(self, directory: str | Path, target: str = "incoming") -> list[ImportResult]:
        root = Path(directory)
        if not root.exists() or not root.is_dir():
            return [ImportResult(source=root, destination=None, status="skipped", reason="missing_directory")]

        files = [p for p in root.iterdir() if p.is_file()]
        return self.import_files(files, target=target)

    def _resolve_target(self, target: str) -> Path:
        if target == "incoming":
            return self.config.incoming_dir
        if target == "scans":
            return self.config.scans_dir
        raise ValueError("target must be 'incoming' or 'scans'")

    @staticmethod
    def _unique_target(folder: Path, filename: str) -> Path:
        target = folder / filename
        if not target.exists():
            return target
        i = 1
        while True:
            candidate = folder / f"{target.stem}_{i}{target.suffix}"
            if not candidate.exists():
                return candidate
            i += 1
