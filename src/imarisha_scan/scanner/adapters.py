from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Protocol


class ScannerAdapter(Protocol):
    def is_available(self) -> bool:
        ...

    def scan_to_files(self, output_dir: str | Path, pages: int = 1) -> list[Path]:
        ...


class WindowsTwainAdapter:
    """TWAIN adapter entrypoint for Windows USB scanners."""

    def is_available(self) -> bool:
        # `twain` Python bindings vary by environment; this is a safe runtime probe.
        return importlib.util.find_spec("twain") is not None

    def scan_to_files(self, output_dir: str | Path, pages: int = 1) -> list[Path]:
        raise NotImplementedError("TWAIN scan implementation is pending hardware integration.")


class WindowsWiaAdapter:
    """WIA fallback adapter for Windows USB scanners."""

    def is_available(self) -> bool:
        # WIA is usually accessed via COM/win32 APIs; keep as explicit fallback interface.
        return importlib.util.find_spec("win32com") is not None

    def scan_to_files(self, output_dir: str | Path, pages: int = 1) -> list[Path]:
        raise NotImplementedError("WIA scan implementation is pending hardware integration.")


class LinuxSaneAdapter:
    def is_available(self) -> bool:
        return importlib.util.find_spec("sane") is not None

    def scan_to_files(self, output_dir: str | Path, pages: int = 1) -> list[Path]:
        raise NotImplementedError("SANE adapter integration is pending platform-specific implementation.")


class FolderImportAdapter:
    def __init__(
        self,
        allowed_suffixes: tuple[str, ...] = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"),
    ) -> None:
        self.allowed_suffixes = tuple(s.lower() for s in allowed_suffixes)

    def is_available(self) -> bool:
        return True

    def scan_to_files(self, output_dir: str | Path, pages: int = 1) -> list[Path]:
        del pages
        root = Path(output_dir)
        if not root.exists():
            return []
        return sorted(
            [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in self.allowed_suffixes]
        )
