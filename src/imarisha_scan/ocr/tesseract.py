from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .base import OcrResult


class LocalTesseractEngine:
    def __init__(self, binary: str = "tesseract") -> None:
        self.binary = binary

    def is_available(self) -> bool:
        return shutil.which(self.binary) is not None

    def extract_text(self, image_path: str | Path, language: str = "eng") -> OcrResult:
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Input image not found: {image_path}")
        if not self.is_available():
            raise RuntimeError(
                "Tesseract is not installed. Bundle local OCR binaries/language packs for offline use."
            )

        completed = subprocess.run(
            [self.binary, str(image_path), "stdout", "-l", language],
            capture_output=True,
            text=True,
            check=True,
        )
        return OcrResult(text=completed.stdout.strip(), provider="tesseract", confidence=None)
