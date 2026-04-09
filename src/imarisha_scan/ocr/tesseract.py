from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .base import OcrResult


class LocalTesseractEngine:
    def __init__(self, binary: str | None = None) -> None:
        configured = (binary or os.getenv("IMARISHA_TESSERACT_BIN", "")).strip()
        self.binary = configured or "tesseract"

    def _candidate_binaries(self) -> list[str]:
        return [
            self.binary,
            "/opt/homebrew/bin/tesseract",
            "/usr/local/bin/tesseract",
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        ]

    def _resolve_binary(self) -> str | None:
        for candidate in self._candidate_binaries():
            if not candidate:
                continue
            if Path(candidate).is_file():
                return candidate
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return None

    def is_available(self) -> bool:
        return self._resolve_binary() is not None

    def extract_text(self, image_path: str | Path, language: str = "eng") -> OcrResult:
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Input image not found: {image_path}")

        binary = self._resolve_binary()
        if binary is None:
            raise RuntimeError(
                "Tesseract is not installed or not on PATH. Set IMARISHA_TESSERACT_BIN to the executable path, "
                "or bundle OCR sidecars (.ocr/.qr/.answers)."
            )

        completed = subprocess.run(
            [binary, str(image_path), "stdout", "-l", language],
            capture_output=True,
            text=True,
            check=True,
        )
        return OcrResult(text=completed.stdout.strip(), provider="tesseract", confidence=None)
