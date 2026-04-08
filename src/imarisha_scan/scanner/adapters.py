from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ScannerAdapter(Protocol):
    def scan_to_files(self, output_dir: str | Path) -> list[Path]:
        ...


class WindowsWiaAdapter:
    def scan_to_files(self, output_dir: str | Path) -> list[Path]:
        raise NotImplementedError("WIA/TWAIN adapter integration is pending platform-specific implementation.")


class LinuxSaneAdapter:
    def scan_to_files(self, output_dir: str | Path) -> list[Path]:
        raise NotImplementedError("SANE adapter integration is pending platform-specific implementation.")


class FolderImportAdapter:
    def __init__(self, allowed_suffixes: tuple[str, ...] = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff")) -> None:
        self.allowed_suffixes = tuple(s.lower() for s in allowed_suffixes)

    def scan_to_files(self, output_dir: str | Path) -> list[Path]:
        root = Path(output_dir)
        if not root.exists():
            return []
        return sorted(
            [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in self.allowed_suffixes]
        )
