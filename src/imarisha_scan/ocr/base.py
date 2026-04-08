from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(slots=True)
class OcrResult:
    text: str
    provider: str
    confidence: float | None = None


class OcrEngine(Protocol):
    def extract_text(self, image_path: str | Path, language: str = "eng") -> OcrResult:
        ...
