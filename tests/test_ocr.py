from pathlib import Path

import pytest

from imarisha_scan.ocr import LocalTesseractEngine


def test_tesseract_engine_missing_input_file_raises(tmp_path: Path) -> None:
    engine = LocalTesseractEngine()
    with pytest.raises(FileNotFoundError):
        engine.extract_text(tmp_path / "missing.png")
